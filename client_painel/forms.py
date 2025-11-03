"""
Formulários do Dashboard
Implementa validações e interface de usuário para gerenciamento de instâncias
"""

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from core.models import Client, Contact, Appointment, ScheduleConfig, WorkingDay, BlockedDay
from django.forms import inlineformset_factory

User = get_user_model()


class LoginForm(forms.Form):
    """
    Formulário de login do sistema
    """
    username = forms.CharField(
        label='Usuário',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite seu usuário',
            'autocomplete': 'username'
        })
    )

    password = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua senha',
            'autocomplete': 'current-password'
        })
    )


class UserProfileForm(forms.ModelForm):
    """
    Formulário para edição do perfil do usuário.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'preferred_language']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Sobrenome'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        labels = {
            'first_name': _('Nome'),
            'last_name': _('Sobrenome'),
            'preferred_language': _('Idioma Preferido')
        }


class ClientProfileForm(forms.ModelForm):
    """
    Formulário para edição dos dados do cliente.
    """
    class Meta:
        model = Client
        fields = [
            'full_name',
            'phone',
            'client_type',
            'cpf',
            'cnpj',
            'company_name',
            'billing_address',
            'billing_city',
            'billing_state',
            'billing_zip_code',
            'billing_country'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome Completo'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(00) 00000-0000'
            }),
            'client_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'cpf': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '000.000.000-00'
            }),
            'cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00.000.000/0000-00'
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Razão Social'
            }),
            'billing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Endereço completo'
            }),
            'billing_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cidade'
            }),
            'billing_state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UF',
                'maxlength': 2
            }),
            'billing_zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00000-000'
            }),
            'billing_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'BR'
            })
        }
        labels = {
            'full_name': _('Nome Completo'),
            'phone': _('Telefone'),
            'client_type': _('Tipo de Cliente'),
            'cpf': _('CPF'),
            'cnpj': _('CNPJ'),
            'company_name': _('Razão Social'),
            'billing_address': _('Endereço'),
            'billing_city': _('Cidade'),
            'billing_state': _('Estado (UF)'),
            'billing_zip_code': _('CEP'),
            'billing_country': _('País')
        }


class ChangePasswordForm(forms.Form):
    """
    Formulário para alteração de senha.
    """
    current_password = forms.CharField(
        label=_('Senha Atual'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua senha atual'
        })
    )
    new_password = forms.CharField(
        label=_('Nova Senha'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite a nova senha'
        }),
        help_text=_('Mínimo de 8 caracteres')
    )
    confirm_password = forms.CharField(
        label=_('Confirmar Nova Senha'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirme a nova senha'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password and new_password != confirm_password:
            raise forms.ValidationError(_('As senhas não conferem.'))

        return cleaned_data


class AppointmentForm(forms.ModelForm):
    """
    Formulário para criação e edição de consultas/appointments.
    """
    # Campo extra para buscar/criar contato por telefone ou nome
    contact_search = forms.CharField(
        label=_('Paciente'),
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome ou telefone do paciente',
            'id': 'contactSearch'
        }),
        help_text=_('Digite o nome ou telefone do paciente')
    )

    class Meta:
        model = Appointment
        fields = ['contact', 'date', 'time']
        widgets = {
            'contact': forms.Select(attrs={
                'class': 'form-select',
                'id': 'contactSelect'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            })
        }
        labels = {
            'contact': _('Paciente'),
            'date': _('Data'),
            'time': _('Horário')
        }

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra contatos por cliente
        if client:
            self.fields['contact'].queryset = Contact.objects.filter(client=client)

        # Se está editando, preenche o contact_search com o nome do contato
        if self.instance and self.instance.pk and self.instance.contact:
            self.fields['contact_search'].initial = (
                self.instance.contact.name or self.instance.contact.phone_number
            )


class ScheduleConfigForm(forms.ModelForm):
    """
    Formulário para configuração geral da agenda.
    """
    class Meta:
        model = ScheduleConfig
        fields = ['appointment_duration']
        widgets = {
            'appointment_duration': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        labels = {
            'appointment_duration': _('Duração Padrão das Consultas')
        }


class WorkingDayForm(forms.ModelForm):
    """
    Formulário para configuração de dias de atendimento.
    """
    class Meta:
        model = WorkingDay
        fields = ['weekday', 'is_active', 'start_time', 'end_time', 'lunch_start_time', 'lunch_end_time']
        widgets = {
            'weekday': forms.Select(attrs={
                'class': 'form-select'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'lunch_start_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'lunch_end_time': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            })
        }
        labels = {
            'weekday': _('Dia da Semana'),
            'is_active': _('Ativo'),
            'start_time': _('Horário de Início'),
            'end_time': _('Horário de Término'),
            'lunch_start_time': _('Início do Almoço'),
            'lunch_end_time': _('Término do Almoço')
        }
        help_texts = {
            'is_active': _('Se desativado, não haverá atendimento neste dia'),
            'lunch_start_time': _('Opcional'),
            'lunch_end_time': _('Opcional')
        }


class BlockedDayForm(forms.ModelForm):
    """
    Formulário para bloqueio de dias específicos.
    """
    class Meta:
        model = BlockedDay
        fields = ['date', 'reason']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'reason': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Feriado, Férias, etc.'
            })
        }
        labels = {
            'date': _('Data'),
            'reason': _('Motivo')
        }


# Formset para WorkingDays (permite editar múltiplos dias de uma vez)
WorkingDayFormSet = inlineformset_factory(
    ScheduleConfig,
    WorkingDay,
    form=WorkingDayForm,
    extra=0,
    can_delete=True,
    min_num=0,
    max_num=7  # Máximo 7 dias da semana
)

# Formset para BlockedDays
BlockedDayFormSet = inlineformset_factory(
    ScheduleConfig,
    BlockedDay,
    form=BlockedDayForm,
    extra=1,
    can_delete=True
)
