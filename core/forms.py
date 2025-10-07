from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Client

User = get_user_model()


class ClientRegistrationForm(forms.ModelForm):
    """
    Formulário de registro de cliente.
    """

    # Campos de senha
    password = forms.CharField(
        label=_('Senha'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Digite sua senha',
        }),
        help_text=_('Mínimo de 8 caracteres')
    )
    password_confirm = forms.CharField(
        label=_('Confirmar Senha'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirme sua senha',
        })
    )

    # Checkbox de termos
    accept_terms = forms.BooleanField(
        label=_('Li e aceito os termos de uso'),
        required=True,
        error_messages={
            'required': _('Você precisa aceitar os termos de uso para continuar.')
        }
    )

    class Meta:
        model = Client
        fields = [
            'full_name',
            'email',
            'phone',
            'client_type',
            'cpf',
            'cnpj',
            'company_name',
            'billing_address',
            'billing_city',
            'billing_state',
            'billing_zip_code',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nome completo',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'seu@email.com',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(00) 00000-0000',
            }),
            'client_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'cpf': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '000.000.000-00',
            }),
            'cnpj': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00.000.000/0000-00',
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Razão Social da Empresa',
            }),
            'billing_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Endereço completo',
            }),
            'billing_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cidade',
            }),
            'billing_state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'UF',
                'maxlength': 2,
            }),
            'billing_zip_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00000-000',
            }),
        }
        labels = {
            'full_name': _('Nome Completo'),
            'email': _('E-mail'),
            'phone': _('Telefone'),
            'client_type': _('Tipo de Cliente'),
            'cpf': _('CPF'),
            'cnpj': _('CNPJ'),
            'company_name': _('Razão Social'),
            'billing_address': _('Endereço'),
            'billing_city': _('Cidade'),
            'billing_state': _('Estado (UF)'),
            'billing_zip_code': _('CEP'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Campos opcionais inicialmente
        self.fields['phone'].required = False
        self.fields['cpf'].required = False
        self.fields['cnpj'].required = False
        self.fields['company_name'].required = False
        self.fields['billing_address'].required = False
        self.fields['billing_city'].required = False
        self.fields['billing_state'].required = False
        self.fields['billing_zip_code'].required = False

    def clean_email(self):
        """Valida se o e-mail já não está em uso."""
        email = self.cleaned_data.get('email', '').lower()

        if Client.objects.filter(email=email).exists():
            raise ValidationError(_('Este e-mail já está cadastrado.'))

        if User.objects.filter(email=email).exists():
            raise ValidationError(_('Este e-mail já está cadastrado.'))

        return email

    def clean_cpf(self):
        """Valida formato do CPF."""
        cpf = self.cleaned_data.get('cpf', '')

        if cpf:
            # Remove caracteres não numéricos
            cpf_digits = ''.join(filter(str.isdigit, cpf))
            if len(cpf_digits) != 11:
                raise ValidationError(_('CPF deve conter 11 dígitos.'))

            # Verifica se já existe
            if Client.objects.filter(cpf=cpf).exists():
                raise ValidationError(_('Este CPF já está cadastrado.'))

        return cpf

    def clean_cnpj(self):
        """Valida formato do CNPJ."""
        cnpj = self.cleaned_data.get('cnpj', '')

        if cnpj:
            # Remove caracteres não numéricos
            cnpj_digits = ''.join(filter(str.isdigit, cnpj))
            if len(cnpj_digits) != 14:
                raise ValidationError(_('CNPJ deve conter 14 dígitos.'))

            # Verifica se já existe
            if Client.objects.filter(cnpj=cnpj).exists():
                raise ValidationError(_('Este CNPJ já está cadastrado.'))

        return cnpj

    def clean_password_confirm(self):
        """Valida se as senhas conferem."""
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')

        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError(_('As senhas não conferem.'))

        return password_confirm

    def clean(self):
        """Validações que envolvem múltiplos campos."""
        cleaned_data = super().clean()
        client_type = cleaned_data.get('client_type')
        cpf = cleaned_data.get('cpf')
        cnpj = cleaned_data.get('cnpj')
        company_name = cleaned_data.get('company_name')
        password = cleaned_data.get('password')

        # Valida senha usando validators do Django
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                self.add_error('password', e)

        # Valida CPF para pessoa física
        if client_type == 'individual' and not cpf:
            self.add_error('cpf', _('CPF é obrigatório para pessoa física.'))

        # Valida CNPJ e razão social para pessoa jurídica
        if client_type == 'company':
            if not cnpj:
                self.add_error('cnpj', _('CNPJ é obrigatório para pessoa jurídica.'))
            if not company_name:
                self.add_error('company_name', _('Razão social é obrigatória para pessoa jurídica.'))

        return cleaned_data

    def save(self, commit=True):
        """Cria o cliente e depois o usuário associado."""
        # Salva o cliente primeiro
        client = super().save(commit=commit)

        # Cria o usuário associado ao cliente (inativo até confirmar email)
        user = User.objects.create_user(
            username=client.email,
            email=client.email,
            password=self.cleaned_data['password'],
            first_name=client.full_name.split()[0] if client.full_name else '',
            last_name=' '.join(client.full_name.split()[1:]) if len(client.full_name.split()) > 1 else '',
            client=client,  # Associa o cliente ao usuário
            is_active=False,  # Inativo até confirmar email
            email_confirmed=False
        )

        return user  # Retorna o user para poder gerar token


class OTPVerificationForm(forms.Form):
    """
    Formulário de verificação de código OTP.
    """
    otp_code = forms.CharField(
        label=_('Código de Verificação'),
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '000000',
            'autofocus': True,
            'autocomplete': 'off',
        }),
        help_text=_('Digite o código de 6 dígitos enviado para seu e-mail')
    )

    def clean_otp_code(self):
        """Valida se o código contém apenas dígitos."""
        otp_code = self.cleaned_data.get('otp_code', '')

        if not otp_code.isdigit():
            raise ValidationError(_('O código deve conter apenas números.'))

        return otp_code
