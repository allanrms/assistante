from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings

from common.models import BaseUUIDModel, HistoryBaseModel


# Create your models here.

class AssistantContextFile(BaseUUIDModel, HistoryBaseModel):
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
    
    llm_config = models.ForeignKey(
        'LLMProviderConfig',
        on_delete=models.CASCADE,
        related_name='context_files',
        verbose_name="Configuração LLM"
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name="Nome do arquivo",
        help_text="Nome descritivo para identificar o arquivo"
    )
    
    file = models.FileField(
        upload_to='assistant_context/',
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

    class Meta:
        verbose_name = "Arquivo de Contexto"
        verbose_name_plural = "Arquivos de Contexto"
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


class LLMProviderConfig(BaseUUIDModel, HistoryBaseModel):
    owner = models.ForeignKey('core.Client', on_delete=models.CASCADE, related_name='llm_configs')

    class Meta:
        verbose_name = "Configuração de LLM"
        verbose_name_plural = "Configurações de LLM"
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
    instructions = models.TextField(
        blank=True,
        null=True,
        verbose_name="Instruções",
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

    has_calendar_tools = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name if self.display_name else f"{self.get_name_display()} - {self.model}"



class ChatHistory(models.Model):

    CHANNEL_CHOICES = (
        ("whatsapp", "WhatsApp"),
        ("telegram", "Telegram"),
        ("web", "Web"),
        ("other", "Outro"),
    )

    class Meta:
        verbose_name = "Histórico de Chat"
        verbose_name_plural = "Históricos de Chat"
        ordering = ["-created_at"]

    session_id = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name="ID da Sessão"
    )
    message = models.JSONField(
        verbose_name="Mensagem",
        help_text="Estrutura JSON contendo mensagens do humano ou da IA"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    closed = models.BooleanField(
        default=False,
        verbose_name="Sessão Encerrada",
        help_text="Indica se a sessão foi encerrada"
    )

    # Novo campo para indicar o tipo/origem da mensagem
    type = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default="whatsapp",
        verbose_name="Canal de Origem"
    )

    # Novo campo external_id
    external_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID Externo",
        help_text="ID de referência em sistema externo (ex: WhatsApp, CRM, n8n)"
    )

    # @staticmethod
    # def create(session_id: str, content: str, additional_kwargs=None, response_metadata=None):
    #     """Cria uma entrada de histórico para uma mensagem humana."""
    #     message = {
    #         "type": "human",
    #         "content": content,
    #         "additional_kwargs": additional_kwargs or {},
    #         "response_metadata": response_metadata or {}
    #     }
    #     instance = ChatHistory(session_id=session_id, message=message)
    #     instance.clean()
    #     instance.save()
    #     return instance

    @staticmethod
    def create(
            session_id: str,
            content: str,
            response: None,
            external_id=None,
            type = 'whatsapp',
            tool_calls=None,
            additional_kwargs=None,
            response_metadata=None,
            invalid_tool_calls=None,

    ):
        """Cria uma entrada de histórico para uma resposta de IA."""


        message = {
            "content": content,
            "response": response,
            "type": type,
            "tool_calls": tool_calls or [],
            "additional_kwargs": additional_kwargs or {},
            "response_metadata": response_metadata or {},
            "invalid_tool_calls": invalid_tool_calls or []
        }
        instance = ChatHistory(session_id=session_id, message=message, external_id=external_id)
        instance.clean()
        instance.save()
        return instance

    @staticmethod
    def close(external_id: str):
        ChatHistory.objects.filter(external_id=external_id).update(closed=True)

    def __str__(self):
        return f"Sessão {self.session_id}"

    def clean(self):
        """
        Valida se o campo 'message' segue o formato correto dependendo do 'type'.
        """
        if not isinstance(self.message, dict):
            raise ValidationError({"message": "A mensagem deve ser um objeto JSON (dict)."})

        # msg_type = self.message.get("type")
        # if msg_type not in ["human", "ai"]:
        #     raise ValidationError({"message": "O campo 'type' deve ser 'human' ou 'ai'."})

        # Validação para humano
        # if msg_type == "human":
        #     required_fields = {"type", "content", "additional_kwargs", "response_metadata"}
        #     missing = required_fields - self.message.keys()
        #     if missing:
        #         raise ValidationError({"message": f"Mensagem humana faltando campos: {', '.join(missing)}"})

        # Validação para IA
        # if msg_type == "ai":
        #     required_fields = {
        #         "type", "content", "tool_calls", "additional_kwargs",
        #         "response_metadata", "invalid_tool_calls"
        #     }
        #     missing = required_fields - self.message.keys()
        #     if missing:
        #         raise ValidationError({"message": f"Mensagem de IA faltando campos: {', '.join(missing)}"})

