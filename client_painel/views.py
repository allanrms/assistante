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
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.response import Response
from rest_framework import status

from whatsapp_connector.models import EvolutionInstance, MessageHistory
from google_calendar.models import GoogleCalendarAuth
from core.models import Appointment, Contact, ScheduleConfig, WorkingDay, BlockedDay, Service, ServiceAvailability
from core.forms import ServiceForm, ServiceAvailabilityFormSet
from .forms import (
    LoginForm, UserProfileForm, ClientProfileForm, ChangePasswordForm,
    AppointmentForm, ScheduleConfigForm, WorkingDayFormSet, BlockedDayFormSet
)
from django.http import JsonResponse
from django.shortcuts import get_object_or_404


def login_view(request):
    """
    View de login do sistema com suporte a 2FA.
    """
    if request.user.is_authenticated:
        return redirect('client_painel:home')

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
                    return render(request, 'client_painel/login.html', {'form': form})

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
                        return redirect('client_painel:home')
                else:
                    messages.error(request, 'Sua conta está inativa. Entre em contato com o suporte.')
            else:
                messages.error(request, 'E-mail ou senha inválidos. Tente novamente.')
    else:
        form = LoginForm()

    return render(request, 'client_painel/login.html', {'form': form})


@login_required
def logout_view(request):
    """
    View de logout do sistema
    """
    logout(request)
    messages.info(request, 'Você foi desconectado com sucesso.')
    return redirect('client_painel:login')


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
    
    return render(request, 'client_painel/home.html', context)


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
                return redirect('client_painel:profile')
            active_tab = 'user'

        elif 'update_client' in request.POST:
            client_form = ClientProfileForm(request.POST, instance=request.user.client)
            if client_form.is_valid():
                client_form.save()
                messages.success(request, 'Dados do cliente atualizados com sucesso!')
                return redirect('client_painel:profile?tab=client')
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
                    return redirect('client_painel:profile?tab=password')
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

    return render(request, 'client_painel/profile.html', context)


