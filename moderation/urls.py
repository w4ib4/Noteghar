from django.urls import path
from . import views

app_name = 'moderation'

urlpatterns = [
    # Main dashboard
    path('', views.moderator_dashboard, name='dashboard'),
    
    # Pending content lists
    path('pending-notes/', views.pending_notes_list, name='pending_notes'),
    path('pending-reports/', views.pending_reports_list, name='pending_reports'),
    
    # Note moderation actions
    path('note/<int:pk>/approve/', views.approve_note, name='approve_note'),
    path('note/<int:pk>/reject/', views.reject_note, name='reject_note'),
    
    # Report handling
    path('report/<int:pk>/review/', views.review_report, name='review_report'),
    
    # History and logs
    path('history/', views.moderation_history, name='history'),
]
