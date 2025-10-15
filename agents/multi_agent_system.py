"""
Sistema de Múltiplos Agentes - Aline Atendimento e Aline Agenda

Este módulo implementa um sistema de múltiplos agentes LangChain que se comunicam entre si:
- AgendaAgent: Especialista em gerenciamento de calendário e agendamento
- AtendimentoAgent: Assistente conversacional que interage com o paciente

A comunicação entre os agentes é feita através de ferramentas especializadas.
"""

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import initialize_agent, AgentType, Tool
from langchain.schema import HumanMessage, AIMessage
from django.conf import settings
from agents.models import LLMProviderConfig
from whatsapp_connector.models import MessageHistory
from google_calendar.langchain_tools import GoogleCalendarLangChainTools
from datetime import datetime, timedelta
import json


class AgendaAgent:
    """
    Agente especializado em gerenciamento de calendário e agendamento.
    Este agente tem acesso às ferramentas do Google Calendar e executa
    todas as operações relacionadas a disponibilidade e criação de eventos.
    """

    def __init__(self, llm_config: LLMProviderConfig, number_whatsapp: str):
        """
        Inicializa o AgendaAgent

        Args:
            llm_config: Configuração do modelo LLM
            number_whatsapp: Número do WhatsApp da sessão
        """
        self.llm_config = llm_config
        self.number_whatsapp = number_whatsapp
        self.llm = self._create_llm()
        self.tools = self._create_calendar_tools()
        self.agent = self._create_agent()

        print("✅ AgendaAgent inicializado com sucesso")

    def _create_llm(self):
        """Cria o modelo LLM baseado na configuração"""
        provider = self.llm_config.name

        if provider == "openai":
            return ChatOpenAI(
                model=self.llm_config.model,
                temperature=0.1,  # Baixa temperatura para precisão em agendamentos
                max_tokens=self.llm_config.max_tokens,
                openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
            )
        elif provider == "anthropic":
            return ChatAnthropic(
                model=self.llm_config.model,
                temperature=0.1,
                max_tokens=self.llm_config.max_tokens,
                anthropic_api_key=getattr(settings, 'ANTHROPIC_API_KEY', '')
            )
        elif provider == "google":
            return ChatGoogleGenerativeAI(
                model=self.llm_config.model,
                temperature=0.1,
                max_output_tokens=self.llm_config.max_tokens,
                google_api_key=getattr(settings, 'GOOGLE_API_KEY', '')
            )
        else:
            return ChatOpenAI(
                model=self.llm_config.model or "gpt-4o",
                temperature=0.1,
                openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
            )

    def _create_calendar_tools(self):
        """Cria ferramentas de calendário para o agente"""
        tools = []

        # Google Calendar Tools
        if self.llm_config.has_calendar_tools:
            google_calendar_tools = GoogleCalendarLangChainTools(self.number_whatsapp)
            tools.extend(google_calendar_tools.get_tools())

        # Ferramenta para obter hora atual
        def get_current_time(_=None):
            now = datetime.now()
            days_of_week = {
                0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
                3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
            }
            day_of_week = days_of_week[now.weekday()]
            return f"{now.strftime('%d/%m/%Y %H:%M')} ({day_of_week})"

        tools.append(Tool(
            name="get_current_time",
            func=get_current_time,
            description="Obtém a data e hora atual no formato brasileiro com dia da semana"
        ))

        # Ferramenta para verificar dia da semana
        def get_weekday(data_str: str):
            try:
                data_obj = datetime.strptime(data_str, '%d/%m/%Y')
                days_of_week = {
                    0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
                    3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
                }
                day_of_week = days_of_week[data_obj.weekday()]
                return f"{data_str} é uma {day_of_week}"
            except ValueError:
                return "❌ Formato de data inválido. Use DD/MM/YYYY"

        tools.append(Tool(
            name="get_weekday",
            func=get_weekday,
            description="Verifica qual dia da semana é uma data específica. Formato: DD/MM/YYYY"
        ))

        # Ferramenta para encontrar próximas datas
        def get_next_weekday(weekday: str):
            try:
                today = datetime.now()
                target_weekdays = {
                    "terca": 1,
                    "terça": 1,
                    "quinta": 3
                }

                normalized_weekday = weekday.lower().strip()
                if normalized_weekday not in target_weekdays:
                    return "❌ Use 'terça' ou 'quinta'"

                target_day = target_weekdays[normalized_weekday]
                days_until_target = (target_day - today.weekday()) % 7

                if days_until_target == 0:
                    days_until_target = 7

                next_date = today + timedelta(days=days_until_target)
                following_date = next_date + timedelta(days=7)

                return f"""Próximas {normalized_weekday}s:
1. {next_date.strftime('%d/%m/%Y')} ({normalized_weekday})
2. {following_date.strftime('%d/%m/%Y')} ({normalized_weekday})"""
            except Exception as e:
                return f"❌ Erro: {str(e)}"

        tools.append(Tool(
            name="proximo_dia_semana",
            func=get_next_weekday,
            description="Encontra as próximas 2 ocorrências de terça ou quinta a partir de hoje. Use: 'terça' ou 'quinta'"
        ))

        return tools

    def _create_agent(self):
        """Cria o agente de agenda com instruções específicas"""
        # Ler instruções do arquivo
        try:
            with open('/home/allanramos/Documentos/workspace/pessoal/assistante/agents/instructions/aline_agenda.md', 'r', encoding='utf-8') as f:
                agenda_instructions = f.read()
        except Exception as e:
            print(f"⚠️ Erro ao ler instruções da agenda: {e}")
            agenda_instructions = "Você é um assistente de agendamento."

        current_time = datetime.now().strftime('%d/%m/%Y %H:%M')

        system_prompt = f"""
{agenda_instructions}

## INFORMAÇÕES DA SESSÃO
- Número WhatsApp: {self.number_whatsapp}
- Data/Hora atual: {current_time}
- Formato do título para criar evento: [TIPO-EVENTO] +55{self.number_whatsapp} — Nome do Paciente

## IMPORTANTE
- Você NUNCA conversa diretamente com o paciente
- Receba instruções, processe com as ferramentas e retorne dados estruturados
- Sempre retorne respostas COMPLETAS das ferramentas (não resuma)
- Para criar evento, use criar_evento_calendar() somente com todas as informações
"""

        try:
            return initialize_agent(
                self.tools,
                self.llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5,
                agent_kwargs={"system_message": system_prompt}
            )
        except Exception as e:
            print(f"⚠️ Erro ao criar agente com system_message, tentando alternativa: {e}")
            # Fallback: criar sem system_message customizado
            return initialize_agent(
                self.tools,
                self.llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                verbose=True,
                handle_parsing_errors=True,
                max_iterations=5
            )

    def process_request(self, request: str, chat_history: list = None):
        """
        Processa uma requisição de agendamento

        Args:
            request: Requisição com informações de agendamento
            chat_history: Histórico de conversa com o AgendaAgent

        Returns:
            Resposta estruturada do agente
        """
        try:
            print(f"\n🗓️  AGENDA AGENT - Processando requisição")
            print(f"📥 Request: {request[:200]}...")

            # Garantir que chat_history está no formato correto
            if chat_history is None:
                chat_history = []

            # Validar que é uma lista
            if not isinstance(chat_history, list):
                print(f"⚠️ chat_history não é uma lista, convertendo para lista vazia")
                chat_history = []

            # Processar request - usar um dicionário limpo para evitar problemas de parsing
            agent_input = {
                "input": request,
                "chat_history": chat_history
            }

            response = self.agent.invoke(agent_input)

            result = response.get("output", "")
            print(f"✅ AGENDA AGENT - Resposta gerada")
            print(f"📤 Response: {result[:200]}...")

            return result

        except Exception as e:
            import traceback
            print(f"❌ AGENDA AGENT - Erro: {e}")
            print(f"📍 Traceback: {traceback.format_exc()}")
            return f"❌ Erro ao processar agendamento: {str(e)}"


