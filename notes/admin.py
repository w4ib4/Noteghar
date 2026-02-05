from django.contrib import admin
from django.utils.html import format_html
from .models import Course, Semester, Subject, Note, Download

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'created_at')
    search_fields = ('name', 'code')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('number', 'name')
    ordering = ('number',)


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'course', 'semester')
    list_filter = ('course', 'semester')
    search_fields = ('name', 'code')
    prepopulated_fields = {'slug': ('code', 'name')}


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'subject', 'uploaded_by', 'status', 'download_count', 'created_at')
    list_filter = ('status', 'course', 'semester', 'created_at')
    search_fields = ('title', 'description', 'tags')
    readonly_fields = ('download_count', 'view_count', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'file', 'tags')
        }),
        ('Classification', {
            'fields': ('course', 'semester', 'subject')
        }),
        ('Status', {
            'fields': ('status', 'approved_by', 'approved_at')
        }),
        ('Metadata', {
            'fields': ('uploaded_by', 'download_count', 'view_count', 'created_at', 'updated_at')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.role == 'admin':
            return qs
        elif request.user.role == 'moderator':
            return qs
        return qs.filter(uploaded_by=request.user)


@admin.register(Download)
class DownloadAdmin(admin.ModelAdmin):
    list_display = ('note', 'user', 'downloaded_at', 'ip_address')
    list_filter = ('downloaded_at',)
    search_fields = ('note__title', 'user__username')
    readonly_fields = ('note', 'user', 'downloaded_at', 'ip_address')


from .models import Rating, Report

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('note', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('note__title', 'user__username', 'review')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('note', 'reported_by', 'reason', 'status', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('note__title', 'reported_by__username', 'description')
    readonly_fields = ('created_at', 'reviewed_at')
    
    fieldsets = (
        ('Report Information', {
            'fields': ('note', 'reported_by', 'reason', 'description', 'created_at')
        }),
        ('Moderator Actions', {
            'fields': ('status', 'reviewed_by', 'moderator_notes', 'reviewed_at')
        }),
    )
