from django.utils import translation


class UserLanguageMiddleware:
    """
    Middleware para definir a linguagem baseada na preferência do usuário logado
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            # Verificar se request tem user e se está autenticado
            if hasattr(request, 'user') and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated:
                # Usar linguagem preferida do usuário diretamente
                user_language = getattr(request.user, 'preferred_language', None)
                if user_language:
                    translation.activate(user_language)
                    request.LANGUAGE_CODE = user_language
        except Exception:
            # Se algo der errado, continua sem alterar o idioma
            pass
        
        response = self.get_response(request)
        translation.deactivate()
        return response