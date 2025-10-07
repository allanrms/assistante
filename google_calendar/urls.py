from django.urls import path
from . import views

app_name = 'google_calendar'

urlpatterns = [
    path('request-integration/', views.request_calendar_integration, name='request_integration'),
    path('oauth2/callback/', views.oauth2_callback, name='oauth2_callback'),
    # path('create-event/', views.create_calendar_event, name='create_event'),
    # path('list-events/', views.list_calendar_events, name='list_events'),
]