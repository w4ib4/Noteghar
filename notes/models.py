from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify

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
