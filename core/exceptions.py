from rest_framework.exceptions import APIException
from rest_framework import status


class WhatsAppConnectorException(APIException):

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, detail, status_code=None, original_exception=None):

        if status_code is None and original_exception is not None:
            status_code = getattr(original_exception, 'status_code', None)

        # Se ainda não tem status_code, usa o padrão (500)
        if status_code is not None:
            self.status_code = status_code

        super().__init__(detail)
