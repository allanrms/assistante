from django.db import models
from django.utils import timezone
from pgvector.django import VectorField
from common.models import BaseUUIDModel, HistoryBaseModel
import uuid


# Create your models here.

def generate_unique_message_id():
    """Generate a unique message ID"""
    return str(uuid.uuid4())

class AgentFile(BaseUUIDModel, HistoryBaseModel):
    """
    Arquivos de contexto para assistants
    """
    FILE_TYPES = (
        ('pdf', 'PDF'),
        ('txt', 'Texto'),
        ('docx', 'Word'),
        ('md', 'Markdown'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('html', 'HTML'),
        ('jpg', 'Imagem JPEG'),
        ('png', 'Imagem PNG'),
        ('gif', 'Imagem GIF'),
        ('webp', 'Imagem WEBP'),
    )
    
    STATUS_CHOICES = (
        ('uploading', 'Enviando'),
        ('processing', 'Processando'),
        ('ready', 'Pronto'),
        ('error', 'Erro'),
    )

    agent = models.ForeignKey("Agent", on_delete=models.CASCADE, related_name="files")
    
    name = models.CharField(
        max_length=255,
        verbose_name="Nome do arquivo",
        help_text="Nome descritivo para identificar o arquivo"
    )
    
    file = models.FileField(
        upload_to='agent_files/',
        verbose_name="Arquivo",
        help_text="Arquivo a ser usado como contexto"
    )
    
    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPES,
        verbose_name="Tipo do arquivo",
        help_text="Formato do arquivo (PDF, texto, imagem, etc.)"
    )
    
    extracted_content = models.TextField(
        blank=True, null=True,
        verbose_name="Conteúdo extraído",
        help_text="Texto extraído do arquivo para usar como contexto"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='uploading',
        verbose_name="Status",
        help_text="Status atual do processamento do arquivo"
    )
    
    error_message = models.TextField(
        blank=True, null=True,
        verbose_name="Mensagem de erro",
        help_text="Descrição do erro caso o processamento falhe"
    )
    
    file_size = models.PositiveIntegerField(
        blank=True, null=True,
        verbose_name="Tamanho do arquivo (bytes)",
        help_text="Tamanho do arquivo em bytes"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se desativado, o arquivo não será incluído no contexto"
    )
    
    openai_file_id = models.CharField(
        max_length=255,
        blank=True, null=True,
        verbose_name="OpenAI File ID",
        help_text="ID do arquivo na OpenAI Files API (para PDFs)"
    )

    vectorized = models.BooleanField(
        default=False,
        verbose_name="Vetorizado",
        help_text="Indica se o arquivo já foi processado para busca vetorial"
    )

    class Meta:
        verbose_name = "Arquivo"
        verbose_name_plural = "Arquivos"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_file_type_display()})"
    
    def get_file_extension(self):
        """Retorna a extensão do arquivo"""
        import os
        return os.path.splitext(self.file.name)[1].lower()
    
    def get_file_size_display(self):
        """Retorna o tamanho do arquivo formatado"""
        if not self.file_size:
            return "N/A"
        
        size = self.file_size
        if size < 1024:
            return f"{size} bytes"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

class Agent(BaseUUIDModel, HistoryBaseModel):
    owner = models.ForeignKey('core.Client', on_delete=models.CASCADE, related_name='agents')

    class Meta:
        verbose_name = "Agente"
        verbose_name_plural = "Agentes"
        ordering = ["-created_at"]

    PROVIDERS = (
        ("openai", "OpenAI"),
        ("anthropic", "Anthropic"),
        ("google", "Google DeepMind"),
        ("mistral", "Mistral AI"),
        ("cohere", "Cohere"),
        ("meta", "Meta (LLaMA)"),
        ("xai", "xAI (Grok)"),
        ("other", "Outro"),
    )

    display_name = models.CharField(
        max_length=100,
        verbose_name="Nome da Configuração",
        help_text="Nome para identificar esta configuração (ex: 'OpenAI GPT-4 - Suporte')",
        default="Configuração LLM"
    )
    name = models.CharField(
        max_length=50,
        choices=PROVIDERS,
        default="openai",
        verbose_name="Fornecedor LLM",
        help_text="Provedor do modelo de linguagem (OpenAI, Anthropic, Google, etc.)"
    )
    model = models.CharField(
        max_length=100,
        verbose_name="Modelo",
        help_text="Ex: gpt-3.5-turbo, claude-3, mistral-7b, etc."
    )
    system_prompt = models.TextField(
        blank=True,
        null=True,
        verbose_name="Instruções do agente",
        help_text="Prompt inicial ou system message"
    )
    max_tokens = models.PositiveIntegerField(
        default=1024,
        verbose_name="Máximo de tokens",
        help_text="Número máximo de tokens na resposta gerada"
    )
    temperature = models.FloatField(
        default=0.7,
        verbose_name="Temperatura",
        help_text="Controla a aleatoriedade das respostas (0.0 = determinístico, 1.0 = criativo)"
    )
    top_p = models.FloatField(
        default=1.0,
        verbose_name="Top-p",
        help_text="Amostragem nuclear (nucleus sampling)"
    )
    presence_penalty = models.FloatField(
        default=0.0,
        verbose_name="Penalidade de presença",
        help_text="Penaliza tokens já mencionados para aumentar diversidade de tópicos"
    )
    frequency_penalty = models.FloatField(
        default=0.0,
        verbose_name="Penalidade de frequência",
        help_text="Penaliza tokens repetidos para reduzir repetição de frases"
    )

    has_calendar_tools = models.BooleanField(
        default=False,
        verbose_name="Ferramentas de Calendário",
        help_text="Habilita integração com Google Calendar"
    )

    def __str__(self):
        return self.display_name if self.display_name else f"{self.get_name_display()} - {self.model}"

