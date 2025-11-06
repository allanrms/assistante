from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import EmailValidator, RegexValidator
from django.core.mail import send_mail
from django.conf import settings
import uuid
import pyotp

User = get_user_model()


class Client(models.Model):
    """
    Modelo de Cliente para o sistema Assistante.
    Representa um cliente que pode contratar serviços.
    """

    CLIENT_TYPE_CHOICES = [
        ('individual', _('Pessoa Física')),
        ('company', _('Pessoa Jurídica')),
    ]

    STATUS_CHOICES = [
        ('pending', _('Pendente de Confirmação')),
        ('active', _('Ativo')),
        ('inactive', _('Inativo')),
        ('suspended', _('Suspenso')),
    ]

    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Dados Básicos
    full_name = models.CharField(
        max_length=255,
        verbose_name=_('Nome Completo')
    )
    email = models.EmailField(
        unique=True,
        validators=[EmailValidator()],
        verbose_name=_('E-mail')
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name=_('Telefone')
    )

    # Tipo de Cliente
    client_type = models.CharField(
        max_length=20,
        choices=CLIENT_TYPE_CHOICES,
        default='individual',
        verbose_name=_('Tipo de Cliente')
    )

    # Dados de Pessoa Jurídica (opcional)
    company_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Razão Social')
    )
    cnpj = models.CharField(
        max_length=18,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('CNPJ')
    )

    # Dados de Pessoa Física (opcional)
    cpf = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        unique=True,
        verbose_name=_('CPF')
    )

    # Dados de Faturamento
    billing_address = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Endereço de Faturamento')
    )
    billing_city = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_('Cidade')
    )
    billing_state = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        verbose_name=_('Estado')
    )
    billing_zip_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        verbose_name=_('CEP')
    )
    billing_country = models.CharField(
        max_length=2,
        default='BR',
        verbose_name=_('País')
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_('Status')
    )

    # 2FA (Two-Factor Authentication)
    # Política do cliente: determina se 2FA é obrigatório para todos os usuários
    is_2fa_enabled = models.BooleanField(
        default=False,
        verbose_name=_('2FA Habilitado'),
        help_text=_('Quando ativo, todos os usuários deste cliente precisarão usar 2FA')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Cliente')
        verbose_name_plural = _('Clientes')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['client_type']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    def save(self, *args, **kwargs):
        """
        Validações customizadas no save.
        """
        # Validação de CPF para pessoa física
        if self.client_type == 'individual' and not self.cpf:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('CPF é obrigatório para pessoa física'))

        # Validação de CNPJ para pessoa jurídica
        if self.client_type == 'company' and not self.cnpj:
            from django.core.exceptions import ValidationError
            raise ValidationError(_('CNPJ é obrigatório para pessoa jurídica'))

        super().save(*args, **kwargs)

    def enable_2fa(self):
        """
        Habilita 2FA para o cliente (política).
        Cada usuário terá seu próprio otp_secret gerado no primeiro uso.
        """
        self.is_2fa_enabled = True
        self.save()

    def disable_2fa(self):
        """
        Desabilita 2FA para o cliente (política).
        """
        self.is_2fa_enabled = False
        self.save()

    def generate_otp_for_user(self, user):
        """
        Gera um código OTP de 6 dígitos válido por 5 minutos para um usuário específico.
        """
        if not user.otp_secret:
            user.otp_secret = pyotp.random_base32()
            user.save(update_fields=['otp_secret'])

        totp = pyotp.TOTP(user.otp_secret, interval=300)  # 5 minutos
        return totp.now()

    def verify_otp_for_user(self, user, otp_code):
        """
        Verifica se o código OTP fornecido é válido para um usuário específico.
        """
        if not user.otp_secret:
            return False

        totp = pyotp.TOTP(user.otp_secret, interval=300)  # 5 minutos
        return totp.verify(otp_code, valid_window=1)  # Aceita código anterior e próximo

    def send_otp_email_for_user(self, user):
        """
        Envia o código OTP por e-mail para um usuário específico.
        """
        otp_code = self.generate_otp_for_user(user)
        subject = 'Código de Verificação - Assistante'
        message = f'''
Olá {user.get_full_name() or user.username},

Seu código de verificação é: {otp_code}

Este código é válido por 5 minutos.

Se você não solicitou este código, ignore este e-mail.

Atenciosamente,
Equipe Assistante
        '''

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True

