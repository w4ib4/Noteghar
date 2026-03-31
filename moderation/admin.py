# ==========================================
# moderation/admin.py
# ==========================================

from django.contrib import admin
from django.utils.html import format_html
from .models import (
    ModerationAction,
    ModeratorPerformance,
    ModerationQueue,
    ModeratorNote,
    ModerationSettings
)


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ('id', 'moderator', 'action_type', 'note_link', 'target_user', 'created_at')
    list_filter = ('action_type', 'created_at', 'moderator')
    search_fields = ('moderator__username', 'target_user__username', 'note__title', 'reason')
    readonly_fields = ('created_at', 'ip_address')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Action Information', {
            'fields': ('moderator', 'action_type', 'reason')
        }),
        ('Related Objects', {
            'fields': ('note', 'report', 'target_user')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def note_link(self, obj):
        if obj.note:
            return format_html(
                '<a href="/admin/notes/note/{}/change/">{}</a>',
                obj.note.id,
                obj.note.title[:50]
            )
        return '-'
    note_link.short_description = 'Note'


@admin.register(ModeratorPerformance)
class ModeratorPerformanceAdmin(admin.ModelAdmin):
    list_display = (
        'moderator',
        'total_actions',
        'total_approvals',
        'total_rejections',
        'accuracy_score',
        'last_action_date'
    )
    list_filter = ('last_action_date',)
    search_fields = ('moderator__username',)
    readonly_fields = (
        'total_actions',
        'total_approvals',
        'total_rejections',
        'total_removals',
        'last_action_date',
        'updated_at'
    )
    
    actions = ['update_metrics']
    
    def update_metrics(self, request, queryset):
        for performance in queryset:
            performance.update_metrics()
        self.message_user(request, f"Updated metrics for {queryset.count()} moderators.")
    update_metrics.short_description = "Recalculate performance metrics"


@admin.register(ModerationQueue)
class ModerationQueueAdmin(admin.ModelAdmin):
    list_display = (
        'note',
        'priority',
        'assigned_to',
        'report_count',
        'days_pending',
        'added_at'
    )
    list_filter = ('priority', 'assigned_to', 'added_at')
    search_fields = ('note__title',)
    readonly_fields = ('report_count', 'days_pending', 'added_at', 'updated_at')
    
    actions = ['recalculate_priority']
    
    def recalculate_priority(self, request, queryset):
        for queue_item in queryset:
            queue_item.calculate_priority()
        self.message_user(request, f"Recalculated priority for {queryset.count()} items.")
    recalculate_priority.short_description = "Recalculate priority"


@admin.register(ModeratorNote)
class ModeratorNoteAdmin(admin.ModelAdmin):
    list_display = ('note', 'moderator', 'is_flagged', 'created_at')
    list_filter = ('is_flagged', 'created_at', 'moderator')
    search_fields = ('note__title', 'moderator__username', 'content')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ModerationSettings)
class ModerationSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Auto-Approval Settings', {
            'fields': (
                'auto_approve_trusted_users',
                'trusted_user_threshold'
            )
        }),
        ('Queue Settings', {
            'fields': ('max_pending_days',)
        }),
        ('Assignment Settings', {
            'fields': (
                'enable_auto_assignment',
                'load_balancing_enabled'
            )
        }),
        ('Notification Settings', {
            'fields': (
                'notify_on_assignment',
                'notify_on_report'
            )
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('updated_at',)
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not ModerationSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion
        return False