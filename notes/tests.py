"""
Unit Tests  : UserProfile, NoteRequest, Note, award_points,
              check_and_award_badges, rate_limit decorator
Integration : Upload → Approve → Points → Badge (full workflow)

Run:  python manage.py test notes --verbosity=2
"""

from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from unittest.mock import patch

from notes.models import (
    Note, Course, Semester, Subject, Rating, RatingHelpful,
    Bookmark, NoteRequest, NoteRequestResponse,
    Badge, UserBadge, UserProfile, PointTransaction, RateLimit, Download,
)
from notes.badge_utils import award_points, check_and_award_badges, update_user_stats

User = get_user_model()
# HELPERS
def make_user(username='student1', role='student', password='testpass123'):
    return User.objects.create_user(username=username, password=password,
                                    email=f'{username}@test.com', role=role)


def make_note(uploader, course, semester, subject, status='pending'):
    dummy_file = SimpleUploadedFile('test.pdf', b'%PDF-1.4 fake content',
                                    content_type='application/pdf')
    return Note.objects.create(
        title='Test Note',
        description='A test note description',
        subject=subject,
        course=course,
        semester=semester,
        file=dummy_file,
        uploaded_by=uploader,
        status=status,
    )
# SECTION A — UNIT TESTS: UserProfile Model
class UserProfileLevelTest(TestCase):
    """Unit tests for UserProfile.get_level() thresholds."""

    def setUp(self):
        self.user = make_user()
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_level_1_at_zero_points(self):
        """A brand-new user with 0 points should be Level 1 (Beginner)."""
        self.profile.total_points = 0
        self.assertEqual(self.profile.get_level(), 1)

    def test_level_1_below_100_points(self):
        """99 points should still be Level 1."""
        self.profile.total_points = 99
        self.assertEqual(self.profile.get_level(), 1)

    def test_level_2_at_exactly_100_points(self):
        """Exactly 100 points triggers Level 2 (Student)."""
        self.profile.total_points = 100
        self.assertEqual(self.profile.get_level(), 2)

    def test_level_3_at_500_points(self):
        """500 points → Level 3 (Scholar)."""
        self.profile.total_points = 500
        self.assertEqual(self.profile.get_level(), 3)

    def test_level_4_at_1000_points(self):
        """1000 points → Level 4 (Expert)."""
        self.profile.total_points = 1000
        self.assertEqual(self.profile.get_level(), 4)

    def test_level_5_at_2500_points(self):
        """2500 points → Level 5 (Professor)."""
        self.profile.total_points = 2500
        self.assertEqual(self.profile.get_level(), 5)

    def test_level_6_at_5000_points(self):
        """5000 points → Level 6 (Legend) — max level."""
        self.profile.total_points = 5000
        self.assertEqual(self.profile.get_level(), 6)

    def test_level_name_beginner(self):
        """Level 1 name should contain 'Beginner'."""
        self.profile.level = 1
        self.assertIn('Beginner', self.profile.get_level_name())

    def test_level_name_legend(self):
        """Level 6 name should contain 'Legend'."""
        self.profile.level = 6
        self.assertIn('Legend', self.profile.get_level_name())

    def test_next_level_points_from_level_1(self):
        """From 50 pts, next threshold is 100."""
        self.profile.total_points = 50
        self.assertEqual(self.profile.get_next_level_points(), 100)

    def test_next_level_points_returns_none_at_max(self):
        """At max level there is no next threshold — returns None."""
        self.profile.total_points = 6000
        self.assertIsNone(self.profile.get_next_level_points())

    def test_add_points_no_level_up(self):
        """Adding 50 pts to a 0-pt profile should NOT trigger level up."""
        self.profile.total_points = 0
        self.profile.level = 1
        self.profile.save()
        leveled_up = self.profile.add_points(50)
        self.assertFalse(leveled_up)
        self.assertEqual(self.profile.total_points, 50)

    def test_add_points_triggers_level_up(self):
        """Adding 10 pts when at 95 should cross 100-pt threshold → Level 2."""
        self.profile.total_points = 95
        self.profile.level = 1
        self.profile.save()
        leveled_up = self.profile.add_points(10)
        self.assertTrue(leveled_up)
        self.assertEqual(self.profile.level, 2)