class Employee(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='employees',
        help_text=_('Cliente')
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='employees',
        help_text=_('Usuário')
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')
        unique_together = [['client', 'user']]
        indexes = [
            models.Index(fields=['client',]),
        ]

class Tag(models.Model):
    """
    Modelo de Tag para categorização de contatos.
    Cada tag tem um nome e uma cor para facilitar visualização.
    """

    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacionamento com cliente
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='tags',
        verbose_name=_('Cliente'),
        help_text=_('Cliente proprietário desta tag')
    )

    # Dados da tag
    name = models.CharField(
        max_length=50,
        verbose_name=_('Nome'),
        help_text=_('Nome da tag (ex: VIP, Cliente, Prospect)')
    )

    color = models.CharField(
        max_length=7,
        default='#3B82F6',  # Azul padrão
        verbose_name=_('Cor'),
        help_text=_('Cor em formato hexadecimal (ex: #FF5733)'),
        validators=[
            RegexValidator(
                regex='^#[0-9A-Fa-f]{6}$',
                message=_('Cor deve estar no formato hexadecimal (ex: #FF5733)')
            )
        ]
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')
        ordering = ['name']
        # Cada cliente pode ter tags com nomes únicos
        unique_together = [['client', 'name']]
        indexes = [
            models.Index(fields=['client', 'name']),
        ]

    def __str__(self):
        return f"{self.name}"

    @classmethod
    def get_or_create_tag(cls, client, name, color='#3B82F6'):
        """
        Busca ou cria uma tag para um cliente específico.

        Args:
            client (Client): Cliente proprietário da tag
            name (str): Nome da tag
            color (str): Cor em hexadecimal (opcional)

        Returns:
            tuple: (Tag, created)
        """
        # Normalizar nome (capitalizar primeira letra)
        normalized_name = name.strip().capitalize()

        tag, created = cls.objects.get_or_create(
            client=client,
            name=normalized_name,
            defaults={'color': color}
        )

        return tag, created

class Contact(models.Model):
    """
    Modelo de Contato para o sistema Orbi.
    Representa um contato que interagiu via WhatsApp.
    """

    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacionamento com cliente (opcional - pode não ser cliente ainda)
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name=_('Cliente')
    )

    # Dados do contato
    phone_number = models.CharField(
        unique=True,
        max_length=20,
        verbose_name=_('Número de Telefone'),
        help_text=_('Número no formato internacional (ex: 5511999999999)')
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Nome')
    )

    profile_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Nome do Perfil WhatsApp')
    )

    profile_pic_url = models.URLField(
        blank=True,
        null=True,
        verbose_name=_('Foto de Perfil')
    )

    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name=_('E-mail')
    )

    # Metadados
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Notas'),
        help_text=_('Observações sobre o contato')
    )

    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='contacts',
        verbose_name=_('Tags'),
        help_text=_('Tags associadas a este contato')
    )

    # Estatísticas
    first_contact_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Primeiro Contato')
    )

    last_contact_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Último Contato')
    )

    total_messages = models.IntegerField(
        default=0,
        verbose_name=_('Total de Mensagens')
    )

    # Status
    is_blocked = models.BooleanField(
        default=False,
        verbose_name=_('Bloqueado'),
        help_text=_('Se bloqueado, o bot não responderá mensagens deste contato')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Ativo')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Contato')
        verbose_name_plural = _('Contatos')
        ordering = ['-last_contact_at']
        # Um mesmo número pode ser contato de diferentes clientes
        unique_together = [['phone_number', 'client']]
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['client']),
            models.Index(fields=['is_blocked']),
            models.Index(fields=['last_contact_at']),
        ]

    def __str__(self):
        if self.name:
            return f"{self.name} ({self.phone_number})"
        return self.phone_number

    @classmethod
    def get_or_create_from_whatsapp(cls, phone_number, **kwargs):
        """
        Busca ou cria um contato a partir de dados do WhatsApp.

        IMPORTANTE: Considera phone_number + client para buscar/criar.
        Um mesmo número pode ser contato de diferentes clientes.

        Args:
            phone_number (str): Número de telefone do contato
            **kwargs: Dados adicionais (client, name, profile_name, profile_pic_url, etc)

        Returns:
            tuple: (Contact, created)
        """
        # Normalizar número de telefone (remover espaços e caracteres especiais)
        normalized_phone = cls.normalize_phone_number(phone_number)

        # Extrair client dos kwargs se fornecido
        client = kwargs.pop('client', None)

        # Construir filtros de busca
        lookup_fields = {'phone_number': normalized_phone}
        if client:
            lookup_fields['client'] = client

        # Preparar defaults (incluindo client se fornecido)
        defaults = kwargs.copy()
        if client:
            defaults['client'] = client

        # Buscar ou criar contato por phone_number + client
        contact, created = cls.objects.get_or_create(
            **lookup_fields,
            defaults=defaults
        )

        # Se já existe, atualizar informações se fornecidas
        if not created:
            needs_update = False

            # Atualizar campos se fornecidos e diferentes (exceto client)
            for field, value in kwargs.items():
                if value and getattr(contact, field) != value:
                    setattr(contact, field, value)
                    needs_update = True

            # Incrementar contador de mensagens
            contact.total_messages += 1

            # Sempre salvar se não foi criado agora (para atualizar last_contact_at e contador)
            contact.save()

        return contact, created

    @staticmethod
    def normalize_phone_number(phone_number):
        """
        Normaliza um número de telefone removendo caracteres especiais.

        Args:
            phone_number (str): Número a ser normalizado

        Returns:
            str: Número normalizado
        """
        import re
        # Remove @s.whatsapp.net se presente
        phone_number = phone_number.replace('@s.whatsapp.net', '')

        # Remove tudo exceto números
        normalized = re.sub(r'\D', '', phone_number)

        return normalized

    def block(self, reason=None):
        """
        Bloqueia o contato.

        Args:
            reason (str, optional): Motivo do bloqueio
        """
        self.is_blocked = True
        if reason:
            current_notes = self.notes or ''
            self.notes = f"{current_notes}\n[BLOQUEADO] {reason}" if current_notes else f"[BLOQUEADO] {reason}"
        self.save()

    def unblock(self):
        """
        Desbloqueia o contato.
        """
        self.is_blocked = False
        self.save()

    def add_tag(self, tag_name, color='#3B82F6'):
        """
        Adiciona uma tag ao contato.

        Args:
            tag_name (str ou Tag): Nome da tag ou objeto Tag
            color (str): Cor em hexadecimal (usado apenas se tag_name for string)

        Returns:
            Tag: Objeto tag adicionado
        """
        # Se já é um objeto Tag, adicionar diretamente
        if isinstance(tag_name, Tag):
            tag = tag_name
        else:
            # Se é string, buscar ou criar a tag
            if not self.client:
                raise ValueError("Contato precisa ter um cliente vinculado para adicionar tags")

            tag, created = Tag.get_or_create_tag(
                client=self.client,
                name=tag_name,
                color=color
            )

        # Adicionar tag ao contato se ainda não estiver
        if not self.tags.filter(id=tag.id).exists():
            self.tags.add(tag)

        return tag

    def remove_tag(self, tag_name):
        """
        Remove uma tag do contato.

        Args:
            tag_name (str ou Tag): Nome da tag ou objeto Tag
        """
        # Se já é um objeto Tag, remover diretamente
        if isinstance(tag_name, Tag):
            self.tags.remove(tag_name)
        else:
            # Se é string, buscar a tag e remover
            if self.client:
                try:
                    tag = Tag.objects.get(client=self.client, name__iexact=tag_name)
                    self.tags.remove(tag)
                except Tag.DoesNotExist:
                    pass  # Tag não existe, não há nada a remover

    def get_tags_list(self):
        """
        Retorna a lista de objetos Tag do contato.

        Returns:
            QuerySet: QuerySet de Tags
        """
        return self.tags.all()

    def get_tags_display(self):
        """
        Retorna as tags formatadas para exibição (lista de nomes).

        Returns:
            list: Lista de nomes de tags
        """
        return [tag.name for tag in self.tags.all()]

    def link_to_client(self, client):
        """
        Vincula o contato a um cliente.

        Args:
            client (Client): Cliente a ser vinculado
        """
        self.client = client
        self.save()

    def get_message_history(self):
        """
        Retorna o histórico completo de mensagens deste contato.

        Returns:
            QuerySet: Histórico de mensagens
        """
        from whatsapp_connector.models import MessageHistory
        # Usar o related_name 'chat_sessions' do ForeignKey
        return MessageHistory.objects.filter(chat_session__in=self.chat_sessions.all())

    def increment_message_count(self):
        """
        Incrementa o contador de mensagens do contato.
        """
        self.total_messages += 1
        self.save(update_fields=['total_messages', 'updated_at'])

