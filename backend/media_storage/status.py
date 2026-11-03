import time
from media_storage.models import MediaTransfer


class MediaReserveStatus:
    def __init__(self, store, spool):
        self.store, self.spool = store, spool

    def update(self):
        oldest = (MediaTransfer.objects.filter(state__in=['pending', 'failed']).order_by('created_at')
                  .values_list('created_at', flat=True).first())
        self.store.write({'heartbeat_at': time.time(), 'pending_since': oldest.timestamp() if oldest else None,
            'failed': MediaTransfer.objects.filter(state='failed').exists(),
            'free_bytes': self.spool.free_bytes(), 'reserve_bytes': self.spool.reserve_bytes})

    def heartbeat(self):
        state = self.store.read()
        if time.time() - state.get('heartbeat_at', 0) >= 5:
            self.store.write({**state, 'heartbeat_at': time.time()})

    @staticmethod
    def problem(state, now):
        if not state or now - state.get('heartbeat_at', 0) > 720:
            return 'Не работает проверка переноса резервных изображений в S3'
        if state.get('free_bytes', 0) < state.get('reserve_bytes', 0) + 256 * 1024**2:
            return 'Заканчивается место для резервных изображений на сервере Тамбура'
        if state.get('failed'):
            return 'Перенос некоторых изображений в S3 исчерпал повторы; требуется проверка очереди'
        if state.get('pending_since') and now - state['pending_since'] > 120:
            return 'Изображения временно хранятся на сервере Тамбура и ожидают переноса в S3'
        return None
