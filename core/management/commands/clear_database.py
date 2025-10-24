from django.core.management.base import BaseCommand
from agents.models import (
    Agent,
    AgentFile,
    AgentDocument,
    Conversation,
    Message,
    ConversationSummary,
    LongTermMemory
)
from whatsapp_connector.models import (
    EvolutionInstance,
    ChatSession,
    MessageHistory
)
from google_calendar.models import GoogleCalendarAuth
from core.models import Client, Contact


class Command(BaseCommand):
    help = 'Limpa todo o banco de dados mantendo apenas os usuários'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Confirma a limpeza sem pedir confirmação interativa',
        )

    def handle(self, *args, **options):
        # Contagem antes da limpeza
        counts = {
            'messages': Message.objects.count(),
            'conversation_summaries': ConversationSummary.objects.count(),
            'conversations': Conversation.objects.count(),
            'long_term_memories': LongTermMemory.objects.count(),
            'agent_documents': AgentDocument.objects.count(),
            'agent_files': AgentFile.objects.count(),
            'agents': Agent.objects.count(),
            'message_history': MessageHistory.objects.count(),
            'chat_sessions': ChatSession.objects.count(),
            'contacts': Contact.objects.count(),
            'evolution_instances': EvolutionInstance.objects.count(),
            'google_calendar_auths': GoogleCalendarAuth.objects.count(),
            'clients': Client.objects.count(),
        }

        self.stdout.write(
            self.style.WARNING('\n' + '=' * 80)
        )
        self.stdout.write(
            self.style.WARNING('⚠️  ATENÇÃO: LIMPEZA DO BANCO DE DADOS')
        )
        self.stdout.write(
            self.style.WARNING('=' * 80)
        )
        self.stdout.write('\nOs seguintes dados serão PERMANENTEMENTE deletados:\n')

        for model_name, count in counts.items():
            if count > 0:
                self.stdout.write(f'  • {model_name}: {count} registros')

        self.stdout.write(
            self.style.SUCCESS('\n✓ Os usuários (User) e suas senhas serão MANTIDOS\n')
        )

        # Confirmação
        if not options['yes']:
            self.stdout.write(
                self.style.WARNING('Digite "LIMPAR" (em maiúsculas) para confirmar a operação:')
            )
            confirmation = input('> ')

            if confirmation != 'LIMPAR':
                self.stdout.write(
                    self.style.ERROR('\n❌ Operação cancelada pelo usuário.\n')
                )
                return

        self.stdout.write(
            self.style.WARNING('\n' + '=' * 80)
        )
        self.stdout.write(
            self.style.WARNING('🗑️  INICIANDO LIMPEZA DO BANCO DE DADOS...')
        )
        self.stdout.write(
            self.style.WARNING('=' * 80 + '\n')
        )

        # Ordem de deleção respeitando as foreign keys
        deletions = [
            # Agents - dependentes primeiro
            ('Mensagens de Conversas', Message),
            ('Resumos de Conversas', ConversationSummary),
            ('Conversas', Conversation),
            ('Memórias de Longo Prazo', LongTermMemory),
            ('Documentos de Agents', AgentDocument),
            ('Arquivos de Agents', AgentFile),
            ('Agents', Agent),

            # WhatsApp Connector - dependentes primeiro
            ('Histórico de Mensagens', MessageHistory),
            ('Sessões de Chat', ChatSession),
            ('Contatos', Contact),
            ('Instâncias Evolution', EvolutionInstance),

            # Google Calendar
            ('Autenticações Google Calendar', GoogleCalendarAuth),

            # Core - por último
            ('Clientes', Client),
        ]

        for model_name, model_class in deletions:
            count = model_class.objects.count()
            if count > 0:
                model_class.objects.all().delete()
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {model_name}: {count} registros deletados')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⏭  {model_name}: nenhum registro para deletar')
                )

        self.stdout.write(
            self.style.SUCCESS('\n' + '=' * 80)
        )
        self.stdout.write(
            self.style.SUCCESS('✅ LIMPEZA CONCLUÍDA COM SUCESSO!')
        )
        self.stdout.write(
            self.style.SUCCESS('=' * 80)
        )
        self.stdout.write(
            self.style.SUCCESS('\n💡 Apenas os usuários (User) foram mantidos no banco de dados\n')
        )