class ReceptionistAgent:
    """
    Agente conversacional que interage com o paciente.
    Este agente coleta informações e se comunica com o AgendaAgent
    quando precisa de dados relacionados a agendamento.
    """

    def __init__(self, llm_config: LLMProviderConfig, message_history: MessageHistory, agenda_agent: AgendaAgent):
        """
        Inicializa o AtendimentoAgent

        Args:
            llm_config: Configuração do modelo LLM
            message_history: Histórico de mensagem atual
            agenda_agent: Instância do AgendaAgent para comunicação
        """
        self.llm_config = llm_config
        self.message_history = message_history
        self.chat_session = message_history.chat_session
        self.agenda_agent = agenda_agent
        self.llm = self._create_llm()
        self.tools = self._create_tools()
        self.agent = self._create_agent()

        # Histórico de comunicação com o AgendaAgent
        self.agenda_chat_history = []

        print("✅ AtendimentoAgent inicializado com sucesso")

    def _create_llm(self):
        """Cria o modelo LLM baseado na configuração"""
        provider = self.llm_config.name

        if provider == "openai":
            return ChatOpenAI(
                model=self.llm_config.model,
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                top_p=self.llm_config.top_p,
                presence_penalty=self.llm_config.presence_penalty,
                frequency_penalty=self.llm_config.frequency_penalty,
                openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
            )
        elif provider == "anthropic":
            return ChatAnthropic(
                model=self.llm_config.model,
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                top_p=self.llm_config.top_p,
                anthropic_api_key=getattr(settings, 'ANTHROPIC_API_KEY', '')
            )
        elif provider == "google":
            return ChatGoogleGenerativeAI(
                model=self.llm_config.model,
                temperature=self.llm_config.temperature,
                max_output_tokens=self.llm_config.max_tokens,
                top_p=self.llm_config.top_p,
                google_api_key=getattr(settings, 'GOOGLE_API_KEY', '')
            )
        else:
            return ChatOpenAI(
                model=self.llm_config.model or "gpt-4o",
                temperature=self.llm_config.temperature,
                openai_api_key=getattr(settings, 'OPENAI_API_KEY', '')
            )

    def _create_tools(self):
        """Cria ferramentas para o agente de atendimento"""
        tools = []
        number_whatsapp = self.chat_session.from_number

        # Ferramenta para consultar o AgendaAgent
        def consultar_agenda(request: str):
            """
            Consulta o AgendaAgent para operações de calendário.

            Use esta ferramenta quando precisar:
            - Verificar horários disponíveis
            - Criar um agendamento
            - Verificar dia da semana de uma data
            - Buscar próximas datas de terça ou quinta
            - Listar eventos do calendário

            Exemplos de requisições:
            - "Preciso verificar horários disponíveis para 02/10/2025"
            - "Criar evento para João Silva, consulta particular, dia 02/10/2025 às 09:00"
            - "Verificar se 03/10/2025 é terça ou quinta"
            - "Buscar próximas terças disponíveis"
            """
            try:
                print(f"\n💬 ATENDIMENTO → AGENDA")
                print(f"📤 Solicitação: {request}")

                # Consultar o AgendaAgent
                response = self.agenda_agent.process_request(request, self.agenda_chat_history)

                # Adicionar ao histórico de comunicação entre agentes
                self.agenda_chat_history.append(HumanMessage(content=request))
                self.agenda_chat_history.append(AIMessage(content=response))

                print(f"📥 AGENDA → ATENDIMENTO")
                print(f"📨 Resposta: {response[:200]}...")

                return response

            except Exception as e:
                return f"❌ Erro ao consultar agenda: {str(e)}"

        tools.append(Tool(
            name="consultar_agenda",
            func=consultar_agenda,
            description="""Consulta o assistente de agenda (Aline Agenda) para operações de calendário.

Use quando precisar:
- Verificar horários disponíveis para uma data
- Criar um agendamento/evento no calendário
- Verificar qual dia da semana é uma data
- Buscar próximas terças ou quintas
- Listar eventos do calendário

IMPORTANTE:
- Passe TODAS as informações necessárias na requisição
- Para criar evento, inclua: nome completo, tipo de consulta, data e horário
- Sempre apresente a resposta COMPLETA ao paciente (não resuma)

Exemplos:
consultar_agenda("Verificar horários disponíveis para dia 02/10/2025")
consultar_agenda("Criar evento: João Silva, particular, 02/10/2025 às 09:00")
consultar_agenda("Qual dia da semana é 03/10/2025?")
consultar_agenda("Buscar próximas terças-feiras")
"""
        ))

        # Ferramenta para enviar arquivos
        def send_file(file_name: str):
            """Envia um arquivo disponível para o usuário via WhatsApp"""
            try:
                from whatsapp_connector.services import EvolutionAPIService
                from agents.models import AssistantContextFile
                import re

                print(f"📤 Ferramenta enviar_arquivo chamada com: '{file_name}'")

                clean_name = re.sub(r'\s*\([^)]*\)\s*$', '', file_name).strip()
                print(f"🧹 Nome limpo: '{clean_name}'")

                file_obj = self.llm_config.context_files.filter(
                    name__icontains=clean_name,
                    is_active=True,
                    status='ready'
                ).first()

                if not file_obj:
                    available_files = self.llm_config.context_files.filter(
                        is_active=True,
                        status='ready'
                    ).values_list('name', flat=True)
                    files_list = ', '.join(available_files) if available_files else 'nenhum'
                    return f"❌ Arquivo '{file_name}' não encontrado. Arquivos disponíveis: {files_list}"

                file_path = file_obj.file.path

                service = EvolutionAPIService(self.chat_session.evolution_instance)
                response = service.send_file_message(
                    to_number=number_whatsapp,
                    file_url_or_path=file_path,
                    caption=file_obj.name
                )

                if response:
                    return f"✅ Arquivo '{file_obj.name}' enviado com sucesso!"
                else:
                    return f"❌ Erro ao enviar arquivo '{file_obj.name}'"

            except Exception as e:
                return f"❌ Erro ao enviar arquivo: {str(e)}"

        tools.append(Tool(
            name="enviar_arquivo",
            func=send_file,
            description="Envia um arquivo disponível para o usuário. Use o nome exato do arquivo conforme listado."
        ))

        # Ferramenta para atualizar resumo do contato
        def update_contact_summary(resumo: str):
            """Atualiza o resumo sobre este contato no ChatSession"""
            try:
                print(f"📝 Atualizando resumo do contato {number_whatsapp}")

                self.chat_session.contact_summary = resumo
                self.chat_session.save(update_fields=['contact_summary'])

                print(f"✅ Resumo atualizado: {resumo[:100]}...")
                return "OK (não responder ao usuário; continue a conversa normalmente)."

            except Exception as e:
                print(f"❌ Erro ao atualizar resumo: {e}")
                return f"❌ Erro ao atualizar resumo: {str(e)}"

        tools.append(Tool(
            name="update_contact_summary",
            func=update_contact_summary,
            description="""Atualiza/salva informações importantes sobre este usuário para lembrar em conversas futuras.

Sempre ADICIONE novas informações ao resumo existente (não substitua).
Use formato: "Campo: Valor | Campo2: Valor2"

Exemplo: update_contact_summary('Nome: João Silva | Profissão: Engenheiro | Cidade: São Paulo')"""
        ))

        return tools

    def _create_agent(self):
        """Cria o agente de atendimento com instruções específicas"""
        # Ler instruções do arquivo
        try:
            with open('/home/allanramos/Documentos/workspace/pessoal/assistante/agents/instructions/aline_atendimento.md', 'r', encoding='utf-8') as f:
                atendimento_instructions = f.read()
        except Exception as e:
            print(f"⚠️ Erro ao ler instruções de atendimento: {e}")
            atendimento_instructions = "Você é um assistente de atendimento."

        current_time = datetime.now().strftime('%d/%m/%Y %H:%M')
        numero_whatsapp = self.chat_session.from_number

        # Obter lista de arquivos disponíveis
        available_files = self._get_available_files()

        # Obter resumo do contato
        contact_summary_section = ""
        if self.chat_session.contact_summary:
            contact_summary_section = f""" ## 👤 RESUMO DO CONTATO {self.chat_session.contact_summary}

⚠️ Use essas informações para personalizar o atendimento e evitar perguntar coisas que você já sabe.
🔄 Sempre que descobrir NOVAS informações importantes, atualize o resumo usando a ferramenta `update_contact_summary`.
"""

        system_prompt = f""" {atendimento_instructions}

## INFORMAÇÕES DA SESSÃO
- Número WhatsApp: {numero_whatsapp}
- Data/Hora atual: {current_time}
{contact_summary_section}
"""

        return initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            early_stopping_method="generate",
            agent_kwargs={"system_message": system_prompt}
        )

    def _get_available_files(self):
        """Obtém lista de arquivos disponíveis"""
        context_files = self.llm_config.context_files.filter(
            is_active=True,
            status='ready'
        )

        if not context_files.exists():
            return ""

        files_section = "\n\n## 📁 ARQUIVOS DISPONÍVEIS PARA ENVIO\n\n"
        files_section += "Você tem acesso aos seguintes arquivos que podem ser enviados ao usuário:\n\n"

        for file_obj in context_files:
            files_section += f"- {file_obj.name} ({file_obj.get_file_type_display()})\n"

        files_section += "\n**Para enviar:** use enviar_arquivo(\"nome exato do arquivo\")\n"

        return files_section

    def send_message(self, user_message: str):
        """
        Processa mensagem do usuário através do agente

        Args:
            user_message: Mensagem do usuário

        Returns:
            dict: Resposta do agente
        """
        try:
            print(f"\n🤖 ATENDIMENTO AGENT - INICIANDO")
            print(f"📱 Sessão: {self.chat_session.from_number}")
            print(f"💬 Mensagem: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")

            # Recuperar histórico
            chat_history = self._get_chat_history()
            print(f"📚 Histórico: {len(chat_history)} mensagens")

            # Executar agente
            response = self.agent.invoke({
                "input": user_message,
                "chat_history": chat_history
            })

            ai_response = response.get("output", "")
            print(f"✅ ATENDIMENTO AGENT - SUCESSO")
            print(f"📤 Resposta: {ai_response[:150]}{'...' if len(ai_response) > 150 else ''}")

            # Atualizar o MessageHistory com a resposta
            self.message_history.response = ai_response
            self.message_history.processing_status = 'completed'
            self.message_history.save()

            return {
                "success": True,
                "response": ai_response,
                "model": self.llm_config.model,
                "provider": self.llm_config.get_name_display()
            }

        except Exception as e:
            print(f"❌ ERRO ATENDIMENTO AGENT: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "Desculpe, ocorreu um erro ao processar sua mensagem."
            }

    def _get_chat_history(self):
        """Recupera histórico da conversa no formato LangChain"""
        try:
            last_messages = self.chat_session.messages.order_by("created_at")[:15]
            memory_messages = []

            for msg in last_messages:
                user_content = msg.content or ""
                ai_content = msg.response or ""

                if user_content.strip():
                    memory_messages.append(HumanMessage(content=user_content.strip()))
                if ai_content.strip():
                    memory_messages.append(AIMessage(content=ai_content.strip()))

            return memory_messages

        except Exception as e:
            print(f"Erro ao recuperar histórico: {e}")
            return []