class AgendaView(LoginRequiredMixin, View):
    """
    View da página de Agenda com visualização semanal
    """
    login_url = 'client_painel:login'

    def get(self, request):
        if not request.user.client:
            messages.warning(request, 'Você precisa completar seu cadastro de cliente.')
            return redirect('core:register')

        client = request.user.client

        # Busca Appointments da semana atual (filtrados por cliente através dos contatos)
        # Obter semana atual (Domingo = 0, Segunda = 1, ...)
        today = timezone.now().date()

        # Suporta 3 modos de visualização:
        # 1. Intervalo customizado via start_date e end_date
        # 2. Navegação de semanas via week_offset
        # 3. Semana atual (padrão)

        start_date_param = request.GET.get('start_date')
        end_date_param = request.GET.get('end_date')

        if start_date_param and end_date_param:
            # Modo 1: Intervalo customizado
            try:
                from datetime import datetime
                start_of_week = datetime.strptime(start_date_param, '%Y-%m-%d').date()
                end_of_week = datetime.strptime(end_date_param, '%Y-%m-%d').date()

                # Para manter o grid de 7 dias, ajustamos o end_of_week para ser sempre 6 dias após o start
                # Mas vamos buscar appointments no intervalo real selecionado
                # O grid sempre mostrará 7 dias começando pelo start_of_week
                week_offset = None  # Não aplicável neste modo
            except ValueError:
                # Se as datas forem inválidas, volta para semana atual
                days_since_sunday = (today.weekday() + 1) % 7
                start_of_week = today - timedelta(days=days_since_sunday)
                end_of_week = start_of_week + timedelta(days=6)
                week_offset = 0
        else:
            # Modo 2 ou 3: week_offset ou semana atual
            week_offset = int(request.GET.get('week_offset', 0))

            # Calcular início da semana (Domingo) com offset
            days_since_sunday = (today.weekday() + 1) % 7
            start_of_week = today - timedelta(days=days_since_sunday) + timedelta(weeks=week_offset)
            end_of_week = start_of_week + timedelta(days=6)

        # Verifica se está na visualização mensal para buscar appointments do mês inteiro
        view_param = request.GET.get('view')
        if view_param == 'mes' or (start_date_param and end_date_param and (end_of_week - start_of_week).days > 7):
            # Se for visualização mensal, busca o mês completo incluindo dias do mês anterior/posterior
            # que aparecem no calendário (até 42 dias = 6 semanas)
            first_day_of_month = start_of_week.replace(day=1)
            last_day_of_month = (first_day_of_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

            # Calcula o início do grid (pode incluir dias do mês anterior)
            start_of_grid = first_day_of_month - timedelta(days=first_day_of_month.weekday() + 1 if first_day_of_month.weekday() != 6 else 0)
            # Calcula o fim do grid (pode incluir dias do mês seguinte)
            end_of_grid = start_of_grid + timedelta(days=41)

            appointments_week = Appointment.objects.filter(
                contact__client=client,
                date__gte=start_of_grid,
                date__lte=end_of_grid
            ).select_related('contact').order_by('date', 'time')
        else:
            # Busca appointments da semana para o calendário
            appointments_week = Appointment.objects.filter(
                contact__client=client,
                date__gte=start_of_week,
                date__lte=end_of_week
            ).select_related('contact').order_by('date', 'time')

        # Busca appointments do dia para a sidebar "Pacientes do dia"
        appointments_today = Appointment.objects.filter(
            contact__client=client,
            date=today
        ).select_related('contact').order_by('time')

        # Serializa appointments para JSON (para uso no JavaScript)
        import json
        appointments_data = []
        for appointment in appointments_week:
            # Calcula o dia da semana: 0=Domingo, 1=Segunda, ..., 6=Sábado
            # Python weekday() retorna 0=Segunda, mas precisamos 0=Domingo para o grid
            weekday = (appointment.date.weekday() + 1) % 7

            appointments_data.append({
                'id': appointment.id,  # ID como int (não precisa converter para string)
                'contact_name': appointment.contact.name or appointment.contact.phone_number,
                'date': appointment.date.isoformat(),
                'time': appointment.time.strftime('%H:%M'),
                'weekday': weekday,  # Dia da semana calculado no backend
                'scheduled_for': appointment.scheduled_for.isoformat() if appointment.scheduled_for else None,
            })

        # Busca todos os contatos do cliente para o select do modal
        contacts = Contact.objects.filter(client=client).order_by('name')

        context = {
            'appointments_week': appointments_week,
            'appointments_today': appointments_today,
            'appointments_json': json.dumps(appointments_data),
            'contacts': contacts,
            'start_of_week': start_of_week,
            'end_of_week': end_of_week,
            'today': today,
            'week_offset': week_offset,
        }

        return render(request, 'client_painel/agenda.html', context)


class AppointmentCreateView(LoginRequiredMixin, View):
    """
    View para criar um novo appointment
    """
    login_url = 'client_painel:login'

    def post(self, request):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        client = request.user.client
        form = AppointmentForm(request.POST, client=client)

        if form.is_valid():
            appointment = form.save(commit=False)

            # Define scheduled_for baseado em date e time
            from datetime import datetime
            appointment.scheduled_for = datetime.combine(
                appointment.date,
                appointment.time
            )

            # Validar disponibilidade do horário
            validation_error = self._validate_appointment_availability(client, appointment.date, appointment.time)
            if validation_error:
                return JsonResponse({'error': validation_error}, status=400)

            appointment.save()

            return JsonResponse({
                'success': True,
                'appointment': {
                    'id': appointment.id,  # ID como int
                    'contact_name': appointment.contact.name or appointment.contact.phone_number,
                    'date': appointment.date.isoformat(),
                    'time': appointment.time.strftime('%H:%M'),
                    'weekday': (appointment.date.weekday() + 1) % 7
                }
            })
        else:
            return JsonResponse({
                'error': 'Erro ao criar consulta',
                'errors': form.errors
            }, status=400)

    def _validate_appointment_availability(self, client, date, time):
        """
        Valida se o horário está disponível para agendamento.
        Retorna mensagem de erro se não estiver disponível, None caso contrário.
        """
        # Busca configuração da agenda
        try:
            schedule_config = ScheduleConfig.objects.get(client=client)
        except ScheduleConfig.DoesNotExist:
            return None  # Se não há configuração, permite agendar

        # 1. Verifica se o dia está bloqueado
        if schedule_config.blocked_days.filter(date=date).exists():
            blocked_day = schedule_config.blocked_days.get(date=date)
            reason = blocked_day.reason or 'sem motivo especificado'
            return f'Este dia está bloqueado para agendamentos ({reason}).'

        # 2. Verifica se o dia da semana está ativo
        # Python weekday: 0=Monday, 6=Sunday
        # WorkingDay weekday: 0=Monday, 6=Sunday
        weekday = date.weekday()

        try:
            working_day = schedule_config.working_days.get(weekday=weekday)
        except WorkingDay.DoesNotExist:
            return 'Não há configuração de atendimento para este dia da semana.'

        if not working_day.is_active:
            return 'Não há atendimento neste dia da semana.'

        # 3. Verifica se está no horário de almoço
        if working_day.lunch_start_time and working_day.lunch_end_time:
            if working_day.lunch_start_time <= time < working_day.lunch_end_time:
                return 'Este horário corresponde ao intervalo de almoço.'

        # 4. Verifica se está dentro do horário de expediente
        if time < working_day.start_time or time >= working_day.end_time:
            return f'Este horário está fora do expediente ({working_day.start_time.strftime("%H:%M")} - {working_day.end_time.strftime("%H:%M")}).'

        # 5. Verifica se o horário está na lista de horários disponíveis
        available_times = working_day.get_available_times(date)
        time_str = time.strftime('%H:%M')
        available_times_str = [t.strftime('%H:%M') for t in available_times]

        if time_str not in available_times_str:
            return 'Este horário não está disponível para agendamentos.'

        return None  # Horário disponível


class AppointmentUpdateView(LoginRequiredMixin, View):
    """
    View para editar um appointment existente
    """
    login_url = 'client_painel:login'

    def get(self, request, appointment_id):
        """Retorna os dados do appointment para edição"""
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        try:
            appointment = Appointment.objects.select_related('contact').get(
                id=appointment_id,
                contact__client=request.user.client
            )

            return JsonResponse({
                'id': appointment.id,  # ID como int
                'contact_id': str(appointment.contact.id),  # UUID do contact mantém como string
                'contact_name': appointment.contact.name or appointment.contact.phone_number,
                'date': appointment.date.isoformat(),
                'time': appointment.time.strftime('%H:%M'),
            })
        except Appointment.DoesNotExist:
            return JsonResponse({'error': 'Consulta não encontrada'}, status=404)

    def post(self, request, appointment_id):
        """Atualiza o appointment"""
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        try:
            appointment = Appointment.objects.get(
                id=appointment_id,
                contact__client=request.user.client
            )

            form = AppointmentForm(request.POST, instance=appointment, client=request.user.client)

            if form.is_valid():
                appointment = form.save(commit=False)

                # Atualiza scheduled_for
                from datetime import datetime
                appointment.scheduled_for = datetime.combine(
                    appointment.date,
                    appointment.time
                )

                # Validar disponibilidade do horário
                validation_error = self._validate_appointment_availability(
                    request.user.client,
                    appointment.date,
                    appointment.time
                )
                if validation_error:
                    return JsonResponse({'error': validation_error}, status=400)

                appointment.save()

                return JsonResponse({
                    'success': True,
                    'appointment': {
                        'id': appointment.id,  # ID como int
                        'contact_name': appointment.contact.name or appointment.contact.phone_number,
                        'date': appointment.date.isoformat(),
                        'time': appointment.time.strftime('%H:%M'),
                        'weekday': (appointment.date.weekday() + 1) % 7
                    }
                })
            else:
                return JsonResponse({
                    'error': 'Erro ao atualizar consulta',
                    'errors': form.errors
                }, status=400)

        except Appointment.DoesNotExist:
            return JsonResponse({'error': 'Consulta não encontrada'}, status=404)

    def _validate_appointment_availability(self, client, date, time):
        """
        Valida se o horário está disponível para agendamento.
        Retorna mensagem de erro se não estiver disponível, None caso contrário.
        """
        # Busca configuração da agenda
        try:
            schedule_config = ScheduleConfig.objects.get(client=client)
        except ScheduleConfig.DoesNotExist:
            return None  # Se não há configuração, permite agendar

        # 1. Verifica se o dia está bloqueado
        if schedule_config.blocked_days.filter(date=date).exists():
            blocked_day = schedule_config.blocked_days.get(date=date)
            reason = blocked_day.reason or 'sem motivo especificado'
            return f'Este dia está bloqueado para agendamentos ({reason}).'

        # 2. Verifica se o dia da semana está ativo
        # Python weekday: 0=Monday, 6=Sunday
        # WorkingDay weekday: 0=Monday, 6=Sunday
        weekday = date.weekday()

        try:
            working_day = schedule_config.working_days.get(weekday=weekday)
        except WorkingDay.DoesNotExist:
            return 'Não há configuração de atendimento para este dia da semana.'

        if not working_day.is_active:
            return 'Não há atendimento neste dia da semana.'

        # 3. Verifica se está no horário de almoço
        if working_day.lunch_start_time and working_day.lunch_end_time:
            if working_day.lunch_start_time <= time < working_day.lunch_end_time:
                return 'Este horário corresponde ao intervalo de almoço.'

        # 4. Verifica se está dentro do horário de expediente
        if time < working_day.start_time or time >= working_day.end_time:
            return f'Este horário está fora do expediente ({working_day.start_time.strftime("%H:%M")} - {working_day.end_time.strftime("%H:%M")}).'

        # 5. Verifica se o horário está na lista de horários disponíveis
        available_times = working_day.get_available_times(date)
        time_str = time.strftime('%H:%M')
        available_times_str = [t.strftime('%H:%M') for t in available_times]

        if time_str not in available_times_str:
            return 'Este horário não está disponível para agendamentos.'

        return None  # Horário disponível


class AppointmentDeleteView(LoginRequiredMixin, View):
    """
    View para deletar um appointment
    """
    login_url = 'client_painel:login'

    def post(self, request, appointment_id):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        try:
            appointment = Appointment.objects.get(
                id=appointment_id,
                contact__client=request.user.client
            )

            appointment.delete()

            return JsonResponse({'success': True})

        except Appointment.DoesNotExist:
            return JsonResponse({'error': 'Consulta não encontrada'}, status=404)


class ScheduleSettingsView(LoginRequiredMixin, View):
    """
    View para configuração da agenda (horários, dias bloqueados, etc).
    """
    login_url = 'client_painel:login'

    def get(self, request):
        if not request.user.client:
            messages.warning(request, 'Você precisa completar seu cadastro de cliente.')
            return redirect('core:register')

        client = request.user.client

        # Busca ou cria a configuração da agenda do cliente
        schedule_config, created = ScheduleConfig.objects.get_or_create(
            client=client,
            defaults={'appointment_duration': 60}
        )

        # Se foi criado, vamos criar os 7 dias da semana com configurações padrão
        if created:
            # Segunda a Sexta: 08:00-18:00 com almoço 12:00-13:00
            for weekday in range(5):  # 0-4 (Seg-Sex)
                WorkingDay.objects.create(
                    schedule_config=schedule_config,
                    weekday=weekday,
                    is_active=True,
                    start_time='08:00',
                    end_time='18:00',
                    lunch_start_time='12:00',
                    lunch_end_time='13:00'
                )
            # Sábado: 08:00-12:00 sem almoço
            WorkingDay.objects.create(
                schedule_config=schedule_config,
                weekday=5,
                is_active=False,
                start_time='08:00',
                end_time='12:00'
            )
            # Domingo: desativado
            WorkingDay.objects.create(
                schedule_config=schedule_config,
                weekday=6,
                is_active=False,
                start_time='08:00',
                end_time='12:00'
            )

        # Formulário de configuração principal
        config_form = ScheduleConfigForm(instance=schedule_config)

        # Formsets para dias de trabalho e dias bloqueados
        working_days_formset = WorkingDayFormSet(
            instance=schedule_config,
            queryset=schedule_config.working_days.all().order_by('weekday')
        )
        blocked_days_formset = BlockedDayFormSet(
            instance=schedule_config,
            queryset=schedule_config.blocked_days.all().order_by('-date')
        )

        context = {
            'config_form': config_form,
            'working_days_formset': working_days_formset,
            'blocked_days_formset': blocked_days_formset,
            'schedule_config': schedule_config,
        }

        return render(request, 'client_painel/schedule_settings.html', context)

    def post(self, request):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        client = request.user.client

        # Busca a configuração existente
        try:
            schedule_config = ScheduleConfig.objects.get(client=client)
        except ScheduleConfig.DoesNotExist:
            return JsonResponse({'error': 'Configuração não encontrada'}, status=404)

        # Processa os formulários
        config_form = ScheduleConfigForm(request.POST, instance=schedule_config)
        working_days_formset = WorkingDayFormSet(
            request.POST,
            instance=schedule_config
        )
        blocked_days_formset = BlockedDayFormSet(
            request.POST,
            instance=schedule_config
        )

        if config_form.is_valid() and working_days_formset.is_valid() and blocked_days_formset.is_valid():
            # Salva a configuração principal
            config_form.save()

            # Salva os dias de trabalho
            working_days_formset.save()

            # Salva os dias bloqueados
            blocked_days_formset.save()

            messages.success(request, 'Configurações da agenda atualizadas com sucesso!')
            return redirect('client_painel:schedule_settings')
        else:
            # Retorna para a página com os erros
            messages.error(request, 'Erro ao salvar configurações. Verifique os campos.')

            context = {
                'config_form': config_form,
                'working_days_formset': working_days_formset,
                'blocked_days_formset': blocked_days_formset,
                'schedule_config': schedule_config,
            }

            return render(request, 'client_painel/schedule_settings.html', context)


class ScheduleAvailabilityView(LoginRequiredMixin, View):
    """
    API endpoint to get schedule availability configuration (working days, blocked days, etc).
    """
    login_url = 'client_painel:login'

    def get(self, request):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        client = request.user.client

        # Get or create schedule config
        schedule_config, _ = ScheduleConfig.objects.get_or_create(
            client=client,
            defaults={'appointment_duration': 60}
        )

        # Get working days
        working_days = {}
        for working_day in schedule_config.working_days.all():
            working_days[working_day.weekday] = {
                'is_active': working_day.is_active,
                'start_time': working_day.start_time.strftime('%H:%M') if working_day.start_time else None,
                'end_time': working_day.end_time.strftime('%H:%M') if working_day.end_time else None,
                'lunch_start_time': working_day.lunch_start_time.strftime('%H:%M') if working_day.lunch_start_time else None,
                'lunch_end_time': working_day.lunch_end_time.strftime('%H:%M') if working_day.lunch_end_time else None,
                'available_times': [t.strftime('%H:%M') for t in working_day.get_available_times()]
            }

        # Get blocked days
        blocked_days = []
        for blocked_day in schedule_config.blocked_days.all():
            blocked_days.append({
                'date': blocked_day.date.isoformat(),
                'reason': blocked_day.reason
            })

        return JsonResponse({
            'appointment_duration': schedule_config.appointment_duration,
            'working_days': working_days,
            'blocked_days': blocked_days
        })


# ===== CRUD de Serviços =====

class ServiceListView(LoginRequiredMixin, ListView):
    """
    View para listar serviços do cliente usando django.views.generic.ListView
    """
    model = Service
    template_name = 'client_painel/services/list.html'
    context_object_name = 'services'
    login_url = 'client_painel:login'

    def get_queryset(self):
        if not self.request.user.client:
            return Service.objects.none()
        return Service.objects.filter(
            client=self.request.user.client
        ).prefetch_related('availabilities').order_by('name')

    def get_context_data(self, **kwargs):
        """Adiciona dados processados ao contexto"""
        context = super().get_context_data(**kwargs)

        # Processa availabilities para agrupar por dia da semana
        for service in context['services']:
            grouped = {}
            for avail in service.availabilities.filter(is_active=True).order_by('weekday', 'start_time'):
                weekday_name = avail.get_weekday_display()
                if weekday_name not in grouped:
                    grouped[weekday_name] = []
                grouped[weekday_name].append(avail)
            service.grouped_availabilities = grouped

        return context

    def dispatch(self, request, *args, **kwargs):
        if not request.user.client:
            messages.warning(request, 'Você precisa completar seu cadastro de cliente.')
            return redirect('core:register')
        return super().dispatch(request, *args, **kwargs)


class ServiceCreateView(LoginRequiredMixin, View):
    """
    View para criar um novo serviço usando django.views.generic
    """
    login_url = 'client_painel:login'

    def post(self, request):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        client = request.user.client
        form = ServiceForm(request.POST, client=client)
        formset = ServiceAvailabilityFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            service = form.save()
            formset.instance = service
            formset.save()

            messages.success(request, 'Serviço criado com sucesso!')
            return JsonResponse({
                'success': True,
                'redirect': reverse_lazy('client_painel:service_list')
            })
        else:
            errors = {}
            if form.errors:
                errors['form'] = form.errors
            if formset.errors:
                errors['formset'] = formset.errors
            if formset.non_form_errors():
                errors['formset_non_form'] = formset.non_form_errors()

            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)


