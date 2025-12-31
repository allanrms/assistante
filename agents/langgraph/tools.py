"""
Ferramentas auxiliares para a Secretária Virtual

Este módulo contém funções que interagem com o banco de dados Django
para realizar operações de agendamento.

IMPORTANTE: Estas funções NÃO devem ser chamadas diretamente pela LLM.
Elas são chamadas APENAS pelos nós específicos do grafo.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from core.models import Appointment, AppointmentToken, Contact
import secrets


def gerar_link_agendamento(runtime):
    """
    Gera um link único de agendamento para o contato.

    Args:
        runtime: Objeto runtime com informações da conversa

    Returns:
        str: Mensagem com o link de agendamento

    Regras:
        - NUNCA inventar links
        - Sempre gerar token único
        - Link expira em 7 dias
    """
    try:
        # Buscar contato da conversa
        conversation = runtime.conversation
        contact = conversation.contact

        if not contact:
            return "❌ Desculpe, não consegui identificar seu contato. Por favor, tente novamente."

        # Criar agendamento em rascunho
        appointment = Appointment.objects.create(
            contact=contact,
            status='draft'
        )

        # Gerar token único
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=7)

        # Criar token de agendamento
        appointment_token = AppointmentToken.objects.create(
            appointment=appointment,
            token=token,
            expires_at=expires_at
        )

        # Gerar URL pública (ajustar base_url conforme ambiente)
        base_url = settings.BACKEND_BASE_URL.rstrip('/')
        public_url = appointment_token.get_public_url(base_url)

        return f"""📅 Perfeito! Aqui está seu link para agendar:

{public_url}

✅ Este link é válido por 7 dias
📱 Você pode acessar pelo celular ou computador
⏰ Escolha o melhor horário disponível

Após confirmar o agendamento, você receberá uma confirmação aqui no WhatsApp."""

    except Exception as e:
        print(f"❌ Erro ao gerar link de agendamento: {e}")
        return "❌ Desculpe, ocorreu um erro ao gerar o link. Por favor, tente novamente em alguns instantes."


def consultar_agendamentos(runtime):
    """
    Consulta os agendamentos do contato.

    Args:
        runtime: Objeto runtime com informações da conversa

    Returns:
        str: Lista formatada de agendamentos ou mensagem de ausência

    Regras:
        - Mostrar apenas agendamentos com data/hora definida (exclui rascunhos)
        - Excluir agendamentos cancelados
        - Ordenar por data/hora
        - Mostrar ID para cancelamento/reagendamento
    """
    try:
        # Buscar contato da conversa
        conversation = runtime.conversation
        contact = conversation.contact

        if not contact:
            return "❌ Desculpe, não consegui identificar seu contato."

        # Buscar agendamentos ativos (excluindo rascunhos e cancelados)
        appointments = contact.appointments.filter(
            scheduled_for__isnull=False
        ).exclude(
            status='cancelled'
        ).order_by('date', 'time')

        if not appointments.exists():
            return """📅 Você não possui agendamentos no momento.

Gostaria de agendar uma consulta?"""

        # Formatar lista de agendamentos
        message = "📅 Seus agendamentos:\n\n"

        for apt in appointments:
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
            }.get(apt.status, '📋')

            if apt.scheduled_for:
                date_str = apt.scheduled_for.strftime('%d/%m/%Y às %H:%M')
            else:
                date_str = "Data a definir"

            message += f"{status_emoji} ID: {apt.id}\n"
            message += f"   Data: {date_str}\n"
            message += f"   Status: {apt.get_status_display()}\n\n"

        message += "💡 Para cancelar ou reagendar, informe o ID da consulta."

        return message

    except Exception as e:
        print(f"❌ Erro ao consultar agendamentos: {e}")
        return "❌ Desculpe, ocorreu um erro ao consultar seus agendamentos."


def cancelar_agendamento(appointment_id: int, runtime):
    """
    Cancela um agendamento específico.

    Args:
        appointment_id: ID do agendamento a cancelar
        runtime: Objeto runtime com informações da conversa

    Returns:
        str: Mensagem de confirmação ou erro

    Regras:
        - Validar que o agendamento pertence ao contato
        - Não permitir cancelar agendamentos já realizados
        - Atualizar status para 'cancelled'
    """
    try:
        # Buscar contato da conversa
        conversation = runtime.conversation
        contact = conversation.contact

        if not contact:
            return "❌ Desculpe, não consegui identificar seu contato."

        # Buscar agendamento
        try:
            appointment = Appointment.objects.get(
                id=appointment_id,
                contact=contact
            )
        except Appointment.DoesNotExist:
            return f"❌ Agendamento ID {appointment_id} não encontrado ou não pertence a você."

        # Validar se pode cancelar
        if appointment.status == 'draft':
            return "⚠️ Este agendamento ainda está em rascunho e não foi confirmado."

        if appointment.status == 'cancelled':
            return "⚠️ Este agendamento já está cancelado."

        if appointment.status == 'completed':
            return "⚠️ Não é possível cancelar um agendamento já realizado."

        # Cancelar agendamento
        appointment.status = 'cancelled'
        appointment.save()

        if appointment.scheduled_for:
            date_str = appointment.scheduled_for.strftime('%d/%m/%Y às %H:%M')
        else:
            date_str = "Data não definida"

        return f"""✅ Agendamento cancelado com sucesso!

