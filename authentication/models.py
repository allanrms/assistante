from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class User(AbstractUser):
    """
    Modelo de usuário personalizado com campo de linguagem preferida
    """
    LANGUAGE_CHOICES = settings.LANGUAGES

    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default=settings.LANGUAGE_CODE,
        verbose_name="Idioma Preferido",
        help_text="Idioma preferido do usuário para a interface"
    )

    client = models.ForeignKey(
        'core.Client',
        on_delete=models.CASCADE,
        related_name='users',
        verbose_name="Cliente",
        help_text="Cliente ao qual este usuário pertence",
        null=True,
        blank=True
    )

    # Campos de confirmação de email
    email_confirmed = models.BooleanField(
        default=False,
        verbose_name="E-mail Confirmado",
        help_text="Indica se o usuário confirmou seu e-mail"
    )
    email_confirmation_token = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Token de Confirmação",
        help_text="Token para confirmação de e-mail"
    )
    email_confirmation_sent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Confirmação Enviada em",
        help_text="Data e hora em que o e-mail de confirmação foi enviado"
    )

    # Campos de autenticação em 2 fatores
    # Nota: is_2fa_enabled fica no Client (política do cliente)
    # O otp_secret fica aqui no User (cada usuário tem seu próprio secret)
    otp_secret = models.CharField(
        max_length=32,
        blank=True,
        null=True,
        verbose_name="Chave Secreta OTP",
        help_text="Chave secreta individual para geração de códigos OTP"
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.username or self.email

    def generate_confirmation_token(self):
        """
        Gera um token único para confirmação de e-mail.
        """
        import secrets
        self.email_confirmation_token = secrets.token_urlsafe(32)
        self.save(update_fields=['email_confirmation_token'])
        return self.email_confirmation_token

    def confirm_email(self):
        """
        Confirma o e-mail do usuário e ativa a conta.
        """
        self.email_confirmed = True
        self.is_active = True
        self.email_confirmation_token = None
        self.save(update_fields=['email_confirmed', 'is_active', 'email_confirmation_token'])
