from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.core.mail import mail_admins
import os
import traceback
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from .models import Agent, AgentFile
from .forms import AgentForm, AgentFileForm
# from .services import create_llm_service
from whatsapp_connector.models import EvolutionInstance
from whatsapp_connector.services import EvolutionAPIService
from core.mixins import ClientRequiredMixin
from agents.langchain.vectorstore import get_vectorstore_for_agent, get_collection_uuid_by_name
from agents.patterns.factories.file_processors import FileProcessorFactory


# === AGENTS VIEWS ===

class AgentListView(ClientRequiredMixin, LoginRequiredMixin, ListView):
    """
    Lista todos os agents/LLM configs
    """
    model = Agent
    template_name = 'agents/agents/list.html'
    context_object_name = 'agents'
    paginate_by = 20

    def get_queryset(self):
        queryset = Agent.objects.filter(owner=self.request.user.client).order_by('-created_at')

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
                Q(system_prompt__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['provider_choices'] = Agent.PROVIDERS
        context['current_provider'] = self.request.GET.get('provider', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class AgentDetailView(ClientRequiredMixin, LoginRequiredMixin, DetailView):
    """
    Detalhes de um agent específico
    """
    model = Agent
    template_name = 'agents/agents/detail.html'
    context_object_name = 'agent'

    def get_queryset(self):
        return Agent.objects.filter(owner=self.request.user.client)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.get_object()

        # Contar instâncias que usam este agent (apenas do cliente atual)
        context['instances_using'] = EvolutionInstance.objects.filter(
            agent=agent, owner=self.request.user.client
        ).count()

        # Listar algumas instâncias que usam (apenas do cliente atual)
        context['example_instances'] = EvolutionInstance.objects.filter(
            agent=agent, owner=self.request.user.client
        )[:5]

        # Adicionar preview do prompt final
        context['final_prompt'] = agent.build_prompt()

        # Adicionar contagem de chunks para cada arquivo
        from agents.models import LangchainEmbedding
        files_with_chunks = []
        for file in agent.files.all()[:6]:
            chunks_count = LangchainEmbedding.objects.filter(
                cmetadata__agent_file_id=str(file.id)
            ).count()
            files_with_chunks.append({
                'file': file,
                'chunks_count': chunks_count
            })
        context['files_with_chunks'] = files_with_chunks

        return context


class AgentCreateView(ClientRequiredMixin, LoginRequiredMixin, CreateView):
    """
    Criar um novo agent
    """
    model = Agent
    form_class = AgentForm
    template_name = 'agents/agents/create.html'
    success_url = reverse_lazy('agents:agent_list')

    def get_initial(self):
        """
        Define valores padrão para novos agents
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
            messages.success(self.request, f'Agent "{self.object.display_name}" criado com sucesso! Agora você pode adicionar arquivos de contexto para personalizar as respostas.')
            return redirect('agents:agent_detail', pk=self.object.pk)

        except Exception as e:
            messages.error(self.request, f'Erro ao criar agent: {str(e)}')
            return self.form_invalid(form)


class AgentUpdateView(ClientRequiredMixin, LoginRequiredMixin, UpdateView):
    """
    Editar um agent existente
    """
    model = Agent
    form_class = AgentForm
    template_name = 'agents/agents/edit.html'

    def get_queryset(self):
        return Agent.objects.filter(owner=self.request.user.client)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Gerar preview do prompt final
        try:
            context['final_prompt'] = self.object.build_prompt()
        except Exception as e:
            context['final_prompt'] = f"Erro ao gerar preview: {str(e)}"

        # Contar arquivos vetorizados (files com status 'ready')
        context['vectorized_files_count'] = self.object.files.filter(status='ready').count()

        return context

    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            self.object = form.save()
            messages.success(self.request, f'Agent "{self.object.display_name}" atualizado com sucesso!')
            return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f'Erro ao atualizar agent: {str(e)}')
            return self.form_invalid(form)


class AgentDeleteView(ClientRequiredMixin, LoginRequiredMixin, DeleteView):
    """
    Deletar um agent
    """
    model = Agent
    template_name = 'agents/agents/confirm_delete.html'
    success_url = reverse_lazy('agents:agent_list')
    context_object_name = 'agent'

    def get_queryset(self):
        return Agent.objects.filter(owner=self.request.user.client)

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        agent_name = self.object.display_name

        # Verificar se há instâncias usando este agent (apenas do cliente atual)
        instances_count = EvolutionInstance.objects.filter(
            agent=self.object, owner=request.user.client
        ).count()

        if instances_count > 0:
            messages.warning(
                request,
                f'Não é possível deletar: {instances_count} instância(s) ainda usam este agent. '
                'Remova ou altere a configuração das instâncias primeiro.'
            )
            return redirect('agents:agent_detail', pk=self.object.pk)

        try:
            response = super().delete(request, *args, **kwargs)
            messages.success(request, f'Agent "{agent_name}" removido com sucesso!')
            return response

        except Exception as e:
            messages.error(request, f'Erro ao deletar agent: {str(e)}')
            return redirect('agents:agent_list')


# Views para gerenciar arquivos de contexto dos agents
class AgentFileUploadView(LoginRequiredMixin, CreateView):
    """
    View para upload de arquivos de contexto
    """
    model = AgentFile
    form_class = AgentFileForm
    template_name = 'agents/files/upload.html'

    def form_valid(self, form):
        # Associar o arquivo ao agent (apenas do usuário atual)
        agent_id = self.kwargs.get('agent_id')
        agent = get_object_or_404(Agent, id=agent_id, owner=self.request.user.client)

        context_file = form.save(commit=False)
        context_file.agent = agent

        # Determinar tipo do arquivo baseado na extensão
        if context_file.file:
            file_extension = context_file.get_file_extension()
            for choice_value, choice_label in AgentFile.FILE_TYPES:
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

        # Processar arquivo imediatamente (para desenvolvimento)
        # TODO: Mover para Celery para processamento assíncrono em produção
        try:
            self.process_file_content(context_file)

            # Verificar se foi processado com sucesso
            context_file.refresh_from_db()

            if context_file.status == 'ready':
                messages.success(
                    self.request,
                    f'✅ Arquivo "{context_file.name}" processado e vetorizado com sucesso!'
                )
            elif context_file.status == 'error':
                messages.error(
                    self.request,
                    f'❌ Erro ao processar "{context_file.name}": {context_file.error_message}'
                )
            else:
                messages.warning(
                    self.request,
                    f'⏳ Arquivo "{context_file.name}" em processamento...'
                )

        except Exception as e:
            traceback.print_exc()
            messages.error(
                self.request,
                f'❌ Erro ao processar arquivo: {str(e)}'
            )
            subject = "process_file_content - Falha Crítica"
            message = f'{traceback.format_exc()}\n\nLocals: {locals()}'
            mail_admins(subject, message)

        return redirect('agents:agent_file_list', agent_id=agent.pk)

    def build_vectorstore(self, context_file, document_str):
        """
        Processa o arquivo: carrega, faz chunking e vetoriza no PGVector.

        Fluxo:
        1. Detecta tipo do arquivo e carrega com loader apropriado
        2. Divide o conteúdo em chunks e vetoriza no PGVector
        """
        agent = context_file.agent

        try:

            doc = Document(page_content=document_str, metadata={"source": "string"})
            documents = [doc]

            # 3. Chunking do conteúdo
            splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=500)
            chunks = splitter.split_documents(documents)

            # 4. Preparar documentos para PGVector
            docs_to_add = []
            for i, chunk in enumerate(chunks):
                doc = Document(
                    page_content=chunk.page_content,
                    metadata={
                        "source": context_file.file.name,
                        "file_name": context_file.name,
                        "agent_file_id": str(context_file.id),
                        "page": chunk.metadata.get("page", 0),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "agent_id": str(agent.id),
                        "file_type": context_file.file_type,
                    }
                )
                docs_to_add.append(doc)

            # 5. Salvar chunks no PGVector
            vectorstore, collection_info = get_vectorstore_for_agent(agent)
            vectorstore.add_documents(docs_to_add)

            # Persistir collection_uuid se necessário
            if isinstance(collection_info, str):
                collection_uuid = get_collection_uuid_by_name(collection_info)
                if collection_uuid:
                    agent.collection_uuid = collection_uuid
                    agent.save(update_fields=['collection_uuid'])

            context_file.status = 'ready'
            context_file.error_message = None

        except Exception as e:
            traceback.print_exc()
            context_file.status = 'error'
            context_file.error_message = f'Erro durante processamento: {str(e)}'

        context_file.save()

    def process_file_content(self, context_file):
        """
        Processa o arquivo: extrai conteúdo com IA e gera embeddings
        """
        try:
            file_path = context_file.file.path

            file_processor = FileProcessorFactory(agent=context_file.agent)
            result = file_processor.process_file(file_path, use_ai=True)

            if not result['success']:
                context_file.status = 'error'
                context_file.error_message = result['error']
                context_file.save()
                return

            context_file.save()

            # 3. Gerar embedding (vetorização)
            try:
                self.build_vectorstore(context_file, result['extracted_text'])

            except Exception as e:
                # Se falhar vetorização, manter arquivo mas marcar como não vetorizado
                context_file.status = 'error'
                context_file.vectorized = False
                context_file.error_message = f'Arquivo pronto mas erro na vetorização: {str(e)}'

        except Exception as e:
            context_file.status = 'error'
            context_file.error_message = f'Erro durante processamento: {str(e)}'

        context_file.save()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs.get('agent_id')
        context['agent'] = get_object_or_404(Agent, id=agent_id, owner=self.request.user.client)
        return context


class AgentFileListView(LoginRequiredMixin, ListView):
    """
    View para listar arquivos de contexto de um agent
    """
    model = AgentFile
    template_name = 'agents/files/list.html'
    context_object_name = 'files'
    paginate_by = 20

    def get_queryset(self):
        agent_id = self.kwargs.get('agent_id')
        return AgentFile.objects.filter(
            agent_id=agent_id,
            agent__owner=self.request.user.client
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs.get('agent_id')
        context['agent'] = get_object_or_404(Agent, id=agent_id, owner=self.request.user.client)

        # Adicionar contagem de chunks para cada arquivo
        from agents.models import LangchainEmbedding
        files_with_chunks = []
        for file in context['files']:
            chunks_count = LangchainEmbedding.objects.filter(
                cmetadata__agent_file_id=str(file.id)
            ).count()
            files_with_chunks.append({
                'file': file,
                'chunks_count': chunks_count
            })
        context['files_with_chunks'] = files_with_chunks

        return context


class AgentFileUpdateView(LoginRequiredMixin, UpdateView):
    """
    View para editar arquivos de contexto
    """
    model = AgentFile
    form_class = AgentFileForm
    template_name = 'agents/files/edit.html'

    def get_queryset(self):
        return AgentFile.objects.filter(agent__owner=self.request.user.client)

    def get_form_class(self):
        # Formulário simplificado para edição (sem campo de arquivo)
        class EditForm(AgentFileForm):
            class Meta(AgentFileForm.Meta):
                fields = ['name', 'is_active']

        return EditForm

    def form_valid(self, form):
        messages.success(self.request, f'Arquivo "{form.instance.name}" atualizado com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.agent.pk})


class AgentFileDeleteView(LoginRequiredMixin, DeleteView):
    """
    View para deletar arquivos de contexto
    """
    model = AgentFile
    template_name = 'agents/files/delete.html'

    def get_queryset(self):
        return AgentFile.objects.filter(agent__owner=self.request.user.client)

    def get_success_url(self):
        return reverse_lazy('agents:agent_detail', kwargs={'pk': self.object.agent.pk})
    
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
