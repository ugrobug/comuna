from django.contrib import admin
from django.utils import timezone
from media_storage.models import MediaTransfer


@admin.register(MediaTransfer)
class MediaTransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'state', 'size', 'attempts', 'next_attempt_at', 'last_error', 'created_at')
    list_filter = ('state',)
    readonly_fields = ('key', 'state', 'size', 'sha256', 'attempts', 'next_attempt_at', 'last_error', 'created_at', 'updated_at')
    fields = readonly_fields
    actions = ('retry',)
    show_full_result_count = False

    @admin.action(description='Повторить перенос выбранных изображений в S3')
    def retry(self, request, queryset):
        ids = list(queryset.filter(state='failed').values_list('pk', flat=True)[:100])
        for deleting, state in ((False, 'pending'), (True, 'deleting')):
            MediaTransfer.objects.filter(pk__in=ids, state='failed', delete_requested=deleting).update(
                state=state, attempts=0, next_attempt_at=timezone.now(), last_error='', lease_token='')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
