from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0004_remove_use_multi_agent_field'),
    ]

    operations = [
        CreateExtension('vector'),
    ]
