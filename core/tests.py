from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Client

User = get_user_model()


class ClientModelTest(TestCase):
    """
    Testes para o modelo Client.
    """

    def setUp(self):
        """
        Setup inicial para os testes.
        """
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpassword123'
        )

    def test_create_client_individual(self):
        """
        Testa criação de cliente pessoa física.
        """
        client = Client.objects.create(
            user=self.user,
            full_name='João Silva',
            email='test@example.com',
            client_type='individual',
            cpf='12345678901'
        )

        self.assertEqual(client.full_name, 'João Silva')
        self.assertEqual(client.email, 'test@example.com')
        self.assertEqual(client.client_type, 'individual')
        self.assertEqual(client.status, 'pending')
        self.assertFalse(client.email_confirmed)

    def test_create_client_company(self):
        """
        Testa criação de cliente pessoa jurídica.
        """
        client = Client.objects.create(
            user=self.user,
            full_name='Empresa LTDA',
            email='test@example.com',
            client_type='company',
            cnpj='12345678901234',
            company_name='Empresa LTDA'
        )

        self.assertEqual(client.client_type, 'company')
        self.assertEqual(client.cnpj, '12345678901234')
        self.assertEqual(client.company_name, 'Empresa LTDA')

    def test_confirm_email(self):
        """
        Testa confirmação de e-mail.
        """
        client = Client.objects.create(
            user=self.user,
            full_name='João Silva',
            email='test@example.com',
            client_type='individual',
            cpf='12345678901'
        )

        # Gera token e confirma
        token = client.generate_confirmation_token()
        self.assertIsNotNone(token)
        self.assertIsNotNone(client.email_confirmation_token)

        client.confirm_email()

        self.assertTrue(client.email_confirmed)
        self.assertEqual(client.status, 'active')
        self.assertIsNone(client.email_confirmation_token)


class ClientRegistrationAPITest(APITestCase):
    """
    Testes para o endpoint de registro de clientes.
    """

    def test_register_client_individual_success(self):
        """
        Testa registro de cliente pessoa física com sucesso.
        """
        data = {
            'full_name': 'João Silva',
            'email': 'joao@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'client_type': 'individual',
            'cpf': '12345678901',
            'phone': '11999999999',
        }

        response = self.client.post('/api/clients/register/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('client', response.data)

        # Verifica que o cliente foi criado
        client = Client.objects.get(email='joao@example.com')
        self.assertEqual(client.full_name, 'João Silva')
        self.assertEqual(client.client_type, 'individual')
        self.assertEqual(client.status, 'pending')
        self.assertFalse(client.email_confirmed)

        # Verifica que o usuário foi criado
        user = User.objects.get(email='joao@example.com')
        self.assertTrue(user.check_password('TestPassword123!'))

        # Verifica que o e-mail foi enviado
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Confirme seu e-mail', mail.outbox[0].subject)

    def test_register_client_company_success(self):
        """
        Testa registro de cliente pessoa jurídica com sucesso.
        """
        data = {
            'full_name': 'Empresa LTDA',
            'email': 'empresa@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'client_type': 'company',
            'cnpj': '12345678901234',
            'company_name': 'Empresa LTDA',
        }

        response = self.client.post('/api/clients/register/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        client = Client.objects.get(email='empresa@example.com')
        self.assertEqual(client.client_type, 'company')
        self.assertEqual(client.cnpj, '12345678901234')

    def test_register_client_missing_cpf(self):
        """
        Testa registro de pessoa física sem CPF (deve falhar).
        """
        data = {
            'full_name': 'João Silva',
            'email': 'joao@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'client_type': 'individual',
            # CPF faltando
        }

        response = self.client.post('/api/clients/register/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cpf', response.data)

    def test_register_client_missing_cnpj(self):
        """
        Testa registro de pessoa jurídica sem CNPJ (deve falhar).
        """
        data = {
            'full_name': 'Empresa LTDA',
            'email': 'empresa@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'client_type': 'company',
            'company_name': 'Empresa LTDA',
            # CNPJ faltando
        }

        response = self.client.post('/api/clients/register/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cnpj', response.data)

    def test_register_client_password_mismatch(self):
        """
        Testa registro com senhas diferentes (deve falhar).
        """
        data = {
            'full_name': 'João Silva',
            'email': 'joao@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'DifferentPassword123!',
            'client_type': 'individual',
            'cpf': '12345678901',
        }

        response = self.client.post('/api/clients/register/', data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password_confirm', response.data)

    def test_register_client_duplicate_email(self):
        """
        Testa registro com e-mail duplicado (deve falhar).
        """
        # Primeiro registro
        data1 = {
            'full_name': 'João Silva',
            'email': 'joao@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'client_type': 'individual',
            'cpf': '12345678901',
        }
        self.client.post('/api/clients/register/', data1, format='json')

        # Segundo registro com mesmo e-mail
        data2 = {
            'full_name': 'Maria Silva',
            'email': 'joao@example.com',
            'password': 'TestPassword123!',
            'password_confirm': 'TestPassword123!',
            'client_type': 'individual',
            'cpf': '98765432109',
        }

        response = self.client.post('/api/clients/register/', data2, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)


class EmailConfirmationAPITest(APITestCase):
    """
    Testes para o endpoint de confirmação de e-mail.
    """

    def setUp(self):
        """
        Setup inicial para os testes.
        """
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='testpassword123'
        )

        self.client_obj = Client.objects.create(
            user=self.user,
            full_name='João Silva',
            email='test@example.com',
            client_type='individual',
            cpf='12345678901'
        )

        self.token = self.client_obj.generate_confirmation_token()

    def test_confirm_email_success(self):
        """
        Testa confirmação de e-mail com sucesso.
        """
        response = self.client.post(
            '/api/clients/confirm-email/',
            {'token': self.token},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

        # Verifica que o e-mail foi confirmado
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.email_confirmed)
        self.assertEqual(self.client_obj.status, 'active')

    def test_confirm_email_invalid_token(self):
        """
        Testa confirmação com token inválido.
        """
        response = self.client.post(
            '/api/clients/confirm-email/',
            {'token': 'invalid-token'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_email_via_get(self):
        """
        Testa confirmação via GET (link clicável).
        """
        response = self.client.get(
            f'/api/clients/confirm-email/?token={self.token}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verifica que o e-mail foi confirmado
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.email_confirmed)

    def test_confirm_email_already_confirmed(self):
        """
        Testa confirmação de e-mail já confirmado.
        """
        # Gera o token antes de confirmar
        token = self.client_obj.email_confirmation_token

        # Confirma o e-mail (isso limpa o token)
        self.client_obj.confirm_email()

        # Tenta confirmar novamente com o token antigo (que não existe mais)
        # Isso deve retornar 400 porque o token foi limpo
        response = self.client.get(
            f'/api/clients/confirm-email/?token={token}'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
