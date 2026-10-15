"""
Обновлённые модели для events/models.py

Изменения по сравнению с оригиналом:
1. Event: добавлено поле default_duration_minutes
2. TimeSlot: добавлено поле duration_minutes
3. TimeSlot.clean(): валидация — нельзя создавать слоты в прошлом
4. Event.clean(): валидация — дедлайн не может быть в прошлом
5. Добавлены helper-методы для отображения длительности

После замены файла:
    python manage.py makemigrations events
    python manage.py migrate
"""
import uuid
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone


class Event(models.Model):
    """Событие, по которому проводится опрос времени."""

    slug = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    location = models.CharField('Место проведения', max_length=200, blank=True)

    creator = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='created_events', verbose_name='Организатор'
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    deadline = models.DateTimeField(
        'Срок голосования', null=True, blank=True,
        help_text='После этого времени голосование закроется автоматически'
    )
    closed_manually = models.BooleanField('Закрыто вручную', default=False)
    notification_sent = models.BooleanField('Уведомление отправлено', default=False)

    # НОВОЕ: длительность по умолчанию для новых вариантов времени
    default_duration_minutes = models.PositiveIntegerField(
        'Длительность по умолчанию (мин)',
        default=60,
        help_text='Подставится для новых вариантов времени'
    )

    class Meta:
        verbose_name = 'Событие'
        verbose_name_plural = 'События'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('events:detail', kwargs={'slug': self.slug})

    def clean(self):
        # Дедлайн не может быть в прошлом
        if self.deadline and self.deadline < timezone.now():
            raise ValidationError({'deadline': 'Дедлайн не может быть в прошлом'})

    def is_closed(self):
        if self.closed_manually:
            return True
        if self.deadline and timezone.now() >= self.deadline:
            return True
        return False

    def get_best_slot(self):
        best_slot = None
        best_score = -1
        for slot in self.time_slots.all():
            score = slot.get_score()
            if score > best_score:
                best_score = score
                best_slot = slot
        return best_slot

    def get_participants_count(self):
        return Vote.objects.filter(
            time_slot__event=self
        ).values('participant_name').distinct().count()


class TimeSlot(models.Model):
    """Конкретный вариант даты/времени для голосования."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE,
        related_name='time_slots', verbose_name='Событие'
    )
    date_time = models.DateTimeField('Дата и время начала')

    # НОВОЕ: длительность этого конкретного варианта
    duration_minutes = models.PositiveIntegerField(
        'Длительность (мин)',
        default=60,
        help_text='Длительность события для этого варианта'
    )

    class Meta:
        verbose_name = 'Вариант времени'
        verbose_name_plural = 'Варианты времени'
        ordering = ['date_time']

    def __str__(self):
        return f"{self.event.title} — {self.date_time.strftime('%d.%m.%Y %H:%M')}"

    def clean(self):
        # При создании нельзя ставить прошлое время
        # (при редактировании уже существующих слотов не валидируем, чтобы
        #  не сломать прошедшие голосования)
        if not self.pk and self.date_time and self.date_time < timezone.now():
            raise ValidationError({
                'date_time': 'Нельзя создать вариант времени в прошлом'
            })

    def get_yes_votes(self):
        return self.votes.filter(answer='yes').count()

    def get_maybe_votes(self):
        return self.votes.filter(answer='maybe').count()

    def get_no_votes(self):
        return self.votes.filter(answer='no').count()

    def get_total_votes(self):
        return self.votes.count()

    def get_score(self):
        """Балл: 'да'=вес, 'возможно'=вес*0.5, 'нет'=0."""
        from decimal import Decimal
        yes_score = sum((v.weight for v in self.votes.filter(answer='yes')), Decimal(0))
        maybe_score = sum((v.weight * Decimal('0.5') for v in self.votes.filter(answer='maybe')), Decimal(0))
        return float(yes_score + maybe_score)

    def get_end_time(self):
        """Время окончания события."""
        return self.date_time + timedelta(minutes=self.duration_minutes)

    def get_duration_display(self):
        """Длительность в формате '1 ч 30 мин'."""
        h = self.duration_minutes // 60
        m = self.duration_minutes % 60
        if h == 0:
            return f'{m} мин'
        if m == 0:
            return f'{h} ч'
        return f'{h} ч {m} мин'


class ParticipantWeight(models.Model):
    """Настроенный организатором вес голоса участника для конкретного события."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE,
        related_name='participant_weights', verbose_name='Событие'
    )
    participant_name = models.CharField('Имя участника', max_length=100)
    weight = models.DecimalField('Вес голоса', max_digits=4, decimal_places=2, default=1)

    class Meta:
        verbose_name = 'Вес участника'
        verbose_name_plural = 'Веса участников'
        unique_together = [['event', 'participant_name']]

    def __str__(self):
        return f"{self.participant_name} × {self.weight} ({self.event.title})"


class Vote(models.Model):
    """Голос участника за вариант времени."""

    ANSWER_CHOICES = [
        ('yes', 'Да'),
        ('maybe', 'Возможно'),
        ('no', 'Нет'),
    ]

    time_slot = models.ForeignKey(
        TimeSlot, on_delete=models.CASCADE,
        related_name='votes', verbose_name='Вариант времени'
    )
    participant_name = models.CharField('Имя участника', max_length=100)
    participant_email = models.EmailField('Email участника', blank=True, default='')
    answer = models.CharField(
        'Ответ', max_length=10, choices=ANSWER_CHOICES, default='yes'
    )
    weight = models.DecimalField(
        'Вес голоса', max_digits=4, decimal_places=2, default=1
    )
    voted_at = models.DateTimeField('Время голосования', auto_now_add=True)

    class Meta:
        verbose_name = 'Голос'
        verbose_name_plural = 'Голоса'
        unique_together = [['time_slot', 'participant_name']]

    def __str__(self):
        return f"{self.participant_name}: {self.get_answer_display()} за {self.time_slot}"
