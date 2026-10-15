"""
Конфигурация админки Django
"""
from django.contrib import admin
from .models import Event, TimeSlot, Vote


class TimeSlotInline(admin.TabularInline):
    model = TimeSlot
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'created_at', 'deadline', 'closed_manually')
    list_filter = ('closed_manually', 'created_at')
    search_fields = ('title', 'creator__username')
    inlines = [TimeSlotInline]


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('event', 'date_time')
    list_filter = ('date_time',)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('participant_name', 'time_slot', 'answer', 'voted_at')
    list_filter = ('answer', 'voted_at')
    search_fields = ('participant_name',)
