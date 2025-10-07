import traceback

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.conf import settings

from common.models import BaseUUIDModel, HistoryBaseModel


class EvolutionInstance(BaseUUIDModel, HistoryBaseModel):
    """
    Modelo para gerenciar instâncias do Evolution API
    Cada instância representa uma conexão WhatsApp independente
    """
    STATUS_CHOICES = (
        ('disconnected', 'Desconectada'),
        ('connecting', 'Conectando'),
        ('connected', 'Conectada'),
        ('error', 'Erro'),
    )

    owner = models.ForeignKey('core.Client', on_delete=models.CASCADE, related_name='evolution_instances')
    name = models.CharField('Nome da Instância', max_length=100, unique=True)
    instance_evolution_id = models.CharField('Id da Instância no Evolution API', max_length=100, unique=True, null=True, blank=True)
    instance_name = models.CharField('Nome no Evolution API', max_length=100, unique=True)
    base_url = models.URLField('URL Base do Evolution API')
    api_key = models.CharField('Chave da API', max_length=255)
    status = models.CharField('Status', max_length=20, choices=STATUS_CHOICES, default='disconnected')

    # Informações da conexão WhatsApp
    phone_number = models.CharField(
        'Número do WhatsApp', 
        max_length=20, 
        blank=True, 
        null=True,
        help_text='Número capturado automaticamente após o pareamento via QR Code'
    )
    profile_name = models.CharField('Nome do Perfil', max_length=100, blank=True, null=True)
    profile_pic_url = models.URLField('URL da Foto de Perfil', blank=True, null=True)

    last_connection = models.DateTimeField('Última Conexão', blank=True, null=True)

    # Configurações
    is_active = models.BooleanField('Ativa', default=True)
    webhook_url = models.URLField('URL do Webhook', blank=True, null=True)
    ignore_own_messages = models.BooleanField(
        'Ignorar Mensagens Próprias',
        default=True,
        help_text='Se ativo, ignora mensagens enviadas pelo próprio número da instância'
    )
    authorized_numbers = models.TextField(
        'Números Autorizados',
        blank=True,
        null=True,
        help_text='Lista de números autorizados separados por vírgula (ex: 5511999999999, 5511888888888)'
    )
    
    # Configuração de LLM para esta instância
    llm_config = models.ForeignKey(
        'agents.LLMProviderConfig',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name='Configuração LLM',
        help_text='Configuração do modelo de IA para esta instância'
    )

    class Meta:
        verbose_name = 'Instância Evolution'
        verbose_name_plural = 'Instâncias Evolution'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.instance_name}) - {self.get_status_display()}"

    @property
    def is_connected(self):
        """Verifica se a instância está conectada"""
        return self.status == 'connected'

    @property
    def connection_info(self):
        """Retorna informações da conexão formatadas"""
        if self.phone_number and self.profile_name:
            return f"{self.profile_name} ({self.phone_number})"
        return "Não conectado"
    
    def get_authorized_numbers_list(self):
        """Retorna a lista de números autorizados como lista"""
        if not self.authorized_numbers:
            return []
        
        # Remove espaços e separa por vírgula
        numbers = [num.strip() for num in self.authorized_numbers.split(',')]
        # Remove números vazios
        return [num for num in numbers if num]
    
    def is_number_authorized(self, phone_number):
        """Verifica se um número está autorizado"""
        authorized_list = self.get_authorized_numbers_list()
        if not authorized_list:  # Se não há números configurados, todos são autorizados
            return True
        return phone_number in authorized_list
    
    def fetch_and_update_connection_info(self):
        """
        Busca e atualiza informações da instância conectada via Evolution API
        """
        try:
            import requests

            headers = {'apikey': self.api_key}
            updated = False

            # Endpoint principal para buscar informações da instância
            url = f"{self.base_url}/instance/fetchInstances"
            response = requests.get(url, headers=headers, timeout=15)

            print(f'fetch_and_update_connection_info {response.json()}')

            if response.status_code == 200:
                data = response.json()

                # Procurar a instância específica na lista
                instance_info = None
                if isinstance(data, list):
                    for item in data:
                        # Novo formato da API - objetos diretamente no array
                        if item.get('name') == self.instance_name:
                            instance_info = item
                            break

                if instance_info:
                    # Extrair informações do novo formato da API
                    owner_jid = instance_info.get('ownerJid', '')
                    profile_name = instance_info.get('profileName', '')
                    profile_pic_url = instance_info.get('profilePicUrl')
                    api_status = instance_info.get('connectionStatus', '')
                    # Pegar instance_evolution_id do Setting
                    setting_info = instance_info.get('Setting', {})
                    instance_evolution_id = setting_info.get('instanceId', '')

                    # Atualizar instance_evolution_id se for diferente
                    if instance_evolution_id and instance_evolution_id != self.instance_evolution_id:
                        self.instance_evolution_id = instance_evolution_id
                        updated = True
                        print(f"🆔 Instance evolution ID updated: {instance_evolution_id}")

                    # Capturar número da conta (ownerJid é o formato completo)
                    if owner_jid and '@s.whatsapp.net' in owner_jid:
                        phone_number = owner_jid.replace('@s.whatsapp.net', '')
                        if phone_number != self.phone_number:
                            self.phone_number = phone_number
                            updated = True
                            print(f"📱 Phone number updated: {phone_number}")

                    # Atualizar informações do perfil
                    if profile_name and profile_name != self.profile_name:
                        self.profile_name = profile_name
                        updated = True
                        print(f"👤 Profile name updated: {profile_name}")

                    if profile_pic_url and profile_pic_url != self.profile_pic_url:
                        self.profile_pic_url = profile_pic_url
                        updated = True
                        print(f"📸 Profile pic updated: {profile_pic_url}")

                    # Mapear status da API para nosso modelo
                    status_mapping = {
                        'open': 'connected',
                        'connecting': 'connecting',
                        'close': 'disconnected',
                        'closed': 'disconnected'
                    }
                    new_status = status_mapping.get(api_status, self.status)
                    if new_status != self.status:
                        self.status = new_status
                        updated = True
                        print(f"🔄 Status updated: {api_status} -> {new_status}")

                    # Atualizar última conexão
                    self.last_connection = timezone.now()
                    updated = True

                    if updated:
                        self.save()
                        print(f"✅ Updated connection info for instance {self.name}: {owner_jid} (status: {api_status})")
                        return True
                else:
                    print(f"⚠️ Instance {self.instance_name} not found in API response")
                    # Debug: mostrar nomes disponíveis
                    available_names = [item.get('name', 'unknown') for item in data] if isinstance(data, list) else []
                    print(f"   Available instances: {available_names}")

        except Exception as e:
            traceback.print_exc()
            print(f"❌ Error fetching connection info for instance {self.name}: {e}")

        return False


