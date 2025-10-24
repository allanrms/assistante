from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

def load_documents(paths):
    docs = []
    for path in paths:
        if path.endswith(".pdf"):
            loader = PyPDFLoader(path)
        else:
            loader = TextLoader(path, encoding="utf-8")
        docs.extend(loader.load())
    return docs

def split_documents(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    return splitter.split_documents(docs)