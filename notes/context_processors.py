from .models import Note, Report

def moderation_stats(request):
    """
    Add moderation stats to context for all templates
    """
    if request.user.is_authenticated and (
        request.user.role in ['moderator', 'admin'] or request.user.is_superuser
    ):
        pending_notes = Note.objects.filter(status='pending').count()
        pending_reports = Report.objects.filter(status='pending').count()
        return {
            'pending_notes_count': pending_notes,
            'pending_reports_count': pending_reports,
            'total_pending': pending_notes + pending_reports,
        }
    return {}