import logging

from django.conf import settings
from django.core.mail import send_mass_mail
from django.utils import timezone

logger = logging.getLogger(__name__)


def _build_event_url(event, request=None):
    if request is not None:
        return request.build_absolute_uri(f'/events/{event.slug}/')
    site_url = settings.SITE_URL.rstrip('/')
    return f'{site_url}/events/{event.slug}/'


def _format_dt(dt):
    """Дата/время в часовом поясе проекта (TIME_ZONE), а не в UTC."""
    return timezone.localtime(dt).strftime('%d.%m.%Y %H:%M')


def _build_results_text(event):
    best_slot = event.get_best_slot()
    slots_lines = []
    for slot in event.time_slots.prefetch_related('votes').all():
        marker = ' [лучший]' if best_slot and slot.id == best_slot.id else ''
        slots_lines.append(
            f"  {_format_dt(slot.date_time)} ({slot.get_duration_display()}){marker}\n"
            f"    Да: {slot.get_yes_votes()}  Возможно: {slot.get_maybe_votes()}  Нет: {slot.get_no_votes()}"
        )
    return '\n'.join(slots_lines)


def send_voting_results(event, request=None):
    """Отправляет итоги голосования участникам и организатору."""
    from events.models import Vote

    best_slot = event.get_best_slot()
    event_url = _build_event_url(event, request)
    results_text = _build_results_text(event)

    best_line = ''
    if best_slot and best_slot.get_total_votes() > 0:
        best_line = f'\nЛучший вариант: {_format_dt(best_slot.date_time)}\n'

    from_email = settings.DEFAULT_FROM_EMAIL
    datatuple = []

    # Участники, указавшие email
    participants = (
        Vote.objects
        .filter(time_slot__event=event)
        .exclude(participant_email='')
        .values('participant_name', 'participant_email')
        .distinct()
    )
    for p in participants:
        subject = f'Результаты голосования: {event.title}'
        body = (
            f'Здравствуйте, {p["participant_name"]}!\n\n'
            f'Голосование «{event.title}» завершено.\n'
            f'{best_line}\n'
            f'Результаты по всем вариантам:\n'
            f'{results_text}\n\n'
            f'Ссылка на событие: {event_url}\n'
        )
        datatuple.append((subject, body, from_email, [p['participant_email']]))

    # Организатор (если email задан)
    creator_email = event.creator.email
    if creator_email:
        subject = f'Голосование завершено: {event.title}'
        body = (
            f'Здравствуйте, {event.creator.get_full_name() or event.creator.username}!\n\n'
            f'Голосование «{event.title}» завершено.\n'
            f'{best_line}\n'
            f'Результаты по всем вариантам:\n'
            f'{results_text}\n\n'
            f'Ссылка на событие: {event_url}\n'
        )
        datatuple.append((subject, body, from_email, [creator_email]))

    if not datatuple:
        logger.info('Событие %s: нет адресов для рассылки', event.slug)
        return

    try:
        sent = send_mass_mail(datatuple, fail_silently=False)
        logger.info('Событие %s: отправлено %d писем', event.slug, sent)
    except Exception as exc:
        logger.error('Ошибка отправки результатов голосования (событие %s): %s', event.slug, exc)
        raise
