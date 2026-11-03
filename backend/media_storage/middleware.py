from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from media_storage.spool import MediaReserveFull


class MediaReserveErrorsMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, MediaReserveFull):
            response = JsonResponse({'error': str(exception), 'detail': str(exception), 'success': 0}, status=503)
            response['Retry-After'] = '60'
            return response
        return None
