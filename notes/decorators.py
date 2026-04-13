from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from datetime import timedelta
from .models import RateLimit

def rate_limit(action_type, max_per_day=10, max_per_hour=5):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = request.user

            if user.is_staff or user.is_superuser:
                return view_func(request, *args, **kwargs)

            # Only limit the actual action, not page loads
            if request.method != 'POST':
                return view_func(request, *args, **kwargs)

            now = timezone.now()
            day_ago = now - timedelta(days=1)
            hour_ago = now - timedelta(hours=1)

            daily_count = RateLimit.objects.filter(
                user=user,
                action_type=action_type,
                timestamp__gte=day_ago
            ).count()

            if daily_count >= max_per_day:
                messages.error(
                    request,
                    f'Daily limit reached ({max_per_day}/{action_type}). Try tomorrow.'
                )
                return redirect('notes:my_notes')   # or 'notes:list'

            hourly_count = RateLimit.objects.filter(
                user=user,
                action_type=action_type,
                timestamp__gte=hour_ago
            ).count()

            if hourly_count >= max_per_hour:
                messages.error(
                    request,
                    f'Hourly limit reached ({max_per_hour}/{action_type}). Slow down.'
                )
                return redirect('notes:my_notes')   # or 'notes:list'

            response = view_func(request, *args, **kwargs)

            RateLimit.objects.create(
                user=user,
                action_type=action_type,
                ip_address=request.META.get('REMOTE_ADDR')
            )

            return response
        return wrapped_view
    return decorator