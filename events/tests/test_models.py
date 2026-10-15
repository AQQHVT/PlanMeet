"""
Тесты моделей приложения events.

Покрывают ключевую бизнес-логику PlanMeet:
- алгоритм подсчёта баллов слота (get_score)
- выбор лучшего варианта времени (get_best_slot)
- определение закрытия события (is_closed)
- подсчёт уникальных участников (get_participants_count)
- защита от повторного голосования (unique_together)
- вспомогательные методы отображения длительности
"""
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from events.models import Event, TimeSlot, Vote


# --- Фикстуры ---------------------------------------------------------------

@pytest.fixture
def user(db):
    return User.objects.create_user(username='organizer', password='pass12345')


@pytest.fixture
def event(user):
    return Event.objects.create(title='Планёрка', creator=user)


@pytest.fixture
def slot(event):
    return TimeSlot.objects.create(
        event=event,
        date_time=timezone.now() + timedelta(days=1),
        duration_minutes=60,
    )


# --- get_score --------------------------------------------------------------

def test_score_yes_vote_counts_full_weight(slot):
    Vote.objects.create(time_slot=slot, participant_name='Аня', answer='yes', weight=1)
    assert slot.get_score() == pytest.approx(1.0)


def test_score_maybe_vote_counts_half_weight(slot):
    Vote.objects.create(time_slot=slot, participant_name='Боря', answer='maybe', weight=1)
    assert slot.get_score() == pytest.approx(0.5)


def test_score_no_vote_counts_zero(slot):
    Vote.objects.create(time_slot=slot, participant_name='Вера', answer='no', weight=1)
    assert slot.get_score() == pytest.approx(0.0)


def test_score_mixed_votes_sum_correctly(slot):
    Vote.objects.create(time_slot=slot, participant_name='Аня', answer='yes', weight=1)
    Vote.objects.create(time_slot=slot, participant_name='Боря', answer='maybe', weight=1)
    Vote.objects.create(time_slot=slot, participant_name='Вера', answer='no', weight=1)
    # 1 (yes) + 0.5 (maybe) + 0 (no) = 1.5
    assert slot.get_score() == pytest.approx(1.5)


def test_score_respects_participant_weight(slot):
    # Голос с весом 2 и ответом "да" даёт 2 балла
    Vote.objects.create(time_slot=slot, participant_name='Босс', answer='yes', weight=2)
    assert slot.get_score() == pytest.approx(2.0)


# --- get_best_slot ----------------------------------------------------------

def test_best_slot_is_highest_scoring(event):
    weak = TimeSlot.objects.create(
        event=event, date_time=timezone.now() + timedelta(days=1))
    strong = TimeSlot.objects.create(
        event=event, date_time=timezone.now() + timedelta(days=2))

    Vote.objects.create(time_slot=weak, participant_name='Аня', answer='maybe', weight=1)
    Vote.objects.create(time_slot=strong, participant_name='Аня', answer='yes', weight=1)
    Vote.objects.create(time_slot=strong, participant_name='Боря', answer='yes', weight=1)

    assert event.get_best_slot() == strong


def test_best_slot_none_when_no_slots(event):
    assert event.get_best_slot() is None


# --- is_closed --------------------------------------------------------------

def test_event_open_by_default(event):
    assert event.is_closed() is False


def test_event_closed_manually(event):
    event.closed_manually = True
    assert event.is_closed() is True


def test_event_closed_when_deadline_passed(user):
    past = Event.objects.create(
        title='Прошедшее', creator=user,
        deadline=timezone.now() - timedelta(hours=1),
    )
    assert past.is_closed() is True


def test_event_open_when_deadline_in_future(user):
    future = Event.objects.create(
        title='Будущее', creator=user,
        deadline=timezone.now() + timedelta(hours=1),
    )
    assert future.is_closed() is False


# --- get_participants_count -------------------------------------------------

def test_participants_counted_uniquely(event):
    s1 = TimeSlot.objects.create(
        event=event, date_time=timezone.now() + timedelta(days=1))
    s2 = TimeSlot.objects.create(
        event=event, date_time=timezone.now() + timedelta(days=2))
    # Аня голосует за оба слота — но считается один раз
    Vote.objects.create(time_slot=s1, participant_name='Аня', answer='yes', weight=1)
    Vote.objects.create(time_slot=s2, participant_name='Аня', answer='no', weight=1)
    Vote.objects.create(time_slot=s1, participant_name='Боря', answer='yes', weight=1)
    assert event.get_participants_count() == 2


# --- Защита от повторного голосования ---------------------------------------

def test_duplicate_vote_same_slot_and_name_rejected(slot):
    Vote.objects.create(time_slot=slot, participant_name='Аня', answer='yes', weight=1)
    with pytest.raises(IntegrityError):
        Vote.objects.create(time_slot=slot, participant_name='Аня', answer='no', weight=1)


# --- Вспомогательные методы отображения -------------------------------------

@pytest.mark.parametrize('minutes,expected', [
    (30, '30 мин'),
    (60, '1 ч'),
    (90, '1 ч 30 мин'),
    (120, '2 ч'),
])
def test_duration_display_formats(event, minutes, expected):
    s = TimeSlot.objects.create(
        event=event,
        date_time=timezone.now() + timedelta(days=1),
        duration_minutes=minutes,
    )
    assert s.get_duration_display() == expected


def test_end_time_is_start_plus_duration(event):
    start = timezone.now() + timedelta(days=1)
    s = TimeSlot.objects.create(event=event, date_time=start, duration_minutes=90)
    assert s.get_end_time() == start + timedelta(minutes=90)
