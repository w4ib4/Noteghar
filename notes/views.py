from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import FileResponse, Http404
from django.utils import timezone
from .models import Note, Course, Semester, Subject, Download
from .forms import NoteUploadForm, NoteSearchForm
from .models import Rating, Report
from .forms import RatingForm, ReportForm
from django.db.models import Avg, Count

def note_list_view(request):
    """
    Display all approved notes with search and filter
    """
    notes = Note.objects.filter(status='approved').select_related(
        'subject', 'course', 'semester', 'uploaded_by'
    )
    
    form = NoteSearchForm(request.GET)
    
    # Search
    query = request.GET.get('query')
    if query:
        notes = notes.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(tags__icontains=query)
        )
    
    # Filters
    if form.is_valid():
        if form.cleaned_data.get('course'):
            notes = notes.filter(course=form.cleaned_data['course'])
        if form.cleaned_data.get('semester'):
            notes = notes.filter(semester=form.cleaned_data['semester'])
        if form.cleaned_data.get('subject'):
            notes = notes.filter(subject=form.cleaned_data['subject'])
    
    context = {
        'notes': notes,
        'form': form,
        'total_notes': notes.count()
    }
    return render(request, 'notes/note_list.html', context)

from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Count
from .models import Note, Rating, Download

def note_detail_view(request, pk):
    """
    Display note details with ratings
    """
    note = get_object_or_404(Note, pk=pk, status='approved')
    note.view_count += 1
    note.save(update_fields=['view_count'])

    # Ratings queryset
    ratings = note.ratings.all().select_related('user')

    # Aggregated rating data
    rating_stats = ratings.aggregate(
        average_rating=Avg('rating'),
        rating_count=Count('id'),
    )  # [web:66][web:65]

    average_rating = rating_stats['average_rating'] or 0
    rating_count = rating_stats['rating_count'] or 0

    user_rating = None
    has_downloaded = False

    if request.user.is_authenticated:
        has_downloaded = Download.objects.filter(
            note=note, user=request.user
        ).exists()
        try:
            user_rating = Rating.objects.get(note=note, user=request.user)
        except Rating.DoesNotExist:
            user_rating = None

    # Tags: split in view, not in template
    if note.tags:
        tag_list = [tag.strip() for tag in note.tags.split(',')]
    else:
        tag_list = []

    context = {
        'note': note,
        'ratings': ratings,
        'user_rating': user_rating,
        'has_downloaded': has_downloaded,
        'average_rating': round(average_rating, 1),
        'rating_count': rating_count,
        'tag_list': tag_list,
    }

    return render(request, 'notes/note_detail.html', context)

@login_required
def note_upload_view(request):
    """
    Upload new note
    """
    if request.method == 'POST':
        form = NoteUploadForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.uploaded_by = request.user
            note.status = 'pending'  # Requires moderation
            note.save()
            messages.success(request, 'Note uploaded successfully! It will be available after moderation.')
            return redirect('notes:my_notes')
    else:
        form = NoteUploadForm()
    
    return render(request, 'notes/note_upload.html', {'form': form})


