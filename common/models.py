import uuid

from django.db import models
from simple_history.models import HistoricalRecords

class BaseUUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Metadados
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        abstract = True

# Create your models here.
class TimestampModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class HistoryMixinSave(object):

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


class HistoryBaseModel(HistoryMixinSave, models.Model):
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True
