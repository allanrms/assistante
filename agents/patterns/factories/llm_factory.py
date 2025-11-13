"""
Factory para criação de LLMs e Embeddings.

Seguindo melhores práticas da documentação LangChain:
- Configurações consistentes (timeout, max_retries)
- Validação de parâmetros
- Type hints apropriados
- Logs estruturados
- Tratamento de erros robusto
"""

from uuid import UUID
from typing import List, Optional

from django.conf import settings
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from agents.models import Agent


class PaddedEmbeddings(Embeddings):
    """
    Wrapper para embeddings que adiciona padding com zeros para atingir dimensão alvo.

    Usado para permitir embeddings de diferentes dimensões no mesmo banco de dados pgvector.
    - Google: 768 dims → 1536 dims (padding com zeros)
    - OpenAI: 1536 dims → 1536 dims (sem padding)
    """

    def __init__(self, base_embeddings: Embeddings, target_dim: int = 1536, provider: str = 'openai'):
        """
        Args:
            base_embeddings: Embedding base (OpenAI ou Google)
            target_dim: Dimensão alvo (padrão: 1536 para compatibilidade com banco)
            provider: Nome do provider ('openai' ou 'google')
        """
        self.base_embeddings = base_embeddings
        self.target_dim = target_dim
        self.provider = provider

    def _pad_vector(self, vector: List[float]) -> List[float]:
        """Adiciona padding com zeros se necessário"""
        current_dim = len(vector)
        if current_dim < self.target_dim:
            # Adicionar zeros ao final
            padding = [0.0] * (self.target_dim - current_dim)
            return vector + padding
        return vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeda múltiplos documentos com padding"""
        vectors = self.base_embeddings.embed_documents(texts)
        return [self._pad_vector(v) for v in vectors]

    def embed_query(self, text: str) -> List[float]:
        """Embeda uma query com padding"""
        vector = self.base_embeddings.embed_query(text)
        return self._pad_vector(vector)

class LLMFactory:
    """Factory para criação dinâmica de agentes LangChain.

    Cria LLMs, Embeddings e Agentes completos baseados na configuração
    do modelo Agent do Django. Suporta múltiplos providers:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude)
    - Google (Gemini)

    Attributes:
        agent: Configuração do Agent (Django model)
        contact_id: ID do contato (opcional)
        tools_factory: Factory de ferramentas (opcional)
        evolution_instance: Instância Evolution (opcional)
        llm: Modelo LLM criado
        embeddings: Modelo de embeddings criado
        tools: Lista de ferramentas
        langchain_agent: Agente LangChain completo

    Example:
        >>> from agents.models import Agent
        >>> agent_config = Agent.objects.get(name="google")
        >>> factory = LLMFactory(agent=agent_config)
        >>> response = factory.llm.invoke("Hello!")
    """

    def __init__(
        self,
        agent: Agent,
        contact_id: Optional[UUID] = None,
        tools_factory: Optional[callable] = None,
        evolution_instance: Optional[object] = None,
        create_agent: bool = True
    ):
        """Inicializa factory e cria todos os componentes.

        Args:
            agent: Configuração do modelo LLM (Django Agent model)
            contact_id: ID do contato para injetar nas ferramentas
            tools_factory: Função que cria ferramentas (ex: create_reception_tools)
            evolution_instance: Instância Evolution para envio de mensagens/arquivos
            create_agent: Se False, apenas cria LLM e embeddings (útil para tasks)

        Raises:
            Exception: Se houver erro na criação de qualquer componente
        """
        print(f"🏭 [Factory] Inicializando LLMFactory para agent: {agent.name}")

        try:
            self.agent = agent
            self.contact_id = contact_id
            self.tools_factory = tools_factory
            self.evolution_instance = evolution_instance

            # Criar componentes na ordem correta
            self.llm = self._create_llm()
            self.embeddings = self._create_embeddings()

            # Criar tools e agent apenas se necessário
            if create_agent:
                self.tools = self._create_tools()
            else:
                self.tools = []
                self.langchain_agent = None
                print(f"⚠️  [Factory] Modo simplificado (apenas LLM + Embeddings)")

            print(f"✅ [Factory] Inicialização completa!")

        except Exception as e:
            print(f"❌ [Factory] Erro ao inicializar: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e

    def _create_llm(self) -> BaseChatModel:
        """Cria modelo LLM com configurações robustas.

        Aplica configurações consistentes para todos os providers:
        - timeout: 30 segundos (evita travamentos)
        - max_retries: 2 tentativas (resiliência)
        - Validação de parâmetros

        Returns:
            BaseChatModel: LLM configurado (OpenAI, Anthropic ou Google)

        Raises:
            ValueError: Se configuração do agent for inválida
        """
        provider = self.agent.name.lower() if self.agent.name else ""
        model_name = self.agent.model or ""

        # Validações básicas
        if not model_name:
            print(f"⚠️  [LLM] Modelo não especificado, usando defaults")

        # Parâmetros comuns para todos os modelos
        common_params = {
            "temperature": self.agent.temperature if hasattr(self.agent, 'temperature') else 0.5,
            "timeout": 30.0,  # 30 segundos de timeout
            "max_retries": 2,  # Até 2 tentativas em caso de falha
        }

        print(f"🤖 [LLM] Criando: {provider.title()} - Modelo: {model_name}")
        print(f"⚙️  [LLM] Config: temp={common_params['temperature']}, timeout={common_params['timeout']}s, retries={common_params['max_retries']}")

        if provider == "openai":
            return ChatOpenAI(
                model=model_name or "gpt-4o",
                temperature=common_params["temperature"],
                max_tokens=self.agent.max_tokens if hasattr(self.agent, 'max_tokens') and self.agent.max_tokens else 2000,
                top_p=self.agent.top_p if hasattr(self.agent, 'top_p') else 1.0,
                presence_penalty=self.agent.presence_penalty if hasattr(self.agent, 'presence_penalty') else 0.0,
                frequency_penalty=self.agent.frequency_penalty if hasattr(self.agent, 'frequency_penalty') else 0.0,
                timeout=common_params["timeout"],
                max_retries=common_params["max_retries"],
                api_key=getattr(settings, 'OPENAI_API_KEY', '')
            )

        elif provider == "anthropic":
            return ChatAnthropic(
                model=model_name or "claude-3-5-sonnet-20241022",
                temperature=common_params["temperature"],
                max_tokens=self.agent.max_tokens if hasattr(self.agent, 'max_tokens') and self.agent.max_tokens else 4096,
                top_p=self.agent.top_p if hasattr(self.agent, 'top_p') else 1.0,
                timeout=common_params["timeout"],
                max_retries=common_params["max_retries"],
                api_key=getattr(settings, 'ANTHROPIC_API_KEY', '')
            )

        elif provider == "google":
            return ChatGoogleGenerativeAI(
                model=model_name or "gemini-2.0-flash-exp",
                temperature=common_params["temperature"],
                max_tokens=self.agent.max_tokens if hasattr(self.agent, 'max_tokens') and self.agent.max_tokens else 1000,
                top_p=self.agent.top_p if hasattr(self.agent, 'top_p') else 1.0,
                timeout=common_params["timeout"],
                max_retries=common_params["max_retries"],
                google_api_key=getattr(settings, 'GOOGLE_API_KEY', '')
            )

        else:
            # Fallback para OpenAI
            print(f"⚠️  [LLM] Provider desconhecido '{provider}', usando OpenAI como fallback")
            return ChatOpenAI(
                model=model_name or "gpt-4o",
                temperature=common_params["temperature"],
                max_tokens=2000,
                timeout=common_params["timeout"],
                max_retries=common_params["max_retries"],
                api_key=getattr(settings, 'OPENAI_API_KEY', '')
            )

    def _create_embeddings(self) -> PaddedEmbeddings:
        """Cria modelo de Embeddings com dimensão padronizada.

        O banco usa dimensão fixa de 1536 (compatibilidade pgvector):
        - OpenAI: 1536 dims nativo (sem padding necessário)
        - Google: 768 dims → 1536 dims (padding automático)
        - Anthropic: Usa OpenAI embeddings como padrão

        Returns:
            PaddedEmbeddings: Embeddings configurado com padding automático

        Note:
            O wrapper PaddedEmbeddings adiciona zeros automaticamente
            se a dimensão for menor que 1536.
        """
        provider = self.agent.name.lower() if self.agent.name else ""

        print(f"🔢 [Embeddings] Criando para provider: {provider.title()}")

        if provider == "google":
            print(f"📊 [Embeddings] Google: 768 dims → 1536 (com padding)")
            try:
                base_embeddings = GoogleGenerativeAIEmbeddings(
                    model="models/embedding-001",
                    google_api_key=getattr(settings, 'GOOGLE_API_KEY', '')
                )
                return PaddedEmbeddings(base_embeddings, target_dim=1536, provider='google')
            except Exception as e:
                print(f"⚠️  [Embeddings] Erro ao criar Google Embeddings: {str(e)}")
                print(f"⚠️  [Embeddings] Fallback para OpenAI")
                # Fallback para OpenAI
                base_embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=getattr(settings, 'OPENAI_API_KEY', '')
                )
                return PaddedEmbeddings(base_embeddings, target_dim=1536, provider='openai')
        else:
            # OpenAI como padrão (openai, anthropic, outros)
            print(f"📊 [Embeddings] OpenAI: 1536 dims (nativo)")
            try:
                base_embeddings = OpenAIEmbeddings(
                    model="text-embedding-3-small",
                    api_key=getattr(settings, 'OPENAI_API_KEY', '')
                )
                return PaddedEmbeddings(base_embeddings, target_dim=1536, provider='openai')
            except Exception as e:
                print(f"❌ [Embeddings] Erro ao criar OpenAI Embeddings: {str(e)}")
                raise

    def _create_tools(self):
        """
        Cria ferramentas disponíveis para o agente.
        Se tools_factory foi fornecido, usa ele. Caso contrário, retorna lista vazia.

        Returns:
            Lista de ferramentas LangChain
        """
        if self.tools_factory and self.contact_id:
            # Usar factory personalizado (ex: create_reception_tools)
            evolution_instance_id = self.evolution_instance.id if self.evolution_instance else None

            tools = self.tools_factory(
                contact_id=self.contact_id,
                # evolution_instance_id=evolution_instance_id
            )

            return tools
        else:
            print('⚠️ Nenhuma ferramenta criada (tools_factory ou contact_id não fornecidos)')
            return []

