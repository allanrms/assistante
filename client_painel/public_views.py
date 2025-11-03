"""
Views públicas para agendamento
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from datetime import datetime, timedelta, date
import json

from core.models import Appointment, AppointmentToken, ScheduleConfig, WorkingDay, BlockedDay


class PublicAppointmentAvailabilityAPI(View):
    """
    API pública para consultar horários disponíveis de uma data específica
    """

    def get(self, request, token, date_str):
        """Retorna horários disponíveis para uma data específica"""
        # Busca o token
        appointment_token = get_object_or_404(AppointmentToken, token=token)

        # Verifica se o token é válido
        if not appointment_token.is_valid():
            return JsonResponse({
                'error': 'Token inválido ou expirado.'
            }, status=400)

        try:
            check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'error': 'Formato de data inválido.'
            }, status=400)

        appointment = appointment_token.appointment
        contact = appointment.contact
        client = contact.client

        # Busca configuração da agenda
        try:
            schedule_config = ScheduleConfig.objects.get(client=client)
        except ScheduleConfig.DoesNotExist:
            return JsonResponse({
                'error': 'Configuração de agenda não encontrada.'
            }, status=400)

        # Verifica se o dia não está bloqueado
        if schedule_config.blocked_days.filter(date=check_date).exists():
            return JsonResponse({
                'available_times': [],
                'message': 'Este dia está bloqueado.'
            })

        # Verifica se o dia da semana está ativo
        weekday = check_date.weekday()

        try:
            working_day = schedule_config.working_days.get(weekday=weekday)
        except WorkingDay.DoesNotExist:
            return JsonResponse({
                'available_times': [],
                'message': 'Não há atendimento neste dia da semana.'
            })

        if not working_day.is_active:
            return JsonResponse({
                'available_times': [],
                'message': 'Não há atendimento neste dia da semana.'
            })

        # Pega horários disponíveis
        available_times = working_day.get_available_times(check_date)

        # Remove horários já agendados
        existing_appointments = Appointment.objects.filter(
            contact__client=client,
            date=check_date,
            time__isnull=False,  # Apenas appointments com horário definido
            status__in=['confirmed', 'pending', 'draft']
        ).exclude(
            id=appointment.id
        ).values_list('time', flat=True)

        available_times = [t for t in available_times if t not in existing_appointments]

        return JsonResponse({
            'available_times': [t.strftime('%H:%M') for t in available_times],
            'date': check_date.isoformat()
        })


class PublicAppointmentView(View):
    """
    View pública para o paciente escolher data e hora do agendamento
    """

    def get(self, request, token):
        """Exibe a página de agendamento"""
        # Busca o token
        appointment_token = get_object_or_404(AppointmentToken, token=token)

        # Verifica se o token é válido
        if not appointment_token.is_valid():
            return render(request, 'client_painel/public_appointment_expired.html', {
                'token': appointment_token,
            })

        appointment = appointment_token.appointment
        contact = appointment.contact
        client = contact.client

        # Busca configuração da agenda
        try:
            schedule_config = ScheduleConfig.objects.get(client=client)
        except ScheduleConfig.DoesNotExist:
            return render(request, 'client_painel/public_appointment_error.html', {
                'error': 'Configuração de agenda não encontrada.'
            })

        # Gera próximos 30 dias de disponibilidade
        today = date.today()
        available_dates = []

        for days_ahead in range(30):
            check_date = today + timedelta(days=days_ahead)

            # Verifica se o dia não está bloqueado
            if schedule_config.blocked_days.filter(date=check_date).exists():
                continue

            # Verifica se o dia da semana está ativo
            weekday = check_date.weekday()  # 0=Monday

            try:
                working_day = schedule_config.working_days.get(weekday=weekday)
            except WorkingDay.DoesNotExist:
                continue

            if not working_day.is_active:
                continue

            # Pega horários disponíveis
            available_times = working_day.get_available_times(check_date)

            # Remove horários já agendados (de QUALQUER cliente para evitar conflitos)
            # Busca todos os appointments daquele dia que estão confirmados, pendentes ou em rascunho
            existing_appointments = Appointment.objects.filter(
                contact__client=client,  # Apenas do mesmo cliente (clínica)
                date=check_date,
                time__isnull=False,  # Apenas appointments com horário definido
                status__in=['confirmed', 'pending', 'draft']  # Inclui draft para reservar horário temporariamente
            ).exclude(
                id=appointment.id  # Exclui o próprio appointment sendo editado (se aplicável)
            ).values_list('time', flat=True)

            # Remove horários ocupados
            available_times = [t for t in available_times if t not in existing_appointments]

            if available_times:
                available_dates.append({
                    'date': check_date.isoformat(),
                    'date_formatted': check_date.strftime('%d/%m/%Y'),
                    'weekday': check_date.strftime('%A'),
                    'times': [t.strftime('%H:%M') for t in available_times]
                })

        context = {
            'token': token,
            'appointment': appointment,
            'contact': contact,
            'available_dates': json.dumps(available_dates),
            'expires_at': appointment_token.expires_at,
        }

        return render(request, 'client_painel/public_appointment.html', context)

    def post(self, request, token):
        """Processa a seleção de data e hora"""
        appointment_token = get_object_or_404(AppointmentToken, token=token)

        # Verifica se o token é válido
        if not appointment_token.is_valid():
            return JsonResponse({
                'error': 'Este link de agendamento expirou ou já foi utilizado.'
            }, status=400)

        # Pega data e hora selecionadas
        selected_date = request.POST.get('date')
        selected_time = request.POST.get('time')

        if not selected_date or not selected_time:
            return JsonResponse({
                'error': 'Data e hora são obrigatórias.'
            }, status=400)

        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            time_obj = datetime.strptime(selected_time, '%H:%M').time()
        except ValueError:
            return JsonResponse({
                'error': 'Formato de data ou hora inválido.'
            }, status=400)

        # Atualiza o appointment
        appointment = appointment_token.appointment
        appointment.date = date_obj
        appointment.time = time_obj
        appointment.scheduled_for = datetime.combine(date_obj, time_obj)
        appointment.status = 'pending'  # Muda para aguardando confirmação
        appointment.save()

        # Marca o token como usado
        appointment_token.is_used = True
        appointment_token.save()

        return JsonResponse({
            'success': True,
            'message': 'Agendamento realizado com sucesso! Você receberá uma confirmação em breve.',
            'date': date_obj.strftime('%d/%m/%Y'),
            'time': time_obj.strftime('%H:%M')
        })
