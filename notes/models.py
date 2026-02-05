from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator
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
        return f"{self.code} - {self.name} ({self.course.code}, Sem {self.semester.number})"


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
    
    # File upload
    file = models.FileField(
        upload_to='notes/%Y/%m/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'doc', 'ppt', 'pptx'])]
    )
    file_size = models.IntegerField(default=0, help_text="File size in bytes")
    
    # Metadata
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    
    # Stats
    download_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)
    
    def get_average_rating(self):
        #Get average rating for this note
        avg = self.ratings.aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0

    def get_rating_count(self):
        #Get total number of ratings
        return self.ratings.count()

    def get_user_rating(self, user):
        #Get specific user's rating for this note
        if user.is_authenticated:
            try:
                return self.ratings.get(user=user).rating
            except Rating.DoesNotExist:
                return None
        return None
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
    
    def get_file_extension(self):
        return self.file.name.split('.')[-1].upper()
    
    def get_file_size_mb(self):
        return round(self.file_size / (1024 * 1024), 2)
    
    def is_approved(self):
        return self.status == 'approved'


class Download(models.Model):
    """
    Track note downloads
    """
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='downloads')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='downloads')
    downloaded_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-downloaded_at']
    
    def __str__(self):
        return f"{self.user.username} downloaded {self.note.title}"

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
    
    class Meta:
        unique_together = ['note', 'user']  # One rating per user per note
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} rated {self.note.title}: {self.rating}/5"
    
    def get_helpful_count(self):
        """Get count of users who found this rating helpful"""
        return self.helpful_marks.count()

    def is_helpful_by_user(self, user):
        """Check if specific user marked this as helpful"""
        if user.is_authenticated:
            return self.helpful_marks.filter(user=user).exists()
        return False


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


class ModerationAction(models.Model):
    """
    Log of all moderation actions for tracking
    """
    ACTION_TYPES = [
        ('approve', 'Approved Content'),
        ('reject', 'Rejected Content'),
        ('remove', 'Removed Content'),
        ('warn', 'Warned User'),
        ('restore', 'Restored Content'),
    ]
    
    moderator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='moderation_actions'
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, null=True, blank=True)
    report = models.ForeignKey(Report, on_delete=models.SET_NULL, null=True, blank=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='received_actions', 
        null=True, 
        blank=True
    )
    
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.moderator.username} - {self.action_type} - {self.created_at}"