# SECTION B — UNIT TESTS: NoteRequest Model

class NoteRequestModelTest(TestCase):
    """Unit tests for NoteRequest expiry logic."""

    def setUp(self):
        self.user = make_user()
        self.course = Course.objects.create(name='Computer Science', code='CS')
        self.semester = Semester.objects.create(name='First Semester', number=1)

    def _make_request(self, expires_delta_days):
        return NoteRequest.objects.create(
            requester=self.user,
            course=self.course,
            semester=self.semester,
            topic='Test Topic',
            description='Test description',
            expires_at=timezone.now() + timedelta(days=expires_delta_days),
        )

    def test_is_expired_returns_false_for_future_request(self):
        """A request expiring in 10 days should NOT be expired."""
        req = self._make_request(10)
        self.assertFalse(req.is_expired())

    def test_is_expired_returns_true_for_past_expiry(self):
        """A request whose expires_at is in the past IS expired."""
        req = self._make_request(-1)
        self.assertTrue(req.is_expired())

    def test_expires_at_auto_set_on_save(self):
        """When expires_at is not provided, save() should auto-set it to now+30d."""
        req = NoteRequest(
            requester=self.user,
            course=self.course,
            semester=self.semester,
            topic='Auto-expire test',
            description='desc',
        )
        req.save()
        self.assertIsNotNone(req.expires_at)
        expected = timezone.now() + timedelta(days=30)
        diff = abs((req.expires_at - expected).total_seconds())
        self.assertLess(diff, 10, "expires_at should be within 10 seconds of now+30d")

    def test_get_responses_count_zero_initially(self):
        """A new request has 0 responses."""
        req = self._make_request(30)
        self.assertEqual(req.get_responses_count(), 0)

# SECTION C — UNIT TESTS: Note Model Methods
class NoteModelMethodsTest(TestCase):
    """Unit tests for Note helper methods."""

    def setUp(self):
        self.student = make_user('uploader')
        self.rater1 = make_user('rater1')
        self.rater2 = make_user('rater2')
        self.course = Course.objects.create(name='IT', code='IT101')
        self.semester = Semester.objects.create(name='Semester 1', number=1)
        self.subject = Subject.objects.create(
            name='Python', code='PY101', course=self.course, semester=self.semester
        )
        self.note = make_note(self.student, self.course, self.semester,
                              self.subject, status='approved')

    def test_get_average_rating_returns_zero_with_no_ratings(self):
        """Note with no ratings should return average of 0."""
        self.assertEqual(self.note.get_average_rating(), 0)

    def test_get_average_rating_correct_calculation(self):
        """Average of [4, 2] = 3.0."""
        Rating.objects.create(note=self.note, user=self.rater1, rating=4)
        Rating.objects.create(note=self.note, user=self.rater2, rating=2)
        self.note.refresh_from_db()
        self.assertEqual(self.note.get_average_rating(), 3.0)

    def test_get_rating_count(self):
        """Rating count should match number of Rating objects."""
        Rating.objects.create(note=self.note, user=self.rater1, rating=5)
        self.assertEqual(self.note.get_rating_count(), 1)

    def test_get_user_rating_returns_none_for_unrated(self):
        """get_user_rating() returns None when user has not rated."""
        result = self.note.get_user_rating(self.rater1)
        self.assertIsNone(result)

    def test_get_user_rating_returns_value_when_rated(self):
        """get_user_rating() returns the correct integer rating."""
        Rating.objects.create(note=self.note, user=self.rater1, rating=3)
        self.assertEqual(self.note.get_user_rating(self.rater1), 3)

    def test_is_approved_true_for_approved_note(self):
        self.assertTrue(self.note.is_approved())

    def test_is_approved_false_for_pending_note(self):
        self.note.status = 'pending'
        self.assertFalse(self.note.is_approved())

    def test_is_bookmarked_by_returns_false_when_not_bookmarked(self):
        self.assertFalse(self.note.is_bookmarked_by(self.rater1))

    def test_is_bookmarked_by_returns_true_after_bookmark(self):
        Bookmark.objects.create(user=self.rater1, note=self.note)
        self.assertTrue(self.note.is_bookmarked_by(self.rater1))

