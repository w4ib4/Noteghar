from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User Admin with qualification document viewing"""
    
    list_display = (
        'username', 
        'email', 
        'role', 
        'institution', 
        'is_verified',
        'qualification_status',  # New
        'created_at'
    )
    list_filter = (
        'role', 
        'is_verified', 
        'qualification_verified',  # New
        'is_active', 
        'created_at'
    )
    search_fields = ('username', 'email', 'institution__name')
    ordering = ('-created_at',)
    
    # Custom column to show qualification status
    def qualification_status(self, obj):
        if obj.role != 'moderator':
            return '-'
        
        if obj.qualification_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Verified</span>'
            )
        elif obj.qualification_document:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳ Pending Review</span>'
            )
        else:
            return format_html(
                '<span style="color: red;">✗ No Document</span>'
            )
    qualification_status.short_description = 'Qualification Status'
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'phone', 'institution', 'profile_picture', 'bio', 'is_verified')
        }),
        ('Moderator Specializations', {
            'fields': ('specialization_courses', 'specialization_subjects'),
            'classes': ('collapse',)
        }),
        ('Qualification Documents', {
            'fields': (
                'qualification_document',
                'qualification_document_preview',  # Custom readonly field
                'qualification_verified',
                'qualification_notes'
            ),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('qualification_document_preview',)
    
    # Custom method to preview the document
    def qualification_document_preview(self, obj):
        if not obj.qualification_document:
            return 'No document uploaded'
        
        file_url = obj.qualification_document.url
        file_name = obj.qualification_document.name.split('/')[-1]
        file_ext = file_name.split('.')[-1].lower()
        
        if file_ext in ['jpg', 'jpeg', 'png']:
            return format_html(
                '<div>'
                '<p><strong>Document:</strong> <a href="{}" target="_blank">{}</a></p>'
                '<img src="{}" style="max-width: 500px; max-height: 500px; border: 1px solid #ddd; padding: 5px;"/>'
                '</div>',
                file_url, file_name, file_url
            )
        elif file_ext == 'pdf':
            return format_html(
                '<div>'
                '<p><strong>Document:</strong> <a href="{}" target="_blank">{}</a></p>'
                '<p><a href="{}" target="_blank" class="button">📄 View PDF</a></p>'
                '<iframe src="{}" width="100%" height="600px" style="border: 1px solid #ddd;"></iframe>'
                '</div>',
                file_url, file_name, file_url, file_url
            )
        else:
            return format_html(
                '<a href="{}" target="_blank">Download: {}</a>',
                file_url, file_name
            )
    
    qualification_document_preview.short_description = 'Document Preview'
    
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('role', 'email', 'institution')
        }),
    )