"""
Тесты представлений и рассылки приложения events.

Покрывают:
- время в письмах с итогами выводится в часовом поясе проекта, а не в UTC
- закрытие голосования не падает, если письма отправить не удалось
- скрипт страницы события подключается ровно один раз
"""
from datetime import datetime, timezone as dt_timezone
from unittest import mock

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from events.emails import send_voting_results
from events.models import Event, TimeSlot, Vote


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username='organizer', email='org@example.com', password='pass12345'
    )


@pytest.fixture
def event(user):
    return Event.objects.create(title='Планёрка', creator=user)


@pytest.fixture
def slot(event):
    # 16:35 UTC = 19:35 по Москве (TIME_ZONE = 'Europe/Moscow')
    return TimeSlot.objects.create(
        event=event,
        date_time=datetime(2030, 12, 15, 16, 35, tzinfo=dt_timezone.utc),
    )


def test_results_email_uses_local_time(event, slot):
    Vote.objects.create(time_slot=slot, participant_name='Аня',
                        participant_email='anya@example.com', answer='yes')

    send_voting_results(event)

    assert len(mail.outbox) == 2  # участник + организатор
    for message in mail.outbox:
        assert '15.12.2030 19:35' in message.body
        assert '16:35' not in message.body


def test_close_event_survives_email_failure(client, user, event, slot):
    Vote.objects.create(time_slot=slot, participant_name='Аня', answer='yes')
    client.force_login(user)

    with mock.patch('events.emails.send_mass_mail', side_effect=OSError('SMTP down')):
        response = client.post(reverse('events:close', kwargs={'slug': event.slug}))

    assert response.status_code == 302
    event.refresh_from_db()
    assert event.closed_manually is True


def test_event_page_includes_script_once(client, event, slot):
    response = client.get(reverse('events:detail', kwargs={'slug': event.slug}))

    assert response.status_code == 200
    assert response.content.decode().count("getElementById('votes-form')") == 1