📅 Data: {date_str}
🆔 ID: {appointment.id}

Se precisar reagendar, estou à disposição!"""

    except Exception as e:
        print(f"❌ Erro ao cancelar agendamento: {e}")
        return "❌ Desculpe, ocorreu um erro ao cancelar o agendamento."


def reagendar_consulta(appointment_id: int, runtime):
    """
    Reagenda uma consulta existente (gera novo link).

    Args:
        appointment_id: ID do agendamento a reagendar
        runtime: Objeto runtime com informações da conversa

    Returns:
        str: Mensagem com novo link de agendamento

    Regras:
        - Validar que o agendamento pertence ao contato
        - Cancelar agendamento anterior
        - Gerar novo link de agendamento
    """
    try:
        # Buscar contato da conversa
        conversation = runtime.conversation
        contact = conversation.contact

        if not contact:
            return "❌ Desculpe, não consegui identificar seu contato."

        # Buscar agendamento
        try:
            old_appointment = Appointment.objects.get(
                id=appointment_id,
                contact=contact
            )
        except Appointment.DoesNotExist:
            return f"❌ Agendamento ID {appointment_id} não encontrado ou não pertence a você."

        # Validar se pode reagendar
        if old_appointment.status == 'draft':
            return "⚠️ Este agendamento ainda está em rascunho e não foi confirmado."

        if old_appointment.status == 'cancelled':
            return "⚠️ Este agendamento já está cancelado. Gostaria de criar um novo agendamento?"

        if old_appointment.status == 'completed':
            return "⚠️ Este agendamento já foi realizado. Gostaria de criar um novo agendamento?"

        # Cancelar agendamento antigo
        old_appointment.status = 'cancelled'
        old_appointment.save()

        # Criar novo agendamento
        new_appointment = Appointment.objects.create(
            contact=contact,
            status='draft'
        )

        # Gerar token único
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(days=7)

        # Criar token de agendamento
        appointment_token = AppointmentToken.objects.create(
            appointment=new_appointment,
            token=token,
            expires_at=expires_at
        )

        # Gerar URL pública
        base_url = "https://seu-dominio.com.br"  # TODO: Pegar de settings
        public_url = appointment_token.get_public_url(base_url)

        return f"""✅ Agendamento anterior cancelado!

📅 Aqui está seu novo link para reagendar:

{public_url}

✅ Link válido por 7 dias
📱 Escolha o melhor horário disponível
⏰ Você receberá confirmação após agendar"""

    except Exception as e:
        print(f"❌ Erro ao reagendar consulta: {e}")
        return "❌ Desculpe, ocorreu um erro ao reagendar a consulta."


def request_human_intervention(reason: str, runtime):
    """
    Solicita intervenção humana na conversa.

    Args:
        reason: Motivo da transferência
        runtime: Objeto runtime com informações da conversa

    Regras:
        - Alterar Conversation.status para 'human'
        - Registrar motivo da transferência
        - NUNCA continuar atendimento após transferência
    """
    try:
        conversation = runtime.conversation
        agent = conversation.evolution_instance.agent if conversation.evolution_instance else None

        # Buscar critérios de transferência humana do agente
        intervention_rules_text = "    ⚠️ Nenhum critério específico cadastrado."

        if agent and agent.human_handoff_criteria:
            # Formatar as regras com indentação e destaque
            rules = agent.human_handoff_criteria.strip()

            # Processar cada linha das regras
            formatted_lines = []
            for line in rules.split("\n"):
                line = line.strip()
                if line:
                    # Se a linha já começa com -, manter
                    # Senão, adicionar -
                    if not line.startswith("-"):
                        line = f"- {line}"
                    formatted_lines.append(f"    ❗ {line}")

            intervention_rules_text = "\n".join(formatted_lines)

        # Status anterior para log
        status_anterior = conversation.status

        # Alterar status para atendimento humano
        conversation.status = 'human'
        conversation.save()

        # Verificar se salvou corretamente
        conversation.refresh_from_db()

        # Log MUITO VISÍVEL da transferência
        print("\n" + "="*80)
        print("🚨🚨🚨 TRANSFERÊNCIA PARA ATENDIMENTO HUMANO EXECUTADA 🚨🚨🚨")
        print("="*80)
        print(f"📋 Conversa ID: {conversation.id}")
        print(f"📱 Contato: {conversation.from_number}")
        print(f"📝 Motivo: {reason}")
        print(f"🔄 Status: {status_anterior} → {conversation.status}")
        print(f"✅ Status confirmado no DB: {conversation.status}")

        # Exibir critérios de transferência se existirem
        if agent and agent.human_handoff_criteria:
            print(f"\n🔔 Critérios de intervenção configurados para '{agent.display_name}':")
            for line in intervention_rules_text.split("\n"):
                print(line)

        print("="*80 + "\n")

        return True

    except Exception as e:
        print("\n" + "="*80)
        print("❌❌❌ ERRO NA TRANSFERÊNCIA PARA HUMANO ❌❌❌")
        print("="*80)
        print(f"Erro: {str(e)}")
        print("="*80 + "\n")
        return False