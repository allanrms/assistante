# Generated manually to fix data integrity issues

from django.db import migrations


def fix_invalid_agent_references(apps, schema_editor):
    """
    Remove referências inválidas de agent_id que não existem na tabela agents_agent.
    Isso resolve o erro de IntegrityError quando há EvolutionInstances apontando
    para Agents que foram deletados.
    """
    EvolutionInstance = apps.get_model('whatsapp_connector', 'EvolutionInstance')
    Agent = apps.get_model('agents', 'Agent')

    # Pegar todos os IDs válidos de agents
    valid_agent_ids = set(Agent.objects.values_list('id', flat=True))

    # Buscar EvolutionInstances com agent_id inválido
    invalid_instances = EvolutionInstance.objects.exclude(
        agent_id__in=valid_agent_ids
    ).exclude(agent_id__isnull=True)

    count = invalid_instances.count()

    if count > 0:
        print(f"⚠️  Encontradas {count} instância(s) Evolution com agent_id inválido")
        print(f"   Definindo agent_id como NULL para essas instâncias...")

        # Definir agent_id como NULL para instâncias com referência inválida
        invalid_instances.update(agent_id=None)

        print(f"✅ {count} instância(s) corrigida(s) com sucesso")
    else:
        print("✅ Nenhuma referência inválida encontrada")


def reverse_func(apps, schema_editor):
    # Não há como reverter essa migração de dados
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('whatsapp_connector', '0005_alter_evolutioninstance_agent_and_more'),
        ('agents', '0009_remove_longtermmemory_source_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_invalid_agent_references, reverse_func),
    ]
