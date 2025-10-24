# dialog_test/nodes/__init__.py
"""
Módulo de agentes para o sistema de conversação LangGraph.

Cada agente é responsável por um domínio específico e cria suas próprias tools internamente:
- recepcao_agent: Atendimento inicial, coleta de dados do contato
- agenda_agent: Gerenciamento de agendamentos e calendário

Uso:
    from dialog_test.nodes import create_recepcao_node, create_agenda_node

    # Agentes criam suas próprias tools internamente
    recepcao_node = create_recepcao_node(contact)
    agenda_node = create_agenda_node(contact, client)
"""

from .secretary_agent import create_recepcao_node
from .calendar_agent import create_agenda_node

__all__ = [
    'create_recepcao_node',
    'create_agenda_node',
]
