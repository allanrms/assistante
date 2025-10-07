"""
Formulários do Dashboard
Implementa validações e interface de usuário para gerenciamento de instâncias
"""

from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from core.models import Client

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
