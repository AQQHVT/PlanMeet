"""
Представления для главной страницы
"""
from django.shortcuts import render
from events.models import Event


def home(request):
    """
    Главная страница приложения.
    Показывает кнопки создания события и авторизации,
    а также историю событий для авторизованных пользователей.
    """
    context = {}
    if request.user.is_authenticated:
        # История событий, созданных пользователем
        user_events = Event.objects.filter(creator=request.user).order_by('-created_at')
        context['user_events'] = user_events
    return render(request, 'core/home.html', context)
