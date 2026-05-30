from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from itertools import groupby
from operator import attrgetter
from .models import UserProfile, UserBadge, Badge, PointTransaction

from .models import (
    Note,
    Course,
    Semester,
    Subject,
    Download,
    Rating,
    Report,
    Bookmark,
    Tag,
    RateLimit,
    NoteRequest,
    NoteRequestResponse,
)
from .forms import (
    NoteUploadForm,
    NoteSearchForm,
    RatingForm,
    ReportForm,
)
from .decorators import rate_limit


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
            Q(subject__name__icontains=query) |
            Q(course__name__icontains=query) |
            Q(uploaded_by__username__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

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


def note_detail_view(request, pk):
    """
    Display note details with ratings
    """
    note = get_object_or_404(Note, pk=pk)
    
    # Access control for non-approved notes
    if note.status != 'approved':
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to view this note.')
            return redirect('account_login')
        
        is_uploader = request.user == note.uploaded_by
        is_staff = request.user.is_staff or request.user.is_superuser
        
        if not (is_uploader or is_staff):
            messages.error(request, 'This note is not available.')
            return redirect('notes:list')
    
    # Track view — only record once per user per note
    if request.user.is_authenticated:
        if not Download.objects.filter(note=note, user=request.user, is_download=False).exists():
            Download.objects.create(
                note=note,
                user=request.user,
                is_download=False,
                ip_address=request.META.get('REMOTE_ADDR', '')
            )
    
    note.view_count += 1
    note.save(update_fields=['view_count'])
    
    # Get ratings
    ratings = note.ratings.all().select_related('user')
    
    # Calculate rating stats
    rating_stats = ratings.aggregate(
        average_rating=Avg('rating'),
        rating_count=Count('id'),
    )
    
    average_rating = rating_stats['average_rating'] or 0
    rating_count = rating_stats['rating_count'] or 0
    
    # User-specific data
    user_rating = None
    has_downloaded = False
    is_bookmarked = False  # ADD THIS
    
    if request.user.is_authenticated:
        has_downloaded = Download.objects.filter(
            note=note, user=request.user, is_download=True
        ).exists()
        
        # Check if bookmarked
        is_bookmarked = note.is_bookmarked_by(request.user)  # ADD THIS
        
        try:
            user_rating = Rating.objects.get(note=note, user=request.user)
        except Rating.DoesNotExist:
            user_rating = None
    
    # Get tags
    tag_list = note.tags.all()
    
    context = {
        'note': note,
        'ratings': ratings,
        'user_rating': user_rating,
        'has_downloaded': has_downloaded,
        'is_bookmarked': is_bookmarked,  # ADD THIS
        'average_rating': round(average_rating, 1),
        'rating_count': rating_count,
        'tag_list': tag_list,
    }
    
    return render(request, 'notes/note_detail.html', context)
@login_required
@rate_limit('upload', max_per_day=10, max_per_hour=3)
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
            messages.success(
                request,
                'Note uploaded successfully! It will be available after moderation.'
            )
            return redirect('notes:my_notes')
    else:
        form = NoteUploadForm()

    return render(request, 'notes/note_upload.html', {'form': form})

from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def note_download_view(request, pk):
    note = get_object_or_404(Note, pk=pk)

    is_moderator = (
        request.user.is_superuser or
        getattr(request.user, 'role', None) in ['moderator', 'admin']
    )

    can_download = (
        note.status == 'approved' or
        request.user == note.uploaded_by or
        is_moderator
    )

    if not can_download:
        return HttpResponseForbidden("You are not allowed to download this note.")

    Download.objects.create(
        note=note,
        user=request.user,
        is_download=True,
        ip_address=request.META.get('REMOTE_ADDR', '')
    )

    note.download_count += 1
    note.save(update_fields=['download_count'])

    messages.success(request, f'Downloading: {note.title}')
    return FileResponse(note.file.open('rb'), as_attachment=True)


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


# ==================== AJAX SUBJECT LOADER ====================

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


# ==================== RATING & REPORT VIEWS ====================

@login_required
@rate_limit('rating', max_per_day=20, max_per_hour=5)
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
@rate_limit('report', max_per_day=5, max_per_hour=2)
def report_note_view(request, pk):
    """
    Report a note — students only
    """
    note = get_object_or_404(Note, pk=pk)

    # Moderators and admins cannot report notes
    if getattr(request.user, 'role', None) in ['moderator', 'admin'] or request.user.is_superuser:
        messages.error(request, 'Moderators and admins cannot report notes.')
        return redirect('notes:detail', pk=pk)

    # Cannot report your own note
    if note.uploaded_by == request.user:
        messages.error(request, 'You cannot report your own note.')
        return redirect('notes:detail', pk=pk)

    # Check if user already reported this note
    existing_report = Report.objects.filter(
        note=note,
        reported_by=request.user,
        status='pending'
    ).first()
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
            messages.success(
                request,
                'Report submitted successfully. Our moderators will review it.'
            )
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


@login_required
def mark_rating_helpful(request, pk):
    """
    Mark a rating as helpful (toggle)
    """
    from .models import RatingHelpful

    rating = get_object_or_404(Rating, pk=pk)

    if request.method == 'POST':
        # Toggle helpful mark
        helpful, created = RatingHelpful.objects.get_or_create(
            rating=rating,
            user=request.user
        )

        if not created:
            # Already marked, so remove it
            helpful.delete()
            messages.success(request, 'Removed from helpful.')
        else:
            # Newly marked as helpful
            messages.success(request, 'Marked as helpful!')

    return redirect('notes:detail', pk=rating.note.pk)


# ==================== BOOKMARK VIEWS ====================

@login_required
def toggle_bookmark(request, pk):
    """
    Toggle bookmark for a note (add/remove)
    """
    note = get_object_or_404(Note, pk=pk, status='approved')

    bookmark, created = Bookmark.objects.get_or_create(
        user=request.user,
        note=note
    )

    if not created:
        # Already bookmarked, so remove it
        bookmark.delete()
        messages.success(request, f'Removed "{note.title}" from bookmarks.')
        action = 'removed'
    else:
        # Newly bookmarked
        messages.success(request, f'Added "{note.title}" to bookmarks!')
        action = 'added'

    # Return JSON for AJAX or redirect for regular request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'action': action,
            'bookmark_count': note.get_bookmark_count()
        })

    # Redirect back to where they came from
    return redirect(request.META.get('HTTP_REFERER', 'notes:detail'))


