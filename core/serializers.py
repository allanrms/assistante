from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from .models import Client

User = get_user_model()


class ClientRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer para registro de novos clientes.
    Inclui criação do usuário e do perfil de cliente.
    """

    # Campos do usuário
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = Client
        fields = [
            'full_name',
            'email',
            'password',
            'password_confirm',
            'phone',
            'client_type',
            'company_name',
            'cnpj',
            'cpf',
            'billing_address',
            'billing_city',
            'billing_state',
            'billing_zip_code',
            'billing_country',
        ]
        extra_kwargs = {
            'phone': {'required': False},
            'company_name': {'required': False},
            'cnpj': {'required': False},
            'cpf': {'required': False},
            'billing_address': {'required': False},
            'billing_city': {'required': False},
            'billing_state': {'required': False},
            'billing_zip_code': {'required': False},
        }

    def validate_email(self, value):
        """
        Valida se o e-mail já não está em uso.
        """
        if Client.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _('Este e-mail já está cadastrado.')
            )
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                _('Este e-mail já está cadastrado.')
            )
        return value.lower()

    def validate_cpf(self, value):
        """
        Valida formato do CPF.
        """
        if value:
            # Remove caracteres não numéricos
            cpf = ''.join(filter(str.isdigit, value))
            if len(cpf) != 11:
                raise serializers.ValidationError(
                    _('CPF deve conter 11 dígitos.')
                )
            # Verifica se já existe
            if Client.objects.filter(cpf=value).exists():
                raise serializers.ValidationError(
                    _('Este CPF já está cadastrado.')
                )
        return value

    def validate_cnpj(self, value):
        """
        Valida formato do CNPJ.
        """
        if value:
            # Remove caracteres não numéricos
            cnpj = ''.join(filter(str.isdigit, value))
            if len(cnpj) != 14:
                raise serializers.ValidationError(
                    _('CNPJ deve conter 14 dígitos.')
                )
            # Verifica se já existe
            if Client.objects.filter(cnpj=value).exists():
                raise serializers.ValidationError(
                    _('Este CNPJ já está cadastrado.')
                )
        return value

    def validate(self, attrs):
        """
        Validações que envolvem múltiplos campos.
        """
        # Valida senhas
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': _('As senhas não conferem.')
            })

        # Valida senha usando validators do Django
        try:
            validate_password(attrs['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({
                'password': list(e.messages)
            })

        # Valida CPF para pessoa física
        if attrs.get('client_type') == 'individual' and not attrs.get('cpf'):
            raise serializers.ValidationError({
                'cpf': _('CPF é obrigatório para pessoa física.')
            })

        # Valida CNPJ para pessoa jurídica
        if attrs.get('client_type') == 'company' and not attrs.get('cnpj'):
            raise serializers.ValidationError({
                'cnpj': _('CNPJ é obrigatório para pessoa jurídica.')
            })

        # Valida razão social para pessoa jurídica
        if attrs.get('client_type') == 'company' and not attrs.get('company_name'):
            raise serializers.ValidationError({
                'company_name': _('Razão social é obrigatória para pessoa jurídica.')
            })

        return attrs

    def create(self, validated_data):
        """
        Cria o usuário e o perfil de cliente.
        """
        # Remove campos que não pertencem ao modelo Client
        password = validated_data.pop('password')
        validated_data.pop('password_confirm')

        # Cria o usuário
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=password,
            first_name=validated_data['full_name'].split()[0] if validated_data['full_name'] else '',
            last_name=' '.join(validated_data['full_name'].split()[1:]) if len(validated_data['full_name'].split()) > 1 else '',
        )

        # Cria o cliente
        client = Client.objects.create(
            user=user,
            **validated_data
        )

        return client


class ClientSerializer(serializers.ModelSerializer):
    """
    Serializer para exibição de dados do cliente.
    """

    class Meta:
        model = Client
        fields = [
            'id',
            'full_name',
            'email',
            'phone',
            'client_type',
            'company_name',
            'cnpj',
            'cpf',
            'billing_address',
            'billing_city',
            'billing_state',
            'billing_zip_code',
            'billing_country',
            'status',
            'email_confirmed',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'email_confirmed',
            'created_at',
            'updated_at',
        ]


class EmailConfirmationSerializer(serializers.Serializer):
    """
    Serializer para confirmação de e-mail.
    """
    token = serializers.CharField(required=True)

    def validate_token(self, value):
        """
        Valida se o token existe e é válido.
        """
        try:
            client = Client.objects.get(email_confirmation_token=value)
            if client.email_confirmed:
                raise serializers.ValidationError(
                    _('Este e-mail já foi confirmado.')
                )
            return value
        except Client.DoesNotExist:
            raise serializers.ValidationError(
                _('Token inválido ou expirado.')
            )
