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
    path('rating/<int:pk>/helpful/', views.mark_rating_helpful, name='mark_helpful'),  
    path('<int:pk>/report/', views.report_note_view, name='report'),
    path('moderation/', views.moderation_dashboard, name='moderation_dashboard'),
    path('moderation/approve/<int:pk>/', views.approve_note_view, name='approve_note'),
    path('moderation/reject/<int:pk>/', views.reject_note_view, name='reject_note'),
    path('moderation/report/<int:pk>/', views.review_report_view, name='review_report'),
    # Bookmarks
    path('bookmarks/', views.my_bookmarks, name='my_bookmarks'),
    path('<int:pk>/bookmark/', views.toggle_bookmark, name='toggle_bookmark'),
    path('bookmark/<int:pk>/update-notes/', views.update_bookmark_notes, name='update_bookmark_notes'),
    
    # History
    path('history/', views.my_history, name='my_history'),
    
    # Tags
    path('tags/', views.tag_list, name='tag_list'),
    path('tags/suggest/', views.suggest_tag, name='suggest_tag'),
    path('tags/<slug:slug>/', views.tag_browse, name='tag_browse'),
    
    
    # Trending
    path('trending/', views.trending_view, name='trending'),
    # path('top/<int:course_id>/', views.top_notes_by_course, name='top_by_course'),
    
    # Note Requests
    path('requests/', views.request_board, name='request_board'),
    path('requests/create/', views.create_note_request, name='create_request'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/<int:pk>/respond/', views.respond_to_request, name='respond_to_request'),
    path('requests/<int:request_id>/best/<int:response_id>/', views.mark_best_answer, name='mark_best_answer'),
    # gamification

    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('profile/<str:username>/', views.user_profile_view, name='user_profile'),
    path('my-profile/', views.my_profile, name='my_profile'),
]
 
