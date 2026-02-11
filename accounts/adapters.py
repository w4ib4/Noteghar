from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import resolve_url
from django.urls import reverse

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to handle role-based redirects and signup
    """
    
    def get_login_redirect_url(self, request):
        """
        Redirect based on user role after login
        """
        user = request.user
        
        if user.is_admin_user():
            return resolve_url('admin:index')
        elif user.is_moderator():
            return resolve_url('moderation:dashboard')
        else:
            return resolve_url('core:home')
    
    def is_open_for_signup(self, request):
        """
        Allow signup only through our custom views
        """
        #handle signup through custom views
        return True
    
    def save_user(self, request, user, form, commit=True):
        """
        Save user with custom fields
        """
        user = super().save_user(request, user, form, commit=False)
        
        # Get role from form
        if hasattr(form, 'cleaned_data'):
            user.role = form.cleaned_data.get('role', 'student')
            user.institution = form.cleaned_data.get('institution', '')
        
        if commit:
            user.save()
        return user