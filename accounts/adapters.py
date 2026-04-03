from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter for allauth to handle role-based signups
    """

    def is_open_for_signup(self, request):
        return True

    def save_user(self, request, user, form, commit=True):
        """
        Save user - let the form handle role-specific fields
        """
        user = super().save_user(request, user, form, commit=False)
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


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter for social (Google) login.
    Automatically assigns the 'student' role to users who sign up via Google.
    """

    def is_open_for_signup(self, request, sociallogin):
        return True

    def save_user(self, request, sociallogin, form=None):
        """
        Called when a new user signs up via Google.
        Assigns the default 'student' role.
        """
        user = super().save_user(request, sociallogin, form)

        # Assign default role if not already set
        if hasattr(user, 'role') and not user.role:
            user.role = 'student'
            user.save()

        return user

    def populate_user(self, request, sociallogin, data):
        """
        Populate user fields from Google profile data.
        """
        user = super().populate_user(request, sociallogin, data)
        return user