class AgentDocument(models.Model):
    agent = models.ForeignKey(
        "agents.Agent",
        on_delete=models.CASCADE,
        related_name="documents",
        help_text="Agente ao qual este documento pertence"
    )
    content = models.TextField(
        help_text="Texto do documento para busca semântica"
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Informações adicionais sobre o documento"
    )
    embedding = VectorField(
        dimensions=1536,
        help_text="Representação vetorial do conteúdo para busca semântica"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora de criação do documento"
    )

    class Meta:
        verbose_name = "Documento do Agente"
        verbose_name_plural = "Documentos dos Agentes"
        ordering = ['-created_at']

class Conversation(models.Model):
    CONVERSATION_STATUS = (
        ("ai", "Atendimento por IA"),
        ("human", "Atendimento humano"),
        ("closed", "Encerrada"),
    )

    evolution_instance = models.ForeignKey(
        'whatsapp_connector.EvolutionInstance',
        on_delete=models.CASCADE,
        related_name='conversations',
        blank=True,
        null=True,
        verbose_name='Instância Evolution'
    )
    contact = models.ForeignKey(
        'core.Contact',
        on_delete=models.SET_NULL,
        related_name='conversations',
        blank=True,
        null=True,
        verbose_name='Contato',
        help_text='Contato associado a esta sessão'
    )
    from_number = models.CharField(
        max_length=50,
        verbose_name="Número de origem",
        help_text="Número do WhatsApp que iniciou a conversa"
    )
    to_number = models.CharField(
        max_length=50,
        verbose_name="Número de destino",
        help_text="Número do WhatsApp que recebe as mensagens"
    )
    status = models.CharField(
        max_length=20,
        choices=CONVERSATION_STATUS,
        default="ai",
        verbose_name="Status da sessão",
        help_text="Define se a conversa é atendida por IA, humano ou está encerrada"
    )
    contact_summary = models.TextField(
        blank=True,
        null=True,
        verbose_name="Resumo do contato",
        help_text="Resumo das informações importantes sobre este contato, atualizado pela IA"
    )
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = "Conversação"
        verbose_name_plural = "Conversações"
        ordering = ["-id"]

    @classmethod
    def get_or_create_active_session(cls, contact, from_number, to_number, evolution_instance=None):
        """
        Busca uma sessão ativa (ai ou human) ou cria uma nova
        IMPORTANTE: Considera a evolution_instance para evitar conflito entre instâncias diferentes

        Args:
            contact: Contato
            from_number: Número de origem
            to_number: Número de destino
            evolution_instance: Instância Evolution (opcional)

        Returns:
            tuple: (Conversation, created)
        """
        # Buscar sessão ativa existente para este número E instância
        query_filter = {
            'from_number': from_number,
            'status__in': ['ai', 'human']
        }

        # IMPORTANTE: Se evolution_instance for fornecido, filtrar por ele
        # Isso garante que números usando diferentes instâncias tenham sessões separadas
        if evolution_instance:
            query_filter['evolution_instance'] = evolution_instance

        active_session = cls.objects.filter(**query_filter).last()

        if active_session:
            print(f"♻️ Reutilizando sessão existente: {active_session.id} (instância: {active_session.evolution_instance})")
            return active_session, False

        # Criar nova sessão se não encontrar ativa
        new_session = cls.objects.create(
            contact=contact,
            from_number=from_number,
            to_number=to_number,
            status='ai',  # Default para AI
            evolution_instance=evolution_instance
        )

        print(f"✨ Nova sessão criada: {new_session.id} (instância: {evolution_instance})")
        return new_session, True

    def allows_ai_response(self):
        """
        Verifica se a sessão permite resposta automática do AI

        Returns:
            bool: True se o AI pode responder, False caso contrário
        """
        return self.status == 'ai'

    def is_human_attended(self):
        """
        Verifica se a sessão está sendo atendida por humano

        Returns:
            bool: True se está em atendimento humano, False caso contrário
        """
        return self.status == 'human'

    def is_closed(self):
        """
        Verifica se a sessão está encerrada

        Returns:
            bool: True se está encerrada, False caso contrário
        """
        return self.status == 'closed'

    def __str__(self):
        return f"Conversação {self.from_number} → {self.to_number} ({self.get_status_display()})"

