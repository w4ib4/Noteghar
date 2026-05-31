from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta
from django.db.models import F, Q, Count, Avg, Case, When, Value, IntegerField
from django.db.models.functions import Coalesce
from django.db.models import Avg


class Course(models.Model):
    """
    Academic courses/programs ( Computer Science, Engineering....)
    """
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Semester(models.Model):
    """
    Semester levels (1st, 2nd, 3rd, ...)
    """
    name = models.CharField(max_length=50)
    number = models.IntegerField(unique=True)

    class Meta:
        ordering = ['number']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """
    Subjects under courses and semesters
    """
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='subjects')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='subjects')
    description = models.TextField(blank=True)
    slug = models.SlugField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['course', 'semester', 'name']
        unique_together = ['code', 'course', 'semester']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.code}-{self.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name} ({self.course.code}, {self.semester.name})"


class Institution(models.Model):
    """
    Educational institutions/universities
    """
    name = models.CharField(max_length=300, unique=True)
    short_name = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200, blank=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True, help_text='Is this institution accepting submissions?')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.short_name if self.short_name else self.name

    def get_total_notes(self):
        """Get count of approved notes from this institution"""
        return self.notes.filter(status='approved').count()

class Tag(models.Model):
    """Pre-defined and user-suggested tags"""
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-usage_count', 'name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Note(models.Model):
    """
    Uploaded study materials/notes
    """
    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    title = models.CharField(max_length=300)
    description = models.TextField()
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='notes')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='notes')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='notes')
    # institution = models.ForeignKey(
    #     Institution,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='notes',
    #     help_text='Institution where this material is used'
    # )
    assigned_moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_notes',
        help_text='Moderator assigned to review this note'
    )
    # File upload
    file = models.FileField(
        upload_to='notes/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc', 'ppt', 'pptx'])]
    )
    file_size = models.IntegerField(default=0, help_text="File size in bytes")

    # Metadata
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tags = models.ManyToManyField(Tag, blank=True, related_name='notes')

    # Stats
    download_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_notes'

    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    # Rating helpers
    def get_average_rating(self):
        # Get average rating for this note
        avg = self.ratings.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0

    def get_rating_count(self):
        # Get total number of ratings
        return self.ratings.count()

    def get_user_rating(self, user):
        # Get specific user's rating for this note
        if user.is_authenticated:
            try:
                return self.ratings.get(user=user).rating
            except Rating.DoesNotExist:
                return None
        return None

    def get_file_extension(self):
        return self.file.name.split('.')[-1].upper()

    def get_file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)

    def is_approved(self):
        return self.status == 'approved'

    def assign_moderator(self):
        """
        Automatically assign a moderator based on specialization with load balancing.
        Priority: subject specialist → course specialist → any active moderator.
        Among eligible moderators, pick the one with fewest currently assigned pending notes.
        """
        from accounts.models import User
        from django.db.models import Count, Q
        from moderation.models import ModerationSettings

        # Get moderation settings (avoid shadowing django.conf.settings)
        mod_settings = ModerationSettings.get_settings()

        if not mod_settings.enable_auto_assignment:
            return None

        # 1. Try subject specialists first
        moderators = User.objects.filter(
            role='moderator',
            is_active=True,
            specialization_subjects=self.subject
        )

        # 2. Fall back to course specialists
        if not moderators.exists():
            moderators = User.objects.filter(
                role='moderator',
                is_active=True,
                specialization_courses=self.course
            )

        # 3. Fall back to any active moderator or superuser
        if not moderators.exists():
            moderators = User.objects.filter(
                Q(role='moderator', is_active=True) | Q(is_superuser=True)
            )

        if not moderators.exists():
            return None

        # Load balancing: pick the moderator with fewest pending assigned notes
        if mod_settings.load_balancing_enabled:
            moderator = moderators.annotate(
                num_notes=Count('assigned_notes', filter=Q(assigned_notes__status='pending'))
            ).order_by('num_notes').first()
        else:
            moderator = moderators.first()

        self.assigned_moderator = moderator
        return moderator

    def save(self, *args, **kwargs):
        # Auto-assign moderator on first save if note is pending and not yet assigned
        if not self.pk and self.status == 'pending' and self.assigned_moderator is None:
            self.assign_moderator()
        super().save(*args, **kwargs)

    def is_bookmarked_by(self, user):
        """Check if note is bookmarked by user"""
        if not user.is_authenticated:
            return False
        return self.bookmarked_by.filter(user=user).exists()
    
    def get_bookmark_count(self):
        """Get total bookmark count"""
        return self.bookmarked_by.count()


