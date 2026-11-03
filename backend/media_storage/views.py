from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.views import View
from media_storage.models import MediaTransfer
from media_storage.spool import LocalMediaSpool


class MediaSpoolView(View):
    """Stable URL: local bytes during outage, verified S3 object after transfer."""
    def get(self, request, key):
        storage_key = '_spool/' + key
        if not LocalMediaSpool.is_key(storage_key):
            raise Http404
        spool = LocalMediaSpool()
        # Development and direct backend access; production nginx handles local files.
        if spool.local.exists(storage_key):
            response = FileResponse(spool.local.open(storage_key, 'rb'))
        elif MediaTransfer.objects.filter(key=storage_key, state='uploaded').exists():
            response = HttpResponseRedirect(default_storage.s3_storage.url(storage_key))
        else:
            raise Http404
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = "default-src 'none'; sandbox"
        response['Cache-Control'] = 'public, max-age=300'
        return response