@login_required
def my_bookmarks(request):
    """
    Display user's bookmarked notes
    """
    bookmarks = Bookmark.objects.filter(
        user=request.user
    ).select_related('note', 'note__subject', 'note__course', 'note__uploaded_by')

    # Filter by course/subject if provided
    course_id = request.GET.get('course')
    subject_id = request.GET.get('subject')

    if course_id:
        bookmarks = bookmarks.filter(note__course_id=course_id)
    if subject_id:
        bookmarks = bookmarks.filter(note__subject_id=subject_id)

    # Group by course for better organization
    bookmarks_list = list(bookmarks)
    bookmarks_by_course = {}

    for course, items in groupby(bookmarks_list, key=lambda x: x.note.course):
        bookmarks_by_course[course] = list(items)

    context = {
        'bookmarks': bookmarks,
        'bookmarks_by_course': bookmarks_by_course,
        'total_bookmarks': bookmarks.count(),
        'courses': Course.objects.all(),
    }

    return render(request, 'notes/my_bookmarks.html', context)


@login_required
def update_bookmark_notes(request, pk):
    """
    Update personal notes on a bookmark
    """
    bookmark = get_object_or_404(Bookmark, pk=pk, user=request.user)

    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        bookmark.notes = notes
        bookmark.save()
        messages.success(request, 'Bookmark notes updated!')

    return redirect('notes:my_bookmarks')


# ==================== TAG VIEWS ====================

def tag_browse(request, slug):
    """
    Browse notes by tag
    """
    tag = get_object_or_404(Tag, slug=slug, is_approved=True)
    notes = Note.objects.filter(
        tags=tag,
        status='approved'
    ).select_related('course', 'subject', 'uploaded_by')

    context = {
        'tag': tag,
        'notes': notes,
        'total_notes': notes.count(),
    }

    return render(request, 'notes/tag_browse.html', context)