class Download(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='downloads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_download = models.BooleanField(default=True, help_text='False if just viewed')  # ADD THIS
    
    class Meta:
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['user', '-downloaded_at']),
            models.Index(fields=['note', '-downloaded_at']),
        ]


class Rating(models.Model):
    """
    User ratings for notes (1-5 stars)
    """
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ratings')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Rating from 1 to 5 stars"
    )
    review = models.TextField(blank=True, help_text="Optional review text")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_helpful_count(self):
        """Get count of users who found this helpful"""
        return self.helpful_marks.count()
    
    def is_helpful_by_user(self, user):
        """Check if user marked this as helpful"""
        return self.helpful_marks.filter(user=user).exists()
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['note', 'user']
        indexes = [
            models.Index(fields=['note', '-created_at']),
            models.Index(fields=['user']),
        ]


class Report(models.Model):
    """
    User reports for inappropriate content
    """
    REASON_CHOICES = (
        ('spam', 'Spam or Misleading'),
        ('inappropriate', 'Inappropriate Content'),
        ('copyright', 'Copyright Violation'),
        ('low_quality', 'Low Quality/Incomplete'),
        ('wrong_category', 'Wrong Category'),
        ('other', 'Other'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    )

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='reports')
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made'
    )
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(help_text="Detailed description of the issue")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Moderator actions
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reports_reviewed'
    )
    moderator_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report by {self.reported_by.username} on {self.note.title}"


class RatingHelpful(models.Model):
    """
    Track which users found a rating helpful
    """
    rating = models.ForeignKey('Rating', on_delete=models.CASCADE, related_name='helpful_marks')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('rating', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} found rating helpful"

class Bookmark(models.Model):
    """User bookmarks for notes"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    note = models.ForeignKey('Note', on_delete=models.CASCADE, related_name='bookmarked_by')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Personal notes about this bookmark')
    
    class Meta:
        unique_together = ['user', 'note']
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', '-created_at'])]
    
    def __str__(self):
        return f'{self.user.username} bookmarked {self.note.title}'
    
    def is_bookmarked_by(self, user):
        if not user.is_authenticated:
            return False
        return self.bookmarked_by.filter(user=user).exists()
    
    def get_bookmark_count(self):
        return self.bookmarked_by.count()

class RateLimit(models.Model):
    """Track user actions for rate limiting"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=50, choices=[
        ('upload', 'Upload Note'),
        ('report', 'Report Note'),
        ('rating', 'Rate Note'),
    ])
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['user', 'action_type', '-timestamp'])]


