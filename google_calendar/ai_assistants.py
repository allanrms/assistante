import traceback
from django.utils import timezone
from django_ai_assistant import AIAssistant, method_tool
from datetime import datetime, timedelta
from .services import GoogleCalendarService


class GoogleCalendarAIAssistant(AIAssistant):
    id = "google_calendar_assistant"
    name = "Assistente de Google Calendar"
    instructions = """
OBJETIVO: Usar as ferramentas disponíveis para EXECUTAR ações no Google Calendar, não apenas responder.

FERRAMENTAS DISPONÍVEIS:
1. conectar_google_calendar() - Conecta usuário ao Google via OAuth2
2. criar_evento_calendar() - Cria eventos REAIS no Google Calendar
3. listar_eventos_calendar() - Lista eventos existentes
4. verificar_disponibilidade() - Verifica conflitos de horário
5. verificar_disponibilidade_detalhada() - Debug detalhado da agenda
6. deletar_evento_por_telefone() - Cancela eventos do usuário (PREFERIDA)
7. deletar_evento() - Cancela eventos por título/hora (backup)

INSTRUÇÕES CRÍTICAS:
- SEMPRE use as ferramentas para executar ações, não apenas responda
- NUNCA invente resultados - use as ferramentas para obter dados reais
- Se usuário não estiver conectado, use conectar_google_calendar()
- Para agendamentos, SEMPRE use criar_evento_calendar()
- Para consultas, SEMPRE use listar_eventos_calendar()
- Para cancelamentos, SEMPRE use deletar_evento() - NÃO apenas diga que vai cancelar
- Se detectar palavra "debug" na solicitação, use verificar_disponibilidade_detalhada()

REGRA CRÍTICA PARA CANCELAMENTOS:
- Para cancelar eventos do usuário atual: use deletar_evento_por_telefone()
- Esta função automaticamente encontra eventos pelo número do WhatsApp
- NUNCA diga "vou cancelar" sem EXECUTAR a função de deletar
- Após executar, confirme com resultado da função

FORMATO DE TÍTULO OBRIGATÓRIO: [TIPO-EVENTO] +55{número_whatsapp} — {Nome do Paciente}

FLUXO PADRÃO:
1. Recebe contexto completo da conversa + solicitação específica
2. Analisa todo o contexto para entender melhor a situação
3. Verifica se usuário está conectado ao Google
4. Executa ação usando a ferramenta apropriada
5. Retorna resultado técnico e preciso baseado no contexto

TRABALHANDO COM CONTEXTO:
- Leia e compreenda todo o histórico da conversa
- Identifique informações relevantes como: nomes, datas, tipos de consulta
- Use essas informações para ser mais preciso nas ações
- Referencie o contexto em suas respostas quando apropriado

VALIDAÇÕES OBRIGATÓRIAS:
- Verificar conflitos antes de agendar
- Validar formatos de data/hora
- Confirmar conexão Google antes de prosseguir

PROTOCOLO DE DEBUG:
- Se usuário relatar horários livres mas sistema mostrar ocupado
- Use verificar_disponibilidade_detalhada() para investigar
- Compare resultados e explique discrepâncias

ATENÇÃO: SEMPRE QUE FOR CRIAR criar_evento_calendar utilizar FORMATO DE TÍTULO OBRIGATÓRIO: [TIPO-EVENTO] +55{número_whatsapp} — {Nome do Paciente}
- JAMAIS CRIAR SE NÃO TIVER O número_whatsapp e Nome do Paciente


EXECUTE AS FERRAMENTAS - NÃO APENAS RESPONDA!"""


    model = "gpt-4o-mini"

    def get_instructions(self, numero_whatsapp=None):
        base_instructions = self.instructions

        current_time = timezone.now().strftime('%d/%m/%Y %H:%M')
        dynamic_instructions = f"\n\nData e hora atual: {current_time}"

        if numero_whatsapp:
            dynamic_instructions += f"\nNúmero WhatsApp da sessão: {numero_whatsapp}"
            dynamic_instructions += f"\nUse este número no formato de título: [TIPO-EVENTO] +55{numero_whatsapp} — Nome do Paciente"

        return base_instructions + dynamic_instructions

    @method_tool
    def conectar_google_calendar(self, numero_whatsapp: str) -> str:
        """Conecta o Google Calendar do usuário via OAuth2

        Args:
            numero_whatsapp: Número do WhatsApp do usuário

        Returns:
            String com link e instruções para conexão
        """
        try:
            calendar_service = GoogleCalendarService()

            # Primeiro verifica se já está conectado
            try:
                existing_service = calendar_service.get_calendar_service(numero_whatsapp)

                if existing_service:
                    return """✅ *Sua agenda já está conectada!*

🎉 Seu Google Calendar já está integrado e funcionando.

💡 *Comandos disponíveis:*
• "meus eventos" - Ver próximos compromissos
• "criar evento [título]" - Criar novo evento
• "agenda hoje" - Ver eventos de hoje
• "disponibilidade [data]" - Verificar disponibilidade"""

            except Exception:
                # Usuário não está conectado - gera link OAuth2
                pass

            # Gera URL de autorização
            auth_url = calendar_service.get_authorization_url(numero_whatsapp)

            return f"""🔗 *Integração com Google Calendar*

Para conectar sua agenda do Google, clique no link abaixo:

{auth_url}

📋 *Instruções:*
1. Clique no link acima
2. Faça login na sua conta Google
3. Autorize o acesso ao seu calendário
4. Pronto! Sua agenda estará conectada

💡 *O que você poderá fazer depois:*
• Criar eventos via WhatsApp
• Consultar sua agenda
• Receber lembretes
• Sincronizar compromissos

⚠️ *Importante:* O link expira em 1 hora por segurança."""

        except Exception as e:
            traceback.print_exc()
            return f"❌ Erro ao gerar link de conexão: {str(e)}"

    @method_tool
    def listar_eventos_calendar(self, numero_whatsapp: str, max_resultados: int = 10) -> str:
        """Lista os próximos eventos do Google Calendar do usuário

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
            max_resultados: Número máximo de eventos para retornar (padrão: 10)

        Returns:
            String com os eventos formatados ou mensagem de erro
        """
        try:
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(numero_whatsapp, max_results=max_resultados)

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

    @method_tool
    def criar_evento_calendar(
        self,
        numero_whatsapp: str,
        titulo: str,
        data_inicio: str,
        hora_inicio: str = "",
        data_fim: str = "",
        hora_fim: str = "",
        descricao: str = "",
        localizacao: str = ""
    ) -> str:
        """Cria um novo evento no Google Calendar do usuário

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
            titulo: Título do evento
            data_inicio: Data de início no formato DD/MM/YYYY
            hora_inicio: Hora de início no formato HH:MM (opcional, se vazio será evento de dia inteiro)
            data_fim: Data de fim no formato DD/MM/YYYY (opcional, usa data_inicio se vazio)
            hora_fim: Hora de fim no formato HH:MM (opcional, usa hora_inicio + 1 hora se vazio)
            descricao: Descrição do evento (opcional)
            localizacao: Local do evento (opcional)

        Returns:
            String com confirmação de criação ou mensagem de erro
        """
        try:
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

                    # Define hora de fim
                    if hora_fim:
                        hora_fim_obj = datetime.strptime(hora_fim, '%H:%M').time()
                        end_datetime = datetime.combine(data_fim_obj.date(), hora_fim_obj)
                    else:
                        # 1 hora de duração por padrão
                        end_datetime = start_datetime + timedelta(hours=1)

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

            # Cria o evento
            calendar_service = GoogleCalendarService()
            success, result = calendar_service.create_event(numero_whatsapp, event_data)

            if success:
                # Formata informações do evento criado
                data_formatada = data_inicio_obj.strftime('%d/%m/%Y')

                resposta = f"""✅ *Evento criado com sucesso!*

📋 *Título:* {titulo}
📅 *Data:* {data_formatada}"""

                if hora_inicio:
                    resposta += f"\n⏰ *Horário:* {hora_inicio}"
                    if hora_fim:
                        resposta += f" às {hora_fim}"
                    else:
                        hora_fim_calc = (datetime.strptime(hora_inicio, '%H:%M') + timedelta(hours=1)).strftime('%H:%M')
                        resposta += f" às {hora_fim_calc}"
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

    @method_tool
    def verificar_disponibilidade_detalhada(self, numero_whatsapp: str, data: str, hora_inicio: str = "", hora_fim: str = "") -> str:
        """Verifica disponibilidade com logs detalhados para debug

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
            data: Data para verificar no formato DD/MM/YYYY
            hora_inicio: Hora de início no formato HH:MM (opcional)
            hora_fim: Hora de fim no formato HH:MM (opcional)

        Returns:
            String com informação detalhada sobre disponibilidade
        """
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
                resposta += f"✅ Horário {hora_inicio}-{hora_fim} DISPONÍVEL!"
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
                if hora_inicio and hora_fim:
                    resposta += f"\n🔍 *Verificando conflito para {hora_inicio}-{hora_fim}:*\n"
                    conflito = False

                    for event in eventos_do_dia:
                        start = event['start'].get('dateTime', event['start'].get('date'))
                        if 'T' in start:
                            dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                            event_time = dt.time()

                            hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
                            hora_fim_obj = datetime.strptime(hora_fim, '%H:%M').time()

                            # Verificação de conflito mais precisa
                            if hora_inicio_obj <= event_time < hora_fim_obj:
                                conflito = True
                                resposta += f"⚠️ CONFLITO: {event.get('summary')} às {event_time}\n"

                    if not conflito:
                        resposta += f"✅ Horário {hora_inicio}-{hora_fim} DISPONÍVEL!"

            return resposta

        except Exception as e:
            return f"❌ Erro interno ao verificar disponibilidade: {str(e)}"

    @method_tool
    def verificar_disponibilidade(self, numero_whatsapp: str, data: str, hora_inicio: str = "", hora_fim: str = "") -> str:
        """Verifica se o usuário está disponível em uma determinada data/hora

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
            data: Data para verificar no formato DD/MM/YYYY
            hora_inicio: Hora de início no formato HH:MM (opcional)
            hora_fim: Hora de fim no formato HH:MM (opcional)

        Returns:
            String com informação sobre disponibilidade
        """
        try:
            # Lista eventos do dia
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(numero_whatsapp, max_results=50)

            if not success:
                return f"❌ Erro ao verificar disponibilidade: {events}"

            # Converte a data fornecida
            try:
                data_obj = datetime.strptime(data, '%d/%m/%Y')
            except ValueError:
                return "❌ Formato de data inválido. Use DD/MM/YYYY"

            # Filtra eventos do dia especificado
            eventos_do_dia = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                if 'T' in start:  # É datetime
                    event_date = datetime.fromisoformat(start.replace('Z', '+00:00')).date()
                else:  # É só data
                    event_date = datetime.fromisoformat(start).date()

                if event_date == data_obj.date():
                    eventos_do_dia.append(event)

            resposta = f"📅 *Disponibilidade para {data_obj.strftime('%d/%m/%Y')}:*\n\n"

            if not eventos_do_dia:
                resposta += "✅ Você está completamente livre neste dia!"
            else:
                resposta += f"📋 *Você tem {len(eventos_do_dia)} evento(s) neste dia:*\n\n"

                for i, event in enumerate(eventos_do_dia, 1):
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    title = event.get('summary', 'Evento sem título')

                    if 'T' in start:  # É datetime
                        dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        time_str = dt.strftime('%H:%M')

                        # Verifica se há conflito com horário solicitado
                        if hora_inicio and hora_fim:
                            try:
                                hora_inicio_obj = datetime.strptime(hora_inicio, '%H:%M').time()
                                hora_fim_obj = datetime.strptime(hora_fim, '%H:%M').time()

                                event_start_time = dt.time()
                                # Simplificada - apenas verifica sobreposição básica
                                if (hora_inicio_obj <= event_start_time <= hora_fim_obj):
                                    resposta += f"{i}. ⚠️ *{title}* às {time_str} (CONFLITO!)\n"
                                else:
                                    resposta += f"{i}. *{title}* às {time_str}\n"
                            except ValueError:
                                resposta += f"{i}. *{title}* às {time_str}\n"
                        else:
                            resposta += f"{i}. *{title}* às {time_str}\n"
                    else:  # Dia inteiro
                        resposta += f"{i}. *{title}* (dia inteiro)\n"

                # Verifica disponibilidade específica se horário foi fornecido
                if hora_inicio and not hora_fim:
                    resposta += f"\n💡 *Para criar um evento às {hora_inicio}, verifique se não há conflitos acima.*"
                elif hora_inicio and hora_fim:
                    resposta += f"\n💡 *Para o período {hora_inicio}-{hora_fim}, verifique se não há conflitos marcados acima.*"

            return resposta

        except Exception as e:
            return f"❌ Erro interno ao verificar disponibilidade: {str(e)}"

    @method_tool
    def deletar_evento_por_telefone(self, numero_whatsapp: str, tipo_consulta: str = "PRIMEIRA-CONSULTA") -> str:
        """Deleta evento baseado no número do WhatsApp que está no título

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
            tipo_consulta: Tipo da consulta (PRIMEIRA-CONSULTA, RETORNO, etc)

        Returns:
            String com resultado da operação
        """
        try:
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(numero_whatsapp, max_results=50)

            if not success:
                return f"❌ Erro ao buscar eventos: {events}"

            candidato = None
            eventos_encontrados = []

            # Procurar eventos que contenham o número do WhatsApp no título
            for event in events:
                event_title = event.get("summary", "")

                # Verificar se o número está no título (com ou sem +55)
                if (numero_whatsapp in event_title or
                    f"+55{numero_whatsapp}" in event_title or
                    f"55{numero_whatsapp}" in event_title):

                    eventos_encontrados.append(event)

                    # Se também contém o tipo de consulta, é candidato prioritário
                    if tipo_consulta in event_title:
                        candidato = event
                        break

            # Se não encontrou candidato específico, usar o primeiro encontrado
            if not candidato and eventos_encontrados:
                candidato = eventos_encontrados[0]

            if not candidato:
                return f"😕 Não encontrei nenhum evento agendado para o número {numero_whatsapp}."

            # Deletar o evento encontrado
            service = calendar_service.get_calendar_service(numero_whatsapp)
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

    @method_tool
    def deletar_evento(self, numero_whatsapp: str, titulo: str = "", hora: str = "", data: str = "") -> str:
        """Deleta um evento do Google Calendar pelo título ou pela hora

        Args:
            numero_whatsapp: Número do WhatsApp do usuário
            titulo: Título do evento (opcional)
            hora: Hora no formato HH:MM (opcional)
            data: Data no formato DD/MM/YYYY (opcional, usado com hora)

        Returns:
            String com resultado da operação
        """
        try:
            calendar_service = GoogleCalendarService()
            success, events = calendar_service.list_events(numero_whatsapp, max_results=50)

            if not success:
                return f"❌ Erro ao buscar eventos: {events}"

            candidato = None

            # Normaliza inputs
            titulo = titulo.strip().lower() if titulo else ""
            hora = hora.strip() if hora else ""

            for event in events:
                event_title = event.get("summary", "").lower()
                start = event["start"].get("dateTime", event["start"].get("date"))

                # Caso 1: deletar pelo título
                if titulo and titulo in event_title:
                    candidato = event
                    break

                # Caso 2: deletar pela hora (se data for fornecida também, restringe mais)
                if hora and "T" in start:
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    time_str = dt.strftime("%H:%M")

                    if time_str == hora:
                        if data:
                            data_obj = datetime.strptime(data, "%d/%m/%Y").date()
                            if dt.date() == data_obj:
                                candidato = event
                                break
                        else:
                            candidato = event
                            break

            if not candidato:
                return "😕 Não encontrei nenhum evento com esses critérios."

            # Deleta o evento encontrado
            service = calendar_service.get_calendar_service(numero_whatsapp)
            service.events().delete(calendarId="primary", eventId=candidato["id"]).execute()

            return f"🗑️ Evento *{candidato.get('summary', 'Sem título')}* deletado com sucesso!"
        except Exception as e:
            traceback.print_exc()
            return f"❌ Erro ao deletar evento: {str(e)}"