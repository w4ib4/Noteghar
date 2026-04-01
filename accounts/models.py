from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom User model with role-based access
    """
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    institution = models.ForeignKey(
        'notes.Institution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text='User\'s affiliated institution'
    )
    
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    # Moderator-specific fields
    specialization_courses = models.ManyToManyField(
        'notes.Course',
        blank=True,
        related_name='specialized_moderators',
        help_text='Courses this moderator specializes in'
    )
    specialization_subjects = models.ManyToManyField(
        'notes.Subject',
        blank=True,
        related_name='specialized_moderators',
        help_text='Specific subjects within courses'
    )
    
    # ✅ NEW: Qualification proof documents
    qualification_document = models.FileField(
        upload_to='qualifications/%Y/%m/',
        blank=True,
        null=True,
        help_text='Upload degree certificate, transcript, or other proof of qualification (PDF, JPG, PNG)'
    )
    
    qualification_verified = models.BooleanField(
        default=False,
        help_text='Admin has verified the qualification documents'
    )
    
    qualification_notes = models.TextField(
        blank=True,
        help_text='Admin notes about qualification verification'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def is_student(self):
        return self.role == 'student'
    
    def is_moderator(self):
        return self.role == 'moderator'
    
    def is_admin_user(self):
        return self.role == 'admin' or self.is_superuser
    
    def can_moderate_course(self, course):
        """Check if moderator can handle notes from this course"""
        if not self.is_moderator():
            return False
        if self.is_admin_user():
            return True
        return self.specialization_courses.filter(id=course.id).exists()
    
    def can_moderate_subject(self, subject):
        """Check if moderator can handle notes from this subject"""
        if not self.is_moderator():
            return False
        if self.is_admin_user():
            return True
        
        if self.specialization_courses.filter(id=subject.course.id).exists():
            if not self.specialization_subjects.exists():
                return True
            return self.specialization_subjects.filter(id=subject.id).exists()
        return False
    
    def get_specializations_display(self):
        """Get formatted string of specializations"""
        courses = self.specialization_courses.all()
        if courses:
            return ", ".join([c.name for c in courses])
        return "No specialization set"
    
    def get_pending_assignments_count(self):
        """Get count of pending notes assigned to this moderator"""
        if not self.is_moderator():
            return 0
        return self.assigned_notes.filter(status='pending').count()