def tag_list(request):
    """
    List all approved tags
    """
    tags = Tag.objects.filter(is_approved=True).annotate(
        note_count=Count('notes', filter=Q(notes__status='approved'))
    )

    # Popular tags
    popular_tags = tags.filter(usage_count__gte=5).order_by('-usage_count')[:10]
    all_tags = tags.order_by('name')

    context = {
        'popular_tags': popular_tags,
        'all_tags': all_tags,
    }

    return render(request, 'notes/tag_list.html', context)


@login_required
def suggest_tag(request):
    """
    Suggest a new tag (requires moderator approval)
    """
    if request.method == 'POST':
        tag_name = request.POST.get('tag_name', '').strip().lower()
        description = request.POST.get('description', '')

        if tag_name:
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                defaults={
                    'description': description,
                    'created_by': request.user,
                    'is_approved': False
                }
            )

            if created:
                messages.success(
                    request,
                    f'Tag "{tag_name}" suggested! It will be available after moderator approval.'
                )
            else:
                if tag.is_approved:
                    messages.info(request, f'Tag "{tag_name}" already exists!')
                else:
                    messages.info(request, f'Tag "{tag_name}" is pending approval.')

        return redirect('notes:tag_list')

    return render(request, 'notes/suggest_tag.html')


# ==================== HISTORY & TRENDING VIEWS ====================

@login_required
def my_history(request):
    """
    Show user's download and view history
    """
    # Recent downloads (is_download=True)
    downloads = Download.objects.filter(
        user=request.user,
        is_download=True
    ).select_related('note', 'note__subject', 'note__course').order_by('-downloaded_at')[:20]

    # Recent views (is_download=False)
    views = Download.objects.filter(
        user=request.user,
        is_download=False
    ).select_related('note', 'note__subject', 'note__course').order_by('-downloaded_at')[:10]

    # Get unique notes (no duplicates)
    downloaded_notes = {}
    for download in downloads:
        if download.note.id not in downloaded_notes:
            downloaded_notes[download.note.id] = download

    viewed_notes = {}
    for view in views:
        if view.note.id not in viewed_notes and view.note.id not in downloaded_notes:
            viewed_notes[view.note.id] = view

    context = {
        'downloads': list(downloaded_notes.values()),
        'views': list(viewed_notes.values()),
        'total_downloads': len(downloaded_notes),
        'total_views': len(viewed_notes),
    }

    return render(request, 'notes/my_history.html', context)


