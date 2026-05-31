from allauth.account.forms import SignupForm
from django import forms
from django.core.exceptions import ValidationError
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3
from .models import User
from notes.models import Course, Subject, Institution
import re

# Shared helpers
# Common email typos: wrong TLD or wrong domain
_TLD_TYPOS = {
    '.con': '.com', '.cmo': '.com', '.ocm': '.com', '.cpm': '.com',
    '.coml': '.com', '.ney': '.net', '.ogr': '.org', '.rog': '.org',
    '.nte': '.net', '.con': '.com',
}
_DOMAIN_TYPOS = {
    'gmeel.com': 'gmail.com', 'gmial.com': 'gmail.com',
    'gamil.com': 'gmail.com', 'gmal.com':  'gmail.com',
    'gnail.com': 'gmail.com', 'gmail.con': 'gmail.com',
    'yaho.com':  'yahoo.com', 'yahooo.com': 'yahoo.com',
    'hotmial.com': 'hotmail.com', 'outlok.com': 'outlook.com',
}

def _check_email_typo(email):
    """Return a suggested correction if the email looks like a typo, else None."""
    if not email or '@' not in email:
        return None
    lo = email.lower().strip()
    at = lo.rfind('@')
    domain = lo[at + 1:]
    if domain in _DOMAIN_TYPOS:
        return lo[:at + 1] + _DOMAIN_TYPOS[domain]
    for bad, good in _TLD_TYPOS.items():
        if lo.endswith(bad):
            return lo[:-len(bad)] + good
    return None


def validate_strong_password(password):
    """
    Enforce:
      - At least 8 characters
      - At least one digit
      - At least one special character
    Raises ValidationError with a clear, specific message for each rule broken.
    """
    errors = []
    if len(password) < 8:
        errors.append('at least 8 characters')
    if not re.search(r'\d', password):
        errors.append('at least one number (0-9)')
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?`~]', password):
        errors.append('at least one special character (e.g. @, #, !, $)')
    if errors:
        raise ValidationError(
            'Password must contain ' + ', '.join(errors) + '.'
        )

# BASE ALLAUTH FORM
class CustomSignupForm(SignupForm):
    """Base signup form"""
    def save(self, request):
        user = super().save(request)
        return user

# STUDENT SIGNUP FORM
class StudentSignupForm(SignupForm):
    """Student registration form with institution"""
    
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(is_active=True),
        required=False,
        empty_label="Select your institution (Optional)",
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Select your educational institution'
    )
    
    captcha = ReCaptchaField(
        widget=ReCaptchaV3(action='student_signup'),
        label=''
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email Address'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        suggestion = _check_email_typo(email)
        if suggestion:
            raise forms.ValidationError(
                f'Did you mean {suggestion}? Please check your email address.'
            )
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')
        validate_strong_password(password)
        return password

    def save(self, request):
        user = super().save(request)
        user.role = 'student'
        user.institution = self.cleaned_data.get('institution')  # Can be None
        user.is_active = True
        user.save()
        return user

# MODERATOR SIGNUP FORM
class ModeratorSignupForm(SignupForm):
    """Moderator registration with specialization and qualification proof"""
    
    specialization_courses = forms.ModelMultipleChoiceField(
        queryset=Course.objects.all(),
        required=True,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='Select courses you can moderate (choose all that apply)'
    )
    
    specialization_subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        help_text='Optional: Select specific subjects for targeted moderation'
    )
    
    qualifications = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4, 
            'placeholder': 'Describe your education, degrees, certifications, teaching experience, etc...'
        }),
        required=True,
        min_length=50,
        help_text='Explain your qualifications, education, and relevant experience'
    )
    
    qualification_document = forms.FileField(
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        help_text='Upload proof of qualification: degree certificate, transcript, teaching certificate, etc. (PDF, JPG, or PNG, max 5MB)'
    )
    
    captcha = ReCaptchaField(
        widget=ReCaptchaV3(action='moderator_signup'),
        label=''
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email Address'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        suggestion = _check_email_typo(email)
        if suggestion:
            raise forms.ValidationError(
                f'Did you mean {suggestion}? Please check your email address.'
            )
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')
        validate_strong_password(password)
        return password

    def clean_qualifications(self):
        text = self.cleaned_data.get('qualifications', '')
        char_count = len(text.strip())
        if char_count < 25:
            raise forms.ValidationError(
                f'Please provide at least 25 characters ({char_count} written so far). '
                f'Describe your education, degrees, and relevant experience.'
            )
        return text

    def clean_qualification_document(self):
        """Validate the uploaded document"""
        document = self.cleaned_data.get('qualification_document')
        
        if document:
            if document.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 5MB')
            
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            ext = '.' + document.name.split('.')[-1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError('Only PDF, JPG, and PNG files are allowed')
        
        return document
    
    def save(self, request):
        user = super().save(request)
        user.role = 'moderator'
        user.bio = self.cleaned_data.get('qualifications', '')
        user.qualification_document = self.cleaned_data.get('qualification_document')
        user.institution = None  # ✅ Moderators don't have institutions
        user.is_active = False
        user.is_staff = True
        user.save()
        
        # Save many-to-many relationships
        user.specialization_courses.set(self.cleaned_data.get('specialization_courses', []))
        user.specialization_subjects.set(self.cleaned_data.get('specialization_subjects', []))
        
        return user

# ADMIN SIGNUP FORM
class AdminSignupForm(SignupForm):
    """Admin registration (restricted)"""
    
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(is_active=True),
        required=True,
        empty_label="Select institution",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    admin_key = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Admin Registration Key'
        }),
        help_text='Contact system administrator for the registration key'
    )
    
    captcha = ReCaptchaField(
        widget=ReCaptchaV3(action='admin_signup'),
        label=''
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Username'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Email Address'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm Password'})
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '')
        suggestion = _check_email_typo(email)
        if suggestion:
            raise forms.ValidationError(
                f'Did you mean {suggestion}? Please check your email address.'
            )
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1', '')
        validate_strong_password(password)
        return password

    def clean_admin_key(self):
        from django.conf import settings
        admin_key = self.cleaned_data.get('admin_key')
        correct_key = getattr(settings, 'ADMIN_REGISTRATION_KEY', 'noteghar-admin-2024-secure-key')
        
        if admin_key != correct_key:
            raise forms.ValidationError('Invalid admin registration key.')
        return admin_key
    
    def save(self, request):
        user = super().save(request)
        user.role = 'admin'
        user.institution = self.cleaned_data.get('institution')
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user
    
# PROFILE UPDATE FORM
class UserProfileForm(forms.ModelForm):
    """Profile update form"""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'institution', 'bio', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'institution': forms.Select(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }