from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('create/', views.create_event, name='create'),
    path('my/', views.my_events, name='my_events'),
    path('<uuid:slug>/', views.event_detail, name='detail'),
    path('<uuid:slug>/edit/', views.edit_event, name='edit'),
    path('<uuid:slug>/vote/', views.submit_votes, name='submit_votes'),
    path('<uuid:slug>/close/', views.close_event, name='close'),
    path('<uuid:slug>/delete/', views.delete_event, name='delete'),
    path('<uuid:slug>/weights/', views.set_participant_weights, name='weights'),
]
