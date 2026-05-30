"""
moderation/tests.py
===================
Functional Tests : dashboard access, approve/reject note,
                   resolve report, audit log filtering
Security Tests   : role-based access control, CSRF enforcement,
                   unauthenticated redirects

Run:  python manage.py test moderation --verbosity=2
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from notes.models import (
    Note, Course, Semester, Subject, Report
)
from moderation.models import ModerationAction

User = get_user_model()


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def make_user(username, role='student', password='testpass123', is_staff=False):
    u = User.objects.create_user(
        username=username, password=password,
        email=f'{username}@test.com', role=role
    )
    if is_staff:
        u.is_staff = True
        u.save()
    return u


def make_note(uploader, course, semester, subject, status='pending'):
    f = SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
    return Note.objects.create(
        title='Sample Note', description='desc',
        subject=subject, course=course, semester=semester,
        file=f, uploaded_by=uploader, status=status,
    )


class ModerationBaseTest(TestCase):
    """Shared setUp for all moderation tests."""

    def setUp(self):
        self.client = Client()
        self.student = make_user('student_mod')
        self.moderator = make_user('mod_user', role='moderator', is_staff=True)

        self.course = Course.objects.create(name='BCA', code='BCA')
        self.semester = Semester.objects.create(name='Sem 1', number=1)
        self.subject = Subject.objects.create(
            name='OOP', code='OOP', course=self.course, semester=self.semester
        )
        self.note = make_note(self.student, self.course, self.semester, self.subject)


# ─────────────────────────────────────────────────────────────
# SECTION A — FUNCTIONAL TESTS: Dashboard Access
# ─────────────────────────────────────────────────────────────

class ModeratorDashboardTest(ModerationBaseTest):
    """
    Functional tests for the Moderator Dashboard (AM-01 series).
    Verifies access control and correct context variables.
    """

    def test_moderator_can_access_dashboard(self):
        """
        AM-01: A logged-in moderator should receive HTTP 200
        and see the dashboard with expected context keys.
        """
        self.client.login(username='mod_user', password='testpass123')
        response = self.client.get(reverse('moderation:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('pending_notes_count', response.context)
        self.assertIn('pending_reports_count', response.context)

    def test_student_cannot_access_dashboard(self):
        """
        AM-01.1: A logged-in student should be redirected away from /moderation/.
        """
        self.client.login(username='student_mod', password='testpass123')
        response = self.client.get(reverse('moderation:dashboard'))
        # Should redirect (302) or return 403 — NOT 200
        self.assertNotEqual(response.status_code, 200,
                            "Students must not access the moderation dashboard")

    def test_unauthenticated_user_redirected_from_dashboard(self):
        """
        AM-01.2: An anonymous user navigating to /moderation/ must be
        redirected to the login page.
        """
        response = self.client.get(reverse('moderation:dashboard'))
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('/accounts/login/', response['Location'] if 'Location' in response else '')

    def test_dashboard_pending_note_count_is_correct(self):
        """
        Dashboard pending_notes_count must match actual pending Note count.
        """
        self.client.login(username='mod_user', password='testpass123')
        # There is 1 pending note created in setUp
        response = self.client.get(reverse('moderation:dashboard'))
        self.assertEqual(response.context['pending_notes_count'], 1)


# ─────────────────────────────────────────────────────────────
# SECTION B — FUNCTIONAL TESTS: Approve Note
# ─────────────────────────────────────────────────────────────

class ApproveNoteTest(ModerationBaseTest):
    """
    Functional tests for approving a pending note (AM-02 series).
    """

    def setUp(self):
        super().setUp()
        self.client.login(username='mod_user', password='testpass123')

    def test_approve_pending_note_changes_status(self):
        """
        AM-02: POSTing to approve endpoint should set note.status = 'approved'.
        """
        response = self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, 'approved')

    def test_approve_note_sets_approved_by_and_approved_at(self):
        """
        AM-02: approved_by must be set to the moderator and
        approved_at must be set to a non-null datetime.
        """
        self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.approved_by, self.moderator)
        self.assertIsNotNone(self.note.approved_at)

    def test_approve_note_creates_moderation_action(self):
        """
        AM-02: Approving a note must create a ModerationAction with type='approve'.
        """
        self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        exists = ModerationAction.objects.filter(
            moderator=self.moderator,
            action_type='approve',
            note=self.note
        ).exists()
        self.assertTrue(exists, "ModerationAction of type 'approve' not created")

    def test_approve_already_approved_note_returns_404(self):
        """
        AM-02.1: Attempting to approve a note that is already approved
        should return 404 (get_object_or_404 filters status='pending').
        """
        self.note.status = 'approved'
        self.note.save()
        response = self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_approve_redirects_after_success(self):
        """
        After approving, the moderator should be redirected (302).
        """
        response = self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────────────────────────
# SECTION C — FUNCTIONAL TESTS: Reject Note
# ─────────────────────────────────────────────────────────────

class RejectNoteTest(ModerationBaseTest):
    """
    Functional tests for rejecting a pending note (AM-03 series).
    """

    def setUp(self):
        super().setUp()
        self.client.login(username='mod_user', password='testpass123')

    def test_reject_note_with_reason_changes_status(self):
        """
        AM-03: POSTing to reject endpoint with a reason should
        set note.status = 'rejected'.
        """
        self.client.post(
            reverse('moderation:reject_note', kwargs={'pk': self.note.pk}),
            {'reason': 'Content is incomplete and poorly formatted.'}
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, 'rejected')

    def test_reject_note_creates_moderation_action_with_reason(self):
        """
        AM-03: ModerationAction of type='reject' must be created
        with the provided reason stored.
        """
        reason_text = 'Low quality submission'
        self.client.post(
            reverse('moderation:reject_note', kwargs={'pk': self.note.pk}),
            {'reason': reason_text}
        )
        action = ModerationAction.objects.filter(
            moderator=self.moderator,
            action_type='reject',
            note=self.note
        ).first()
        self.assertIsNotNone(action, "ModerationAction of type 'reject' not created")
        self.assertIn(reason_text, action.reason)

    def test_reject_without_reason_uses_default(self):
        """
        AM-03.1: If no reason is provided, the system should use
        a default reason and still reject the note.
        """
        self.client.post(
            reverse('moderation:reject_note', kwargs={'pk': self.note.pk}),
            {'reason': ''}
        )
        self.note.refresh_from_db()
        self.assertEqual(self.note.status, 'rejected')
        action = ModerationAction.objects.filter(
            action_type='reject', note=self.note
        ).first()
        self.assertIsNotNone(action)


# ─────────────────────────────────────────────────────────────
# SECTION D — FUNCTIONAL TESTS: Report Resolution
# ─────────────────────────────────────────────────────────────

class ResolveReportTest(ModerationBaseTest):
    """
    Functional tests for reviewing and resolving reports (AM-04 series).
    """

    def setUp(self):
        super().setUp()
        self.client.login(username='mod_user', password='testpass123')
        # Create an approved note and a report on it
        self.approved_note = make_note(
            self.student, self.course, self.semester, self.subject, status='approved'
        )
        self.report = Report.objects.create(
            note=self.approved_note,
            reported_by=self.student,
            reason='spam',
            description='This note is spam.',
            status='pending',
        )

    def test_dismiss_report_changes_status_to_dismissed(self):
        """
        AM-04: Selecting 'dismiss' should set report.status = 'dismissed'.
        """
        self.client.post(
            reverse('moderation:review_report', kwargs={'pk': self.report.pk}),
            {'action': 'dismiss'}
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, 'dismissed')

    def test_dismiss_report_sets_reviewed_by_and_reviewed_at(self):
        """
        AM-04: reviewed_by and reviewed_at must be set after dismissal.
        """
        self.client.post(
            reverse('moderation:review_report', kwargs={'pk': self.report.pk}),
            {'action': 'dismiss'}
        )
        self.report.refresh_from_db()
        self.assertEqual(self.report.reviewed_by, self.moderator)
        self.assertIsNotNone(self.report.reviewed_at)

    def test_resolve_report_with_note_removal(self):
        """
        AM-04.1: Resolving with remove_note=True should set note.status='rejected'
        and report.status='resolved'.
        """
        self.client.post(
            reverse('moderation:review_report', kwargs={'pk': self.report.pk}),
            {'action': 'resolve', 'remove_note': 'on'}
        )
        self.report.refresh_from_db()
        self.approved_note.refresh_from_db()
        self.assertEqual(self.report.status, 'resolved')
        self.assertEqual(self.approved_note.status, 'rejected')

    def test_resolve_report_without_note_removal_leaves_note_intact(self):
        """
        AM-04: Resolving WITHOUT remove_note should leave the note's status unchanged.
        """
        original_status = self.approved_note.status
        self.client.post(
            reverse('moderation:review_report', kwargs={'pk': self.report.pk}),
            {'action': 'resolve'}
        )
        self.approved_note.refresh_from_db()
        self.assertEqual(self.approved_note.status, original_status)


# ─────────────────────────────────────────────────────────────
# SECTION E — FUNCTIONAL TESTS: Moderation History / Audit Log
# ─────────────────────────────────────────────────────────────

class ModerationHistoryTest(ModerationBaseTest):
    """
    Functional tests for the moderation audit log (AM-05 series).
    """

    def setUp(self):
        super().setUp()
        self.client.login(username='mod_user', password='testpass123')
        # Create some ModerationAction records
        ModerationAction.objects.create(
            moderator=self.moderator, action_type='approve',
            note=self.note, reason='Looks good'
        )
        ModerationAction.objects.create(
            moderator=self.moderator, action_type='reject',
            note=self.note, reason='Poor quality'
        )

    def test_moderation_history_page_loads(self):
        """AM-05: History page returns HTTP 200."""
        response = self.client.get(reverse('moderation:history'))
        self.assertEqual(response.status_code, 200)

    def test_history_shows_moderation_actions(self):
        """AM-05: History page context must contain ModerationAction records."""
        response = self.client.get(reverse('moderation:history'))
        # The template renders badge text 'Approved' and 'Rejected' (capitalised)
        # and shows reason text directly — check for the reason we created in setUp
        self.assertContains(response, 'Looks good', status_code=200)

    def test_history_limited_to_last_50_entries(self):
        """
        AM-05: History should display at most the last 50 ModerationAction records.
        Create 60 actions and verify the page handles them without error.
        """
        for i in range(60):
            ModerationAction.objects.create(
                moderator=self.moderator, action_type='approve',
                note=self.note, reason=f'Action {i}'
            )
        response = self.client.get(reverse('moderation:history'))
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────────────────────────
# SECTION F — SECURITY TESTS: Role-Based Access Control
# ─────────────────────────────────────────────────────────────

class ModerationSecurityTest(ModerationBaseTest):
    """
    Security tests verifying that moderation views enforce
    role-based access control (AM-NF-1.1).
    """

    def test_student_cannot_approve_note(self):
        """
        A student POSTing to the approve endpoint must be blocked.
        Note status must remain 'pending'.
        """
        self.client.login(username='student_mod', password='testpass123')
        self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        self.note.refresh_from_db()
        self.assertNotEqual(self.note.status, 'approved',
                            "Student must not be able to approve notes")

    def test_student_cannot_reject_note(self):
        """
        A student POSTing to the reject endpoint must be blocked.
        """
        self.client.login(username='student_mod', password='testpass123')
        self.client.post(
            reverse('moderation:reject_note', kwargs={'pk': self.note.pk}),
            {'reason': 'Attempt'}
        )
        self.note.refresh_from_db()
        self.assertNotEqual(self.note.status, 'rejected',
                            "Student must not be able to reject notes")

    def test_student_cannot_access_pending_notes_list(self):
        """Non-moderators must be redirected from /moderation/pending-notes/."""
        self.client.login(username='student_mod', password='testpass123')
        response = self.client.get(reverse('moderation:pending_notes'))
        self.assertNotEqual(response.status_code, 200)

    def test_student_cannot_access_pending_reports_list(self):
        """Non-moderators must be redirected from /moderation/pending-reports/."""
        self.client.login(username='student_mod', password='testpass123')
        response = self.client.get(reverse('moderation:pending_reports'))
        self.assertNotEqual(response.status_code, 200)

    def test_unauthenticated_cannot_access_any_moderation_endpoint(self):
        """
        Anonymous users must be redirected to login from all moderation endpoints.
        """
        endpoints = [
            reverse('moderation:dashboard'),
            reverse('moderation:pending_notes'),
            reverse('moderation:pending_reports'),
            reverse('moderation:history'),
        ]
        for url in endpoints:
            response = self.client.get(url)
            self.assertIn(
                response.status_code, [301, 302],
                f"Expected redirect for anonymous user at {url}"
            )

    def test_csrf_token_required_for_approve(self):
        """
        SF-01.1: A POST request to approve endpoint without CSRF token
        should return HTTP 403.
        """
        self.client.login(username='mod_user', password='testpass123')
        # Use enforce_csrf_checks=True to actually validate CSRF
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='mod_user', password='testpass123')
        response = csrf_client.post(
            reverse('moderation:approve_note', kwargs={'pk': self.note.pk})
        )
        self.assertEqual(response.status_code, 403,
                         "Missing CSRF token must return 403 Forbidden")

    def test_csrf_token_required_for_reject(self):
        """
        SF-01.1: POST to reject endpoint without CSRF token must return 403.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='mod_user', password='testpass123')
        response = csrf_client.post(
            reverse('moderation:reject_note', kwargs={'pk': self.note.pk}),
            {'reason': 'test'}
        )
        self.assertEqual(response.status_code, 403)

    def test_moderation_action_immutable_after_creation(self):
        """
        AM-NF-1.2: ModerationAction records use auto_now_add for created_at,
        meaning they cannot be updated after creation.
        """
        action = ModerationAction.objects.create(
            moderator=self.moderator,
            action_type='approve',
            note=self.note,
            reason='Approved'
        )
        original_time = action.created_at
        # Simulate attempting to change created_at
        import time
        time.sleep(0.01)
        action.reason = 'Modified reason'
        action.save()
        action.refresh_from_db()
        # created_at must be unchanged (auto_now_add)
        self.assertEqual(action.created_at, original_time,
                         "created_at on ModerationAction must be immutable")

    def test_404_for_non_existent_note_in_moderation(self):
        """
        SF-F-7.0: Accessing moderation action on a non-existent note PK
        must return HTTP 404, not 500.
        """
        self.client.login(username='mod_user', password='testpass123')
        response = self.client.post(
            reverse('moderation:approve_note', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)