class Appointment(models.Model):
    """
    Represents a medical appointment linked to a WhatsApp contact.
    """

    STATUS_CHOICES = [
        ('draft', 'Rascunho'),
        ('pending', 'Aguardando Confirmação'),
        ('confirmed', 'Confirmado'),
        ('cancelled', 'Cancelado'),
        ('completed', 'Realizado'),
    ]

    contact = models.ForeignKey(
        "core.Contact",
        on_delete=models.CASCADE,
        related_name="appointments",
        help_text="Contato vinculado a este agendamento.",
    )

    # Appointment details
    date = models.DateField(help_text="Data", blank=True, null=True)
    time = models.TimeField(help_text="Hora", blank=True, null=True)

    scheduled_for = models.DateTimeField(help_text="Agendado para", blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Status",
        help_text="Status do agendamento"
    )

    # Google Calendar integration
    calendar_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="ID do Evento no Google Calendar",
        help_text="ID do evento criado no Google Calendar"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated at")

    class Meta:
        verbose_name = "Consulta"
        verbose_name_plural = "Consultas"
        ordering = ["-date", "-time"]
        indexes = [
            models.Index(fields=["date"]),
        ]

    def __str__(self):
        contact_name = self.contact.name or self.contact.phone_number
        return f"{contact_name} "

    def save(self, *args, **kwargs):
        # Auto-sincroniza date/time ao salvar
        if self.scheduled_for:
            self.date = self.scheduled_for.date()
            self.time = self.scheduled_for.time()
        super().save(*args, **kwargs)


