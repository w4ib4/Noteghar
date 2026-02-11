from django.urls import path
from django.views.generic import RedirectView
from .views import StudentSignupView, ModeratorSignupView, AdminSignupView, profile_view

app_name = 'accounts'

urlpatterns = [
    # Role-based signup
    path('signup/student/', StudentSignupView.as_view(), name='signup_student'),
    path('signup/moderator/', ModeratorSignupView.as_view(), name='signup_moderator'),
    path('signup/admin/', AdminSignupView.as_view(), name='signup_admin'),
    
    # Profile
    path('profile/', profile_view, name='profile'),

    # Redirects for compatibility with base.html
    path('login/', RedirectView.as_view(pattern_name='account_login', permanent=False), name='login'),
    path('logout/', RedirectView.as_view(pattern_name='account_logout', permanent=False), name='logout'),
    path('register/', StudentSignupView.as_view(), name='register'),  # Default to student signup
]