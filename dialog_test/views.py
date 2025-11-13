"""
Dialog Test Views - Chat Único Simplificado
"""
import traceback

from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from agents.langgraph.langgraph_app_runner import run_ai_turn
from agents.models import Agent, Conversation
from core.models import Client, Contact
from whatsapp_connector.models import ChatSession, EvolutionInstance


# ========== VIEWS ==========

def chat_view(request):
    """
    Renderiza página do chat único
    """
    clients = Client.objects.all()

    context = {
        'clients': clients,
    }

    return render(request, 'dialog_test/chat.html', context)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def send_message(request):
    """
    Envia mensagem e retorna resposta do MultiAgentOrchestrator

    POST /dialog-test/send/
    {
        "message": "sua mensagem aqui",
        "client_id": "uuid-cliente",
        "agent_id": "uuid-agent",
        "from_number": "numero-customizado"
    }
    """
    try:
        # Extrair dados
        message_text = request.data.get('message', '').strip()
        client_id = request.data.get('client_id')
        agent_id = request.data.get('agent_id')
        from_number = request.data.get('from_number', '').strip()

        # Validar
        if not message_text:
            return Response({'error': 'Mensagem vazia'}, status=status.HTTP_400_BAD_REQUEST)

        if not client_id or not agent_id:
            return Response({'error': 'client_id e agent_id obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)

        if not from_number:
            return Response({'error': 'from_number obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            client = Client.objects.get(id=client_id)
        except (Client.DoesNotExist, Agent.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)

        # Criar/buscar sessão de chat (usando ChatSession do whatsapp_connector)
        to_number = from_number

        try:

            evolution_instance = EvolutionInstance.objects.last()
            output, contact = run_ai_turn(from_number, to_number, message_text, client, evolution_instance=evolution_instance)

            return Response({
                'message': message_text,
                'response': output,
                'success': True
            }, status=status.HTTP_200_OK)

        except Exception as e:
            traceback.print_exc()
            # Marcar mensagem como falha
            # message.processing_status = 'failed'
            # message.response = f'Erro: {str(e)}'
            # message.save()

            return Response({
                'error': str(e),
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        traceback.print_exc()
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_client_llm_configs(request, client_id):
    """
    Retorna as configurações LLM de um cliente

    GET /dialog-test/client/<client_id>/llm-configs/
    """
    try:
        client = Client.objects.get(id=client_id)
        agent = Agent.objects.filter(owner=client)

        configs_data = [{
            'id': str(config.id),
            'name': config.display_name or f"{config.get_name_display()} - {config.model}",
            'provider': config.name,  # Este campo é o provider (openai, anthropic, etc)
            'model': config.model
        } for config in agent]

        return Response({
            'configs': configs_data,
            'success': True
        }, status=status.HTTP_200_OK)

    except Client.DoesNotExist:
        return Response({
            'error': 'Cliente não encontrado',
            'success': False
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def clear_chat(request):
    """
    Limpa o histórico de chat (deleta ChatSession e MessageHistory vinculados)

    POST /dialog-test/clear/
    {
        "client_id": "uuid-cliente",
        "from_number": "numero-customizado"
    }
    """
    try:
        client_id = request.data.get('client_id')
        from_number = request.data.get('from_number')

        if not client_id or not from_number:
            return Response({
                'error': 'client_id e from_number obrigatórios',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)

        # Buscar sessões ativas para este from_number (sem filtrar por to_number)
        contact = Contact.objects.get(client_id=client_id, phone_number=from_number)

        conversations = Conversation.objects.filter(
            contact=contact
        )

        if not conversations.exists():
            return Response({
                'message': 'Nenhuma sessão encontrada para limpar',
                'success': True
            }, status=status.HTTP_200_OK)

        # Deletar sessões (vai cascatear para as mensagens)
        conversations.delete()

        return Response({
            'message': 'Histórico limpo com sucesso',
            'success': True
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e),
            'success': False
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