class ChatSession(models.Model):
    SESSION_STATUS = (
        ("ai", "Atendimento por IA"),
        ("human", "Atendimento humano"),
        ("closed", "Encerrada"),
    )

    evolution_instance = models.ForeignKey(
        'EvolutionInstance',
        on_delete=models.CASCADE,
        related_name='chat_sessions',
        blank=True,
        null=True,
        verbose_name='Instância Evolution'
    )
    from_number = models.CharField(max_length=50, verbose_name="Número de origem")
    to_number = models.CharField(max_length=50, verbose_name="Número de destino")
    status = models.CharField(
        max_length=20,
        choices=SESSION_STATUS,
        default="ai",
        verbose_name="Status da sessão"
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
        verbose_name = "Sessão de Chat"
        verbose_name_plural = "Sessões de Chat"
        ordering = ["-id"]

    @classmethod
    def get_or_create_active_session(cls, from_number, to_number, evolution_instance=None):
        """
        Busca uma sessão ativa (ai ou human) ou cria uma nova
        IMPORTANTE: Considera a evolution_instance para evitar conflito entre instâncias diferentes

        Args:
            from_number: Número de origem
            to_number: Número de destino
            evolution_instance: Instância Evolution (opcional)

        Returns:
            tuple: (ChatSession, created)
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
            from_number=from_number,
            to_number=to_number,
            status='ai',  # Default para AI
            evolution_instance=evolution_instance
        )

        print(f"✨ Nova sessão criada: {new_session.id} (instância: {evolution_instance})")
        return new_session, True

    def __str__(self):
        return f"Sessão {self.from_number} → {self.to_number} ({self.get_status_display()})"

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

class MessageHistory(models.Model):
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
    
    chat_session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    owner = models.ForeignKey('core.Client', on_delete=models.CASCADE, related_name='message_history')
    message_id = models.CharField(max_length=255, unique=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    content = models.TextField(blank=True, null=True)
    media_url = models.URLField(blank=True, null=True)
    media_file = models.FileField(upload_to='whatsapp_media/', blank=True, null=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    received_at = models.DateTimeField(default=timezone.now)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default='pending')
    response = models.TextField(blank=True, null=True)
    # n8n_response = models.JSONField(blank=True, null=True)
    
    # Additional fields from assistante integration
    sender_name = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=50, blank=True, null=True)  # ios, android, etc
    audio_transcription = models.TextField(blank=True, null=True)
    raw_data = models.JSONField(blank=True, null=True)  # Store original webhook data
    received_while_inactive = models.BooleanField(
        'Recebida com instância inativa', 
        default=False,
        help_text='Indica se a mensagem foi recebida enquanto a instância estava inativa'
    )

    
    class Meta:
        ordering = ['-received_at']
    
    def __str__(self):
        return f"{self.message_type} from {self.chat_session.from_number} - {self.message_id}"

class ImageProcessingJob(models.Model):
    JOB_STATUS = (
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    
    PROCESSOR_TYPE = (
        ('n8n', 'n8n Webhook'),
        ('ai', 'AI Vision'),
        ('both', 'Both'),
    )
    
    message = models.ForeignKey(MessageHistory, on_delete=models.CASCADE)
    processor_type = models.CharField(max_length=10, choices=PROCESSOR_TYPE)
    status = models.CharField(max_length=20, choices=JOB_STATUS, default='queued')
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    result = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.processor_type} job for {self.message.message_id}"