# SECTION D — UNIT TESTS: award_points() Utility

class AwardPointsTest(TestCase):
    """Unit tests for the award_points() utility function."""

    def setUp(self):
        self.user = make_user()
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def test_award_points_creates_point_transaction(self):
        """award_points() must create a PointTransaction record."""
        award_points(self.user, 10, 'Uploaded note')
        self.assertTrue(
            PointTransaction.objects.filter(user=self.user, points=10).exists()
        )

    def test_award_points_increments_profile_total(self):
        """award_points() must increment UserProfile.total_points."""
        self.profile.total_points = 0
        self.profile.save()
        award_points(self.user, 15, 'Test reason')
        self.profile.refresh_from_db()
        self.assertGreaterEqual(self.profile.total_points, 15)

    def test_award_points_returns_leveled_up_false_no_threshold(self):
        """Should return leveled_up=False when threshold not crossed."""
        self.profile.total_points = 0
        self.profile.level = 1
        self.profile.save()
        result = award_points(self.user, 5, 'Small award')
        self.assertFalse(result['leveled_up'])

    def test_award_points_returns_leveled_up_true_on_threshold(self):
        """Should return leveled_up=True when 100-pt threshold crossed."""
        self.profile.total_points = 95
        self.profile.level = 1
        self.profile.save()
        result = award_points(self.user, 10, 'Level up test')
        self.assertTrue(result['leveled_up'])
        self.assertEqual(result['new_level'], 2)

    def test_award_points_transaction_reason_stored(self):
        """The reason string must be stored on PointTransaction."""
        award_points(self.user, 5, 'Note approved')
        tx = PointTransaction.objects.get(user=self.user, reason='Note approved')
        self.assertEqual(tx.points, 5)

# SECTION E — UNIT TESTS: check_and_award_badges()


class BadgeAwardTest(TestCase):
    """Unit tests for check_and_award_badges() utility."""

    def setUp(self):
        self.user = make_user()
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.course = Course.objects.create(name='CS', code='CS101')
        self.semester = Semester.objects.create(name='Sem 1', number=1)
        self.subject = Subject.objects.create(
            name='Django', code='DJG', course=self.course, semester=self.semester
        )
        # Create a badge for uploading 1 approved note
        self.badge = Badge.objects.create(
            name='First Upload',
            slug='first-upload',
            description='Upload your first note',
            icon='📝',
            category='contributor',
            requirement_type='upload_count',
            requirement_value=1,
            points_reward=50,
        )

    def _upload_approved_note(self):
        note = make_note(self.user, self.course, self.semester,
                         self.subject, status='approved')
        return note

    def test_badge_awarded_when_threshold_met(self):
        """Badge awarded when user has 1 approved note and requirement_value=1."""
        self._upload_approved_note()
        check_and_award_badges(self.user)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=self.badge).exists())

    def test_badge_not_awarded_when_threshold_not_met(self):
        """Badge NOT awarded when user has 0 approved notes."""
        check_and_award_badges(self.user)
        self.assertFalse(UserBadge.objects.filter(user=self.user, badge=self.badge).exists())

    def test_badge_not_re_awarded_on_second_call(self):
        """Calling check_and_award_badges twice should not create duplicate UserBadge."""
        self._upload_approved_note()
        check_and_award_badges(self.user)
        check_and_award_badges(self.user)
        count = UserBadge.objects.filter(user=self.user, badge=self.badge).count()
        self.assertEqual(count, 1, "Badge must not be awarded more than once")

    def test_badge_points_reward_added_to_profile(self):
        """Earning the badge should add badge.points_reward to profile."""
        initial_points = self.profile.total_points
        self._upload_approved_note()
        check_and_award_badges(self.user)
        self.profile.refresh_from_db()
        self.assertGreaterEqual(self.profile.total_points, initial_points + self.badge.points_reward)