def trending_view(request):
    """
    Show trending notes page
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import F, Q, Count, Avg, FloatField
    from django.db.models.functions import Coalesce, Cast
    
    week_ago = timezone.now() - timedelta(days=7)
    
    # Trending notes
    trending_notes = Note.objects.filter(
        status='approved',
        created_at__gte=week_ago
    ).annotate(
        recent_downloads=Count('downloads', filter=Q(downloads__downloaded_at__gte=week_ago)),
        recent_views=Count('downloads', filter=Q(
            downloads__downloaded_at__gte=week_ago,
            downloads__is_download=False
        )),
        avg_rating=Avg('ratings__rating')
    ).annotate(
        trending_score=Cast(F('recent_downloads') * 3, FloatField()) + 
                       Cast(F('recent_views'), FloatField()) + 
                       Coalesce(F('avg_rating'), 0.0) * 10.0
    ).order_by('-trending_score')[:10]
    
    # Top rated
    top_rated = Note.objects.filter(
        status='approved'
    ).annotate(
        avg_rating=Avg('ratings__rating'),
        rating_count=Count('ratings')
    ).filter(
        rating_count__gte=3
    ).order_by('-avg_rating', '-rating_count')[:10]
    
    # Most downloaded
    most_downloaded = Note.objects.filter(
        status='approved'
    ).order_by('-download_count')[:10]
    
    context = {
        'trending_notes': trending_notes,
        'top_rated': top_rated,
        'most_downloaded': most_downloaded,
    }
    
    return render(request, 'notes/trending.html', context)

# ==================== NOTE REQUEST VIEWS ====================

@login_required
def create_note_request(request):
    """
    Create a new note request
    """
    if request.method == 'POST':
        course_id = request.POST.get('course')
        semester_id = request.POST.get('semester')
        subject_id = request.POST.get('subject')
        topic = request.POST.get('topic')
        description = request.POST.get('description')

        if all([course_id, semester_id, topic, description]):
            note_request = NoteRequest.objects.create(
                requester=request.user,
                course_id=course_id,
                semester_id=semester_id,
                subject_id=subject_id if subject_id else None,
                topic=topic,
                description=description
            )

            messages.success(
                request,
                'Note request created! Others can now help you.'
            )
            return redirect('notes:request_detail', pk=note_request.pk)
        else:
            messages.error(request, 'Please fill all required fields.')

    context = {
        'courses': Course.objects.all(),
        'semesters': Semester.objects.all(),
    }

    return render(request, 'notes/create_request.html', context)


def request_board(request):
    """
    List all open note requests
    """
    requests_list = NoteRequest.objects.filter(
        status='open',
        expires_at__gt=timezone.now()
    ).select_related('requester', 'course', 'semester', 'subject')

    # Filter by course/semester
    course_id = request.GET.get('course')
    semester_id = request.GET.get('semester')

    if course_id:
        requests_list = requests_list.filter(course_id=course_id)
    if semester_id:
        requests_list = requests_list.filter(semester_id=semester_id)

    context = {
        'requests': requests_list,
        'courses': Course.objects.all(),
        'semesters': Semester.objects.all(),
    }

    return render(request, 'notes/request_board.html', context)


def request_detail(request, pk):
    """
    View a specific note request with responses
    """
    note_request = get_object_or_404(NoteRequest, pk=pk)
    responses = note_request.responses.select_related('note', 'responder')

    context = {
        'request': note_request,
        'responses': responses,
        'can_respond': request.user.is_authenticated and request.user != note_request.requester,
        'is_requester': request.user == note_request.requester if request.user.is_authenticated else False,
    }

    return render(request, 'notes/request_detail.html', context)


@login_required
def respond_to_request(request, pk):
    """
    Respond to a note request with a note
    """
    note_request = get_object_or_404(NoteRequest, pk=pk, status='open')

    if request.user == note_request.requester:
        messages.error(request, 'You cannot respond to your own request.')
        return redirect('notes:request_detail', pk=pk)

    if request.method == 'POST':
        note_id = request.POST.get('note')
        message = request.POST.get('message', '')

        if note_id:
            note = get_object_or_404(
                Note,
                pk=note_id,
                uploaded_by=request.user,
                status='approved'
            )

            response, created = NoteRequestResponse.objects.get_or_create(
                request=note_request,
                note=note,
                defaults={
                    'responder': request.user,
                    'message': message
                }
            )

            if created:
                messages.success(request, 'Response submitted successfully!')
            else:
                messages.info(request, 'You already responded with this note.')

            return redirect('notes:request_detail', pk=pk)

    # Get user's approved notes (same course as request)
    my_notes = Note.objects.filter(
        uploaded_by=request.user,
        status='approved',
        course=note_request.course
    )

    context = {
        'request': note_request,
        'my_notes': my_notes,
    }

    return render(request, 'notes/respond_to_request.html', context)


@login_required
def mark_best_answer(request, request_id, response_id):
    """
    Mark a response as the best answer
    """
    note_request = get_object_or_404(
        NoteRequest,
        pk=request_id,
        requester=request.user
    )
    response = get_object_or_404(
        NoteRequestResponse,
        pk=response_id,
        request=note_request
    )

    if request.method == 'POST':
        note_request.best_answer = response.note
        note_request.status = 'fulfilled'
        note_request.fulfilled_by = response.responder
        note_request.save()

        response.is_helpful = True
        response.save()

        messages.success(
            request,
            'Marked as best answer! Request is now fulfilled.'
        )
        return redirect('notes:request_detail', pk=request_id)

    return redirect('notes:request_detail', pk=request_id)


# MODERATOR VIEWS 

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



 
def leaderboard(request):
    """
    Display leaderboards — students only, moderators and admins excluded
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count, Avg, Sum

    STUDENT_FILTER = {'user__role': 'student', 'user__is_active': True}

    # All-time top contributors
    all_time = UserProfile.objects.select_related('user').filter(
        **STUDENT_FILTER
    ).order_by('-total_points')[:10]

    # Monthly top
    month_ago = timezone.now() - timedelta(days=30)
    monthly_points = PointTransaction.objects.filter(
        created_at__gte=month_ago,
        user__role='student',
        user__is_active=True,
    ).values('user').annotate(
        monthly_total=Sum('points')
    ).order_by('-monthly_total')[:10]

    monthly_users = []
    for entry in monthly_points:
        profile = UserProfile.objects.filter(
            user_id=entry['user'], **STUDENT_FILTER
        ).select_related('user').first()
        if profile:
            monthly_users.append({'profile': profile, 'monthly_points': entry['monthly_total']})

    # Highest rated contributors
    highest_rated = UserProfile.objects.select_related('user').filter(
        **STUDENT_FILTER
    ).annotate(
        avg_rating=Avg('user__notes__ratings__rating'),
        rating_count=Count('user__notes__ratings')
    ).filter(rating_count__gte=5).order_by('-avg_rating')[:10]

    # Trending this week
    week_ago = timezone.now() - timedelta(days=7)
    trending_points = PointTransaction.objects.filter(
        created_at__gte=week_ago,
        user__role='student',
        user__is_active=True,
    ).values('user').annotate(
        weekly_total=Sum('points')
    ).order_by('-weekly_total')[:10]

    trending_users = []
    for entry in trending_points:
        profile = UserProfile.objects.filter(
            user_id=entry['user'], **STUDENT_FILTER
        ).select_related('user').first()
        if profile:
            trending_users.append({'profile': profile, 'weekly_points': entry['weekly_total']})

    # Most helpful reviewers
    helpful_reviewers = UserProfile.objects.select_related('user').filter(
        user__role='student', user__is_active=True
    ).annotate(
        helpful_count=Count('user__ratings__helpful_marks')
    ).filter(helpful_count__gt=0).order_by('-helpful_count')[:10]

    context = {
        'all_time': all_time,
        'monthly_users': monthly_users,
        'highest_rated': highest_rated,
        'trending_users': trending_users,
        'helpful_reviewers': helpful_reviewers,
    }

    return render(request, 'notes/leaderboard.html', context)