class NoteRequest(models.Model):
    """Users can request notes for specific topics"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('fulfilled', 'Fulfilled'),
        ('expired', 'Expired'),
    ]
    
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='note_requests')
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    semester = models.ForeignKey('Semester', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.SET_NULL, null=True, blank=True)
    topic = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    fulfilled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_requests')
    best_answer = models.ForeignKey('Note', on_delete=models.SET_NULL, null=True, blank=True, related_name='best_answer_for')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.topic} - {self.course.name}'
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def get_responses_count(self):
        return self.responses.count()


class NoteRequestResponse(models.Model):
    """Responses to note requests"""
    request = models.ForeignKey(NoteRequest, on_delete=models.CASCADE, related_name='responses')
    note = models.ForeignKey('Note', on_delete=models.CASCADE)
    responder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_helpful = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['request', 'note']
        ordering = ['-created_at']

class Badge(models.Model):
    """
    Achievement badges that users can earn
    """
    CATEGORY_CHOICES = [
        ('contributor', 'Contributor'),
        ('engagement', 'Engagement'),
        ('community', 'Community'),
        ('special', 'Special'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    icon = models.CharField(max_length=10, help_text='Emoji icon')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    
    # Requirements
    requirement_type = models.CharField(max_length=50, help_text='upload_count, rating_avg, etc.')
    requirement_value = models.IntegerField(help_text='Threshold value')
    
    # Rewards
    points_reward = models.IntegerField(default=0)
    
    # Display
    color = models.CharField(max_length=20, default='primary')
    order = models.IntegerField(default=0, help_text='Display order')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['category', 'order']
    
    def __str__(self):
        return f'{self.icon} {self.name}'
 
 
class UserBadge(models.Model):
    """
    Badges earned by users
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    progress = models.IntegerField(default=0, help_text='Progress towards next level')
    
    class Meta:
        unique_together = ['user', 'badge']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.badge.name}'
 
 
class UserProfile(models.Model):
    """
    Extended user profile with gamification stats
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    
    # Points & Level
    total_points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    
    # Stats
    notes_uploaded = models.IntegerField(default=0)
    notes_downloaded = models.IntegerField(default=0)
    notes_viewed = models.IntegerField(default=0)
    reviews_written = models.IntegerField(default=0)
    helpful_marks_received = models.IntegerField(default=0)
    bookmarks_count = models.IntegerField(default=0)
    requests_fulfilled = models.IntegerField(default=0)
    
    # Streaks
    upload_streak = models.IntegerField(default=0)
    login_streak = models.IntegerField(default=0)
    last_upload_date = models.DateField(null=True, blank=True)
    last_login_date = models.DateField(null=True, blank=True)
    
    # Rankings
    global_rank = models.IntegerField(null=True, blank=True)
    monthly_rank = models.IntegerField(null=True, blank=True)
    
    # Bio & Social
    bio = models.TextField(blank=True, max_length=500)
    website = models.URLField(blank=True)
    twitter = models.CharField(max_length=100, blank=True)
    
    # Settings
    show_badges = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f'{self.user.username} Profile'
    
    def get_level(self):
        """Calculate level based on points"""
        if self.total_points < 100:
            return 1
        elif self.total_points < 500:
            return 2
        elif self.total_points < 1000:
            return 3
        elif self.total_points < 2500:
            return 4
        elif self.total_points < 5000:
            return 5
        else:
            return 6
    
    def get_level_name(self):
        """Get level name"""
        levels = {
            1: '📝 Beginner',
            2: '📚 Student',
            3: '📖 Scholar',
            4: '🎓 Expert',
            5: '👨‍🏫 Professor',
            6: '👑 Legend',
        }
        return levels.get(self.level, '📝 Beginner')
    
    def get_next_level_points(self):
        """Points needed for next level"""
        thresholds = [100, 500, 1000, 2500, 5000]
        for threshold in thresholds:
            if self.total_points < threshold:
                return threshold
        return None  # Max level
    
    def add_points(self, points, reason=''):
        """Add points and check for level up"""
        old_level = self.level
        self.total_points += points
        self.level = self.get_level()
        self.save()
        
        # Check if leveled up
        if self.level > old_level:
            return True  # Leveled up
        return False
 
 
class PointTransaction(models.Model):
    """
    Log of all point transactions
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='point_transactions')
    points = models.IntegerField()
    reason = models.CharField(max_length=200)
    related_note = models.ForeignKey(Note, on_delete=models.SET_NULL, null=True, blank=True)
    related_rating = models.ForeignKey(Rating, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username}: {self.points} pts - {self.reason}'