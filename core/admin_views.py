from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from accounts.models import User
from notes.models import Note, Report, Institution, Course, Subject, Download

@staff_member_required
def admin_dashboard(request):
    """Custom admin dashboard"""
    
    context = {
        # User statistics
        'total_users': User.objects.count(),
        'students_count': User.objects.filter(role='student').count(),
        'moderators_count': User.objects.filter(role='moderator', is_active=True).count(),
        'pending_moderators_count': User.objects.filter(role='moderator', is_active=False).count(),
        
        # Note statistics
        'pending_notes_count': Note.objects.filter(status='pending').count(),
        'approved_notes_count': Note.objects.filter(status='approved').count(),
        'total_notes': Note.objects.count(),
        
        # Report statistics
        'pending_reports_count': Report.objects.filter(status='pending').count(),
        
        # Other statistics
        'institutions_count': Institution.objects.count(),
        'courses_count': Course.objects.count(),
        'subjects_count': Subject.objects.count(),
        'total_downloads': Download.objects.count(),
        
        # Recent activity
        'recent_notes': Note.objects.select_related('uploaded_by').order_by('-created_at')[:10],
    }
    
    return render(request, 'admin/custom_dashboard.html', context)