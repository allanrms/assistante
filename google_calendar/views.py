from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .services import GoogleCalendarService


@api_view(['POST'])
def request_calendar_integration(request):
    """
    Endpoint para solicitar integração com Google Calendar via WhatsApp
    """
    whatsapp_number = request.data.get('whatsapp_number')

    if not whatsapp_number:
        return Response({'error': 'Número do WhatsApp é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        service = GoogleCalendarService()
        auth_url = service.get_authorization_url(whatsapp_number)

        return Response({
            'success': True,
            'auth_url': auth_url,
            'message': 'URL de autorização gerada com sucesso'
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def oauth2_callback(request):
    """
    Callback do OAuth2 do Google
    """
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')

    if error:
        return HttpResponse(f"Erro na autorização: {error}", status=400)

    if not code or not state:
        return HttpResponse("Parâmetros de autorização inválidos", status=400)

    try:
        service = GoogleCalendarService()
        success, message = service.handle_oauth_callback(code, state)

        if success:
            return HttpResponse(f"""
                <html>
                <head><title>Integração Realizada</title></head>
                <body>
                    <h2>✅ Integração com Google Calendar realizada com sucesso!</h2>
                    <p>{message}</p>
                    <p>Você já pode fechar esta janela e voltar ao WhatsApp.</p>
                    <script>
                        setTimeout(function() {{
                            window.close();
                        }}, 3000);
                    </script>
                </body>
                </html>
            """)
        else:
            return HttpResponse(f"""
                <html>
                <head><title>Erro na Integração</title></head>
                <body>
                    <h2>❌ Erro na integração</h2>
                    <p>{message}</p>
                </body>
                </html>
            """, status=400)

    except Exception as e:
        return HttpResponse(f"Erro interno: {str(e)}", status=500)


# @api_view(['POST'])
# def create_calendar_event(request):
#     """
#     Cria um evento no Google Calendar
#     """
#     whatsapp_number = request.data.get('whatsapp_number')
#     event_data = request.data.get('event_data')
#
#     if not whatsapp_number or not event_data:
#         return Response({'error': 'Número do WhatsApp e dados do evento são obrigatórios'}, status=status.HTTP_400_BAD_REQUEST)
#
#     try:
#         service = GoogleCalendarService()
#         success, message = service.create_event(whatsapp_number, event_data)
#
#         if success:
#             return Response({'success': True, 'message': message})
#         else:
#             return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
#
#     except Exception as e:
#         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# @api_view(['GET'])
# def list_calendar_events(request):
#     """
#     Lista eventos do Google Calendar
#     """
#     whatsapp_number = request.query_params.get('whatsapp_number')
#     max_results = int(request.query_params.get('max_results', 10))
#
#     if not whatsapp_number:
#         return Response({'error': 'Número do WhatsApp é obrigatório'}, status=status.HTTP_400_BAD_REQUEST)
#
#     try:
#         service = GoogleCalendarService()
#         success, result = service.list_events(whatsapp_number, max_results)
#
#         if success:
#             return Response({'success': True, 'events': result})
#         else:
#             return Response({'error': result}, status=status.HTTP_400_BAD_REQUEST)
#
#     except Exception as e:
#         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
