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


@register.filter
def weekday_name(date):
    """
    Retorna o nome do dia da semana em português abreviado.
    Usage: {{ some_date|weekday_name }}
    """
    weekday_names = {
        0: 'SEG',  # Segunda-feira
        1: 'TER',  # Terça-feira
        2: 'QUA',  # Quarta-feira
        3: 'QUI',  # Quinta-feira
        4: 'SEX',  # Sexta-feira
        5: 'SÁB',  # Sábado
        6: 'DOM',  # Domingo
    }
    try:
        return weekday_names.get(date.weekday(), '')
    except (AttributeError, TypeError):
        return ''


@register.filter
def weekday_full_name(date):
    """
    Retorna o nome completo do dia da semana em português.
    Usage: {{ some_date|weekday_full_name }}
    """
    weekday_names = {
        0: 'Segunda-feira',
        1: 'Terça-feira',
        2: 'Quarta-feira',
        3: 'Quinta-feira',
        4: 'Sexta-feira',
        5: 'Sábado',
        6: 'Domingo',
    }
    try:
        return weekday_names.get(date.weekday(), '')
    except (AttributeError, TypeError):
        return ''


@register.filter
def month_name(date):
    """
    Retorna o nome do mês em português.
    Usage: {{ some_date|month_name }}
    """
    month_names = {
        1: 'janeiro',
        2: 'fevereiro',
        3: 'março',
        4: 'abril',
        5: 'maio',
        6: 'junho',
        7: 'julho',
        8: 'agosto',
        9: 'setembro',
        10: 'outubro',
        11: 'novembro',
        12: 'dezembro',
    }
    try:
        return month_names.get(date.month, '')
    except (AttributeError, TypeError):
        return ''
