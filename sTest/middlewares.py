import logging

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class GlobalExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('Exception Handler')

    def __call__(self, request):
        self.logger.info(f"Incoming request: {request.path}")
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        # Log every exception
        self.logger.exception(f'Error processing the request - {request} because of {exception}')

        response = {
            'detail': ''
        }
        # Handle specific exceptions
        if isinstance(exception, ObjectDoesNotExist):
            response['detail'] = 'Resource not found.'
            return JsonResponse(data=response, status=400)
        elif isinstance(exception, ValidationError):
            response['detail'] = str(exception)
            return JsonResponse(data=response, status=400)
        else:
            response['detail'] = 'An unexpected error occurred.'
            # For other exceptions, return a generic error message
            return JsonResponse(data=response, status=500)


class CustomCSRFMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if response.status_code == 403 and 'CSRF Failed:' in str(response.content):
            new_data = {"detail": "A user is already logged in."}
            return JsonResponse(new_data, status=403)
        return response
