from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from notes.models import Note, Download
from django.db.models import Count

def home_view(request):
    """
    Homepage view - shows landing page for guests, dashboard for logged-in users
    """
    if request.user.is_authenticated:
        return dashboard_view(request)
    return render(request, 'core/home.html')


@login_required
def dashboard_view(request):
    """
    User dashboard with stats and recent activity
    """
    user = request.user
    
    # Get user's notes stats
    my_notes = Note.objects.filter(uploaded_by=user)
    total_notes = my_notes.count()
    approved_notes = my_notes.filter(status='approved').count()
    pending_notes = my_notes.filter(status='pending').count()
    rejected_notes = my_notes.filter(status='rejected').count()
    
    # Total downloads of user's notes
    total_downloads = sum(note.download_count for note in my_notes)
    
    # Recent downloads by user
    recent_downloads = Download.objects.filter(user=user).select_related('note').order_by('-downloaded_at')[:5]
    
    # Recent uploads
    recent_uploads = my_notes.order_by('-created_at')[:5]
    
    # Most downloaded notes 
    popular_notes = Note.objects.filter(status='approved').order_by('-download_count')[:5]
    
    context = {
        'total_notes': total_notes,
        'approved_notes': approved_notes,
        'pending_notes': pending_notes,
        'rejected_notes': rejected_notes,
        'total_downloads': total_downloads,
        'recent_downloads': recent_downloads,
        'recent_uploads': recent_uploads,
        'popular_notes': popular_notes,
    }
    
    return render(request, 'core/dashboard.html', context)