# SECTION F — UNIT TESTS: rate_limit Decorator


class RateLimitDecoratorTest(TestCase):
    """Unit tests for the @rate_limit decorator via HTTP client."""

    def setUp(self):
        self.client = Client()
        self.student = make_user('limittest')
        self.client.login(username='limittest', password='testpass123')
        self.course = Course.objects.create(name='Eng', code='ENG')
        self.semester = Semester.objects.create(name='Sem 2', number=2)
        self.subject = Subject.objects.create(
            name='Math', code='MTH', course=self.course, semester=self.semester
        )

    def _dummy_pdf(self):
        return SimpleUploadedFile('note.pdf', b'%PDF-1.4 content',
                                  content_type='application/pdf')

    def _upload_post(self):
        return self.client.post(reverse('notes:upload'), {
            'title': 'Note',
            'description': 'Test',
            'course': self.course.id,
            'semester': self.semester.id,
            'subject': self.subject.id,
            'file': self._dummy_pdf(),
        }, follow=True)

    def test_admin_bypasses_rate_limit(self):
        """Staff users should never be blocked by rate limiting."""
        admin = make_user('adminuser', role='admin')
        admin.is_staff = True
        admin.save()
        self.client.login(username='adminuser', password='testpass123')
        # Saturate the RateLimit table as if the user uploaded many times
        for _ in range(15):
            RateLimit.objects.create(
                user=admin, action_type='upload',
                timestamp=timezone.now()
            )
        response = self._upload_post()
        # Should NOT be redirected with an error — admin bypasses limit
        self.assertNotContains(response, 'Daily limit reached', status_code=200)

    def test_student_blocked_after_daily_limit(self):
        """Student blocked after exceeding max_per_day=10 uploads."""
        for _ in range(10):
            RateLimit.objects.create(
                user=self.student, action_type='upload',
                timestamp=timezone.now()
            )
        response = self._upload_post()
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('Daily limit' in m or 'limit reached' in m.lower() for m in messages),
            "Expected daily rate limit error message"
        )

    def test_student_blocked_after_hourly_limit(self):
        """Student blocked after exceeding max_per_hour=3 uploads."""
        for _ in range(3):
            RateLimit.objects.create(
                user=self.student, action_type='upload',
                timestamp=timezone.now()
            )
        response = self._upload_post()
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('Hourly limit' in m or 'limit reached' in m.lower() for m in messages),
            "Expected hourly rate limit error message"
        )
# SECTION G — INTEGRATION TESTS: Full Upload → Approve → Points workflow

