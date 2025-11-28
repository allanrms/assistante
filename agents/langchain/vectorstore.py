import uuid
from langchain_postgres import PGVector
from langchain_openai import OpenAIEmbeddings
from django.conf import settings

from agents.models import LangchainCollection

# Conexão com PostgreSQL usando psycopg3
CONNECTION_STRING = (
    f"postgresql+psycopg://{settings.DATABASES['default']['USER']}:"
    f"{settings.DATABASES['default']['PASSWORD']}@"
    f"{settings.DATABASES['default']['HOST']}:"
    f"{settings.DATABASES['default']['PORT']}/"
    f"{settings.DATABASES['default']['NAME']}"
)


def get_vectorstore(collection_name: str):
    """
    Retorna instância do PGVector vectorstore.

    Args:
        collection_name: Nome da coleção no PGVector
    """
    embeddings = OpenAIEmbeddings()

    return PGVector(
        embeddings=embeddings,
        collection_name=collection_name,
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )


def get_vectorstore_for_agent(agent):
    """
    Retorna o vectorstore para um Agent específico.
    Se o agent não tem collection_uuid, cria uma nova coleção.

    Args:
        agent: Instância do Agent model

    Returns:
        tuple: (vectorstore, collection_uuid ou collection_name)
    """

    # Se já tem collection_uuid, usar o nome da coleção existente
    if agent.collection_uuid:
        collection = LangchainCollection.objects.filter(uuid=agent.collection_uuid).first()
        if collection:
            return get_vectorstore(collection.name), agent.collection_uuid

    # Criar nova coleção com nome baseado no agent
    collection_name = f"agent_{agent.id}_{uuid.uuid4().hex[:8]}"
    vectorstore = get_vectorstore(collection_name)

    # O PGVector cria a coleção automaticamente ao adicionar documentos
    # Precisamos buscar o UUID depois de criada
    return vectorstore, collection_name


def get_collection_uuid_by_name(collection_name: str):
    """
    Busca o UUID de uma coleção pelo nome.

    Args:
        collection_name: Nome da coleção

    Returns:
        UUID da coleção ou None
    """
    collection = LangchainCollection.objects.filter(name=collection_name).first()
    return collection.uuid if collection else None


def get_retriever_for_agent(agent, search_type: str = "similarity", k: int = 4):
    """
    Retorna um retriever para um Agent específico.

    Args:
        agent: Instância do Agent model
        search_type: Tipo de busca (similarity, mmr)
        k: Número de documentos a retornar

    Returns:
        Retriever ou None se não houver coleção configurada
    """

    if not hasattr(agent, 'collection_name') or not agent.collection_name:
        # Retorna None se não houver coleção configurada (permite que o agente funcione sem busca vetorial)
        return None

    vectorstore = get_vectorstore(agent.collection_name)
    return vectorstore.as_retriever(
        search_type=search_type,
        search_kwargs={"k": k}
    )