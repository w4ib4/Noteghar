from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Avg
from django.http import FileResponse, Http404
from django.utils import timezone
from .models import Note, Course, Semester, Subject, Download
from .forms import NoteUploadForm, NoteSearchForm

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

def note_detail_view(request, pk):
    """
    Display note details
    """
    note = get_object_or_404(Note, pk=pk, status='approved')
    note.view_count += 1
    note.save(update_fields=['view_count'])
    
    # To Check if user has downloaded the note
    has_downloaded = False
    if request.user.is_authenticated:
        has_downloaded = Download.objects.filter(note=note, user=request.user).exists()
    
    context = {
        'note': note,
        'has_downloaded': has_downloaded,
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