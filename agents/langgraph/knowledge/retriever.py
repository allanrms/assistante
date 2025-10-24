from langchain_openai import ChatOpenAI

def get_rag_chain():
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    vectorstore = load_vectorstore()
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff"
    )
    return qa_chain


def ask(question):
    chain = get_rag_chain()
    response = chain.run(question)
    return response