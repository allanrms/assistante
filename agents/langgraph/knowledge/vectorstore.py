from django.db import models
from langchain_openai import OpenAIEmbeddings

from agents.models import AgentDocument


def create_agent_vectorstore(agent_id, docs):
    embeddings = OpenAIEmbeddings()
    persist_dir = f"./vector_db/{agent_id}"
    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=persist_dir
    )
    vectorstore.persist()
    return vectorstore


def load_agent_vectorstore(agent_id):
    embeddings = OpenAIEmbeddings()
    persist_dir = f"./vector_db/{agent_id}"
    return Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )


def vectorize_texts(agent, texts, metadatas=None):
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")
    vectors = embeddings_model.embed_documents(texts)

    for text, vector, meta in zip(texts, vectors, metadatas or [{}]*len(texts)):
        AgentDocument.objects.create(
            agent=agent,
            content=text,
            metadata=meta,
            embedding=vector
        )

def retrieve_similar_docs(agent, query, top_k=3):
    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")
    query_vec = embeddings_model.embed_query(query)

    # Usa operador <-> (distância euclidiana)
    docs = (
        AgentDocument.objects
        .filter(agent=agent)
        .order_by(models.F("embedding").l2_distance(query_vec))
    )[:top_k]

    return list(docs)