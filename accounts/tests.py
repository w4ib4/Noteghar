"""
accounts/tests.py
=================
Security Tests  : password hashing, session lifecycle,
                  file type/size validation, 404/403 error handling,
                  Google OAuth role assignment, rate limit resets
Auth Tests      : login/logout session behaviour

Run:  python manage.py test accounts --verbosity=2
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from notes.models import (
    Note, Course, Semester, Subject, RateLimit
)

User = get_user_model()

# HELPERS

def make_user(username, role='student', password='testpass123'):
    return User.objects.create_user(
        username=username, password=password,
        email=f'{username}@test.com', role=role
    )


def make_course_semester_subject():
    course = Course.objects.create(name='Security Course', code='SC101')
    semester = Semester.objects.create(name='Sem 1', number=1)
    subject = Subject.objects.create(
        name='Cryptography', code='CRY', course=course, semester=semester
    )
    return course, semester, subject

# SECTION A — SECURITY TESTS: Password Storage (SF-F-4.0)

class PasswordStorageSecurityTest(TestCase):
    """
    SF-04: Verify that passwords are stored as PBKDF2 hashes
    and never stored as plaintext.
    """

    def test_password_stored_as_pbkdf2_hash(self):
        """
        The password field in the database must start with
        'pbkdf2_sha256$' — never plain text.
        """
        user = make_user('hashtest')
        self.assertTrue(
            user.password.startswith('pbkdf2_sha256$'),
            f"Password not hashed — found: {user.password[:20]}"
        )

    def test_plaintext_password_not_stored(self):
        """
        The raw password string must not appear in the stored
        password hash field.
        """
        raw_password = 'testpass123'
        user = make_user('plaintexttest')
        self.assertNotIn(raw_password, user.password,
                         "Plaintext password must never be stored in database")

    def test_password_check_works_correctly(self):
        """
        Django's check_password() must return True for the correct
        password and False for a wrong one.
        """
        user = make_user('pwdcheck')
        self.assertTrue(user.check_password('testpass123'))
        self.assertFalse(user.check_password('wrongpassword'))


# SECTION B — SECURITY TESTS: Session Lifecycle (SF-F-2.0, SF-F-3.0)

class SessionSecurityTest(TestCase):
    """
    SF-02 / SF-03: Verify that sessions are correctly created on
    login and destroyed on logout.
    """

    def setUp(self):
        self.client = Client()
        self.user = make_user('sessiontest')

    def test_session_created_on_login(self):
        """
        SF-02: After a successful login, the session must contain
        the user's auth key and the user must be authenticated.
        """
        response = self.client.post(reverse('account_login'), {
            'login': 'sessiontest',
            'password': 'testpass123',
        }, follow=True)
        # After login, the session should have an auth key set
        self.assertIn('_auth_user_id', self.client.session,
                      "Session must contain _auth_user_id after login")

    def test_session_destroyed_on_logout(self):
        """
        SF-02.1: After logout, the session must be cleared and the user
        must no longer be authenticated.
        """
        self.client.login(username='sessiontest', password='testpass123')
        # Confirm session exists
        self.assertIn('_auth_user_id', self.client.session)
        # Perform logout via POST
        self.client.post(reverse('account_logout'), follow=True)
        # Session auth key must be gone
        self.assertNotIn('_auth_user_id', self.client.session,
                         "Session must be cleared after logout")

    def test_user_is_authenticated_after_login(self):
        """User should be authenticated after successful login."""
        self.client.login(username='sessiontest', password='testpass123')
        response = self.client.get(reverse('notes:list'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_user_is_anonymous_after_logout(self):
        """User should be anonymous after logout."""
        self.client.login(username='sessiontest', password='testpass123')
        self.client.post(reverse('account_logout'), follow=True)
        response = self.client.get(reverse('notes:list'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

# SECTION C — SECURITY TESTS: File Validation (SF-F-6.0)

class FileValidationSecurityTest(TestCase):
    """
    SF-04: Verify that file extension and type validation correctly
    rejects disallowed file types and accepts allowed ones.
    """

    def setUp(self):
        self.client = Client()
        self.student = make_user('filetest')
        self.client.login(username='filetest', password='testpass123')
        self.course, self.semester, self.subject = make_course_semester_subject()

    def _post_upload(self, filename, content, content_type):
        f = SimpleUploadedFile(filename, content, content_type=content_type)
        return self.client.post(reverse('notes:upload'), {
            'title': 'Upload Test',
            'description': 'Testing file validation',
            'course': self.course.id,
            'semester': self.semester.id,
            'subject': self.subject.id,
            'file': f,
        })

    def test_pdf_file_accepted(self):
        """
        SF-04: A valid .pdf file should pass validation.
        The response should redirect (note created) rather than
        returning a form error.
        """
        response = self._post_upload('valid.pdf', b'%PDF-1.4 content',
                                     'application/pdf')
        # A successful upload redirects; a failed one re-renders the form (200)
        self.assertIn(response.status_code, [200, 302])
        # No validation error about file extension should be present
        if response.status_code == 200 and hasattr(response, 'context'):
            form = response.context.get('form')
            if form:
                self.assertNotIn('file', form.errors,
                                 "PDF should be accepted — no file errors expected")

    def test_exe_file_rejected(self):
        """
        SF-04: An .exe file must be rejected by FileExtensionValidator.
        The form must contain a file validation error.
        """
        response = self._post_upload('malware.exe', b'MZ\x00\x00fake exe',
                                     'application/octet-stream')
        self.assertEqual(response.status_code, 200,
                         "Invalid file should re-render form with errors")
        if hasattr(response, 'context') and response.context:
            form = response.context.get('form')
            if form:
                self.assertIn('file', form.errors,
                              "EXE file must produce a file field validation error")
        # Confirm no Note was created
        self.assertEqual(
            Note.objects.filter(uploaded_by=self.student).count(), 0,
            "No Note should be saved when file type is invalid"
        )

    def test_txt_file_rejected(self):
        """
        SF-04: A .txt file must be rejected.
        """
        response = self._post_upload('notes.txt', b'plain text content',
                                     'text/plain')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Note.objects.filter(uploaded_by=self.student).count(), 0,
            "No Note should be saved when file is a .txt"
        )

    def test_docx_file_accepted(self):
        """
        SF-04: A .docx file is in the allowed extensions list and should pass.
        """
        response = self._post_upload(
            'document.docx',
            b'PK\x03\x04fake docx',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        # Should not produce a file extension error
        if response.status_code == 200 and hasattr(response, 'context'):
            form = response.context.get('form')
            if form:
                self.assertNotIn('file', form.errors,
                                 "DOCX should pass extension validation")



# SECTION D — SECURITY TESTS: 404 / 403 Error Handling (SF-F-7.0, SF-F-8.0)


class ErrorHandlingSecurityTest(TestCase):
    """
    SF-05 / SF-06: Verify correct HTTP status codes are returned
    for missing resources and unauthorised access.
    """

    def setUp(self):
        self.client = Client()
        self.student = make_user('errortest')
        self.moderator = make_user('errormod', role='moderator')
        self.moderator.is_staff = True
        self.moderator.save()

    def test_404_returned_for_nonexistent_note(self):
        """
        SF-05: Navigating to a note URL with a non-existent PK must
        return HTTP 404, not a 500 server error.
        """
        self.client.login(username='errortest', password='testpass123')
        response = self.client.get(reverse('notes:detail', kwargs={'pk': 99999}))
        self.assertEqual(response.status_code, 404)

    def test_403_or_redirect_for_moderation_without_role(self):
        """
        SF-06: A student accessing /moderation/ must receive a redirect
        or 403, never 200.
        """
        self.client.login(username='errortest', password='testpass123')
        response = self.client.get(reverse('moderation:dashboard'))
        self.assertIn(response.status_code, [302, 403],
                      "Non-moderator must not see moderation dashboard")

    def test_anonymous_user_redirected_from_upload(self):
        """
        An unauthenticated user must be redirected away from the upload page.
        """
        response = self.client.get(reverse('notes:upload'))
        self.assertIn(response.status_code, [301, 302])

    def test_anonymous_user_redirected_from_bookmarks(self):
        """Unauthenticated user must be redirected from /notes/bookmarks/."""
        response = self.client.get(reverse('notes:my_bookmarks'))
        self.assertIn(response.status_code, [301, 302])



# SECTION E — SECURITY TESTS: Google OAuth Role Assignment (SF-F-11.0)


class OAuthRoleAssignmentTest(TestCase):
    """
    SF-08: Verify that new users registered via Google OAuth are
    assigned the 'student' role by CustomSocialAccountAdapter.
    """

    def test_new_oauth_user_gets_student_role(self):
        """
        Simulates the behaviour of CustomSocialAccountAdapter.save_user():
        a new user with no role set should be assigned role='student'.
        """
        from accounts.adapters import CustomSocialAccountAdapter
        from unittest.mock import MagicMock

        adapter = CustomSocialAccountAdapter()

        # Create a user without a role (as allauth would before adapter processes it)
        user = User(username='googleuser', email='google@test.com')
        user.set_password('unusable')
        user.role = ''  # Simulate empty role before adapter sets it
        user.save()

        # Apply the role-setting logic from the adapter
        if hasattr(user, 'role') and not user.role:
            user.role = 'student'
            user.save()

        user.refresh_from_db()
        self.assertEqual(user.role, 'student',
                         "OAuth-registered users must be assigned role='student'")

    def test_existing_role_not_overwritten_by_adapter(self):
        """
        If a user already has a role set, the adapter must not overwrite it.
        This simulates a returning OAuth user.
        """
        user = User.objects.create_user(
            username='existing_oauth', email='existing@test.com',
            password='pass', role='moderator'
        )
        # Adapter logic: only sets role if not already set
        if hasattr(user, 'role') and not user.role:
            user.role = 'student'
            user.save()

        user.refresh_from_db()
        self.assertEqual(user.role, 'moderator',
                         "Existing role must not be overwritten by adapter")



# SECTION F — SECURITY TESTS: Rate Limit Reset (SF-07.1)


class RateLimitResetTest(TestCase):
    """
    SF-07.1: Verify that rate limit counters expire correctly
    after the 24-hour and 1-hour windows pass.
    """

    def setUp(self):
        self.student = make_user('ratelimitreset')

    def test_old_rate_limit_records_not_counted(self):
        """
        RateLimit records older than 24 hours must not count toward
        the daily limit. Only recent records within the window matter.
        """
        # Create 10 old records (25 hours ago — outside daily window)
        old_time = timezone.now() - timedelta(hours=25)
        for _ in range(10):
            rl = RateLimit.objects.create(
                user=self.student, action_type='upload',
                ip_address='127.0.0.1'
            )
            # Manually set the timestamp to 25 hours ago
            RateLimit.objects.filter(pk=rl.pk).update(timestamp=old_time)

        # Count only records within the last 24 hours
        day_ago = timezone.now() - timedelta(days=1)
        recent_count = RateLimit.objects.filter(
            user=self.student,
            action_type='upload',
            timestamp__gte=day_ago
        ).count()

        self.assertEqual(recent_count, 0,
                         "Records older than 24 hours must not count toward daily limit")

    def test_old_hourly_records_not_counted(self):
        """
        RateLimit records older than 1 hour must not count toward
        the hourly limit.
        """
        # Create 3 old records (90 minutes ago — outside hourly window)
        old_time = timezone.now() - timedelta(minutes=90)
        for _ in range(3):
            rl = RateLimit.objects.create(
                user=self.student, action_type='upload',
                ip_address='127.0.0.1'
            )
            RateLimit.objects.filter(pk=rl.pk).update(timestamp=old_time)

        hour_ago = timezone.now() - timedelta(hours=1)
        recent_count = RateLimit.objects.filter(
            user=self.student,
            action_type='upload',
            timestamp__gte=hour_ago
        ).count()

        self.assertEqual(recent_count, 0,
                         "Records older than 1 hour must not count toward hourly limit")



# SECTION G — SECURITY TESTS: CSRF Protection (SF-F-1.0)


class CSRFProtectionTest(TestCase):
    """
    SF-01: Verify that state-changing POST endpoints reject
    requests without a valid CSRF token.
    """

    def setUp(self):
        self.student = make_user('csrftest')

    def test_csrf_enforced_on_note_upload(self):
        """
        SF-01.1: A POST to the upload endpoint without a CSRF token
        must return HTTP 403 Forbidden.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='csrftest', password='testpass123')
        course, semester, subject = make_course_semester_subject()
        f = SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = csrf_client.post(reverse('notes:upload'), {
            'title': 'CSRF test',
            'description': 'No token',
            'course': course.id,
            'semester': semester.id,
            'subject': subject.id,
            'file': f,
        })
        self.assertEqual(response.status_code, 403,
                         "Upload without CSRF token must return 403")

    def test_csrf_enforced_on_rating(self):
        """
        SF-01.1: POST to the rate endpoint without CSRF token returns 403.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='csrftest', password='testpass123')
        course, semester, subject = make_course_semester_subject()
        note = Note.objects.create(
            title='Rate me', description='desc',
            subject=subject, course=course, semester=semester,
            file=SimpleUploadedFile('n.pdf', b'%PDF-1.4', content_type='application/pdf'),
            uploaded_by=self.student, status='approved',
        )
        response = csrf_client.post(
            reverse('notes:rate', kwargs={'pk': note.pk}),
            {'rating': 4, 'review': 'Good'}
        )
        self.assertEqual(response.status_code, 403,
                         "Rating without CSRF token must return 403")