class Message(models.Model):
    MESSAGE_TYPES = (
        ('text', 'Text'),
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('extended_text', 'Extended Text'),
    )

    PROCESSING_STATUS = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    owner = models.ForeignKey(
        'core.Client',
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Cliente',
        null=True,
        blank=True
    )
    message_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='ID da Mensagem',
        default=generate_unique_message_id,
        help_text='Identificador único da mensagem'
    )
    message_type = models.CharField(
        max_length=20,
        choices=MESSAGE_TYPES,
        verbose_name='Tipo de Mensagem',
        default='text',
        help_text='Tipo de conteúdo da mensagem (texto, áudio, imagem, etc.)'
    )
    content = models.TextField(
        verbose_name='Mensagem do usuário',
        blank=True,
        null=True,
        help_text='Conteúdo textual da mensagem recebida'
    )
    media_url = models.URLField(
        blank=True,
        null=True,
        verbose_name='URL da Mídia',
        help_text='URL do arquivo de mídia (imagem, áudio, vídeo, documento)'
    )
    media_file = models.FileField(
        upload_to='whatsapp_media/',
        blank=True,
        null=True,
        verbose_name='Arquivo de Mídia'
    )
    response = models.TextField(
        verbose_name='Resposta da IA',
        blank=True,
        null=True,
        help_text='Resposta gerada pelo agente de IA'
    )
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default='pending',
        verbose_name='Status de Processamento',
        help_text='Status do processamento da mensagem pelo sistema'
    )

    # Additional fields from assistante integration
    sender_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name='Nome do Remetente',
        help_text='Nome do usuário que enviou a mensagem'
    )
    source = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Fonte',
        help_text='Origem da mensagem (iOS, Android, Web, etc.)'
    )
    audio_transcription = models.TextField(
        blank=True,
        null=True,
        verbose_name='Transcrição de Áudio',
        help_text='Texto transcrito de mensagens de áudio via Deepgram'
    )
    raw_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name='Dados Brutos',
        help_text='Dados originais do webhook da Evolution API'
    )
    received_while_inactive = models.BooleanField(
        verbose_name='Recebida com instância inativa',
        default=False,
        help_text='Indica se a mensagem foi recebida enquanto a instância estava inativa'
    )

    created_at = models.DateTimeField(verbose_name='Criado em', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='Atualizado em', auto_now=True)
    received_at = models.DateTimeField(
        verbose_name='Recebido em',
        default=timezone.now
    )

    class Meta:
        ordering = ['-received_at']
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'

    def __str__(self):
        return f"{self.message_type} from {self.conversation.from_number} - {self.message_id}"

class ConversationSummary(models.Model):
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        help_text="Conversação associada a este resumo"
    )
    summary = models.TextField(
        help_text="Resumo automático da conversação gerado pela IA"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Data e hora da última atualização do resumo"
    )

    class Meta:
        verbose_name = "Resumo de Conversação"
        verbose_name_plural = "Resumos de Conversações"
        ordering = ['-updated_at']

class LongTermMemory(models.Model):
    contact = models.ForeignKey(
        'core.Contact',
        on_delete=models.SET_NULL,
        related_name='long_term_memories',
        blank=True,
        null=True,
        verbose_name='Contato',
        help_text='Contato associado a esta memória de longo prazo'
    )
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        help_text="Conversação da qual esta memória foi extraída"
    )
    content = models.TextField(
        help_text="Informações importantes extraídas da conversação"
    )
    embedding = VectorField(
        dimensions=1536,
        help_text="Representação vetorial para busca semântica"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Data e hora de criação da memória"
    )

    class Meta:
        verbose_name = "Memória de Longo Prazo"
        verbose_name_plural = "Memórias de Longo Prazo"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["contact"]),
        ]

