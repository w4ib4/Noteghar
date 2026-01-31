# ==========================================
# CREATE: moderation/views.py (if doesn't exist, or add to notes/views.py)
# ==========================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Avg
from notes.models import Note, Report, Rating, Download, ModerationAction
from accounts.models import User

def is_moderator(user):
    """Check if user is moderator or admin"""
    return user.is_authenticated and (user.role in ['moderator', 'admin'] or user.is_superuser)


@user_passes_test(is_moderator)
def moderator_dashboard(request):
    """
    Enhanced moderator dashboard with comprehensive statistics
    """
    # Pending content counts
    pending_notes = Note.objects.filter(status='pending')
    pending_reports = Report.objects.filter(status='pending')
    
    # Recent activity
    recent_notes = Note.objects.filter(status='pending').select_related(
        'uploaded_by', 'subject', 'course', 'semester'
    ).order_by('-created_at')[:10]
    
    recent_reports = Report.objects.filter(
        status='pending'
    ).select_related('note', 'reported_by').order_by('-created_at')[:10]
    
    # Moderator statistics
    if request.user.role == 'moderator':
        my_actions = ModerationAction.objects.filter(moderator=request.user)
        my_actions_count = my_actions.count()
        my_approvals = my_actions.filter(action_type='approve').count()
        my_rejections = my_actions.filter(action_type='reject').count()
    else:
        my_actions_count = 0
        my_approvals = 0
        my_rejections = 0
    
    # Overall statistics
    total_notes = Note.objects.count()
    approved_notes = Note.objects.filter(status='approved').count()
    rejected_notes = Note.objects.filter(status='rejected').count()
    
    total_reports = Report.objects.count()
    resolved_reports = Report.objects.filter(status='resolved').count()
    dismissed_reports = Report.objects.filter(status='dismissed').count()
    
    # Recent moderation actions (all moderators)
    recent_actions = ModerationAction.objects.select_related(
        'moderator', 'note', 'target_user'
    ).order_by('-created_at')[:15]
    
    # Top contributors (students with most approved notes)
    top_contributors = User.objects.filter(
        role='student'
    ).annotate(
        approved_count=Count('notes', filter=Q(notes__status='approved'))
    ).filter(approved_count__gt=0).order_by('-approved_count')[:5]
    
    # Notes needing attention (pending for > 48 hours)
    needs_attention = Note.objects.filter(
        status='pending',
        created_at__lt=timezone.now() - timezone.timedelta(hours=48)
    ).count()
    
    context = {
        'pending_notes_count': pending_notes.count(),
        'pending_reports_count': pending_reports.count(),
        'needs_attention': needs_attention,
        
        'recent_notes': recent_notes,
        'recent_reports': recent_reports,
        'recent_actions': recent_actions,
        
        'my_actions_count': my_actions_count,
        'my_approvals': my_approvals,
        'my_rejections': my_rejections,
        
        'total_notes': total_notes,
        'approved_notes': approved_notes,
        'rejected_notes': rejected_notes,
        'approval_rate': round((approved_notes / total_notes * 100) if total_notes > 0 else 0, 1),
        
        'total_reports': total_reports,
        'resolved_reports': resolved_reports,
        'dismissed_reports': dismissed_reports,
        
        'top_contributors': top_contributors,
    }
    
    return render(request, 'moderation/moderator_dashboard.html', context)


@user_passes_test(is_moderator)
def pending_notes_list(request):
    """List all pending notes for review"""
    notes = Note.objects.filter(status='pending').select_related(
        'uploaded_by', 'subject', 'course', 'semester'
    ).order_by('-created_at')
    
    # Filter by course if specified
    course_id = request.GET.get('course')
    if course_id:
        notes = notes.filter(course_id=course_id)
    
    context = {
        'notes': notes,
        'total_count': notes.count(),
    }
    return render(request, 'moderation/pending_notes.html', context)


@user_passes_test(is_moderator)
def pending_reports_list(request):
    """List all pending reports"""
    reports = Report.objects.filter(status='pending').select_related(
        'note', 'reported_by'
    ).order_by('-created_at')
    
    # Filter by reason if specified
    reason = request.GET.get('reason')
    if reason:
        reports = reports.filter(reason=reason)
    
    context = {
        'reports': reports,
        'total_count': reports.count(),
    }
    return render(request, 'moderation/pending_reports.html', context)


@user_passes_test(is_moderator)
def approve_note(request, pk):
    """Quick approve a note"""
    note = get_object_or_404(Note, pk=pk, status='pending')
    
    note.status = 'approved'
    note.approved_by = request.user
    note.approved_at = timezone.now()
    note.save()
    
    # Log the action
    ModerationAction.objects.create(
        moderator=request.user,
        action_type='approve',
        note=note,
        reason='Note approved'
    )
    
    messages.success(request, f' Note "{note.title}" has been approved!')
    
    # Redirect based on referrer
    next_url = request.GET.get('next', 'moderation:dashboard')
    return redirect(next_url)


@user_passes_test(is_moderator)
def reject_note(request, pk):
    """Reject a note with reason"""
    note = get_object_or_404(Note, pk=pk, status='pending')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Quality standards not met')
        
        note.status = 'rejected'
        note.save()
        
        # Log the action
        ModerationAction.objects.create(
            moderator=request.user,
            action_type='reject',
            note=note,
            reason=reason
        )
        
        messages.warning(request, f'Note "{note.title}" has been rejected.')
        return redirect('moderation:dashboard')
    
    return render(request, 'moderation/reject_note.html', {'note': note})


@user_passes_test(is_moderator)
def review_report(request, pk):
    """Review and resolve a report"""
    report = get_object_or_404(Report, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        moderator_notes = request.POST.get('moderator_notes', '')
        
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.moderator_notes = moderator_notes
        
        if action == 'resolve':
            report.status = 'resolved'
            
            # Optionally remove the note
            if request.POST.get('remove_note'):
                report.note.status = 'rejected'
                report.note.save()
                
                ModerationAction.objects.create(
                    moderator=request.user,
                    action_type='remove',
                    note=report.note,
                    report=report,
                    reason=f"Removed due to report: {report.get_reason_display()}"
                )
            
            messages.success(request, 'Report resolved successfully.')
            
        elif action == 'dismiss':
            report.status = 'dismissed'
            messages.info(request, 'Report dismissed.')
        
        report.save()
        return redirect('moderation:dashboard')
    
    return render(request, 'moderation/review_report.html', {'report': report})


@user_passes_test(is_moderator)
def moderation_history(request):
    """View moderation action history"""
    actions = ModerationAction.objects.select_related(
        'moderator', 'note', 'target_user'
    ).order_by('-created_at')
    
    # Filter by moderator if specified
    moderator_id = request.GET.get('moderator')
    if moderator_id:
        actions = actions.filter(moderator_id=moderator_id)
    
    # Filter by action type
    action_type = request.GET.get('type')
    if action_type:
        actions = actions.filter(action_type=action_type)
    
    # Pagination (optional - implement if needed)
    actions = actions[:50]  # Limit to 50 for now
    
    context = {
        'actions': actions,
        'total_count': actions.count(),
    }
    return render(request, 'moderation/history.html', context)