# -*- coding: utf-8 -*-
from rest_framework import serializers
from whatsapp_connector.models import EvolutionInstance, MessageHistory, ChatSession


class EvolutionInstanceSerializer(serializers.ModelSerializer):
    """
    Serializer para EvolutionInstance com informações completas
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    connection_info = serializers.CharField(read_only=True)
    is_connected = serializers.BooleanField(read_only=True)
    message_count = serializers.SerializerMethodField()
    agent_display = serializers.CharField(source='agent.__str__', read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = EvolutionInstance
        fields = [
            'id', 'name', 'instance_name', 'base_url', 'api_key', 'status', 'status_display',
            'phone_number', 'profile_name', 'profile_pic_url', 'created_at', 'updated_at',
            'last_connection', 'is_active', 'webhook_url', 'connection_info', 'is_connected',
            'message_count', 'agent', 'agent_display', 'owner', 'owner_username'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True}  # Não expor API key nas respostas
        }
    
    def get_message_count(self, obj):
        """Retorna o número total de mensagens da instância"""
        # Como agora as mensagens não têm relação direta com a instância,
        # precisamos contar de forma diferente se necessário
        return 0  # TODO: Implementar contagem se necessário


class EvolutionInstanceCreateSerializer(serializers.ModelSerializer):
    """
    Serializer específico para criação de instância
    """
    class Meta:
        model = EvolutionInstance
        fields = [
            'name', 'instance_name', 'base_url', 'api_key', 'webhook_url', 'agent'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True}
        }


class EvolutionInstanceUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer específico para atualização de instância
    """
    class Meta:
        model = EvolutionInstance
        fields = [
            'name', 'base_url', 'api_key', 'webhook_url', 'is_active', 'agent'
        ]
        extra_kwargs = {
            'api_key': {'write_only': True}
        }


class ChatSessionSerializer(serializers.ModelSerializer):
    """
    Serializer para ChatSession
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            'id', 'from_number', 'to_number', 'status', 'status_display',
            'created_at', 'updated_at', 'message_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'message_count']
    
    def get_message_count(self, obj):
        """Retorna o número de mensagens na sessão"""
        return obj.messages.count()


class MessageHistorySerializer(serializers.ModelSerializer):
    """
    Serializer para MessageHistory
    """
    from_number = serializers.CharField(source='chat_session.from_number', read_only=True)
    to_number = serializers.CharField(source='chat_session.to_number', read_only=True)
    chat_session_status = serializers.CharField(source='chat_session.get_status_display', read_only=True)
    
    class Meta:
        model = MessageHistory
        fields = [
            'id', 'message_id', 'chat_session', 'from_number', 'to_number', 'message_type', 'content',
            'media_url', 'created_at', 'received_at', 'updated_at', 'processing_status', 'ai_response',
            'sender_name', 'source', 'audio_transcription', 'raw_data', 'chat_session_status'
        ]
        read_only_fields = ['id', 'received_at', 'created_at', 'updated_at', 'from_number', 'to_number', 'chat_session_status']