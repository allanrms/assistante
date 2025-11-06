from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.translation import gettext_lazy as _
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView
from django.db import transaction
from rest_framework import status, generics, viewsets, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter
from .models import Client, Service, ServiceAvailability
from .serializers import (
    ClientRegistrationSerializer,
    ClientSerializer,
    EmailConfirmationSerializer,
)
from .forms import ClientRegistrationForm, OTPVerificationForm


class ClientRegistrationView(generics.CreateAPIView):
    """
    API endpoint para registro de novos clientes.

    Cria uma nova conta de cliente, gera token de confirmação
    e envia e-mail de confirmação.
    """
    serializer_class = ClientRegistrationSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        request=ClientRegistrationSerializer,
        responses={
            201: OpenApiResponse(
                response=ClientSerializer,
                description='Cliente criado com sucesso. E-mail de confirmação enviado.'
            ),
            400: OpenApiResponse(description='Dados inválidos'),
        },
        summary='Registrar novo cliente',
        description='Cria uma nova conta de cliente e envia e-mail de confirmação.',
        tags=['Clientes']
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    # Cria o cliente
                    client = serializer.save()

                    # Gera token de confirmação
                    token = client.generate_confirmation_token()
                    client.email_confirmation_sent_at = timezone.now()
                    client.save()

                # Tenta enviar e-mail (fora da transação para não desfazer o cadastro se falhar)
                email_sent = True
                try:
                    self.send_confirmation_email(client, token)
                except Exception as email_error:
                    email_sent = False
                    import logging
                    logging.error(f'Erro ao enviar email de confirmação: {str(email_error)}')

                # Retorna dados do cliente criado
                response_serializer = ClientSerializer(client)
                message = 'Cliente cadastrado com sucesso. Verifique seu e-mail para confirmar a conta.'
                if not email_sent:
                    message = 'Cliente cadastrado, mas houve erro ao enviar email de confirmação. Entre em contato com o suporte.'

                return Response(
                    {
                        'message': message,
                        'client': response_serializer.data,
                        'email_sent': email_sent
                    },
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                # Se o erro ocorrer na criação do cliente, rollback é automático
                return Response(
                    {'error': f'Erro ao criar cliente: {str(e)}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_confirmation_email(self, client, token):
        """
        Envia e-mail de confirmação para o cliente.
        """
        confirmation_url = f"{settings.SITE_URL}/api/clients/confirm-email/?token={token}"

        subject = 'Confirme seu e-mail - Assistante'

        # Contexto para o template
        context = {
            'client_name': client.full_name,
            'confirmation_url': confirmation_url,
            'site_url': settings.SITE_URL,
        }

        # Renderiza o template HTML (se houver)
        # html_message = render_to_string('emails/confirmation_email.html', context)
        # plain_message = strip_tags(html_message)

        # Por enquanto, mensagem simples de texto
        plain_message = f"""
Olá {client.full_name},

Obrigado por se cadastrar no Assistante!

Para confirmar seu e-mail e ativar sua conta, clique no link abaixo:

{confirmation_url}

Se você não se cadastrou no Assistante, ignore este e-mail.

Atenciosamente,
Equipe Assistante
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[client.email],
            fail_silently=False,
        )


class EmailConfirmationView(APIView):
    """
    API endpoint para confirmação de e-mail.

    Confirma o e-mail do cliente usando o token enviado por e-mail.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        request=EmailConfirmationSerializer,
        responses={
            200: OpenApiResponse(
                description='E-mail confirmado com sucesso.'
            ),
            400: OpenApiResponse(description='Token inválido ou expirado'),
        },
        summary='Confirmar e-mail',
        description='Confirma o e-mail do cliente usando o token de confirmação.',
        tags=['Clientes']
    )
    def post(self, request):
        serializer = EmailConfirmationSerializer(data=request.data)

        if serializer.is_valid():
            token = serializer.validated_data['token']

            try:
                client = Client.objects.get(email_confirmation_token=token)
                client.confirm_email()

                return Response(
                    {
                        'message': 'E-mail confirmado com sucesso! Você já pode fazer login.',
                        'email': client.email,
                    },
                    status=status.HTTP_200_OK
                )
            except Client.DoesNotExist:
                return Response(
                    {'error': 'Token inválido ou expirado.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        parameters=[
            {
                'name': 'token',
                'in': 'query',
                'required': True,
                'schema': {'type': 'string'},
                'description': 'Token de confirmação enviado por e-mail'
            }
        ],
        responses={
            200: OpenApiResponse(description='E-mail confirmado com sucesso.'),
            400: OpenApiResponse(description='Token inválido ou expirado'),
        },
        summary='Confirmar e-mail via GET',
        description='Confirma o e-mail do cliente usando o token da URL (para links clicáveis).',
        tags=['Clientes']
    )
    def get(self, request):
        """
        Permite confirmação via GET para links clicáveis em e-mails.
        """
        token = request.query_params.get('token')

        if not token:
            return Response(
                {'error': 'Token não fornecido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            client = Client.objects.get(email_confirmation_token=token)

            if client.email_confirmed:
                return Response(
                    {'message': 'Este e-mail já foi confirmado anteriormente.'},
                    status=status.HTTP_200_OK
                )

            client.confirm_email()

            return Response(
                {
                    'message': 'E-mail confirmado com sucesso! Você já pode fazer login.',
                    'email': client.email,
                },
                status=status.HTTP_200_OK
            )
        except Client.DoesNotExist:
            return Response(
                {'error': 'Token inválido ou expirado.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class ClientDetailView(generics.RetrieveUpdateAPIView):
    """
    API endpoint para visualizar e atualizar dados do cliente.
    """
    serializer_class = ClientSerializer
    queryset = Client.objects.all()

    @extend_schema(
        responses={
            200: ClientSerializer,
            404: OpenApiResponse(description='Cliente não encontrado'),
        },
        summary='Obter detalhes do cliente',
        description='Retorna os dados de um cliente específico.',
        tags=['Clientes']
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=ClientSerializer,
        responses={
            200: ClientSerializer,
            400: OpenApiResponse(description='Dados inválidos'),
            404: OpenApiResponse(description='Cliente não encontrado'),
        },
        summary='Atualizar dados do cliente',
        description='Atualiza os dados de um cliente específico.',
        tags=['Clientes']
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @extend_schema(
        request=ClientSerializer,
        responses={
            200: ClientSerializer,
            400: OpenApiResponse(description='Dados inválidos'),
            404: OpenApiResponse(description='Cliente não encontrado'),
        },
        summary='Atualizar parcialmente dados do cliente',
        description='Atualiza parcialmente os dados de um cliente específico.',
        tags=['Clientes']
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


# ========== Views baseadas em templates (Class-Based Views) ==========


class ClientRegisterView(CreateView):
    """
    View de registro de cliente usando templates Django.
    Utiliza Class-Based View para seguir o padrão do projeto.
    """
    model = Client
    form_class = ClientRegistrationForm
    template_name = 'core/register.html'
    success_url = reverse_lazy('client_painel:login')

    def dispatch(self, request, *args, **kwargs):
        """
        Redireciona usuários autenticados para a home.
        """
        if request.user.is_authenticated:
            messages.info(request, _('Você já está logado.'))
            return redirect('client_painel:home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """
        Chamado quando o formulário é válido.
        Cria o cliente e usuário, gera token e envia email.
        """
        try:
            with transaction.atomic():
                # Cria o cliente e usuário (form.save retorna o user)
                user = form.save()

                # Gera token de confirmação no usuário
                token = user.generate_confirmation_token()
                user.email_confirmation_sent_at = timezone.now()
                user.save()

            # Tenta enviar e-mail (fora da transação para não desfazer o cadastro se falhar)
            try:
                self._send_confirmation_email(user, token)
                messages.success(
                    self.request,
                    _('Cadastro realizado com sucesso! Verifique seu e-mail para confirmar a conta.')
                )
            except Exception as email_error:
                # Cadastro foi salvo, mas email falhou
                messages.warning(
                    self.request,
                    _('Cadastro realizado, mas houve erro ao enviar email de confirmação. '
                      'Entre em contato com o suporte.')
                )
                # Log do erro para debug
                import logging
                logging.error(f'Erro ao enviar email de confirmação: {str(email_error)}')

            return redirect(self.success_url)

        except Exception as e:
            # Se o erro ocorrer na criação do usuário, rollback é automático
            messages.error(self.request, f'Erro ao criar conta: {str(e)}')
            return self.form_invalid(form)

    def _send_confirmation_email(self, user, token):
        """
        Envia e-mail de confirmação para o usuário.
        """
        confirmation_url = f"{settings.SITE_URL}cadastro/confirmar-email/{token}/"

        subject = 'Confirme seu e-mail - Assistante'

        # Mensagem de texto
        plain_message = f"""
Olá {user.get_full_name() or user.username},

Obrigado por se cadastrar no Assistante!

Para confirmar seu e-mail e ativar sua conta, clique no link abaixo:

{confirmation_url}

Se você não se cadastrou no Assistante, ignore este e-mail.

Atenciosamente,
Equipe Assistante
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )


class ConfirmEmailView(View):
    """
    View de confirmação de e-mail.
    Aceita token via URL ou GET parameter.
    """

    def get(self, request, token=None):
        """
        Processa a confirmação de e-mail via GET.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Tenta pegar o token da URL ou do parâmetro GET
        if not token:
            token = request.GET.get('token')

        if not token:
            messages.error(request, _('Token de confirmação não fornecido.'))
            return redirect('client_painel:login')

        try:
            user = User.objects.get(email_confirmation_token=token)

            if user.email_confirmed:
                messages.info(
                    request,
                    _('Este e-mail já foi confirmado anteriormente. Você já pode fazer login.')
                )
            else:
                user.confirm_email()
                messages.success(
                    request,
                    _('E-mail confirmado com sucesso! Você já pode fazer login.')
                )

        except User.DoesNotExist:
            messages.error(request, _('Token inválido ou expirado.'))

        return redirect('client_painel:login')


# ========== 2FA Views ==========


@login_required
def enable_2fa_view(request):
    """
    View para habilitar 2FA.
    """
    client = request.user.client

    if client.is_2fa_enabled:
        messages.info(request, _('A autenticação em 2 fatores já está habilitada.'))
        return redirect('client_painel:profile')

    if request.method == 'POST':
        # Habilita 2FA (política do cliente)
        client.enable_2fa()

        # Envia código OTP por email para o usuário logado
        client.send_otp_email_for_user(request.user)

        messages.success(
            request,
            _('Autenticação em 2 fatores habilitada! Um código de verificação foi enviado para seu e-mail.')
        )
        return redirect('client_painel:profile')

    return render(request, 'core/enable_2fa.html', {'client': client})


@login_required
def disable_2fa_view(request):
    """
    View para desabilitar 2FA com confirmação.
    """
    client = request.user.client

    if not client.is_2fa_enabled:
        messages.info(request, _('A autenticação em 2 fatores já está desabilitada.'))
        return redirect('client_painel:profile')

    if request.method == 'POST':
        if request.POST.get('confirm') == 'yes':
            # Desabilita 2FA
            client.disable_2fa()

            messages.success(
                request,
                _('Autenticação em 2 fatores desabilitada com sucesso.')
            )
            return redirect('client_painel:profile')

    return render(request, 'core/disable_2fa.html', {'client': client})


def verify_otp_view(request):
    """
    View para verificar código OTP durante o login.
    """
    import logging
    from django.contrib.auth import get_user_model
    logger = logging.getLogger(__name__)
    User = get_user_model()

    # Verifica se há um user_id na sessão (setado durante o login)
    user_id = request.session.get('2fa_user_id')
    logger.info(f'verify_otp_view - user_id from session: {user_id}')

    if not user_id:
        logger.warning('verify_otp_view - No user_id in session')
        messages.error(request, _('Sessão inválida. Por favor, faça login novamente.'))
        return redirect('client_painel:login')

    try:
        user = User.objects.get(id=user_id)
        logger.info(f'verify_otp_view - User found: {user.email}')
    except User.DoesNotExist:
        logger.error(f'verify_otp_view - User not found: {user_id}')
        messages.error(request, _('Usuário não encontrado.'))
        return redirect('client_painel:login')
    except Exception as e:
        logger.error(f'verify_otp_view - Exception: {str(e)}')
        messages.error(request, f'Erro ao buscar usuário: {str(e)}')
        return redirect('client_painel:login')

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)

        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']

            # Verifica o código OTP usando o método do cliente com o usuário
            if user.client and user.client.verify_otp_for_user(user, otp_code):
                # Código válido - completa o login
                from django.contrib.auth import login

                login(request, user)

                # Remove dados da sessão 2FA
                del request.session['2fa_user_id']

                messages.success(request, _('Login realizado com sucesso!'))
                return redirect('client_painel:home')
            else:
                messages.error(request, _('Código inválido ou expirado.'))
    else:
        form = OTPVerificationForm()

    logger.info(f'verify_otp_view - Rendering template with user: {user.email}')

    return render(request, 'core/verify_otp.html', {
        'form': form,
        'user': user
    })


def resend_otp_view(request):
    """
    View para reenviar código OTP.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    user_id = request.session.get('2fa_user_id')

    if not user_id:
        messages.error(request, _('Sessão inválida.'))
        return redirect('client_painel:login')

    try:
        user = User.objects.get(id=user_id)
        if user.client:
            user.client.send_otp_email_for_user(user)
            messages.success(request, _('Novo código enviado para seu e-mail.'))
        else:
            messages.error(request, _('Usuário não está vinculado a nenhum cliente.'))
            return redirect('client_painel:login')
    except User.DoesNotExist:
        messages.error(request, _('Usuário não encontrado.'))
        return redirect('client_painel:login')

    return redirect('core:verify_otp')
