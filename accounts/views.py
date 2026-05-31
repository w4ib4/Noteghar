from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View

# Import all forms
from .forms import (
    StudentSignupForm, 
    ModeratorSignupForm, 
    AdminSignupForm,
    UserProfileForm 
)

# ROLE-BASED SIGNUP VIEWS

# ==========================================
# ROLE-BASED LOGIN VIEWS
# ==========================================

def student_login_view(request):
    """Student login — renders custom template, form POSTs to allauth account_login."""
    if request.user.is_authenticated:
        return redirect('core:home')
    return render(request, 'accounts/login_student.html')


def moderator_login_view(request):
    """Moderator login — renders custom template, form POSTs to allauth account_login."""
    if request.user.is_authenticated:
        return redirect('core:home')
    return render(request, 'accounts/login_moderator.html')


def admin_login_view(request):
    """Admin login — renders custom template, form POSTs to allauth account_login."""
    if request.user.is_authenticated:
        return redirect('core:home')
    return render(request, 'accounts/login_admin.html')


class StudentSignupView(View):
    """
    Student registration view
    """
    template_name = 'accounts/signup_student.html'
    form_class = StudentSignupForm
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save(request)
            # login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(
                request,
                'Welcome to NoteGhar! Your student account has been created.'
            )
            return redirect('accounts:student_login')
        return render(request, self.template_name, {'form': form})


class ModeratorSignupView(View):
    """
    Moderator registration view with specialization
    """
    template_name = 'accounts/signup_moderator.html'
    form_class = ModeratorSignupForm
    
    def get(self, request):
        # Allow logged-in students to apply for moderator role
        if request.user.is_authenticated and getattr(request.user, 'role', None) != 'student':
            return redirect('core:home')
        form = self.form_class()
        return render(request, self.template_name, {'form': form, 'is_upgrade': request.user.is_authenticated})

    def post(self, request):
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid():
            if request.user.is_authenticated:
                # Upgrade existing student account to pending moderator
                user = request.user
                user.role = 'moderator'
                user.bio = form.cleaned_data.get('qualifications', '')
                user.qualification_document = form.cleaned_data.get('qualification_document')
                user.is_active = False
                user.is_staff = True
                user.save()
                user.specialization_courses.set(form.cleaned_data.get('specialization_courses', []))
                user.specialization_subjects.set(form.cleaned_data.get('specialization_subjects', []))
                from django.contrib.auth import logout
                logout(request)
                messages.warning(
                    request,
                    'Your moderator application has been submitted! '
                    'Your account is now pending admin approval. '
                    'You will be notified once approved.'
                )
                return redirect('accounts:student_login')
            else:
                form.save(request)
                messages.warning(
                    request,
                    'Your moderator application has been submitted! '
                    'An administrator will review your qualifications. '
                    'You will be notified once approved.'
                )
                return redirect('account_login')
        return render(request, self.template_name, {'form': form, 'is_upgrade': request.user.is_authenticated})

class AdminSignupView(View):
    """
    Admin registration view (restricted)
    """
    template_name = 'accounts/signup_admin.html'
    form_class = AdminSignupForm
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('core:home')
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save(request)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(
                request,
                '✅ Admin account created successfully! You have full system access.'
            )
            return redirect('admin:index')
        return render(request, self.template_name, {'form': form})


# PROFILE VIEW

@login_required
def profile_view(request):
    """
    User profile view and update
    """
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    # Get user statistics
    if request.user.role == 'student':
        from notes.models import Note, Download
        
        uploaded_notes = Note.objects.filter(uploaded_by=request.user)
        total_uploads = uploaded_notes.count()
        approved_uploads = uploaded_notes.filter(status='approved').count()
        pending_uploads = uploaded_notes.filter(status='pending').count()
        total_downloads_of_my_notes = sum(note.download_count for note in uploaded_notes)
        
        my_downloads = Download.objects.filter(user=request.user).count()
        
        stats = {
            'total_uploads': total_uploads,
            'approved_uploads': approved_uploads,
            'pending_uploads': pending_uploads,
            'total_downloads_of_my_notes': total_downloads_of_my_notes,
            'my_downloads': my_downloads,
        }
    elif request.user.role == 'moderator':
        from moderation.models import ModerationAction
        
        my_actions = ModerationAction.objects.filter(moderator=request.user)
        stats = {
            'total_actions': my_actions.count(),
            'approvals': my_actions.filter(action_type='approve').count(),
            'rejections': my_actions.filter(action_type='reject').count(),
            'removals': my_actions.filter(action_type='remove').count(),
        }
    else:
        stats = {}
    
    context = {
        'form': form,
        'stats': stats,
    }
    
    return render(request, 'accounts/profile.html', context)

def signup_select_view(request):
    """Role selection page for signup"""
    if request.user.is_authenticated:
        return redirect('core:home')
    return render(request, 'accounts/signup_select.html')