"""
Ferramentas do Google Calendar para integração com LangChain
"""
import re
import traceback
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from langchain.agents import Tool
from .services import GoogleCalendarService


class GoogleCalendarLangChainTools:
    """Classe que cria ferramentas do Google Calendar para LangChain"""

    def __init__(self, numero_whatsapp: str):
        """
        Inicializa as ferramentas com o número do WhatsApp

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
        """
        self.numero_whatsapp = numero_whatsapp

    def get_tools(self):
        """
        Retorna lista de ferramentas LangChain para Google Calendar

        Returns:
            List[Tool]: Lista de ferramentas LangChain
        """
        return [
            # Tool(
            #     name="conectar_google_calendar",
            #     func=self._conectar_google_calendar,
            #     description="Conecta o Google Calendar do usuário via OAuth2. Use quando o usuário não estiver conectado."
            # ),
            Tool(
                name="listar_eventos_calendar",
                func=self._listar_eventos_calendar,
                description="Retorna todos os eventos já agendados com suas datas e horários ocupados"
            ),
            Tool(
                name="criar_evento_calendar",
                func=self._criar_evento_calendar,
                description="""Cria um novo evento no Google Calendar.
                Formato: titulo|data_inicio|hora_inicio|data_fim|hora_fim|descricao|localizacao
                Exemplo: Consulta médica|25/12/2024|14:30||15:30|Consulta de rotina|Clínica ABC
                Campos opcionais: data_fim, hora_fim, descricao, localizacao"""
            ),
            Tool(
                name="verificar_disponibilidade",
                func=self._verificar_disponibilidade,
                description="""OBRIGATÓRIO para verificar disponibilidade de horários em um dia.
                Retorna TODOS os slots de 30 em 30 minutos (09h-12h e 13h-17h) com status ✅ Disponível ou ❌ Ocupado.
                Use SEMPRE que precisar sugerir horários para o paciente.
                Formato: data
                Exemplo: 30/09/2025"""
            ),
            Tool(
                name="deletar_evento_por_telefone",
                func=self._deletar_evento_por_telefone,
                description="""Deleta evento baseado no número do WhatsApp no título.
                Formato: tipo_consulta (opcional)
                Exemplo: PRIMEIRA-CONSULTA"""
            ),
        ]


    def _listar_eventos_calendar(self, input_str: str = "") -> str:
        """Lista os próximos eventos com horarios já ocupados do Google Calendar do usuário"""
        try:
            # Parse max_resultados do input se fornecido
            max_resultados = 10
            if input_str and input_str.strip().isdigit():
                max_resultados = int(input_str.strip())

            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(self.numero_whatsapp, max_results=max_resultados)

            if not success:
                return f"❌ Erro ao acessar o calendário: {events}"

            if not events:
                return "📅 Você não tem eventos próximos na sua agenda."

            eventos_formatados = ["📅 *Seus Próximos Eventos:*\n"]

            for i, event in enumerate(events, 1):
                start = event['start'].get('dateTime', event['start'].get('date'))
                title = event.get('summary', 'Evento sem título')
                location = event.get('location', '')
                description = event.get('description', '')

                # Formatar data/hora
                if 'T' in start:  # É datetime
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%d/%m/%Y às %H:%M')
                else:  # É só data
                    dt = datetime.fromisoformat(start)
                    formatted_time = dt.strftime('%d/%m/%Y (dia todo)')

                evento_info = f"{i}. *{title}*\n   📅 {formatted_time}"

                if location:
                    evento_info += f"\n   📍 {location}"

                if description and len(description) < 100:
                    evento_info += f"\n   📝 {description}"

                eventos_formatados.append(evento_info)

            return "\n\n".join(eventos_formatados)

        except Exception as e:
            return f"❌ Erro interno ao listar eventos: {str(e)}"

    def _criar_evento_calendar(self, input_str: str) -> str:
        """Cria um novo evento no Google Calendar do usuário"""
        try:
            # Parse do input: titulo|data_inicio|hora_inicio|data_fim|hora_fim|descricao|localizacao
            if not input_str or input_str.strip() == "":
                return "❌ Parâmetros necessários. Use: titulo|data_inicio|hora_inicio|data_fim|hora_fim|descricao|localizacao"

            parts = input_str.split('|')
            if len(parts) < 2:
                return "❌ Formato incorreto. Use: titulo|data_inicio|hora_inicio|data_fim|hora_fim|descricao|localizacao"

            # 🧠 CORREÇÃO: definir o título original ANTES de aplicar o formato
            titulo_original = parts[0].strip()
            data_inicio = parts[1].strip()
            hora_inicio = parts[2].strip() if len(parts) > 2 else ""
            data_fim = parts[3].strip() if len(parts) > 3 else ""
            hora_fim = parts[4].strip() if len(parts) > 4 else ""
            descricao = parts[5].strip() if len(parts) > 5 else ""
            localizacao = parts[6].strip() if len(parts) > 6 else ""

            # ✅ Forçar o formato de título correto
            if "—" not in titulo_original and "+55" not in titulo_original:
                tipo_evento = titulo_original.upper() if titulo_original else "CONSULTA"
                titulo = f"[{tipo_evento}] +55{self.numero_whatsapp} — Nome do Paciente"
            else:
                titulo = titulo_original

            # Processa as datas
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%d/%m/%Y')
            except ValueError:
                return "❌ Formato de data inválido. Use DD/MM/YYYY (ex: 25/12/2024)"

            # Define data de fim se não fornecida
            if not data_fim:
                data_fim_obj = data_inicio_obj
            else:
                try:
                    data_fim_obj = datetime.strptime(data_fim, '%d/%m/%Y')
                except ValueError:
                    return "❌ Formato de data de fim inválido. Use DD/MM/YYYY"

            # Prepara os dados do evento
            event_data = {
                'summary': titulo,
                'description': f"Evento criado via WhatsApp\n\n{descricao}" if descricao else "Evento criado via WhatsApp"
            }

            if localizacao:
                event_data['location'] = localizacao

            # Define horário
            if hora_inicio:
                try:
                    hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
                    start_datetime = datetime.combine(data_inicio_obj.date(), hora_inicio_obj)

                    # Define hora de fim - sempre 29 minutos a mais que hora_inicio
                    end_datetime = start_datetime + timedelta(minutes=29)

                    event_data['start'] = {
                        'dateTime': start_datetime.isoformat(),
                        'timeZone': 'America/Sao_Paulo',
                    }
                    event_data['end'] = {
                        'dateTime': end_datetime.isoformat(),
                        'timeZone': 'America/Sao_Paulo',
                    }

                except ValueError:
                    return "❌ Formato de hora inválido. Use HH:MM (ex: 14:30)"
            else:
                # Evento de dia inteiro
                event_data['start'] = {
                    'date': data_inicio_obj.strftime('%Y-%m-%d'),
                }
                # Para eventos de dia inteiro, a data de fim deve ser o dia seguinte
                event_data['end'] = {
                    'date': (data_fim_obj + timedelta(days=1)).strftime('%Y-%m-%d'),
                }

            # Verifica disponibilidade antes de criar
            if hora_inicio:
                # Verificar se há conflito com eventos existentes
                calendar_service = GoogleCalendarService()
                success, events = calendar_service.list_events(self.numero_whatsapp, max_results=50)

                if success:
                    # Converter horário de início para datetime
                    hora_inicio_dt = datetime.strptime(hora_inicio, '%H:%M').time()
                    hora_fim_dt = (datetime.combine(data_inicio_obj.date(), hora_inicio_dt) + timedelta(minutes=29)).time()

                    # Verificar conflitos com eventos existentes
                    for event in events:
                        start = event['start'].get('dateTime', event['start'].get('date'))

                        if 'T' in start:  # É datetime
                            event_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                            if event_dt.tzinfo:
                                event_dt = event_dt.astimezone().replace(tzinfo=None)

                            # Se é o mesmo dia
                            if event_dt.date() == data_inicio_obj.date():
                                event_time = event_dt.time()

                                # Verificar sobreposição de horários
                                # Um evento conflita se começa antes do fim do novo evento E termina depois do início
                                if hora_inicio_dt <= event_time < hora_fim_dt:
                                    return f"""❌ *Conflito de horário!*

O horário {hora_inicio} já está ocupado com: *{event.get('summary', 'Evento sem título')}*

Por favor, escolha outro horário disponível."""

            # Cria o evento
            calendar_service = GoogleCalendarService()
            success, result = calendar_service.create_event(self.numero_whatsapp, event_data)

            if success:
                # Formata informações do evento criado
                data_formatada = data_inicio_obj.strftime('%d/%m/%Y')

                resposta = f"""✅ *Evento criado com sucesso!*

📋 *Título:* {titulo}
📅 *Data:* {data_formatada}"""

                if hora_inicio:
                    # Calcular hora fim sempre como +29 minutos
                    hora_fim_calc = (datetime.strptime(hora_inicio, '%H:%M') + timedelta(minutes=29)).strftime('%H:%M')
                    resposta += f"\n⏰ *Horário:* {hora_inicio} às {hora_fim_calc}"
                else:
                    resposta += f"\n⏰ *Tipo:* Dia inteiro"

                if localizacao:
                    resposta += f"\n📍 *Local:* {localizacao}"

                if descricao:
                    resposta += f"\n📝 *Descrição:* {descricao}"

                # Extrai link se disponível
                if ': ' in result:
                    link = result.split(': ')[-1]
                    resposta += f"\n\n🔗 *Ver no Google Calendar:* {link}"

                return resposta
            else:
                return f"❌ Erro ao criar evento: {result}"

        except Exception as e:
            return f"❌ Erro interno ao criar evento: {str(e)}"


    def interpretar_data_relativa(self, texto: str) -> str:
            """
            Converte expressões como 'sexta', 'amanhã', 'terça-feira' em uma data real (DD/MM/YYYY)
            baseada na data atual do sistema.
            """
            hoje = datetime.now().date()
            texto = texto.lower()

            # Mapeamento dos dias da semana
            dias_semana = {
                "segunda": 0, "segunda-feira": 0,
                "terça": 1, "terça-feira": 1, "terca": 1, "terca-feira": 1,
                "quarta": 2, "quarta-feira": 2,
                "quinta": 3, "quinta-feira": 3,
                "sexta": 4, "sexta-feira": 4,
                "sábado": 5, "sabado": 5, "sábado-feira": 5,
                "domingo": 6
            }

            # Casos especiais
            if "hoje" in texto:
                return hoje.strftime("%d/%m/%Y")

            if "amanhã" in texto or "amanha" in texto:
                return (hoje + timedelta(days=1)).strftime("%d/%m/%Y")

            if "depois de amanhã" in texto or "depois de amanha" in texto:
                return (hoje + timedelta(days=2)).strftime("%d/%m/%Y")

            # Verificar se mencionou um dia da semana
            for nome_dia, indice in dias_semana.items():
                if re.search(rf"\b{nome_dia}\b", texto):
                    hoje_idx = hoje.weekday()
                    dias_a_frente = (indice - hoje_idx + 7) % 7
                    if dias_a_frente == 0:
                        dias_a_frente = 7  # próxima ocorrência
                    data_resultado = hoje + timedelta(days=dias_a_frente)
                    return data_resultado.strftime("%d/%m/%Y")

            # Se não encontrou nenhuma palavra reconhecida, retorna vazio
            return ""


    def _verificar_disponibilidade(self, input_str: str) -> str:
        """Verifica os horários (30 em 30 min) entre 09h-12h e 13h-17h"""


        def parse_datetime(dt_str: str) -> datetime:
            """Converte string ISO 8601 para datetime naive (sem timezone, sempre horário local)"""
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            if dt.tzinfo:
                dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
                dt = dt.replace(tzinfo=None)
            return dt

        try:
            if not input_str or input_str.strip() == "":
                return "❌ Parâmetros necessários. Use: data"

            # 🆕 NOVO: tentar converter "sexta" ou "terça" em uma data real
            data_interpretada = self.interpretar_data_relativa(input_str)
            if data_interpretada:
                data = data_interpretada
            else:
                # Caso contrário, manter formato manual "DD/MM/YYYY"
                parts = input_str.split('|')
                data = parts[0].strip()

            # Continua o código original normalmente...
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(self.numero_whatsapp, max_results=50)

            if not success:
                return f"❌ Erro ao verificar disponibilidade: {events}"

            # Converte a data fornecida
            try:
                data_obj = datetime.strptime(data, '%d/%m/%Y')
            except ValueError:
                return "❌ Formato de data inválido. Use DD/MM/YYYY"

            blocos = [
                (datetime.combine(data_obj.date(), time(9, 0)), datetime.combine(data_obj.date(), time(12, 0))),
                (datetime.combine(data_obj.date(), time(13, 0)), datetime.combine(data_obj.date(), time(17, 0)))
            ]

            eventos_do_dia = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                start_dt = parse_datetime(start)
                end_dt = parse_datetime(end)
                if end_dt <= start_dt:
                    end_dt = start_dt + timedelta(minutes=1)

                if start_dt.date() == data_obj.date():
                    eventos_do_dia.append((start_dt, end_dt, event.get('summary', 'Evento sem título')))

            eventos_do_dia.sort(key=lambda x: x[0])

            resposta = f"📅 *Disponibilidade em {data_obj.strftime('%d/%m/%Y')} (09h-12h / 13h-17h):*\n\n"

            horarios = []
            for bloco_inicio, bloco_fim in blocos:
                atual = bloco_inicio
                while atual < bloco_fim:
                    fim_slot = atual + timedelta(minutes=30)
                    if fim_slot <= bloco_fim:
                        horarios.append((atual, fim_slot))
                    atual = fim_slot

            for ini, fim in horarios:
                ocupado = False
                evento_nome = None
                for ev_ini, ev_fim, titulo in eventos_do_dia:
                    if ini < ev_fim and fim > ev_ini:
                        ocupado = True
                        evento_nome = titulo
                        break
                if ocupado:
                    resposta += f"❌ {ini.strftime('%H:%M')} - {fim.strftime('%H:%M')} (Ocupado: {evento_nome})\n"
                else:
                    resposta += f"✅ {ini.strftime('%H:%M')} - {fim.strftime('%H:%M')} (Disponível)\n"

            if eventos_do_dia:
                resposta += "\n📋 *Eventos do dia:*\n"
                for i, (ini, fim, titulo) in enumerate(eventos_do_dia, 1):
                    resposta += f"{i}. {titulo} ({ini.strftime('%H:%M')} - {fim.strftime('%H:%M')})\n"

            print(f'resposta {resposta}')
            return resposta

        except Exception as e:
            return f"❌ Erro interno ao verificar disponibilidade: {str(e)}"

    def _verificar_disponibilidade_detalhada(self, numero_whatsapp: str, data: str, hora_inicio: str = "", hora_fim: str = "") -> str:
        """Verifica disponibilidade com logs detalhados para debug"""
        try:
            # Lista eventos
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(numero_whatsapp, max_results=50)

            if not success:
                return f"❌ Erro ao acessar Google Calendar: {events}"

            # Converte a data fornecida
            try:
                data_obj = datetime.strptime(data, '%d/%m/%Y')
            except ValueError:
                return "❌ Formato de data inválido. Use DD/MM/YYYY"

            # Filtra eventos do dia
            eventos_do_dia = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))

                if 'T' in start:  # É datetime
                    event_date = datetime.fromisoformat(start.replace('Z', '+00:00')).date()
                else:  # É só data
                    event_date = datetime.fromisoformat(start).date()

                if event_date == data_obj.date():
                    eventos_do_dia.append(event)

            resposta = f"📅 *Disponibilidade DEBUG para {data_obj.strftime('%d/%m/%Y')}:*\n\n"
            resposta += f"🔍 Total eventos verificados: {len(events)}\n"
            resposta += f"📋 Eventos no dia {data}: {len(eventos_do_dia)}\n\n"

            if not eventos_do_dia:
                resposta += "✅ DIA COMPLETAMENTE LIVRE!\n"
                if hora_inicio:
                    # Calcular hora_fim como +29 minutos
                    hora_fim_calc = (datetime.strptime(hora_inicio, '%H:%M') + timedelta(minutes=29)).strftime('%H:%M')
                    resposta += f"✅ Horário {hora_inicio}-{hora_fim_calc} DISPONÍVEL!"
            else:
                resposta += f"📋 *Eventos encontrados no dia {data}:*\n\n"
                for i, event in enumerate(eventos_do_dia, 1):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    title = event.get('summary', 'Evento sem título')

                    if 'T' in start:  # É datetime
                        dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M')
                        resposta += f"{i}. *{title}* às {time_str}\n"
                    else:
                        resposta += f"{i}. *{title}* (dia inteiro)\n"

                # Verificar conflito específico se horário solicitado
                if hora_inicio:
                    # Sempre calcular hora_fim como +29 minutos
                    hora_fim_calc = (datetime.strptime(hora_inicio, '%H:%M') + timedelta(minutes=29)).strftime('%H:%M')
                    resposta += f"\n🔍 *Verificando conflito para {hora_inicio}-{hora_fim_calc}:*\n"
                    conflito = False

                    for event in eventos_do_dia:
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        if 'T' in start:
                            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                            event_time = dt.time()

                            hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
                            hora_fim_obj = (datetime.strptime(hora_inicio, '%H:%M') + timedelta(minutes=29)).time()

                            # Verificação de conflito mais precisa
                            if hora_inicio_obj <= event_time < hora_fim_obj:
                                conflito = True
                                resposta += f"⚠️ CONFLITO: {event.get('summary')} às {event_time}\n"

                    if not conflito:
                        resposta += f"✅ Horário {hora_inicio}-{hora_fim_calc} DISPONÍVEL!"

            return resposta

        except Exception as e:
            return f"❌ Erro interno ao verificar disponibilidade: {str(e)}"


    def _deletar_evento_por_telefone(self, input_str: str = "PRIMEIRA-CONSULTA") -> str:
        """Deleta evento baseado no número do WhatsApp que está no título"""
        try:
            # Parse do input para tipo de consulta
            tipo_consulta = input_str.strip() if input_str.strip() else "PRIMEIRA-CONSULTA"

            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(self.numero_whatsapp, max_results=50)

            if not success:
                return f"❌ Erro ao buscar eventos: {events}"

            candidato = None
            eventos_encontrados = []

            # Procurar eventos que contenham o número do WhatsApp no título
            for event in events:
                event_title = event.get("summary", "")

                # Verificar se o número está no título (com ou sem +55)
                if (self.numero_whatsapp in event_title or
                    f"+55{self.numero_whatsapp}" in event_title or
                    f"55{self.numero_whatsapp}" in event_title):

                    eventos_encontrados.append(event)

                    # Se também contém o tipo de consulta, é candidato prioritário
                    if tipo_consulta in event_title:
                        candidato = event
                        break

            # Se não encontrou candidato específico, usar o primeiro encontrado
            if not candidato and eventos_encontrados:
                candidato = eventos_encontrados[0]

            if not candidato:
                return f"😕 Não encontrei nenhum evento agendado para o número {self.numero_whatsapp}."

            # Deletar o evento encontrado
            service = calendar_service.get_calendar_service(self.numero_whatsapp)
            service.events().delete(calendarId="primary", eventId=candidato["id"]).execute()

            # Extrair informações do evento deletado
            start = candidato["start"].get("dateTime", candidato["start"].get("date"))
            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                data_formatada = dt.strftime('%d/%m/%Y')
                hora_formatada = dt.strftime('%H:%M')
                info_tempo = f"no dia {data_formatada} às {hora_formatada}"
            else:
                dt = datetime.fromisoformat(start)
                data_formatada = dt.strftime('%d/%m/%Y')
                info_tempo = f"no dia {data_formatada} (dia inteiro)"

            return f"✅ Evento *{candidato.get('summary', 'Sem título')}* foi cancelado com sucesso {info_tempo}!"

        except Exception as e:
            return f"❌ Erro ao deletar evento: {str(e)}"


