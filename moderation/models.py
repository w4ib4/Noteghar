# ==========================================
# moderation/models.py - COMPLETE MODERATION MODELS
# ==========================================

from django.db import models
from django.conf import settings
from django.utils import timezone

class ModerationAction(models.Model):
    """
    Log of all moderation actions for tracking and audit trail
    """
    ACTION_TYPES = [
        ('approve', 'Approved Content'),
        ('reject', 'Rejected Content'),
        ('remove', 'Removed Content'),
        ('warn', 'Warned User'),
        ('restore', 'Restored Content'),
        ('edit', 'Edited Content'),
    ]
    
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='moderation_actions',
        help_text='Moderator who performed the action'
    )
    
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPES,
        db_index=True
    )
    
    # Link to the note being moderated
    note = models.ForeignKey(
        'notes.Note',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='moderation_actions'
    )
    
    # Link to report if action was based on a report
    report = models.ForeignKey(
        'notes.Report',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderation_actions'
    )
    
    # Target user (if warning/action against user)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_moderation_actions',
        null=True,
        blank=True,
        help_text='User who received this moderation action'
    )
    
    reason = models.TextField(
        help_text='Reason for this moderation action'
    )
    
    # Additional details
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text='IP address of moderator'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['moderator', '-created_at']),
            models.Index(fields=['action_type', '-created_at']),
            models.Index(fields=['note', '-created_at']),
        ]
        verbose_name = 'Moderation Action'
        verbose_name_plural = 'Moderation Actions'
    
    def __str__(self):
        return f"{self.moderator.username} - {self.get_action_type_display()} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ModeratorPerformance(models.Model):
    """
    Track moderator performance metrics (optional but useful for analytics)
    """
    moderator = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance',
        limit_choices_to={'role': 'moderator'}
    )
    
    total_actions = models.IntegerField(default=0)
    total_approvals = models.IntegerField(default=0)
    total_rejections = models.IntegerField(default=0)
    total_removals = models.IntegerField(default=0)
    
    # Average time to process (in minutes)
    avg_processing_time = models.FloatField(
        default=0.0,
        help_text='Average time to process a note (in minutes)'
    )
    
    # Quality metrics
    accuracy_score = models.FloatField(
        default=0.0,
        help_text='Accuracy score based on admin reviews (0-100)'
    )
    
    last_action_date = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Moderator Performance'
        verbose_name_plural = 'Moderator Performances'
    
    def __str__(self):
        return f"{self.moderator.username} - Performance Metrics"
    
    def update_metrics(self):
        """Recalculate performance metrics"""
        actions = ModerationAction.objects.filter(moderator=self.moderator)
        
        self.total_actions = actions.count()
        self.total_approvals = actions.filter(action_type='approve').count()
        self.total_rejections = actions.filter(action_type='reject').count()
        self.total_removals = actions.filter(action_type='remove').count()
        
        if actions.exists():
            self.last_action_date = actions.first().created_at
        
        self.save()


class ModerationQueue(models.Model):
    """
    Priority queue for moderation tasks
    """
    PRIORITY_CHOICES = [
        ('low', 'Low Priority'),
        ('normal', 'Normal Priority'),
        ('high', 'High Priority'),
        ('urgent', 'Urgent'),
    ]
    
    note = models.OneToOneField(
        'notes.Note',
        on_delete=models.CASCADE,
        related_name='queue_entry'
    )
    
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='normal',
        db_index=True
    )
    
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_queue_items',
        limit_choices_to={'role': 'moderator'}
    )
    
    # Auto-calculated based on report counts
    report_count = models.IntegerField(default=0)
    
    # How long has this been pending
    days_pending = models.IntegerField(default=0)
    
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', '-report_count', 'added_at']
        verbose_name = 'Moderation Queue Entry'
        verbose_name_plural = 'Moderation Queue'
    
    def __str__(self):
        return f"{self.note.title} - {self.get_priority_display()}"
    
    def calculate_priority(self):
        """Auto-calculate priority based on various factors"""
        from datetime import timedelta
        
        # Count reports
        self.report_count = self.note.reports.filter(status='pending').count()
        
        # Calculate days pending
        self.days_pending = (timezone.now() - self.note.created_at).days
        
        # Determine priority
        if self.report_count >= 5:
            self.priority = 'urgent'
        elif self.report_count >= 3:
            self.priority = 'high'
        elif self.days_pending >= 7:
            self.priority = 'high'
        elif self.days_pending >= 3:
            self.priority = 'normal'
        else:
            self.priority = 'low'
        
        self.save()


class ModeratorNote(models.Model):
    """
    Internal notes between moderators about specific content
    """
    note = models.ForeignKey(
        'notes.Note',
        on_delete=models.CASCADE,
        related_name='moderator_notes'
    )
    
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='internal_notes',
        limit_choices_to={'role__in': ['moderator', 'admin']}
    )
    
    content = models.TextField(
        help_text='Internal note visible only to moderators'
    )
    
    is_flagged = models.BooleanField(
        default=False,
        help_text='Flag for admin attention'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Moderator Note'
        verbose_name_plural = 'Moderator Notes'
    
    def __str__(self):
        return f"Note by {self.moderator.username} on {self.note.title}"


class ModerationSettings(models.Model):
    """
    System-wide moderation settings (singleton pattern)
    """
    # Auto-approval settings
    auto_approve_trusted_users = models.BooleanField(
        default=False,
        help_text='Auto-approve notes from verified users with good history'
    )
    
    trusted_user_threshold = models.IntegerField(
        default=10,
        help_text='Number of approved notes needed to become trusted'
    )
    
    # Queue settings
    max_pending_days = models.IntegerField(
        default=7,
        help_text='Maximum days a note should be pending before escalation'
    )
    
    # Assignment settings
    enable_auto_assignment = models.BooleanField(
        default=True,
        help_text='Automatically assign notes to moderators based on specialization'
    )
    
    load_balancing_enabled = models.BooleanField(
        default=True,
        help_text='Distribute notes evenly among moderators'
    )
    
    # Notification settings
    notify_on_assignment = models.BooleanField(
        default=True,
        help_text='Email moderators when notes are assigned'
    )
    
    notify_on_report = models.BooleanField(
        default=True,
        help_text='Email moderators when reports are filed'
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = 'Moderation Settings'
        verbose_name_plural = 'Moderation Settings'
    
    def __str__(self):
        return "Moderation Settings"
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists (singleton)
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings