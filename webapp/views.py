"""
Views do WebApp
Dashboard principal e autenticação
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Count
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.response import Response
from rest_framework import status

from whatsapp_connector.models import EvolutionInstance, MessageHistory
from google_calendar.models import GoogleCalendarAuth
from .forms import LoginForm, UserProfileForm, ClientProfileForm, ChangePasswordForm


def login_view(request):
    """
    View de login do sistema com suporte a 2FA.
    """
    if request.user.is_authenticated:
        return redirect('webapp:home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Primeiro, verifica se o usuário existe e se a senha está correta
            from django.contrib.auth import get_user_model
            User = get_user_model()

            try:
                # Tenta encontrar o usuário pelo username ou email
                user_obj = User.objects.get(username=username)
            except User.DoesNotExist:
                try:
                    user_obj = User.objects.get(email=username)
                except User.DoesNotExist:
                    user_obj = None

            # Verifica se o usuário existe e se a senha está correta
            if user_obj and user_obj.check_password(password):
                # Verifica se o email foi confirmado
                if not user_obj.email_confirmed:
                    messages.warning(
                        request,
                        _('Você precisa confirmar seu e-mail antes de fazer login. '
                          'Verifique sua caixa de entrada e siga as instruções no e-mail de confirmação.')
                    )
                    return render(request, 'webapp/login.html', {'form': form})

                # Agora autentica o usuário (só funciona se is_active=True)
                user = authenticate(request, username=username, password=password)

                if user is not None:
                    # Verifica se o cliente exige 2FA (política do cliente)
                    if hasattr(user, 'client') and user.client and user.client.is_2fa_enabled:
                        import logging
                        logger = logging.getLogger(__name__)

                        # Salva o user_id na sessão para a verificação OTP
                        request.session['2fa_user_id'] = user.id
                        request.session.modified = True  # Força salvar a sessão
                        logger.info(f'Login - Saved 2fa_user_id to session: {user.id}')

                        # Envia código OTP por email para o usuário
                        try:
                            user.client.send_otp_email_for_user(user)
                            logger.info(f'Login - OTP email sent to: {user.email}')
                        except Exception as e:
                            logger.error(f'Login - Error sending OTP email: {str(e)}')

                        messages.info(
                            request,
                            _('Um código de verificação foi enviado para seu e-mail.')
                        )
                        return redirect('core:verify_otp')
                    else:
                        # Login normal sem 2FA
                        login(request, user)
                        messages.success(request, f'Bem-vindo, {user.get_full_name() or user.username}!')
                        return redirect('webapp:home')
                else:
                    messages.error(request, 'Sua conta está inativa. Entre em contato com o suporte.')
            else:
                messages.error(request, 'E-mail ou senha inválidos. Tente novamente.')
    else:
        form = LoginForm()

    return render(request, 'webapp/login.html', {'form': form})


@login_required
def logout_view(request):
    """
    View de logout do sistema
    """
    logout(request)
    messages.info(request, 'Você foi desconectado com sucesso.')
    return redirect('webapp:login')


@login_required
def webapp_home(request):
    """
    Dashboard principal com estatísticas e resumo
    """
    # Verifica se o usuário tem perfil de cliente
    if not request.user.client:
        messages.warning(request, 'Você precisa completar seu cadastro de cliente.')
        return redirect('core:register')

    client = request.user.client

    # Estatísticas gerais filtradas por cliente
    total_instances = EvolutionInstance.objects.filter(owner=client).count()
    active_instances = EvolutionInstance.objects.filter(owner=client, is_active=True).count()
    connected_instances = EvolutionInstance.objects.filter(
        owner=client, status='connected', is_active=True
    ).count()

    # Mensagens das últimas 24h filtradas por cliente
    last_24h = timezone.now() - timedelta(hours=24)
    recent_messages = MessageHistory.objects.filter(
        received_at__gte=last_24h,
        owner=client
    ).count()

    # Instâncias por status filtradas por cliente
    status_counts = EvolutionInstance.objects.filter(owner=client).values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # Últimas mensagens filtradas por cliente
    latest_messages = MessageHistory.objects.select_related(
        'chat_session'
    ).filter(
        owner=client
    ).order_by('-received_at')[:10]

    # Associar instâncias às mensagens (agora via relação direta)
    for message in latest_messages:
        if message.chat_session and message.chat_session.evolution_instance:
            message.evolution_instance = message.chat_session.evolution_instance
        else:
            message.evolution_instance = None

    # Instâncias recentes filtradas por cliente
    recent_instances = EvolutionInstance.objects.filter(owner=client).order_by('-created_at')[:5]
    
    context = {
        'total_instances': total_instances,
        'active_instances': active_instances,
        'connected_instances': connected_instances,
        'recent_messages_count': recent_messages,
        'status_counts': status_counts,
        'latest_messages': latest_messages,
        'recent_instances': recent_instances,
    }
    
    return render(request, 'webapp/home.html', context)


# API endpoints para gerenciamento de idioma
@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_available_languages(request):
    """
    Retorna os idiomas disponíveis no sistema
    """
    languages = [{'code': code, 'name': name} for code, name in settings.LANGUAGES]
    current_lang = getattr(request.user, 'preferred_language', settings.LANGUAGE_CODE)
    
    return Response({
        'languages': languages,
        'current': current_lang
    })


@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def set_user_language(request):
    """
    Define o idioma preferido do usuário
    """
    language_code = request.data.get('language')
    
    if not language_code:
        return Response({
            'error': str(_('Código do idioma é obrigatório'))
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Verificar se o idioma está disponível
    available_languages = [code for code, name in settings.LANGUAGES]
    if language_code not in available_languages:
        return Response({
            'error': str(_('Idioma "%(language)s" não disponível. Idiomas disponíveis: %(languages)s') % {
                'language': language_code,
                'languages': ', '.join(available_languages)
            })
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Atualizar preferência do usuário diretamente
    request.user.preferred_language = language_code
    request.user.save(update_fields=['preferred_language'])
    
    # Ativar idioma para esta sessão
    translation.activate(language_code)
    request.session['django_language'] = language_code
    
    return Response({
        'message': str(_('Idioma alterado para %(language)s') % {'language': language_code}),
        'language': language_code
    })


@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_user_language(request):
    """
    Retorna o idioma preferido do usuário atual
    """
    user_language = getattr(request.user, 'preferred_language', settings.LANGUAGE_CODE)
    language_name = dict(settings.LANGUAGES).get(user_language, user_language)

    return Response({
        'language': user_language,
        'language_name': language_name
    })


@login_required
def profile_view(request):
    """
    View de perfil do usuário com abas para dados pessoais, dados do cliente e senha.
    """
    if not request.user.client:
        messages.warning(request, 'Você precisa completar seu cadastro de cliente.')
        return redirect('core:register')

    # Determina qual aba está ativa
    active_tab = request.GET.get('tab', 'user')

    # Processa formulários
    if request.method == 'POST':
        if 'update_user' in request.POST:
            user_form = UserProfileForm(request.POST, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, 'Dados pessoais atualizados com sucesso!')
                return redirect('webapp:profile')
            active_tab = 'user'

        elif 'update_client' in request.POST:
            client_form = ClientProfileForm(request.POST, instance=request.user.client)
            if client_form.is_valid():
                client_form.save()
                messages.success(request, 'Dados do cliente atualizados com sucesso!')
                return redirect('webapp:profile?tab=client')
            active_tab = 'client'

        elif 'change_password' in request.POST:
            password_form = ChangePasswordForm(request.POST)
            if password_form.is_valid():
                current_password = password_form.cleaned_data['current_password']
                new_password = password_form.cleaned_data['new_password']

                if not request.user.check_password(current_password):
                    messages.error(request, 'Senha atual incorreta.')
                else:
                    request.user.set_password(new_password)
                    request.user.save()
                    # Atualiza a sessão para não fazer logout
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request, request.user)
                    messages.success(request, 'Senha alterada com sucesso!')
                    return redirect('webapp:profile?tab=password')
            active_tab = 'password'

    # Cria instâncias dos formulários
    user_form = UserProfileForm(instance=request.user)
    client_form = ClientProfileForm(instance=request.user.client)
    password_form = ChangePasswordForm()

    # Verifica status da conexão do Google Calendar
    google_calendar_connected = False
    google_calendar_auth = None
    try:
        google_calendar_auth = GoogleCalendarAuth.objects.get(user=request.user)
        google_calendar_connected = True
    except GoogleCalendarAuth.DoesNotExist:
        pass

    # Verifica se há mensagens na sessão do Google Calendar
    if 'google_calendar_success' in request.session:
        messages.success(request, request.session.pop('google_calendar_success'))
        active_tab = 'integrations'
    if 'google_calendar_error' in request.session:
        messages.error(request, request.session.pop('google_calendar_error'))
        active_tab = 'integrations'

    context = {
        'user_form': user_form,
        'client_form': client_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'google_calendar_connected': google_calendar_connected,
        'google_calendar_auth': google_calendar_auth,
    }

    return render(request, 'webapp/profile.html', context)