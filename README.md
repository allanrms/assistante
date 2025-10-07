# Assistante - WhatsApp Evolution API Integration

Este projeto integra com a Evolution API para receber mensagens do WhatsApp e processar imagens através do n8n ou IA, além de transcrever áudios usando Deepgram.

## Funcionalidades

- **Webhook para Evolution API**: Recebe mensagens do WhatsApp
- **Processamento de Áudio**: Descriptografa e transcreve áudios do WhatsApp usando Deepgram
- **Processamento de Imagem**: Envia imagens para n8n e/ou IA (OpenAI Vision) para interpretação
- **Mensagens de Texto**: Envia mensagens de texto para n8n
- **Envio de Mensagens**: API para enviar mensagens de volta pelo WhatsApp

## Configuração

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env` e configure:

```bash
cp .env.example .env
```

Configure as seguintes variáveis:

- `EVOLUTION_API_BASE_URL`: URL da sua instância Evolution API
- `EVOLUTION_API_TOKEN`: Token da Evolution API
- `EVOLUTION_API_INSTANCE`: Nome da instância
- `N8N_WEBHOOK_URL`: URL do webhook do n8n
- `DEEPGRAM_API_KEY`: Chave da API do Deepgram para transcrição
- `OPENAI_API_KEY`: Chave da API OpenAI (opcional, para análise de imagens)

### 3. Configurar Banco de Dados

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Executar o Servidor

```bash
python manage.py runserver
```

## Endpoints da API

### 1. Webhook Evolution API
**POST** `/api/v1/webhook/evolution/`

Recebe webhooks da Evolution API com mensagens do WhatsApp.

### 2. Webhook n8n Response
**POST** `/api/v1/webhook/n8n/`

Recebe respostas do n8n.

### 3. Enviar Mensagem
**POST** `/api/v1/send/message/`

Envia mensagem via WhatsApp através da Evolution API.

```json
{
  "number": "5583999999999",
  "textMessage": "Sua mensagem aqui"
}
```

### 4. Listar Mensagens
**GET** `/api/v1/messages/`

Lista as últimas 50 mensagens recebidas.

### 5. Detalhes da Mensagem
**GET** `/api/v1/messages/{message_id}/`

Obtém detalhes de uma mensagem específica.

## Tipos de Mensagem Suportados

### Áudio
- Descriptografa áudios do WhatsApp automaticamente
- Transcreve usando Deepgram
- Envia transcrição para n8n

### Imagem
- Baixa e salva imagens
- Envia para n8n para processamento
- Opcionalmente analisa com IA (OpenAI Vision)

### Texto
- Processa mensagens de texto simples e estendidas
- Envia diretamente para n8n

## Configuração da Evolution API

Configure o webhook da Evolution API para apontar para:
```
http://seu-servidor/api/v1/webhook/evolution/
```

## Configuração do n8n

O n8n deve ter um webhook configurado para receber os dados no formato:

```json
{
  "sessionId": "5583999999999@s.whatsapp.net",
  "whatsappReponse": "+5583999999999",
  "action": "sendMessage",
  "chatInput": "texto da mensagem",
  "senderName": "Nome do Remetente",
  "now": "2024-01-01 12:00:00"
}
```

Para responder mensagens, o n8n deve fazer POST para `/api/v1/send/message/`.

## Estrutura do Banco de Dados

### WhatsAppMessage
- `message_id`: ID único da mensagem
- `from_number`: Número do remetente
- `to_number`: Número de destino
- `message_type`: Tipo da mensagem (text, audio, image, video, document)
- `content`: Conteúdo da mensagem
- `sender_name`: Nome do remetente
- `audio_transcription`: Transcrição de áudio (se aplicável)
- `ai_response`: Resposta da IA (se aplicável)
- `n8n_response`: Resposta do n8n
- `processing_status`: Status do processamento

### ImageProcessingJob
- `message`: Referência à mensagem
- `processor_type`: Tipo de processador (n8n, ai, both)
- `status`: Status do job
- `result`: Resultado do processamento

## Admin Interface

Acesse `/admin/` para visualizar e gerenciar mensagens através da interface administrativa do Django.

## Swagger Documentation

Acesse `/swagger/` para a documentação interativa da API.

## Desenvolvimento

### Executar com Debug
```bash
DEBUG=True python manage.py runserver
```

### Logs
Os logs são exibidos no console. Para mensagens de debug, configure `DEBUG=True` no `.env`.

## Notas Importantes

1. As mensagens de áudio do WhatsApp são criptografadas e este projeto inclui a lógica de descriptografia.
2. A transcrição de áudio requer uma chave válida do Deepgram.
3. O processamento de imagem com IA requer uma chave OpenAI.
4. Configure adequadamente os URLs dos webhooks para n8n e Evolution API.

## Configuração da OpenAI (Opcional)

Para habilitar a análise de imagens com IA:

1. Acesse [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Crie uma nova API key
3. Configure no arquivo `.env`:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
```

**Nota**: Sem a configuração da OpenAI, as imagens serão processadas apenas pelo n8n.

## Troubleshooting

### Erro de Criptografia
Verifique se a biblioteca `pycryptodome` está instalada corretamente.

### Erro de Transcrição
Verifique se a `DEEPGRAM_API_KEY` está configurada corretamente.

### Erro 404 na OpenAI API
- Verifique se a `OPENAI_API_KEY` está configurada corretamente
- Confirme se você tem créditos disponíveis na conta OpenAI
- O sistema tenta automaticamente os modelos: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-4-vision-preview`
- Se todos falharem, verifique se sua conta tem acesso aos modelos de visão

### Webhook não funciona
Verifique se os URLs estão acessíveis e se não há firewall bloqueando as conexões.