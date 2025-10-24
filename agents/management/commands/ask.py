from django.core.management.base import BaseCommand
from agents.langgraph.knowledge.retriever import ask


class Command(BaseCommand):
    help = "Faz perguntas ao RAG"

    def add_arguments(self, parser):
        parser.add_argument("question", type=str)

    def handle(self, *args, **options):
        question = options["question"]
        answer = ask(question)
        self.stdout.write(f"🧠 {answer}")
