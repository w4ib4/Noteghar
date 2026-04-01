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
        if request.user.is_authenticated:
            return redirect('core:home')
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        # ✅ FIXED: Pass both POST and FILES
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(request)
            messages.warning(
                request,
                '⏳ Your moderator application has been submitted! '
                'An administrator will review your qualifications and specializations. '
                'You will receive an email once approved.'
            )
            return redirect('account_login')
        return render(request, self.template_name, {'form': form})

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
        from notes.models import ModerationAction
        
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