class UploadApprovePointsIntegrationTest(TestCase):
    """
    Integration test: verifies that uploading a note and then
    approving it correctly awards points across the Notes,
    Moderation and Gamification subsystems.
    """

    def setUp(self):
        self.student = make_user('student_int')
        self.moderator = make_user('mod_int', role='moderator')
        self.moderator.is_staff = True
        self.moderator.save()

        self.course = Course.objects.create(name='BIT', code='BIT')
        self.semester = Semester.objects.create(name='Sem 3', number=3)
        self.subject = Subject.objects.create(
            name='Networks', code='NET', course=self.course, semester=self.semester
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.student)

    def test_upload_awards_10_points(self):
        """
        After uploading a note, the student should immediately
        receive a +10 PointTransaction for 'Uploaded note'.
        """
        make_note(self.student, self.course, self.semester, self.subject)
        tx = PointTransaction.objects.filter(
            user=self.student, reason='Uploaded note'
        ).first()
        self.assertIsNotNone(tx, "PointTransaction for upload not created")
        self.assertEqual(tx.points, 10)

    def test_approval_awards_additional_5_points(self):
        """
        After a moderator approves the note, the student should
        receive a +5 PointTransaction for 'Note approved'.
        """
        note = make_note(self.student, self.course, self.semester, self.subject)
        # Simulate approval (triggers pre_save / post_save signals)
        note.status = 'approved'
        note.approved_by = self.moderator
        note.approved_at = timezone.now()
        note.save()

        tx = PointTransaction.objects.filter(
            user=self.student, reason='Note approved'
        ).first()
        self.assertIsNotNone(tx, "PointTransaction for approval not created")
        self.assertEqual(tx.points, 5)

    def test_total_points_after_upload_and_approval(self):
        """
        After upload (+10) and approval (+5), total_points should
        be at least 15 (more if badge was awarded).
        """
        note = make_note(self.student, self.course, self.semester, self.subject)
        note.status = 'approved'
        note.approved_by = self.moderator
        note.approved_at = timezone.now()
        note.save()

        self.profile.refresh_from_db()
        self.assertGreaterEqual(self.profile.total_points, 15)

    def test_approval_does_not_duplicate_points_on_re_save(self):
        """
        Saving an already-approved note a second time should NOT
        create a second 'Note approved' PointTransaction.
        """
        note = make_note(self.student, self.course, self.semester, self.subject)
        note.status = 'approved'
        note.approved_by = self.moderator
        note.approved_at = timezone.now()
        note.save()
        # Save again without changing status
        note.title = 'Updated title'
        note.save()

        count = PointTransaction.objects.filter(
            user=self.student, reason='Note approved'
        ).count()
        self.assertEqual(count, 1, "Approval points must only be awarded once")

# SECTION H — INTEGRATION TESTS: Rate Note → Signal → Badge

class RatingSignalIntegrationTest(TestCase):
    """
    Integration test: rating a note triggers the post_save signal,
    which awards points and may award a badge.
    """

    def setUp(self):
        self.uploader = make_user('uploader_sig')
        self.rater = make_user('rater_sig')
        self.course = Course.objects.create(name='CS2', code='CS2')
        self.semester = Semester.objects.create(name='Sem 4', number=4)
        self.subject = Subject.objects.create(
            name='AI', code='AI101', course=self.course, semester=self.semester
        )
        self.note = make_note(
            self.uploader, self.course, self.semester, self.subject, status='approved'
        )
        self.uploader_profile, _ = UserProfile.objects.get_or_create(user=self.uploader)

        # Badge for receiving a 5-star rating
        Badge.objects.create(
            name='Star Contributor',
            slug='star-contributor',
            description='Received a 5-star rating',
            icon='⭐',
            category='contributor',
            requirement_type='upload_count',
            requirement_value=1,
            points_reward=20,
        )

    def test_five_star_rating_awards_points_to_uploader(self):
        """
        A 5-star rating from another user should award +3 points
        to the note uploader via the post_save signal.
        """
        Rating.objects.create(note=self.note, user=self.rater, rating=5)
        tx = PointTransaction.objects.filter(
            user=self.uploader, reason='Received 5-star rating'
        ).first()
        self.assertIsNotNone(tx, "5-star rating should award points to uploader")
        self.assertEqual(tx.points, 3)

    def test_non_five_star_rating_does_not_award_points(self):
        """
        Ratings of 1–4 stars should NOT award points to the uploader
        (only 5-star triggers the point award per signals.py logic).
        """
        Rating.objects.create(note=self.note, user=self.rater, rating=3)
        tx = PointTransaction.objects.filter(
            user=self.uploader, reason='Received 5-star rating'
        ).first()
        self.assertIsNone(tx, "Non-5-star rating should not award points")

    def test_rater_cannot_award_points_to_themselves(self):
        """
        If the rater is the uploader, the signal should NOT award points
        (self-rating guard in signals.py).
        """
        Rating.objects.create(note=self.note, user=self.uploader, rating=5)
        tx = PointTransaction.objects.filter(
            user=self.uploader, reason='Received 5-star rating'
        ).first()
        self.assertIsNone(tx, "Self-ratings must not award points")

