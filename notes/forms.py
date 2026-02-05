from django import forms
from .models import Note, Course, Semester, Subject
from .models import Rating, Report

class NoteUploadForm(forms.ModelForm):
    """
    Form for uploading notes
    """
    class Meta:
        model = Note
        fields = ('title', 'description', 'course', 'semester', 'subject', 'file', 'tags')
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter note title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the content of these notes'
            }),
            'course': forms.Select(attrs={
                'class': 'form-control',
            }),
            'semester': forms.Select(attrs={
                'class': 'form-control',
            }),
            'subject': forms.Select(attrs={
                'class': 'form-control',
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.ppt,.pptx'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., important, midterm, finals'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subject'].queryset = Subject.objects.none()
        
        if 'course' in self.data and 'semester' in self.data:
            try:
                course_id = int(self.data.get('course'))
                semester_id = int(self.data.get('semester'))
                self.fields['subject'].queryset = Subject.objects.filter(
                    course_id=course_id, 
                    semester_id=semester_id
                ).order_by('name')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['subject'].queryset = self.instance.course.subjects.filter(
                semester=self.instance.semester
            )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError('File size must be under 10MB')
        return file
    
    def save(self, commit=True):
        note = super().save(commit=False)
        if note.file:
            note.file_size = note.file.size
        if commit:
            note.save()
        return note


class NoteSearchForm(forms.Form):
    """
    Form for searching notes
    """
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search notes...'
        })
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="All Courses"
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="All Semesters"
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="All Subjects"
    )

class RatingForm(forms.ModelForm):
        """
        Form for rating notes
        """
        class Meta:
            model = Rating
            fields = ['rating', 'review']
            widgets = {
                'rating': forms.Select(
                    choices=[(i, f'{i} Stars') for i in range(1, 6)],
                    attrs={'class': 'form-control'}
                ),
                'review': forms.Textarea(attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Share your thoughts about this note (optional)'
                }),
            }


class ReportForm(forms.ModelForm):
    """
    Form for reporting notes
    """
    class Meta:
        model = Report
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Please describe the issue in detail'
            }),
        }
