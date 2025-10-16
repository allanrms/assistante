from core.models import Client, Employee

class ClientSwitcherMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            
            # Superuser can switch to any client
            if user.is_superuser:
                client_id = request.GET.get('client_id')
                if client_id:
                    request.session['selected_client_id'] = client_id
                
                selected_client_id = request.session.get('selected_client_id')
                if selected_client_id:
                    try:
                        user.client = Client.objects.get(pk=selected_client_id)
                    except Client.DoesNotExist:
                        pass # keep default
            
            # Employee can switch between their assigned clients
            elif Employee.objects.filter(user=user).exists():
                client_id = request.GET.get('client_id')
                allowed_clients_pks = Employee.objects.filter(user=user).values_list('client__pk', flat=True)
                
                if client_id and str(client_id) in allowed_clients_pks:
                    request.session['selected_client_id'] = client_id
                
                selected_client_id = request.session.get('selected_client_id')
                if selected_client_id and str(selected_client_id) in allowed_clients_pks:
                    try:
                        user.client = Client.objects.get(pk=selected_client_id)
                    except Client.DoesNotExist:
                        pass # keep default

        response = self.get_response(request)
        return response