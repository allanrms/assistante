from django.db import models
from pgvector.django import VectorField
from common.models import BaseUUIDModel, HistoryBaseModel


# Create your models here.

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
        verbose_name="Tipo do arquivo"
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
        verbose_name="Status"
    )
    
    error_message = models.TextField(
        blank=True, null=True,
        verbose_name="Mensagem de erro"
    )
    
    file_size = models.PositiveIntegerField(
        blank=True, null=True,
        verbose_name="Tamanho do arquivo (bytes)"
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

    vectorized = models.BooleanField(default=False)

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
        verbose_name="Fornecedor LLM"
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
        verbose_name="Máximo de tokens"
    )
    temperature = models.FloatField(
        default=0.7,
        verbose_name="Temperatura"
    )
    top_p = models.FloatField(
        default=1.0,
        verbose_name="Top-p",
        help_text="Amostragem nuclear (nucleus sampling)"
    )
    presence_penalty = models.FloatField(
        default=0.0,
        verbose_name="Penalidade de presença"
    )
    frequency_penalty = models.FloatField(
        default=0.0,
        verbose_name="Penalidade de frequência"
    )

    has_calendar_tools = models.BooleanField(
        default=False,
        verbose_name="Ferramentas de Calendário",
        help_text="Habilita integração com Google Calendar"
    )

    def __str__(self):
        return self.display_name if self.display_name else f"{self.get_name_display()} - {self.model}"

class AgentDocument(models.Model):
    agent = models.ForeignKey("agents.Agent", on_delete=models.CASCADE, related_name="documents")
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=1536)  # depende do modelo de embedding
    created_at = models.DateTimeField(auto_now_add=True)

class Conversation(models.Model):
    CONVERSATION_STATUS = (
        ("ai", "Atendimento por IA"),
        ("human", "Atendimento humano"),
        ("closed", "Encerrada"),
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
    from_number = models.CharField(max_length=50, verbose_name="Número de origem")
    to_number = models.CharField(max_length=50, verbose_name="Número de destino")
    status = models.CharField(
        max_length=20,
        choices=CONVERSATION_STATUS,
        default="ai",
        verbose_name="Status da sessão"
    )
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    content = models.TextField(verbose_name='Mensagem do usuário')
    response = models.TextField(verbose_name='Resposta da IA', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Mensagem'
        verbose_name_plural = 'Mensagens'

    def __str__(self):
        return f"Message #{self.id} - Conversation #{self.conversation_id}"

class ConversationSummary(models.Model):
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE)
    summary = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

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
    source = models.CharField(max_length=64, default="note")
    content = models.TextField()
    embedding = VectorField(dimensions=1536)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["contact"]),
        ]

