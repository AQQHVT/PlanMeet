"""
Формы приложения events.
"""
from django import forms
from django.utils import timezone

from .models import Event


class EventForm(forms.ModelForm):
    """Форма создания/редактирования события."""

    class Meta:
        model = Event
        fields = ['title', 'description', 'location', 'deadline']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Например: Совещание команды',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Краткое описание события (необязательно)',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Офис / Zoom / адрес',
            }),
            'deadline': forms.DateTimeInput(attrs={
                'class': 'form-input',
                'type': 'datetime-local',
            }),
        }
        labels = {
            'title': 'Название события',
            'description': 'Описание',
            'location': 'Место проведения',
            'deadline': 'Дедлайн голосования',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Минимум для дедлайна — сейчас (не в прошлом)
        now_iso = timezone.localtime().strftime('%Y-%m-%dT%H:%M')
        self.fields['deadline'].widget.attrs['min'] = now_iso

    def clean_deadline(self):
        deadline = self.cleaned_data.get('deadline')
        if deadline and deadline < timezone.now():
            raise forms.ValidationError('Дедлайн не может быть в прошлом')
        return deadline