# SECTION I — INTEGRATION TESTS: Note Request Lifecycle

class NoteRequestLifecycleTest(TestCase):
    """
    Integration test: full note request workflow —
    create → respond → mark best answer → points awarded.
    """

    def setUp(self):
        self.requester = make_user('requester_int')
        self.responder = make_user('responder_int')
        self.course = Course.objects.create(name='MBA', code='MBA')
        self.semester = Semester.objects.create(name='Sem 5', number=5)
        self.subject = Subject.objects.create(
            name='Finance', code='FIN', course=self.course, semester=self.semester
        )
        self.responder_profile, _ = UserProfile.objects.get_or_create(user=self.responder)
        self.note = make_note(
            self.responder, self.course, self.semester, self.subject, status='approved'
        )

    def test_request_created_with_open_status(self):
        req = NoteRequest.objects.create(
            requester=self.requester,
            course=self.course,
            semester=self.semester,
            topic='Finance notes',
            description='Need notes for final exam',
        )
        self.assertEqual(req.status, 'open')

    def test_response_created_by_non_requester(self):
        req = NoteRequest.objects.create(
            requester=self.requester,
            course=self.course,
            semester=self.semester,
            topic='Finance notes',
            description='desc',
        )
        response = NoteRequestResponse.objects.create(
            request=req, note=self.note, responder=self.responder, message='Here you go'
        )
        self.assertEqual(req.get_responses_count(), 1)
        self.assertFalse(response.is_helpful)

    def test_mark_best_answer_awards_bonus_points(self):
        """
        When is_helpful is changed from False to True (best answer),
        the responder should receive +20 bonus points.
        """
        req = NoteRequest.objects.create(
            requester=self.requester,
            course=self.course,
            semester=self.semester,
            topic='Finance notes',
            description='desc',
        )
        response = NoteRequestResponse.objects.create(
            request=req, note=self.note, responder=self.responder
        )
        # Mark as best answer — triggers pre_save + post_save signals
        response.is_helpful = True
        response.save()

        tx = PointTransaction.objects.filter(
            user=self.responder, reason='Marked as best answer'
        ).first()
        self.assertIsNotNone(tx, "Best answer should award +20 points")
        self.assertEqual(tx.points, 20)

# PERFORMANCE TESTS — Query Count Assertions


class QueryCountPerformanceTest(TestCase):
    """
    Performance tests using assertNumQueries to verify that
    database-heavy views do not issue excessive SQL queries.
    """

    def setUp(self):
        self.client = Client()
        self.student = make_user('perftest')
        self.client.login(username='perftest', password='testpass123')

        self.course = Course.objects.create(name='Perf Course', code='PC')
        self.semester = Semester.objects.create(name='Sem 1', number=1)
        self.subject = Subject.objects.create(
            name='Performance', code='PRF',
            course=self.course, semester=self.semester
        )
        # Create 10 approved notes to simulate a realistic list page
        for i in range(10):
            make_note(
                self.student, self.course, self.semester,
                self.subject, status='approved'
            )

    def test_note_list_page_query_count(self):
        """
        The note list page must not issue more than 8 queries,
        regardless of how many notes exist.
        Uses select_related to fetch subject/course/semester/uploader in one JOIN.
        """
        with self.assertNumQueries(8):
            self.client.get(reverse('notes:list'))

    def test_note_detail_page_query_count(self):
        """
        The note detail page must not exceed 10 queries,
        including ratings, bookmark status, and download tracking.
        """
        note = Note.objects.filter(status='approved').first()
        with self.assertNumQueries(10):
            self.client.get(reverse('notes:detail', kwargs={'pk': note.pk}))

    def test_leaderboard_page_query_count(self):
        """
        The leaderboard aggregates across UserProfile, Note and Download.
        Must complete in at most 8 queries.
        """
        with self.assertNumQueries(8):
            self.client.get(reverse('notes:leaderboard'))