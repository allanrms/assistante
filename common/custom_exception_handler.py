import traceback

from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import JsonResponse
from rest_framework.utils.serializer_helpers import ReturnDict
from rest_framework.views import exception_handler
from django.utils.translation import gettext_lazy as _

def CustomExceptionHandler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)
    traceback.print_exc()

    # Now add the HTTP status code to the response.
    if response is not None:
        errors = response.data.copy()
        if (type(errors) == dict or type(errors) == ReturnDict) and 'non_field_errors' in errors.keys():
            errors = errors.get('non_field_errors')
        if (type(errors) == dict or type(errors) == ReturnDict) and len(
                errors.keys()) == 1 and 'detail' in errors.keys():
            errors = errors.get('detail')

        # if type(errors) == ReturnDict:
        #     # list_errors = []
        #     for key in errors.keys():
        #         if type(errors[key]) == list:
        #             try:
        #                 errors[key] = u'; '.join(errors[key])
        #             except Exception:
        #                 errors[key] = str(errors[key])
        #
        #         # Transform in list
        #         list_errors.append({'field': key, 'error': "Field is required." if errors[key] == 'This field may not be blank.' else  errors[key]})
            # errors = list_errors
        try:
            if type(exc.get_codes()) == dict:
                code = exc.get_codes().get('non_field_errors', 'field_error')
            else:
                code = exc.get_codes()
        except:
            code = 'not_found'
        response.data = {
            'errors': errors,
            'code': code
        }
    else:
        if type(exc) == ProtectedError:
            error =  _('Esta operação não pode ser executada')
            return JsonResponse({'detail': error},status=400, safe=False)
        elif type(exc) == IntegrityError:
            error =  _('Esta operação não pode ser executada devido a um erro de integridade do banco, contate o suporte')
            return JsonResponse({'detail': error},status=400, safe=False)
        elif type(exc) == TypeError and str(exc) =='one of the hex, bytes, bytes_le, fields, or int arguments must be given':
            error =  _('O sistema não encontrou a referência da entidade, por favor atualize a pagina')
            return JsonResponse({'detail': error},status=400, safe=False)
    return response