from django.urls import path
from django.views.generic import RedirectView, TemplateView
from .views import (
    StudentSignupView, ModeratorSignupView, AdminSignupView,
    student_login_view, moderator_login_view, admin_login_view,
    profile_view, signup_select_view
)

app_name = 'accounts'

urlpatterns = [
    # Signup selection
    path('register/', signup_select_view, name='register'),
    
    # Role-based signup
    path('signup/student/', StudentSignupView.as_view(), name='signup_student'),
    path('signup/moderator/', ModeratorSignupView.as_view(), name='signup_moderator'),
    path('signup/admin/', AdminSignupView.as_view(), name='signup_admin'),
    
    # Role-based login pages
    path('login/student/',   student_login_view,   name='student_login'),
    path('login/moderator/', moderator_login_view, name='moderator_login'),
    path('login/admin/',     admin_login_view,     name='admin_login'),
    
    # Profile
    path('profile/', profile_view, name='profile'),

    # Redirects for compatibility
    path('login/', RedirectView.as_view(pattern_name='account_login', permanent=False), name='login'),
    path('logout/', RedirectView.as_view(pattern_name='account_logout', permanent=False), name='logout'),
]