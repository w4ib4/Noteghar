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
