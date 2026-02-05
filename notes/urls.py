from django.urls import path
from . import views

app_name = 'notes'

urlpatterns = [
    path('', views.note_list_view, name='list'),
    path('upload/', views.note_upload_view, name='upload'),
    path('my-notes/', views.my_notes_view, name='my_notes'),
    path('<int:pk>/', views.note_detail_view, name='detail'),
    path('<int:pk>/download/', views.note_download_view, name='download'),
    path('<int:pk>/delete/', views.note_delete_view, name='delete'),
    path('ajax/load-subjects/', views.load_subjects, name='ajax_load_subjects'),
    path('<int:pk>/rate/', views.rate_note_view, name='rate'),
    path('rating/<int:pk>/delete/', views.delete_rating_view, name='delete_rating'),
    path('<int:pk>/report/', views.report_note_view, name='report'),
    path('moderation/', views.moderation_dashboard, name='moderation_dashboard'),
    path('moderation/approve/<int:pk>/', views.approve_note_view, name='approve_note'),
    path('moderation/reject/<int:pk>/', views.reject_note_view, name='reject_note'),
    path('moderation/report/<int:pk>/', views.review_report_view, name='review_report'),
]