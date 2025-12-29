from django import forms
from agents.models import Agent, AgentFile
from agents.patterns.factories.file_processors import FileProcessorFactory


class AgentForm(forms.ModelForm):
    """
    Formulário para criar e editar agents
    """

    class Meta:
        model = Agent
        fields = ['display_name', 'name', 'model',
                  'role', 'available_tools', 'input_context', 'steps',
                  'expectation', 'anti_hallucination_policies', 'applied_example',
                  'useful_default_messages', 'human_handoff_criteria',
                  'temperature', 'max_tokens', 'top_p', 'presence_penalty', 'frequency_penalty']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ex: Agent de Vendas, Suporte Técnico, Especialista em Ciclismo'
            }),
            'name': forms.Select(attrs={
                'class': 'form-select'
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ex: gemini-2.5-pro, gpt-4o-mini, claude-3-5-sonnet-20241022'
            }),
            # Campos RISE
            'role': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: Você é um assistente virtual especializado em atendimento ao cliente...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'available_tools': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: - Busca em arquivos de contexto\n- Consulta ao Google Calendar\n- Envio de PDFs...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'input_context': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: Analise cada mensagem do usuário e identifique a intenção principal...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'steps': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 8,
                'placeholder': 'Ex:\n1. Cumprimentar o usuário\n2. Identificar a necessidade\n3. Buscar informações relevantes...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'expectation': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: Respostas devem ser objetivas, claras e em português brasileiro...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'anti_hallucination_policies': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: ❌ NUNCA invente informações\n✅ Se não souber, seja honesto...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'applied_example': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 8,
                'placeholder': 'Ex:\nUsuário: "Oi, preciso de ajuda"\nAssistente: "Olá! Como posso ajudar você hoje?"...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'useful_default_messages': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex:\n- Saudação: "Olá! Como posso ajudar você hoje?"\n- Transferência: "Vou transferir você para um atendente humano..."...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'human_handoff_criteria': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex:\n- Emissão de nota fiscal\n- Dúvida quanto a medicação\n- Envio/Pedido do resultado do exame\n- Solicitação de relatório',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'temperature': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0',
                'max': '2'
            }),
            'max_tokens': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '8192'
            }),
            'top_p': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '1'
            }),
            'presence_penalty': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '-2',
                'max': '2'
            }),
            'frequency_penalty': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '-2',
                'max': '2'
            })
        }
        labels = {
            'display_name': 'Nome do Agent',
            'name': 'Provedor de IA',
            'model': 'Modelo',
            'role': 'Role',
            'available_tools': 'Available Tools',
            'input_context': 'Input',
            'steps': 'Steps',
            'expectation': 'Expectation',
            'anti_hallucination_policies': 'Anti-Hallucination Policies',
            'applied_example': 'Applied Example',
            'useful_default_messages': 'Useful Default Messages',
            'human_handoff_criteria': 'Critérios de Transferência Humana',
            'temperature': 'Temperatura',
            'max_tokens': 'Máximo de Tokens',
            'top_p': 'Top-p',
            'presence_penalty': 'Penalidade de Presença',
            'frequency_penalty': 'Penalidade de Frequência'
        }
        help_texts = {
            'display_name': 'Nome personalizado para identificar este agent (ex: "Suporte Técnico", "Vendedor Expert")',
            'name': 'Escolha o provedor de IA (OpenAI, Google DeepMind, Anthropic, etc)',
            'model': 'Nome específico do modelo (ex: gemini-2.5-pro para Google, gpt-4o-mini para OpenAI)',
            'role': 'Define quem é o assistente, sua identidade, expertise e personalidade',
            'available_tools': 'Lista e descrição das ferramentas e recursos disponíveis',
            'input_context': 'Como o assistente deve interpretar e processar as entradas',
            'steps': 'Passo a passo de como processar e responder às solicitações',
            'expectation': 'Formato de respostas, tom, estrutura e estilo esperados',
            'anti_hallucination_policies': 'Regras para evitar alucinações e limites do assistente',
            'applied_example': 'Exemplos práticos de interações e respostas',
            'useful_default_messages': 'Mensagens pré-definidas para situações comuns',
            'human_handoff_criteria': 'Situações em que o assistente deve transferir para atendimento humano (uma por linha iniciando com -)',
            'temperature': 'Controla criatividade (0.0 = conservador, 2.0 = criativo)',
            'max_tokens': 'Limite máximo de tokens na resposta',
            'top_p': 'Amostragem nuclear - controla diversidade da resposta',
            'presence_penalty': 'Penaliza repetição de tópicos (-2.0 a 2.0)',
            'frequency_penalty': 'Penaliza repetição de palavras (-2.0 a 2.0)'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Marca campos obrigatórios
        self.fields['display_name'].required = True
        self.fields['name'].required = True
        self.fields['model'].required = True

        # Campos RISE não são obrigatórios
        self.fields['role'].required = False
        self.fields['available_tools'].required = False
        self.fields['input_context'].required = False
        self.fields['steps'].required = False
        self.fields['expectation'].required = False
        self.fields['anti_hallucination_policies'].required = False
        self.fields['applied_example'].required = False
        self.fields['useful_default_messages'].required = False
        self.fields['human_handoff_criteria'].required = False

        # Os valores padrão são definidos na view AgentCreateView.get_initial()
        # Não precisamos definir aqui para evitar conflitos

    def clean_display_name(self):
        """
        Valida o nome de exibição
        """
        display_name = self.cleaned_data.get('display_name')

        if not display_name:
            raise forms.ValidationError('Nome do Agent é obrigatório')

        # Remove espaços
        display_name = display_name.strip()

        if len(display_name) < 3:
            raise forms.ValidationError('Nome do Agent deve ter pelo menos 3 caracteres')

        return display_name
    
    def clean_model(self):
        """
        Valida o nome do modelo
        """
        model = self.cleaned_data.get('model')

        if not model:
            raise forms.ValidationError('Nome do modelo é obrigatório')

        # Remove espaços
        model = model.strip()

        if len(model) < 3:
            raise forms.ValidationError('Nome do modelo deve ter pelo menos 3 caracteres')

        return model


class AgentSearchForm(forms.Form):
    """
    Formulário de busca para agents
    """
    search = forms.CharField(
        label='Buscar',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Buscar por nome, modelo ou instruções...',
            'autocomplete': 'off'
        })
    )

    provider = forms.ChoiceField(
        label='Provedor',
        choices=[('', 'Todos os provedores')] + list(Agent.PROVIDERS),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )


