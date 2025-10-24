from django.core.management.base import BaseCommand

from agents.langgraph.knowledge import load_documents, split_documents


class Command(BaseCommand):
    help = "Cria o banco vetorial com os documentos"

    def handle(self, *args, **options):
        docs = load_documents(["docs/manual.pdf", "docs/politicas.txt"])
        chunks = split_documents(docs)
        create_vectorstore(chunks)
        self.stdout.write(self.style.SUCCESS("✅ Banco vetorial criado!"))
