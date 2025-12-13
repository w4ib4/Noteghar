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
]