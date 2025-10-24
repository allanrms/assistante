from django.core.management.base import BaseCommand
from agents.models import Conversation, ConversationSummary, LongTermMemory
from agents.tasks import create_conversation_summary, extract_long_term_facts


class Command(BaseCommand):
    help = 'Processa conversas: cria resumos e extrai fatos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--conversation-id',
            type=int,
            help='ID de uma conversa específica para processar'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Processar todas as conversas'
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            help='Processar apenas conversas sem resumo'
        )
        parser.add_argument(
            '--skip-summary',
            action='store_true',
            help='Não criar resumos'
        )
        parser.add_argument(
            '--skip-facts',
            action='store_true',
            help='Não extrair fatos'
        )

    def handle(self, *args, **options):
        # Determinar quais conversas processar
        if options['conversation_id']:
            conversations = Conversation.objects.filter(id=options['conversation_id'])
            self.stdout.write(f"🎯 Processando conversa #{options['conversation_id']}")
        elif options['all']:
            conversations = Conversation.objects.all()
            self.stdout.write(f"🌍 Processando todas as {conversations.count()} conversas")
        elif options['missing_only']:
            conversations = Conversation.objects.filter(summary__isnull=True)
            self.stdout.write(f"📝 Processando {conversations.count()} conversas sem resumo")
        else:
            self.stdout.write(self.style.ERROR("❌ Use --conversation-id, --all ou --missing-only"))
            return

        # Processar cada conversa
        total = conversations.count()
        for i, conversation in enumerate(conversations, 1):
            self.stdout.write(f"\n[{i}/{total}] Conversa #{conversation.id} (Contato: {conversation.contact.phone_number})")

            # Verificar se tem mensagens
            message_count = conversation.messages.count()
            if message_count == 0:
                self.stdout.write(self.style.WARNING(f"  ⚠️ Sem mensagens, pulando..."))
                continue

            self.stdout.write(f"  💬 {message_count} mensagens")

            # Criar resumo
            if not options['skip_summary']:
                try:
                    summary = create_conversation_summary(conversation.id)
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Resumo: {summary[:80]}..."))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ❌ Erro ao criar resumo: {e}"))

            # Extrair fatos
            if not options['skip_facts']:
                try:
                    facts = extract_long_term_facts(conversation.id)
                    self.stdout.write(self.style.SUCCESS(f"  ✅ Fatos extraídos: {len(facts)}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ❌ Erro ao extrair fatos: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\n✨ Processamento completo! {total} conversas processadas."))
