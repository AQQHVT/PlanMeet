"""
Отправляет итоги голосования для событий, у которых истёк дедлайн.

Запуск:
    python manage.py send_deadline_notifications

Рекомендуется ставить в cron каждые 5–15 минут.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import Event
from events.emails import send_voting_results


class Command(BaseCommand):
    help = 'Отправляет итоги голосования по событиям с истёкшим дедлайном'

    def handle(self, *args, **options):
        now = timezone.now()

        # События, у которых дедлайн истёк И уведомление ещё не отправлено
        events = Event.objects.filter(
            deadline__lte=now,
            notification_sent=False,
            closed_manually=False,
        ).select_related('creator')

        if not events.exists():
            self.stdout.write('Нет событий для уведомления')
            return

        for event in events:
            self.stdout.write(f'Обрабатываю: {event.title} (дедлайн: {event.deadline})')
            try:
                send_voting_results(event)
                event.notification_sent = True
                event.save(update_fields=['notification_sent'])
                self.stdout.write(self.style.SUCCESS(f'  Уведомление отправлено'))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'  Ошибка: {exc}'))