class MultiAgentOrchestrator:
    """
    Orquestrador dos múltiplos agentes.
    Gerencia a criação e comunicação entre AgendaAgent e AtendimentoAgent.
    """

    def __init__(self, llm_config: LLMProviderConfig, message_history: MessageHistory):
        """
        Inicializa o sistema de múltiplos agentes

        Args:
            llm_config: Configuração do modelo LLM
            message_history: Histórico de mensagem atual
        """
        self.llm_config = llm_config
        self.message_history = message_history
        self.chat_session = message_history.chat_session

        print(f"\n{'='*60}")
        print(f"🚀 MULTI-AGENT SYSTEM - INICIALIZAÇÃO")
        print(f"{'='*60}")

        # Criar AgendaAgent
        print("\n📅 Inicializando AgendaAgent...")
        self.agenda_agent = AgendaAgent(
            llm_config=llm_config,
            number_whatsapp=self.chat_session.from_number
        )

        # Criar AtendimentoAgent
        print("\n💬 Inicializando AtendimentoAgent...")
        self.atendimento_agent = ReceptionistAgent(
            llm_config=llm_config,
            message_history=message_history,
            agenda_agent=self.agenda_agent
            # agenda_agent=None
        )

        print(f"\n{'='*60}")
        print(f"✅ MULTI-AGENT SYSTEM - PRONTO")
        print(f"{'='*60}\n")

    def send_message(self, user_message: str):
        """
        Processa mensagem do usuário através do sistema de múltiplos agentes

        Args:
            user_message: Mensagem do usuário

        Returns:
            dict: Resposta processada
        """
        # O AtendimentoAgent gerencia toda a conversa
        # e se comunica com o AgendaAgent quando necessário
        return self.atendimento_agent.send_message(user_message)