class ServiceUpdateView(LoginRequiredMixin, View):
    """
    View para editar um serviço existente usando django.views.generic
    """
    login_url = 'client_painel:login'

    def get_object(self, service_id):
        return get_object_or_404(Service, id=service_id, client=self.request.user.client)

    def get(self, request, service_id):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        service = self.get_object(service_id)

        # Retorna os dados do serviço para popular o modal
        availabilities = []
        for availability in service.availabilities.all().order_by('weekday', 'start_time'):
            availabilities.append({
                'id': str(availability.id),
                'weekday': availability.weekday,
                'start_time': availability.start_time.strftime('%H:%M'),
                'end_time': availability.end_time.strftime('%H:%M'),
                'is_active': availability.is_active,
            })

        # Gera URL completa do link de agendamento
        scheduling_url = ''
        if service.auto_scheduling_enabled and service.scheduling_link_token:
            scheduling_url = request.build_absolute_uri(
                f'/agendar/{service.scheduling_link_token}/'
            )

        return JsonResponse({
            'id': str(service.id),
            'name': service.name,
            'slug': service.slug,
            'description': service.description or '',
            'duration': service.duration,
            'price': float(service.price),
            'service_type': service.service_type,
            'auto_scheduling_enabled': service.auto_scheduling_enabled,
            'scheduling_link_token': scheduling_url,
            'scarcity_enabled': service.scarcity_enabled,
            'show_adjacent_slots_only': service.show_adjacent_slots_only,
            'max_daily_options': service.max_daily_options,
            'is_active': service.is_active,
            'availabilities': availabilities,
        })

    def post(self, request, service_id):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        service = self.get_object(service_id)
        form = ServiceForm(request.POST, instance=service, client=request.user.client)
        formset = ServiceAvailabilityFormSet(request.POST, instance=service)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            messages.success(request, 'Serviço atualizado com sucesso!')
            return JsonResponse({
                'success': True,
                'redirect': reverse_lazy('client_painel:service_list')
            })
        else:
            errors = {}
            if form.errors:
                errors['form'] = form.errors
            if formset.errors:
                errors['formset'] = formset.errors
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)


class ServiceDeleteView(LoginRequiredMixin, View):
    """
    View para deletar um serviço usando django.views.generic
    """
    login_url = 'client_painel:login'

    def post(self, request, service_id):
        if not request.user.client:
            return JsonResponse({'error': 'Cliente não encontrado'}, status=400)

        service = get_object_or_404(Service, id=service_id, client=request.user.client)
        service_name = service.name
        service.delete()

        messages.success(request, f'Serviço "{service_name}" excluído com sucesso!')
        return JsonResponse({'success': True})