@login_required
def note_download_view(request, pk):
    """
    Download note file
    """
    note = get_object_or_404(Note, pk=pk, status='approved')
    
    # Track download
    Download.objects.create(
        note=note,
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Increment download count
    note.download_count += 1
    note.save(update_fields=['download_count'])
    
    # Serve file
    try:
        return FileResponse(note.file.open('rb'), as_attachment=True, filename=note.file.name)
    except FileNotFoundError:
        raise Http404("File not found")


@login_required
def my_notes_view(request):
    """
    Display user's uploaded notes
    """
    notes = Note.objects.filter(uploaded_by=request.user).select_related(
        'subject', 'course', 'semester'
    ).order_by('-created_at')
    
    context = {
        'notes': notes,
        'pending_count': notes.filter(status='pending').count(),
        'approved_count': notes.filter(status='approved').count(),
        'rejected_count': notes.filter(status='rejected').count(),
    }
    return render(request, 'notes/my_notes.html', context)


@login_required
def note_delete_view(request, pk):
    """
    Delete own note
    """
    note = get_object_or_404(Note, pk=pk, uploaded_by=request.user)
    
    if request.method == 'POST':
        note.delete()
        messages.success(request, 'Note deleted successfully!')
        return redirect('notes:my_notes')
    
    return render(request, 'notes/note_confirm_delete.html', {'note': note})


# AJAX view for dynamic subject loading
from django.http import JsonResponse

def load_subjects(request):
    """
    AJAX view to load subjects based on course and semester
    """
    course_id = request.GET.get('course_id')
    semester_id = request.GET.get('semester_id')
    
    subjects = Subject.objects.filter(
        course_id=course_id,
        semester_id=semester_id
    ).order_by('name')
    
    return JsonResponse({
        'subjects': list(subjects.values('id', 'name', 'code'))
    })
@login_required
def rate_note_view(request, pk):
    """
    Rate a note
    """
    note = get_object_or_404(Note, pk=pk, status='approved')
    
    if request.method == 'POST':
        # Check if user already rated
        try:
            rating = Rating.objects.get(note=note, user=request.user)
            form = RatingForm(request.POST, instance=rating)
            message = 'Rating updated successfully!'
        except Rating.DoesNotExist:
            form = RatingForm(request.POST)
            message = 'Thank you for rating this note!'
        
        if form.is_valid():
            rating = form.save(commit=False)
            rating.note = note
            rating.user = request.user
            rating.save()
            messages.success(request, message)
        else:
            messages.error(request, 'Please provide a valid rating.')
    
    return redirect('notes:detail', pk=pk)


@login_required
def report_note_view(request, pk):
    """
    Report a note
    """
    note = get_object_or_404(Note, pk=pk)
    
    # Check if user already reported this note
    existing_report = Report.objects.filter(note=note, reported_by=request.user, status='pending').first()
    if existing_report:
        messages.warning(request, 'You have already reported this note.')
        return redirect('notes:detail', pk=pk)
    
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.note = note
            report.reported_by = request.user
            report.save()
            messages.success(request, 'Report submitted successfully. Our moderators will review it.')
            return redirect('notes:detail', pk=pk)
    else:
        form = ReportForm()
    
    return render(request, 'notes/report_note.html', {'form': form, 'note': note})


@login_required
def delete_rating_view(request, pk):
    """
    Delete user's own rating
    """
    rating = get_object_or_404(Rating, pk=pk, user=request.user)
    note_pk = rating.note.pk
    
    if request.method == 'POST':
        rating.delete()
        messages.success(request, 'Rating deleted successfully!')
    
    return redirect('notes:detail', pk=note_pk)


# MODERATOR VIEWS
from django.contrib.auth.decorators import user_passes_test

def is_moderator(user):
    """Check if user is moderator or admin"""
    return user.is_authenticated and (user.role in ['moderator', 'admin'] or user.is_superuser)

@user_passes_test(is_moderator)
def moderation_dashboard(request):
    """
    Dashboard for moderators
    """
    pending_notes = Note.objects.filter(status='pending').select_related('uploaded_by', 'subject')
    pending_reports = Report.objects.filter(status='pending').select_related('note', 'reported_by')
    
    context = {
        'pending_notes': pending_notes,
        'pending_reports': pending_reports,
        'pending_notes_count': pending_notes.count(),
        'pending_reports_count': pending_reports.count(),
    }
    return render(request, 'notes/moderation_dashboard.html', context)


@user_passes_test(is_moderator)
def approve_note_view(request, pk):
    """
    Approve a pending note
    """
    note = get_object_or_404(Note, pk=pk)
    
    if request.method == 'POST':
        note.status = 'approved'
        note.approved_by = request.user
        note.approved_at = timezone.now()
        note.save()
        messages.success(request, f'Note "{note.title}" has been approved!')
        return redirect('notes:moderation_dashboard')
    
    return render(request, 'notes/approve_note.html', {'note': note})


@user_passes_test(is_moderator)
def reject_note_view(request, pk):
    """
    Reject a pending note
    """
    note = get_object_or_404(Note, pk=pk)
    
    if request.method == 'POST':
        note.status = 'rejected'
        note.save()
        messages.warning(request, f'Note "{note.title}" has been rejected.')
        return redirect('notes:moderation_dashboard')
    
    return render(request, 'notes/reject_note.html', {'note': note})


@user_passes_test(is_moderator)
def review_report_view(request, pk):
    """
    Review a report
    """
    report = get_object_or_404(Report, pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        moderator_notes = request.POST.get('moderator_notes', '')
        
        report.reviewed_by = request.user
        report.reviewed_at = timezone.now()
        report.moderator_notes = moderator_notes
        
        if action == 'resolve':
            report.status = 'resolved'
            # Optionally reject the note
            if request.POST.get('reject_note'):
                report.note.status = 'rejected'
                report.note.save()
            messages.success(request, 'Report resolved successfully.')
        elif action == 'dismiss':
            report.status = 'dismissed'
            messages.info(request, 'Report dismissed.')
        
        report.save()
        return redirect('notes:moderation_dashboard')
    
    return render(request, 'notes/review_report.html', {'report': report})