class AgentFileForm(forms.ModelForm):
    """
    Formulário para upload de arquivos de contexto
    """

    class Meta:
        model = AgentFile
        fields = ['name', 'file', 'usage_type', 'is_active']

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'ex: Manual do produto, FAQ, Políticas da empresa'
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.txt,.docx,.md,.csv,.json,.html'
            }),
            'usage_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

        labels = {
            'name': 'Nome do arquivo',
            'file': 'Arquivo',
            'usage_type': 'Tipo de Uso',
            'is_active': 'Ativo'
        }

        help_texts = {
            'name': 'Nome descritivo para identificar o arquivo',
            'file': 'Formatos suportados: PDF, TXT, DOCX, MD, CSV, JSON, HTML (máx. 5MB)',
            'usage_type': 'Define como o agente pode usar este arquivo',
            'is_active': 'Se desativado, o arquivo não será usado como contexto'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Marcar campos obrigatórios
        self.fields['name'].required = True

        # Arquivo é obrigatório apenas na criação, não na edição
        if 'file' in self.fields:
            self.fields['file'].required = not self.instance.pk
        
    def clean_file(self):
        """
        Valida o arquivo enviado
        """
        uploaded_file = self.cleaned_data.get('file')

        if not uploaded_file:
            return uploaded_file

        # Verificar tamanho (5MB)
        max_size = 5 * 1024 * 1024
        if uploaded_file.size > max_size:
            raise forms.ValidationError(f'Arquivo muito grande. Máximo permitido: {max_size / (1024*1024):.1f}MB')
        
        # Verificar extensão
        file_name = uploaded_file.name.lower()
        # Criar instância temporária apenas para obter extensões suportadas
        file_processor_factory = FileProcessorFactory()
        supported_extensions = file_processor_factory.get_supported_extensions()
        
        file_extension = None
        for ext in supported_extensions:
            if file_name.endswith(ext):
                file_extension = ext
                break
                
        if not file_extension:
            supported_list = ', '.join(supported_extensions)
            raise forms.ValidationError(f'Tipo de arquivo não suportado. Formatos aceitos: {supported_list}')
        
        return uploaded_file
    
    def clean_name(self):
        """
        Valida o nome do arquivo
        """
        name = self.cleaned_data.get('name')
        
        if not name:
            raise forms.ValidationError('Nome é obrigatório')
        
        # Remove espaços
        name = name.strip()
        
        if len(name) < 3:
            raise forms.ValidationError('Nome deve ter pelo menos 3 caracteres')

        return name

class GlobalSettingsForm(forms.ModelForm):
    """Form para editar configurações globais do sistema usando framework RISE."""

    class Meta:
        from .models import GlobalSettings
        model = GlobalSettings
        fields = [
            'role',
            'available_tools',
            'input_context',
            'steps',
            'expectation',
            'anti_hallucination_policies',
            'applied_example',
            'useful_default_messages',
        ]
        widgets = {
            'role': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: Você é um assistente virtual especializado em atendimento ao cliente...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'available_tools': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: - Busca em arquivos de contexto\n- Consulta ao Google Calendar\n- Envio de PDFs...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'input_context': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: Analise cada mensagem do usuário e identifique a intenção principal...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'steps': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 8,
                'placeholder': 'Ex:\n1. Cumprimentar o usuário\n2. Identificar a necessidade\n3. Buscar informações relevantes...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'expectation': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: Respostas devem ser objetivas, claras e em português brasileiro...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'anti_hallucination_policies': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex: ❌ NUNCA invente informações\n✅ Se não souber, seja honesto...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'applied_example': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 8,
                'placeholder': 'Ex:\nUsuário: "Oi, preciso de ajuda"\nAssistente: "Olá! Como posso ajudar você hoje?"...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
            'useful_default_messages': forms.Textarea(attrs={
                'class': 'form-control font-monospace',
                'rows': 6,
                'placeholder': 'Ex:\n- Saudação: "Olá! Como posso ajudar você hoje?"\n- Transferência: "Vou transferir você para um atendente humano..."...',
                'style': 'font-size: 14px; line-height: 1.6;'
            }),
        }
        labels = {
            'role': 'Role',
            'available_tools': 'Available Tools',
            'input_context': 'Input',
            'steps': 'Steps',
            'expectation': 'Expectation',
            'anti_hallucination_policies': 'Anti-Hallucination Policies',
            'applied_example': 'Applied Example',
            'useful_default_messages': 'Useful Default Messages',
        }
        help_texts = {
            'role': 'Define quem é o assistente, sua identidade, expertise e personalidade',
            'available_tools': 'Lista e descrição das ferramentas e recursos disponíveis',
            'input_context': 'Como o assistente deve interpretar e processar as entradas',
            'steps': 'Passo a passo de como processar e responder às solicitações',
            'expectation': 'Formato de respostas, tom, estrutura e estilo esperados',
            'anti_hallucination_policies': 'Regras para evitar alucinações e limites do assistente',
            'applied_example': 'Exemplos práticos de interações e respostas',
            'useful_default_messages': 'Mensagens pré-definidas para situações comuns',
        }
