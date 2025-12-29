"""
Script para adicionar políticas anti-alucinação ao Agent.

Execute com: python manage.py shell < add_anti_hallucination_policies.py
Ou: python add_anti_hallucination_policies.py (se configurar Django settings)
"""

ANTI_HALLUCINATION_TEXT = """
🚨 REGRAS CRÍTICAS SOBRE LINKS DE AGENDAMENTO

PROIBIDO - NUNCA FAÇA ISSO:
- ❌ NUNCA construa ou invente URLs manualmente (como "http://exemplo.com/agendar/...")
- ❌ NUNCA reutilize links de mensagens anteriores da conversa
- ❌ NUNCA invente tokens ou IDs de agendamento
- ❌ NUNCA diga que "enviou o link" sem ter chamado a ferramenta gerar_link_agendamento
- ❌ NUNCA copie e cole links de mensagens antigas

OBRIGATÓRIO - SEMPRE FAÇA ISSO:
- ✅ SEMPRE use a ferramenta gerar_link_agendamento para criar links
- ✅ SEMPRE chame a ferramenta novamente se o paciente pedir um novo link
- ✅ SEMPRE aguarde o retorno da ferramenta antes de enviar o link ao paciente
- ✅ SEMPRE verifique se a ferramenta foi executada com sucesso antes de confirmar

VERIFICAÇÃO ANTES DE ENVIAR LINK:
Antes de enviar qualquer link de agendamento, pergunte-se:
1. "Eu chamei a ferramenta gerar_link_agendamento NESTA mensagem?"
2. "O link veio do retorno da ferramenta?"
3. "Estou copiando um link de uma mensagem anterior?"

Se a resposta para 1 ou 2 for NÃO, ou para 3 for SIM, você está ALUCINANDO. PARE e chame a ferramenta.

EXEMPLO CORRETO:
Paciente: "Preciso de um link para agendar"
Você: [CHAMA gerar_link_agendamento]
Ferramenta retorna: "Link: https://..."
Você: "Aqui está o link: [link da ferramenta]"

EXEMPLO ERRADO:
Paciente: "Preciso de um link"
Você: "Aqui está: https://..." ❌ SEM chamar a ferramenta = ALUCINAÇÃO!

OUTRAS REGRAS:
- NUNCA invente números de telefone, emails ou endereços
- NUNCA confirme horários sem consultar ferramentas
- NUNCA invente informações que não tem
"""


def add_policies_to_agent(agent_name: str = None):
    """
    Adiciona ou atualiza políticas anti-alucinação no Agent.

    Args:
        agent_name: Nome do agent. Se None, adiciona em todos.
    """
    from agents.models import Agent

    if agent_name:
        agents = Agent.objects.filter(name=agent_name)
        if not agents.exists():
            print(f"❌ Agent '{agent_name}' não encontrado.")
            return
    else:
        agents = Agent.objects.all()

    for agent in agents:
        current_policies = agent.anti_hallucination_policies or ""

        # Verifica se já tem as políticas
        if "REGRAS CRÍTICAS SOBRE LINKS" in current_policies:
            print(f"⚠️  Agent '{agent.name}' já tem políticas anti-alucinação sobre links.")
            print("   Deseja sobrescrever? (s/n): ", end="")
            response = input().strip().lower()
            if response != 's':
                print(f"   Pulando '{agent.name}'...")
                continue

        # Adiciona ou sobrescreve
        if current_policies:
            agent.anti_hallucination_policies = current_policies + "\n\n" + ANTI_HALLUCINATION_TEXT
        else:
            agent.anti_hallucination_policies = ANTI_HALLUCINATION_TEXT

        agent.save()
        print(f"✅ Políticas adicionadas ao Agent '{agent.name}'")


def main():
    """Função principal."""
    print("=" * 80)
    print("ADICIONAR POLÍTICAS ANTI-ALUCINAÇÃO")
    print("=" * 80)
    print()
    print("Este script adiciona políticas anti-alucinação ao Agent.")
    print("As políticas impedem que a IA invente links de agendamento.")
    print()
    print("Opções:")
    print("1. Adicionar em TODOS os Agents")
    print("2. Adicionar em um Agent específico")
    print()
    print("Escolha uma opção (1 ou 2): ", end="")

    choice = input().strip()

    if choice == "1":
        add_policies_to_agent()
    elif choice == "2":
        print("Digite o nome do Agent: ", end="")
        agent_name = input().strip()
        add_policies_to_agent(agent_name)
    else:
        print("❌ Opção inválida.")

    print()
    print("=" * 80)
    print("Concluído!")
    print("=" * 80)


if __name__ == "__main__":
    # Configurar Django se necessário
    import os
    import django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'assistante.settings')
    django.setup()

    main()