class ScheduleConfig(models.Model):
    """
    Schedule configuration for the client.
    Defines default appointment duration and other global settings.
    """

    APPOINTMENT_DURATION_CHOICES = [
        (30, '30 minutos'),
        (60, '1 hora'),
        (90, '1 hora e 30 minutos'),
        (120, '2 horas'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name='schedule_config',
        verbose_name=_('Cliente'),
        help_text=_('Cliente proprietário desta configuração de agenda')
    )

    appointment_duration = models.IntegerField(
        choices=APPOINTMENT_DURATION_CHOICES,
        default=60,
        verbose_name=_('Tempo de Consulta (minutos)'),
        help_text=_('Duração padrão de cada consulta em minutos')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Configuração de Agenda')
        verbose_name_plural = _('Configurações de Agenda')

    def __str__(self):
        return f"Agenda de {self.client.full_name}"


class WorkingDay(models.Model):
    """
    Working hours configuration per weekday.
    """

    WEEKDAY_CHOICES = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    schedule_config = models.ForeignKey(
        ScheduleConfig,
        on_delete=models.CASCADE,
        related_name='working_days',
        verbose_name=_('Configuração de Agenda')
    )

    weekday = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        verbose_name=_('Dia da Semana'),
        help_text=_('Dia da semana (0=Segunda, 6=Domingo)')
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Ativo'),
        help_text=_('Se desativado, não haverá atendimento neste dia')
    )

    start_time = models.TimeField(
        verbose_name=_('Horário de Início'),
        help_text=_('Horário de início do expediente')
    )

    end_time = models.TimeField(
        verbose_name=_('Horário de Término'),
        help_text=_('Horário de término do expediente')
    )

    lunch_start_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_('Horário de Início do Almoço'),
        help_text=_('Horário de início do intervalo de almoço (opcional)')
    )

    lunch_end_time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_('Horário de Término do Almoço'),
        help_text=_('Horário de término do intervalo de almoço (opcional)')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Dia de Atendimento')
        verbose_name_plural = _('Dias de Atendimento')
        ordering = ['weekday']
        # Each schedule config can have only one configuration per weekday
        unique_together = [['schedule_config', 'weekday']]
        indexes = [
            models.Index(fields=['schedule_config', 'weekday']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        day_name = dict(self.WEEKDAY_CHOICES)[self.weekday]
        status = "Ativo" if self.is_active else "Inativo"
        return f"{day_name} - {self.start_time} às {self.end_time} ({status})"

    def get_available_times(self, date=None):
        """
        Returns list of available times for this day, considering
        the configured appointment duration.

        Args:
            date (date, optional): Specific date to check availability

        Returns:
            list: List of available times (time objects)
        """
        from datetime import datetime, timedelta
        from django.utils import timezone

        if not self.is_active:
            return []

        times = []
        duration = self.schedule_config.appointment_duration

        # Convert times to datetime for calculations
        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)

        lunch_start = None
        lunch_end = None
        if self.lunch_start_time and self.lunch_end_time:
            lunch_start = datetime.combine(datetime.today(), self.lunch_start_time)
            lunch_end = datetime.combine(datetime.today(), self.lunch_end_time)

        # Get current time if checking for today
        now = timezone.localtime(timezone.now())
        is_today = date and date == now.date()

        # Generate available times
        current_time = start
        while current_time + timedelta(minutes=duration) <= end:
            # Check if not in lunch time
            in_lunch = False
            if lunch_start and lunch_end:
                in_lunch = lunch_start <= current_time < lunch_end

            # Check if time hasn't passed yet (only for today)
            time_has_passed = False
            if is_today:
                time_has_passed = current_time.time() <= now.time()

            # Add time if it's not in lunch and hasn't passed yet
            if not in_lunch and not time_has_passed:
                times.append(current_time.time())

            # Move to next time slot
            current_time += timedelta(minutes=duration)

        return times


class BlockedDay(models.Model):
    """
    Specific blocked dates (holidays, vacation, etc).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    schedule_config = models.ForeignKey(
        ScheduleConfig,
        on_delete=models.CASCADE,
        related_name='blocked_days',
        verbose_name=_('Configuração de Agenda')
    )

    date = models.DateField(
        verbose_name=_('Data'),
        help_text=_('Data bloqueada para atendimento')
    )

    reason = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Motivo'),
        help_text=_('Motivo do bloqueio (ex: Feriado, Férias, etc)')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Dia Bloqueado')
        verbose_name_plural = _('Dias Bloqueados')
        ordering = ['date']
        # Each schedule config can have only one block per date
        unique_together = [['schedule_config', 'date']]
        indexes = [
            models.Index(fields=['schedule_config', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        reason_text = f" - {self.reason}" if self.reason else ""
        return f"{self.date.strftime('%d/%m/%Y')}{reason_text}"


class AppointmentToken(models.Model):
    """
    Token for public appointment scheduling link.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='token',
        verbose_name=_('Agendamento'),
        help_text=_('Agendamento associado a este token')
    )

    token = models.CharField(
        max_length=64,
        unique=True,
        verbose_name=_('Token'),
        help_text=_('Token único para acesso público')
    )

    expires_at = models.DateTimeField(
        verbose_name=_('Expira em'),
        help_text=_('Data e hora de expiração do link')
    )

    is_used = models.BooleanField(
        default=False,
        verbose_name=_('Utilizado'),
        help_text=_('Se o link já foi utilizado para confirmar agendamento')
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )

    class Meta:
        verbose_name = _('Token de Agendamento')
        verbose_name_plural = _('Tokens de Agendamento')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"Token para {self.appointment.contact.name or self.appointment.contact.phone_number}"

    def is_valid(self):
        """Verifica se o token ainda é válido"""
        from django.utils import timezone
        return not self.is_used and self.expires_at > timezone.now()

    def get_public_url(self, base_url):
        """Retorna a URL pública do agendamento"""
        return f"{base_url}/agendar/{self.token}/"


