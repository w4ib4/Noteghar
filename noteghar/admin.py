from django.contrib import admin
from django.contrib.admin import AdminSite
from django.shortcuts import render
from accounts.models import User
from notes.models import Note, Report, Institution, Course, Subject, Download
from moderation.models import ModerationAction

class CustomAdminSite(AdminSite):
    site_header = "NoteGhar Administration"
    site_title = "NoteGhar Admin"
    index_title = "Dashboard"
    
    def index(self, request, extra_context=None):
        # Gather statistics
        extra_context = extra_context or {}
        
        # User statistics
        extra_context['total_users'] = User.objects.count()
        extra_context['students_count'] = User.objects.filter(role='student').count()
        extra_context['moderators_count'] = User.objects.filter(role='moderator', is_active=True).count()
        extra_context['pending_moderators_count'] = User.objects.filter(role='moderator', is_active=False).count()
        
        # Note statistics
        extra_context['pending_notes_count'] = Note.objects.filter(status='pending').count()
        extra_context['approved_notes_count'] = Note.objects.filter(status='approved').count()
        extra_context['total_notes'] = Note.objects.count()
        
        # Report statistics
        extra_context['pending_reports_count'] = Report.objects.filter(status='pending').count()
        
        # Other statistics
        extra_context['institutions_count'] = Institution.objects.count()
        extra_context['courses_count'] = Course.objects.count()
        extra_context['subjects_count'] = Subject.objects.count()
        extra_context['total_downloads'] = Download.objects.count()
        
        # Recent activity
        extra_context['recent_notes'] = Note.objects.select_related('uploaded_by').order_by('-created_at')[:10]
        
        return super().index(request, extra_context)

# Replace default admin site
admin_site = CustomAdminSite(name='admin')
admin.site = admin_site