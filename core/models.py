from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.validators import EmailValidator
from django.core.mail import send_mail
from django.conf import settings
import uuid
import pyotp
import secrets

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
