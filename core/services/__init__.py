"""
Services layer para lógica de negócio.

Segue o princípio de Single Responsibility:
- Services contêm lógica de negócio
- Models contêm dados e comportamento básico
- Views/Tools apenas orquestram chamadas aos services
"""

from .appointment_service import AppointmentService

__all__ = ['AppointmentService']