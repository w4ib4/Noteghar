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

    def get_signup_redirect_url(self, request):
        """
        Redirect to the correct login page based on role after signup.
        """
        user = request.user
        if hasattr(user, 'role') and user.role == 'moderator':
            return '/accounts/login/moderator/'
        elif hasattr(user, 'role') and user.role == 'admin':
            return '/accounts/login/admin/'
        else:
            return '/accounts/login/student/'

    def get_login_redirect_url(self, request):
        """
        Redirect users based on their role after login.
        Also updates login streak for students.
        """
        user = request.user

        # Update login streak for students
        if hasattr(user, 'role') and user.role == 'student':
            try:
                from django.utils import timezone
                from notes.models import UserProfile
                profile, _ = UserProfile.objects.get_or_create(user=user)
                today = timezone.now().date()

                if profile.last_login_date is None:
                    profile.login_streak = 1
                elif profile.last_login_date == today:
                    pass  # already logged in today, don't change streak
                elif (today - profile.last_login_date).days == 1:
                    profile.login_streak += 1  # consecutive day
                else:
                    profile.login_streak = 1   # streak broken, reset

                profile.last_login_date = today
                profile.save(update_fields=['login_streak', 'last_login_date'])

                # Check for streak badges
                from notes.badge_utils import check_and_award_badges
                check_and_award_badges(user)
            except Exception:
                pass  # never block login due to gamification errors

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