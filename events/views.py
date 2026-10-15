"""
Представления приложения events: создание и редактирование событий,
голосование, закрытие голосования и управление весами участников.
"""

import json
import logging
from datetime import datetime, timezone as dt_timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.contrib import messages
from django.core.mail import send_mass_mail
from django.conf import settings as django_settings

from .models import Event, TimeSlot, Vote, ParticipantWeight
from .forms import EventForm

logger = logging.getLogger(__name__)


def _parse_iso_datetime(iso_str):
    """
    Парсит ISO-строку в aware-datetime.
    JavaScript присылает время в UTC (с суффиксом Z).
    """
    if not iso_str:
        return None
    s = iso_str.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, dt_timezone.utc)
    return dt


def _validate_slots_data(time_slots_data):
    """
    Валидирует список слотов.
    Возвращает кортеж: (valid_slots, errors)
    """
    valid_slots = []
    errors = []
    now = timezone.now()

    seen_times = set()

    for idx, slot_data in enumerate(time_slots_data, start=1):
        dt_iso = slot_data.get('dateTime', '')
        start_time = _parse_iso_datetime(dt_iso)

        if start_time is None:
            errors.append(f'Вариант #{idx}: некорректный формат даты')
            continue

        # Запрет прошлого
        if start_time < now:
            errors.append(
                f'Вариант #{idx} ({start_time.strftime("%d.%m.%Y %H:%M")}) — время в прошлом'
            )
            continue

        # Длительность
        try:
            duration = int(slot_data.get('durationMinutes', 60))
        except (TypeError, ValueError):
            duration = 60
        if duration < 0 or duration > 1440:  # больше 24 часов — это что-то странное
            duration = 60

        # Уникальность
        if start_time in seen_times:
            errors.append(f'Вариант #{idx} — дубликат времени')
            continue
        seen_times.add(start_time)

        valid_slots.append({'date_time': start_time, 'duration_minutes': duration})

    return valid_slots, errors


@login_required
@require_http_methods(['GET', 'POST'])
def create_event(request):
    """Создание нового события с вариантами времени."""

    if request.method == 'POST':
        form = EventForm(request.POST)

        # Проверим дедлайн на прошлое
        deadline_str = request.POST.get('deadline')
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str)
                if timezone.is_naive(deadline):
                    deadline = timezone.make_aware(deadline)
                if deadline < timezone.now():
                    form.add_error('deadline', 'Дедлайн не может быть в прошлом')
            except ValueError:
                pass

        # Парсим JSON со слотами
        time_slots_json = request.POST.get('time_slots_json', '[]')
        try:
            time_slots_data = json.loads(time_slots_json)
        except json.JSONDecodeError:
            time_slots_data = []

        valid_slots, slot_errors = _validate_slots_data(time_slots_data)

        if not valid_slots:
            for err in slot_errors:
                messages.error(request, err)
            if not slot_errors:
                messages.error(request, 'Добавьте хотя бы один корректный вариант времени')

        if form.is_valid() and valid_slots:
            event = form.save(commit=False)
            event.creator = request.user
            event.save()

            for slot in valid_slots:
                TimeSlot.objects.create(
                    event=event,
                    date_time=slot['date_time'],
                    duration_minutes=slot['duration_minutes'],
                )

            # Если были не-фатальные ошибки (дубликаты, прошлое — но что-то добавили)
            for err in slot_errors:
                messages.warning(request, err)

            messages.success(
                request,
                f'Событие создано! Добавлено вариантов: {len(valid_slots)}'
            )
            return redirect('events:detail', slug=event.slug)
    else:
        form = EventForm()

    return render(request, 'events/create_event.html', {'form': form})


@login_required
@require_http_methods(['GET', 'POST'])
def edit_event(request, slug):
    """Редактирование события (только для создателя)."""
    event = get_object_or_404(Event, slug=slug)

    if event.creator != request.user:
        messages.error(request, 'Вы не можете редактировать это событие')
        return redirect('events:detail', slug=slug)

    if event.is_closed():
        messages.error(request, 'Голосование закрыто — редактирование невозможно')
        return redirect('events:detail', slug=slug)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)

        deadline_str = request.POST.get('deadline')
        if deadline_str:
            try:
                deadline = datetime.fromisoformat(deadline_str)
                if timezone.is_naive(deadline):
                    deadline = timezone.make_aware(deadline)
                if deadline < timezone.now():
                    form.add_error('deadline', 'Дедлайн не может быть в прошлом')
            except ValueError:
                pass

        time_slots_json = request.POST.get('time_slots_json', '[]')
        try:
            time_slots_data = json.loads(time_slots_json)
        except json.JSONDecodeError:
            time_slots_data = []

        valid_slots, slot_errors = _validate_slots_data(time_slots_data)

        if form.is_valid() and valid_slots:
            event = form.save()

            # Сохраняем варианты с голосами; пересоздаём только те, что без голосов
            event.time_slots.filter(votes__isnull=True).delete()

            existing_times = set(event.time_slots.values_list('date_time', flat=True))
            for slot in valid_slots:
                if slot['date_time'] not in existing_times:
                    TimeSlot.objects.create(
                        event=event,
                        date_time=slot['date_time'],
                        duration_minutes=slot['duration_minutes'],
                    )

            messages.success(request, 'Событие обновлено')
            return redirect('events:detail', slug=event.slug)
        else:
            for err in slot_errors:
                messages.error(request, err)
    else:
        form = EventForm(instance=event)

    return render(request, 'events/create_event.html', {
        'form': form,
        'event': event,
        'is_edit': True,
    })