def user_profile_view(request, username):
    """
    Display user profile — content differs based on role.
    Students  : badges, uploaded notes, point activity, download stats.
    Moderators: moderation action log, performance stats. No badges/points.
    """
    from django.contrib.auth import get_user_model
    from moderation.models import ModerationAction
    User = get_user_model()

    profile_user = get_object_or_404(User, username=username)
    role = getattr(profile_user, 'role', 'student')

    context = {
        'profile_user': profile_user,
        'is_own_profile': request.user == profile_user,
        'role': role,
    }

    if role == 'moderator':
        # ── Moderator profile ──────────────────────────────────────────
        recent_actions = ModerationAction.objects.filter(
            moderator=profile_user
        ).select_related('note', 'note__subject', 'note__course').order_by('-created_at')[:15]

        from django.db.models import Count as _Count
        action_stats = ModerationAction.objects.filter(
            moderator=profile_user
        ).aggregate(
            total=_Count('id'),
            approvals=_Count('id', filter=Q(action_type='approve')),
            rejections=_Count('id', filter=Q(action_type='reject')),
            removals=_Count('id', filter=Q(action_type='remove')),
        )

        context.update({
            'recent_actions': recent_actions,
            'action_stats':   action_stats,
        })

    else:
        # ── Student (or admin) profile ─────────────────────────────────
        profile, _ = UserProfile.objects.get_or_create(user=profile_user)

        earned_badges = UserBadge.objects.filter(
            user=profile_user
        ).select_related('badge').order_by('-earned_at')

        uploaded_notes = Note.objects.filter(
            uploaded_by=profile_user,
            status='approved'
        ).select_related('course', 'subject').order_by('-created_at')[:5]

        recent_activity = PointTransaction.objects.filter(
            user=profile_user
        ).order_by('-created_at')[:10]

        total_downloads_received = Download.objects.filter(
            note__uploaded_by=profile_user,
            is_download=True
        ).count()

        avg_rating = Note.objects.filter(
            uploaded_by=profile_user,
            status='approved'
        ).aggregate(avg=Avg('ratings__rating'))['avg'] or 0

        context.update({
            'profile':                 profile,
            'earned_badges':           earned_badges,
            'uploaded_notes':          uploaded_notes,
            'recent_activity':         recent_activity,
            'total_downloads_received':total_downloads_received,
            'avg_rating':              round(avg_rating, 1),
        })

    return render(request, 'notes/user_profile.html', context)
 
 
@login_required
def my_profile(request):
    """
    Redirect to user's own profile
    """
    return redirect('notes:user_profile', username=request.user.username)