class Service(models.Model):
    """
    Modelo de Serviço para o sistema Assistante.
    Representa um serviço oferecido pelo cliente (ex: consulta, exame, procedimento).
    """

    SERVICE_TYPE_CHOICES = [
        ('particular', _('Particular')),
        ('convenio', _('Convênio')),
        ('sus', _('SUS')),
    ]

    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacionamento com cliente (multi-tenant)
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='services',
        verbose_name=_('Cliente'),
        help_text=_('Cliente proprietário deste serviço')
    )

    # Dados Básicos
    name = models.CharField(
        max_length=255,
        verbose_name=_('Nome do Serviço'),
        help_text=_('Nome completo do serviço (ex: Consulta Clínica Geral)')
    )

    slug = models.SlugField(
        max_length=100,
        blank=True,
        verbose_name=_('Sigla'),
        help_text=_('Sigla ou código do serviço (ex: CCG)')
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_('Descrição'),
        help_text=_('Descrição detalhada do serviço')
    )

    duration = models.IntegerField(
        verbose_name=_('Duração (minutos)'),
        help_text=_('Duração do serviço em minutos')
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_('Valor (R$)'),
        help_text=_('Valor do serviço em reais')
    )

    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
        default='particular',
        verbose_name=_('Tipo'),
        help_text=_('Tipo de serviço')
    )

    # AutoAgendamento
    auto_scheduling_enabled = models.BooleanField(
        default=False,
        verbose_name=_('AutoAgendamento Ativo'),
        help_text=_('Permite que clientes agendem este serviço online')
    )

    scheduling_link_token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_('Token do Link'),
        help_text=_('Token único para link público de agendamento')
    )

    # Configurações de Escassez
    scarcity_enabled = models.BooleanField(
        default=False,
        verbose_name=_('Ativar Escassez'),
        help_text=_('Mostra mensagens de escassez (ex: "Apenas 2 vagas restantes")')
    )

    show_adjacent_slots_only = models.BooleanField(
        default=False,
        verbose_name=_('Mostrar Apenas Horários Adjacentes'),
        help_text=_('Mostrar apenas horários próximos ao horário atual')
    )

    max_daily_options = models.IntegerField(
        default=10,
        verbose_name=_('Máximo de Opções por Dia'),
        help_text=_('Número máximo de horários a mostrar por dia')
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Ativo'),
        help_text=_('Serviço está disponível para agendamento')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Serviço')
        verbose_name_plural = _('Serviços')
        ordering = ['name']
        unique_together = [['client', 'slug']]
        indexes = [
            models.Index(fields=['client', 'is_active']),
            models.Index(fields=['slug']),
            models.Index(fields=['auto_scheduling_enabled']),
        ]

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        """Gera token automático para link de agendamento se não existir"""
        import secrets
        if self.auto_scheduling_enabled and not self.scheduling_link_token:
            self.scheduling_link_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def get_public_scheduling_url(self, base_url):
        """Retorna a URL pública de agendamento"""
        if self.auto_scheduling_enabled and self.scheduling_link_token:
            return f"{base_url}/agendar/{self.scheduling_link_token}/"
        return None

    def get_available_days_of_week(self):
        """Retorna os dias da semana em que o serviço está disponível"""
        return self.availabilities.filter(is_active=True).values_list('weekday', flat=True).distinct()

    def has_availability_on_date(self, target_date):
        """Verifica se o serviço está disponível em uma data específica"""
        weekday = target_date.weekday()
        return self.availabilities.filter(weekday=weekday, is_active=True).exists()


class ServiceAvailability(models.Model):
    """
    Disponibilidade semanal do serviço por dia da semana.
    Permite múltiplos períodos por dia (ex: manhã e tarde).
    """

    WEEKDAY_CHOICES = [
        (0, 'Segunda-feira'),
        (1, 'Terça-feira'),
        (2, 'Quarta-feira'),
        (3, 'Quinta-feira'),
        (4, 'Sexta-feira'),
        (5, 'Sábado'),
        (6, 'Domingo'),
    ]

    # Identificação
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacionamento com serviço
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='availabilities',
        verbose_name=_('Serviço')
    )

    # Dia da Semana
    weekday = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        verbose_name=_('Dia da Semana'),
        help_text=_('Dia da semana (0=Segunda, 6=Domingo)')
    )

    # Horários
    start_time = models.TimeField(
        verbose_name=_('Horário de Início'),
        help_text=_('Horário de início da disponibilidade')
    )

    end_time = models.TimeField(
        verbose_name=_('Horário de Término'),
        help_text=_('Horário de término da disponibilidade')
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('Ativo'),
        help_text=_('Período está ativo para agendamento')
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Criado em')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Atualizado em')
    )

    class Meta:
        verbose_name = _('Disponibilidade do Serviço')
        verbose_name_plural = _('Disponibilidades dos Serviços')
        ordering = ['weekday', 'start_time']
        indexes = [
            models.Index(fields=['service', 'weekday']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        day_name = dict(self.WEEKDAY_CHOICES)[self.weekday]
        return f"{self.service.name} - {day_name}: {self.start_time} às {self.end_time}"

    def get_available_time_slots(self, date=None):
        """
        Retorna lista de horários disponíveis para este período,
        considerando a duração do serviço.

        Args:
            date (date, optional): Data específica para verificar disponibilidade

        Returns:
            list: Lista de horários disponíveis (time objects)
        """
        from datetime import datetime, timedelta
        from django.utils import timezone

        if not self.is_active:
            return []

        slots = []
        duration = self.service.duration

        # Converter horários para datetime para cálculos
        start = datetime.combine(datetime.today(), self.start_time)
        end = datetime.combine(datetime.today(), self.end_time)

        # Obter horário atual se for para verificar hoje
        now = timezone.localtime(timezone.now())
        is_today = date and date == now.date()

        # Gerar slots disponíveis
        current_time = start
        while current_time + timedelta(minutes=duration) <= end:
            # Verificar se o horário já passou (apenas para hoje)
            time_has_passed = False
            if is_today:
                time_has_passed = current_time.time() <= now.time()

            # Adicionar slot se não passou
            if not time_has_passed:
                slots.append(current_time.time())

            # Mover para próximo slot
            current_time += timedelta(minutes=duration)

        return slots

    def clean(self):
        """Validação customizada"""
        from django.core.exceptions import ValidationError

        if self.start_time >= self.end_time:
            raise ValidationError(_('Horário de início deve ser anterior ao horário de término'))


