from django.urls import path
from .views import (
    ClientRegistrationView,
    EmailConfirmationView,
    ClientDetailView,
    ClientRegisterView,
    ConfirmEmailView,
    enable_2fa_view,
    disable_2fa_view,
    verify_otp_view,
    resend_otp_view,
)

app_name = 'core'

urlpatterns = [
    # ========== Views baseadas em templates (Web) - Class-Based Views ==========
    # Registro de cliente via template
    path('cadastro/', ClientRegisterView.as_view(), name='register'),

    # Confirmação de e-mail via template
    path('cadastro/confirmar-email/<str:token>/', ConfirmEmailView.as_view(), name='confirm-email'),

    # ========== 2FA URLs ==========
    # Habilitar/Desabilitar 2FA
    path('security/2fa/enable/', enable_2fa_view, name='enable_2fa'),
    path('security/2fa/disable/', disable_2fa_view, name='disable_2fa'),

    # Verificação OTP durante login
    path('verify-otp/', verify_otp_view, name='verify_otp'),
    path('resend-otp/', resend_otp_view, name='resend_otp'),

    # ========== API endpoints (REST) ==========
    # Registro de cliente via API
    path('clients/register/', ClientRegistrationView.as_view(), name='client-register'),

    # Confirmação de e-mail via API
    path('clients/confirm-email/', EmailConfirmationView.as_view(), name='email-confirm-api'),

    # Detalhes do cliente via API
    path('clients/<uuid:pk>/', ClientDetailView.as_view(), name='client-detail'),
]
