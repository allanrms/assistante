from django import template
from datetime import timedelta

register = template.Library()


@register.filter
def add_days(value, days):
    """
    Adiciona dias a uma data.
    Usage: {{ some_date|add_days:3 }}
    """
    try:
        days = int(days)
        return value + timedelta(days=days)
    except (ValueError, TypeError):
        return value