def event_detail(request, slug):
    """Просмотр события и голосование."""
    event = get_object_or_404(Event, slug=slug)
    time_slots = event.time_slots.all().prefetch_related('votes')

    voted_events = request.session.get('voted_events', {})
    has_voted = str(event.slug) in voted_events

    context = {
        'event': event,
        'time_slots': time_slots,
        'best_slot': event.get_best_slot(),
        'is_closed': event.is_closed(),
        'participants_count': event.get_participants_count(),
        'is_creator': request.user.is_authenticated and request.user == event.creator,
        'has_voted': has_voted,
        'voted_as': voted_events.get(str(event.slug), ''),
    }
    return render(request, 'events/event_detail.html', context)


@require_POST
def submit_votes(request, slug):
    """Голосование за все варианты сразу (один раз на участника)."""
    event = get_object_or_404(Event, slug=slug)

    if event.is_closed():
        messages.error(request, 'Голосование по этому событию закрыто')
        return redirect('events:detail', slug=slug)

    participant_name = request.POST.get('participant_name', '').strip()
    if not participant_name:
        messages.error(request, 'Укажите ваше имя')
        return redirect('events:detail', slug=slug)

    # Проверка по сессии
    voted_events = request.session.get('voted_events', {})
    if str(slug) in voted_events:
        messages.error(request, 'Вы уже проголосовали за это событие')
        return redirect('events:detail', slug=slug)

    # Проверка по имени в базе
    if Vote.objects.filter(time_slot__event=event, participant_name=participant_name).exists():
        messages.error(request, f'Участник «{participant_name}» уже проголосовал')
        return redirect('events:detail', slug=slug)

    participant_email = request.POST.get('participant_email', '').strip()

    pw = ParticipantWeight.objects.filter(event=event, participant_name=participant_name).first()
    weight = pw.weight if pw else 1

    time_slots = event.time_slots.all()
    votes_created = 0
    for slot in time_slots:
        answer = request.POST.get(f'answer_{slot.id}', '').strip()
        if answer in ('yes', 'maybe', 'no'):
            Vote.objects.create(
                time_slot=slot,
                participant_name=participant_name,
                participant_email=participant_email,
                answer=answer,
                weight=weight,
            )
            votes_created += 1

    if votes_created == 0:
        messages.error(request, 'Выберите ответ хотя бы для одного варианта')
        return redirect('events:detail', slug=slug)

    voted_events[str(slug)] = participant_name
    request.session['voted_events'] = voted_events
    request.session.modified = True

    messages.success(request, f'Голос участника «{participant_name}» учтён!')
    return redirect('events:detail', slug=slug)


def _send_results_emails(event, request=None):
    """Рассылает итоги голосования участникам и организатору.

    request опционален — без него URL строится из SITE_URL в settings.
    """
    from events.emails import send_voting_results
    send_voting_results(event, request=request)


@login_required
@require_POST
def close_event(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if event.creator != request.user:
        messages.error(request, 'Только создатель может закрыть голосование')
        return redirect('events:detail', slug=slug)
    event.closed_manually = True
    event.notification_sent = True
    event.save()
    try:
        _send_results_emails(event, request)
    except Exception:
        # Ошибка уже записана в лог в send_voting_results; голосование при этом закрыто.
        messages.warning(request, 'Голосование закрыто, но письма с результатами отправить не удалось.')
    else:
        messages.success(request, 'Голосование закрыто. Участники с email получат результаты.')
    return redirect('events:detail', slug=slug)


@login_required
@require_POST
def delete_event(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if event.creator != request.user:
        messages.error(request, 'Только создатель может удалить событие')
        return redirect('events:detail', slug=slug)
    title = event.title
    event.delete()
    messages.success(request, f'Событие «{title}» удалено')
    return redirect('events:my_events')


@login_required
def my_events(request):
    events = Event.objects.filter(creator=request.user).order_by('-created_at')
    return render(request, 'events/my_events.html', {'events': events})


@login_required
@require_http_methods(['GET', 'POST'])
def set_participant_weights(request, slug):
    """Управление весами голосов участников (только для организатора)."""
    from decimal import Decimal, InvalidOperation

    event = get_object_or_404(Event, slug=slug)

    if event.creator != request.user:
        messages.error(request, 'Только организатор может управлять весами')
        return redirect('events:detail', slug=slug)

    # Уникальные участники события
    participant_names = (
        Vote.objects.filter(time_slot__event=event)
        .values_list('participant_name', flat=True)
        .distinct()
        .order_by('participant_name')
    )

    if request.method == 'POST':
        updated = 0
        for name in participant_names:
            raw = request.POST.get(f'weight_{name}', '').strip()
            try:
                weight = Decimal(raw)
                if weight <= 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                messages.error(request, f'Неверный вес для «{name}»: укажите положительное число')
                continue
            ParticipantWeight.objects.update_or_create(
                event=event, participant_name=name,
                defaults={'weight': weight},
            )
            Vote.objects.filter(time_slot__event=event, participant_name=name).update(weight=weight)
            updated += 1

        if updated:
            messages.success(request, f'Веса обновлены для {updated} участн.')
        return redirect('events:detail', slug=slug)

    weights_map = {
        pw.participant_name: pw.weight
        for pw in ParticipantWeight.objects.filter(event=event)
    }
    participants = [
        {'name': name, 'weight': weights_map.get(name, 1)}
        for name in participant_names
    ]

    return render(request, 'events/participant_weights.html', {
        'event': event,
        'participants': participants,
    })
