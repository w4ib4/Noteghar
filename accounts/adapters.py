from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings

class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter for allauth to handle role-based signups
    """
    
    def is_open_for_signup(self, request):
        """
        Allow signups
        """
        return True
    
    def save_user(self, request, user, form, commit=True):
        """
        Save user - let the form handle role-specific fields
        """
        # Only handle basic allauth fields here
        user = super().save_user(request, user, form, commit=False)
        
        # Don't try to set institution here - the form's save() method handles it
        # This prevents errors when institution is not in the form
        
        if commit:
            user.save()
        
        return user
    
    def get_login_redirect_url(self, request):
        """
        Redirect users based on their role after login
        """
        user = request.user
        
        if user.is_superuser or (hasattr(user, 'role') and user.role == 'admin'):
            return '/admin/dashboard/'
        elif hasattr(user, 'role') and user.role == 'moderator':
            return '/moderation/'
        else:
            return '/'