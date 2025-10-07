from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .models import LLMProviderConfig, AssistantContextFile
from .forms import AssistantForm, AssistantContextFileForm
from .services import create_llm_service
from .file_processors import file_processor
from whatsapp_connector.models import EvolutionInstance
from whatsapp_connector.services import EvolutionAPIService
from core.mixins import ClientRequiredMixin


# === ASSISTANTS VIEWS ===

class AssistantListView(ClientRequiredMixin, LoginRequiredMixin, ListView):
    """
    Lista todos os assistants/LLM configs
    """
    model = LLMProviderConfig
    template_name = 'agents/assistants/list.html'
    context_object_name = 'assistants'
    paginate_by = 20

    def get_queryset(self):
        queryset = LLMProviderConfig.objects.filter(owner=self.request.user.client).order_by('-created_at')

        # Filtro por provedor
        provider = self.request.GET.get('provider')
        if provider:
            queryset = queryset.filter(name=provider)

        # Filtro por busca
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(display_name__icontains=search) |
                Q(model__icontains=search) |
                Q(instructions__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provider_choices'] = LLMProviderConfig.PROVIDERS
        context['current_provider'] = self.request.GET.get('provider', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class AssistantDetailView(ClientRequiredMixin, LoginRequiredMixin, DetailView):
    """
    Detalhes de um assistant específico
    """
    model = LLMProviderConfig
    template_name = 'agents/assistants/detail.html'
    context_object_name = 'assistant'

    def get_queryset(self):
        return LLMProviderConfig.objects.filter(owner=self.request.user.client)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assistant = self.get_object()

        # Contar instâncias que usam este assistant (apenas do cliente atual)
        context['instances_using'] = EvolutionInstance.objects.filter(
            llm_config=assistant, owner=self.request.user.client
        ).count()

        # Listar algumas instâncias que usam (apenas do cliente atual)
        context['example_instances'] = EvolutionInstance.objects.filter(
            llm_config=assistant, owner=self.request.user.client
        )[:5]

        return context


class AssistantCreateView(ClientRequiredMixin, LoginRequiredMixin, CreateView):
    """
    Criar um novo assistant
    """
    model = LLMProviderConfig
    form_class = AssistantForm
    template_name = 'agents/assistants/create.html'
    success_url = reverse_lazy('agents:assistant_list')

    def get_initial(self):
        """
        Define valores padrão para novos assistants
        """
        initial = super().get_initial()
        initial['name'] = 'openai'
        initial['model'] = 'gpt-4o-mini'
        print(f"🎯 Definindo valores iniciais: {initial}")
        return initial

    def form_valid(self, form):
        try:
            self.object = form.save(commit=False)
            self.object.owner = self.request.user.client  # Definir o cliente atual como proprietário
            self.object.save()
            messages.success(self.request, f'Assistant "{self.object.display_name}" criado com sucesso! Agora você pode adicionar arquivos de contexto para personalizar as respostas.')
            return redirect('agents:assistant_detail', pk=self.object.pk)

        except Exception as e:
            messages.error(self.request, f'Erro ao criar assistant: {str(e)}')
            return self.form_invalid(form)


class AssistantUpdateView(ClientRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    Editar um assistant existente
    """
    model = LLMProviderConfig
    form_class = AssistantForm
    template_name = 'agents/assistants/edit.html'

    def get_queryset(self):
        return LLMProviderConfig.objects.filter(owner=self.request.user.client)

    def get_success_url(self):
        return reverse_lazy('agents:assistant_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            self.object = form.save()
            messages.success(self.request, f'Assistant "{self.object.display_name}" atualizado com sucesso!')
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f'Erro ao atualizar assistant: {str(e)}')
            return self.form_invalid(form)


class AssistantDeleteView(ClientRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    Deletar um assistant
    """
    model = LLMProviderConfig
    template_name = 'agents/assistants/confirm_delete.html'
    success_url = reverse_lazy('agents:assistant_list')
    context_object_name = 'assistant'

    def get_queryset(self):
        return LLMProviderConfig.objects.filter(owner=self.request.user.client)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        assistant_name = self.object.display_name

        # Verificar se há instâncias usando este assistant (apenas do cliente atual)
        instances_count = EvolutionInstance.objects.filter(
            llm_config=self.object, owner=request.user.client
        ).count()

        if instances_count > 0:
            messages.warning(
                request,
                f'Não é possível deletar: {instances_count} instância(s) ainda usam este assistant. '
                'Remova ou altere a configuração das instâncias primeiro.'
            )
            return redirect('agents:assistant_detail', pk=self.object.pk)

        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, f'Assistant "{assistant_name}" removido com sucesso!')
            return response

        except Exception as e:
            messages.error(request, f'Erro ao deletar assistant: {str(e)}')
            return redirect('agents:assistant_list')


# def _process_text_message(message):
#     """
#     Processa mensagens de texto usando OpenAI ao invés de N8N
#     Similar ao _process_image_message mas para integração OpenAI
#
#     Args:
#         message: Instância do modelo WhatsAppMessage
#
#     Returns:
#         dict: Resultado do processamento
#     """
#     try:
#         print(f"Mensagem de texto detectada para OpenAI: {message}")
#         message.processing_status = 'processing'
#         message.save()
#
#         # Initialize OpenAI service
#         openai_service = OpenAIService()
#         evolution_api = EvolutionAPIService()
#
#         # Send to OpenAI
#         openai_result = openai_service.send_text_message(
#             message.from_number,
#             message.sender_name,
#             message.content
#         )
#
#         if openai_result and openai_result.get('success'):
#             # Save OpenAI response
#             message.ai_response = openai_result
#             message.processing_status = 'completed'
#
#             # Send response back to WhatsApp
#             ai_response_text = openai_result.get('response', '')
#             if ai_response_text:
#                 evolution_api.send_text_message(
#                     message.from_number,
#                     ai_response_text
#                 )
#                 print(f"Resposta enviada para WhatsApp: {ai_response_text}")
#
#         else:
#             message.processing_status = 'failed'
#             error_msg = openai_result.get('error', 'Erro desconhecido') if openai_result else 'Sem resposta da OpenAI'
#             print(f"Falha ao processar com OpenAI: {error_msg}")
#
#         message.save()
#
#         return {
#             'success': openai_result.get('success', False) if openai_result else False,
#             'message_id': message.message_id,
#             'processing_status': message.processing_status
#         }
#
#     except Exception as e:
#         print(f"Error processing text message with OpenAI: {e}")
#         message.processing_status = 'failed'
#         message.save()
#
#         return {
#             'success': False,
#             'error': str(e),
#             'message_id': message.message_id,
#             'processing_status': 'failed'
#         }


# Create your views here.

# Views para gerenciar arquivos de contexto dos assistants
class AssistantContextFileUploadView(LoginRequiredMixin, CreateView):
    """
    View para upload de arquivos de contexto
    """
    model = AssistantContextFile
    form_class = AssistantContextFileForm
    template_name = 'agents/context_files/upload.html'
    
    def form_valid(self, form):
        # Associar o arquivo à configuração LLM (apenas do usuário atual)
        llm_config_id = self.kwargs.get('llm_config_id')
        llm_config = get_object_or_404(LLMProviderConfig, id=llm_config_id, owner=self.request.user.client)
        
        context_file = form.save(commit=False)
        context_file.llm_config = llm_config
        
        # Determinar tipo do arquivo baseado na extensão
        if context_file.file:
            file_extension = context_file.get_file_extension()
            for choice_value, choice_label in AssistantContextFile.FILE_TYPES:
                if file_extension == f'.{choice_value}':
                    context_file.file_type = choice_value
                    break
            else:
                # Padrão para tipos não mapeados
                context_file.file_type = 'txt'
        
        # Salvar tamanho do arquivo
        if context_file.file:
            context_file.file_size = context_file.file.size
            
        context_file.status = 'processing'
        context_file.save()
        
        # Processar arquivo em background (simplificado - pode ser movido para Celery)
        self.process_file_content(context_file)
        
        messages.success(self.request, f'Arquivo "{context_file.name}" enviado com sucesso!')
        return redirect('agents:assistant_detail', pk=llm_config.pk)
    
    def process_file_content(self, context_file):
        """
        Processa o arquivo e extrai o conteúdo
        """
        try:
            file_path = context_file.file.path
            result = file_processor.process_file(file_path)
            
            if result['success']:
                context_file.extracted_content = result['extracted_text']
                context_file.status = 'ready'
                context_file.error_message = None
            else:
                context_file.status = 'error'
                context_file.error_message = result['error']
                
        except Exception as e:
            context_file.status = 'error'
            context_file.error_message = f'Erro durante processamento: {str(e)}'
        
        context_file.save()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        llm_config_id = self.kwargs.get('llm_config_id')
        context['llm_config'] = get_object_or_404(LLMProviderConfig, id=llm_config_id, owner=self.request.user.client)
        return context


class AssistantContextFileListView(LoginRequiredMixin, ListView):
    """
    View para listar arquivos de contexto de um assistant
    """
    model = AssistantContextFile
    template_name = 'agents/context_files/list.html'
    context_object_name = 'context_files'
    paginate_by = 20
    
    def get_queryset(self):
        llm_config_id = self.kwargs.get('llm_config_id')
        return AssistantContextFile.objects.filter(
            llm_config_id=llm_config_id,
            llm_config__owner=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        llm_config_id = self.kwargs.get('llm_config_id')
        context['llm_config'] = get_object_or_404(LLMProviderConfig, id=llm_config_id, owner=self.request.user.client)
        return context


class AssistantContextFileUpdateView(LoginRequiredMixin, UpdateView):
    """
    View para editar arquivos de contexto
    """
    model = AssistantContextFile
    form_class = AssistantContextFileForm
    template_name = 'agents/context_files/edit.html'
    
    def get_queryset(self):
        return AssistantContextFile.objects.filter(llm_config__owner=self.request.user.client)
    
    def get_form_class(self):
        # Formulário simplificado para edição (sem campo de arquivo)
        class EditForm(AssistantContextFileForm):
            class Meta(AssistantContextFileForm.Meta):
                fields = ['name', 'is_active']
        
        return EditForm
    
    def form_valid(self, form):
        messages.success(self.request, f'Arquivo "{form.instance.name}" atualizado com sucesso!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('agents:assistant_detail', kwargs={'pk': self.object.llm_config.pk})


class AssistantContextFileDeleteView(LoginRequiredMixin, DeleteView):
    """
    View para deletar arquivos de contexto
    """
    model = AssistantContextFile
    template_name = 'agents/context_files/delete.html'
    
    def get_queryset(self):
        return AssistantContextFile.objects.filter(llm_config__owner=self.request.user.client)
    
    def get_success_url(self):
        return reverse_lazy('agents:assistant_detail', kwargs={'pk': self.object.llm_config.pk})
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        file_name = self.object.name
        
        # Deletar arquivo físico se existir
        if self.object.file:
            try:
                if os.path.isfile(self.object.file.path):
                    os.remove(self.object.file.path)
            except Exception as e:
                print(f"Error deleting file: {e}")
        
        messages.success(request, f'Arquivo "{file_name}" removido com sucesso!')
        return super().delete(request, *args, **kwargs)
