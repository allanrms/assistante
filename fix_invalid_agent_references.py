#!/usr/bin/env python
"""
Script para corrigir referências inválidas de agent_id em EvolutionInstance.

Este script deve ser executado ANTES de rodar as migrations em produção
se você estiver encontrando o erro:

django.db.utils.IntegrityError: insert or update on table
"whatsapp_connector_evolutioninstance" violates foreign key constraint
"whatsapp_connector_e_llm_config_id_c6aa64e2_fk_agents_ag"

Uso:
    python fix_invalid_agent_references.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'assistante.settings')
django.setup()

from django.db import connection
from whatsapp_connector.models import EvolutionInstance
from agents.models import Agent


def fix_invalid_references():
    """
    Corrige referências inválidas de agent_id que não existem na tabela agents_agent.
    """
    print("=" * 60)
    print("Script de Correção de Referências Inválidas")
    print("=" * 60)
    print()

    # Verificar se a coluna ainda se chama llm_config_id ou já foi renomeada para agent_id
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='whatsapp_connector_evolutioninstance'
            AND (column_name='llm_config_id' OR column_name='agent_id');
        """)
        columns = cursor.fetchall()

        if not columns:
            print("❌ Nenhuma coluna agent_id ou llm_config_id encontrada")
            print("   Certifique-se de que as tabelas existem no banco de dados")
            return False

        column_name = columns[0][0]
        print(f"📌 Coluna encontrada: {column_name}")
        print()

    # Pegar todos os IDs válidos de agents
    valid_agent_ids = set(Agent.objects.values_list('id', flat=True))
    print(f"✅ {len(valid_agent_ids)} agent(s) válido(s) encontrado(s) no banco")
    print()

    # Buscar EvolutionInstances
    total_instances = EvolutionInstance.objects.count()
    print(f"📊 Total de EvolutionInstances: {total_instances}")

    # Buscar instâncias com agent_id não-nulo
    instances_with_agent = EvolutionInstance.objects.exclude(agent_id__isnull=True)
    print(f"📊 Instâncias com agent configurado: {instances_with_agent.count()}")

    # Buscar EvolutionInstances com agent_id inválido
    invalid_instances = EvolutionInstance.objects.exclude(
        agent_id__in=valid_agent_ids
    ).exclude(agent_id__isnull=True)

    count = invalid_instances.count()
    print()

    if count > 0:
        print(f"⚠️  ENCONTRADAS {count} INSTÂNCIA(S) COM AGENT_ID INVÁLIDO:")
        print()

        for instance in invalid_instances:
            print(f"   - ID: {instance.id}")
            print(f"     Nome: {instance.name}")
            print(f"     Agent ID inválido: {instance.agent_id}")
            print()

        # Perguntar confirmação
        response = input("Deseja corrigir essas instâncias definindo agent_id como NULL? (s/n): ")

        if response.lower() in ['s', 'sim', 'y', 'yes']:
            # Executar correção diretamente no banco usando SQL
            with connection.cursor() as cursor:
                # Preparar lista de IDs inválidos
                invalid_ids = [str(inst.id) for inst in invalid_instances]

                if invalid_ids:
                    cursor.execute(f"""
                        UPDATE whatsapp_connector_evolutioninstance
                        SET {column_name} = NULL
                        WHERE id IN ({','.join("'" + id + "'" for id in invalid_ids)});
                    """)

                    affected = cursor.rowcount
                    print()
                    print(f"✅ {affected} instância(s) corrigida(s) com sucesso!")
                    print()
                    return True
        else:
            print()
            print("❌ Operação cancelada pelo usuário")
            print()
            return False
    else:
        print("✅ NENHUMA REFERÊNCIA INVÁLIDA ENCONTRADA!")
        print("   Seu banco de dados está OK para executar as migrations")
        print()
        return True


if __name__ == '__main__':
    try:
        success = fix_invalid_references()

        if success:
            print("=" * 60)
            print("PRÓXIMO PASSO:")
            print("Agora você pode executar as migrations com segurança:")
            print("    python manage.py migrate")
            print("=" * 60)
            sys.exit(0)
        else:
            sys.exit(1)

    except Exception as e:
        print()
        print("❌ ERRO DURANTE A EXECUÇÃO:")
        print(f"   {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)
