from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import (
    Note,
    Rating,
    Download,
    Bookmark,
    NoteRequestResponse,
    RatingHelpful,
)
from .badge_utils import award_points, update_user_stats

# NOTE STATUS TRACKING
@receiver(pre_save, sender=Note)
def cache_old_note_status(sender, instance, **kwargs):
    """
    Cache the old status before save so we can detect real status changes.
    """
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._old_status = old.status if old else None
    else:
        instance._old_status = None


@receiver(post_save, sender=Note)
def auto_assign_moderator(sender, instance, created, **kwargs):
    """Auto-assign note to best matching moderator on upload."""
    if not created or instance.status != 'pending':
        return
    from django.contrib.auth import get_user_model
    from django.db.models import Count
    User = get_user_model()

    moderators = User.objects.filter(role='moderator', is_active=True)

    # Priority 1: exact subject match
    qs = moderators.filter(
        specialization_subjects=instance.subject
    ).annotate(
        workload=Count('assigned_notes', filter=Q(assigned_notes__status='pending'))
    ).order_by('workload')

    # Priority 2: course match
    if not qs.exists():
        qs = moderators.filter(
            specialization_courses=instance.course
        ).annotate(
            workload=Count('assigned_notes', filter=Q(assigned_notes__status='pending'))
        ).order_by('workload')

    # Priority 3: any moderator (least busy)
    if not qs.exists():
        qs = moderators.annotate(
            workload=Count('assigned_notes', filter=Q(assigned_notes__status='pending'))
        ).order_by('workload')

    if qs.exists():
        Note.objects.filter(pk=instance.pk).update(assigned_moderator=qs.first())


@receiver(post_save, sender=Note)
def note_uploaded_points(sender, instance, created, **kwargs):
    """
    Award points when note is first uploaded.
    """
    if created:
        award_points(
            user=instance.uploaded_by,
            points=10,
            reason='Uploaded note',
            related_note=instance
        )


@receiver(post_save, sender=Note)
def note_approved_points(sender, instance, created, **kwargs):
    """
    Award points only when note status changes to approved.
    """
    old_status = getattr(instance, '_old_status', None)

    if not created and instance.status == 'approved' and old_status != 'approved':
        award_points(
            user=instance.uploaded_by,
            points=5,
            reason='Note approved',
            related_note=instance
        )


@receiver(post_save, sender=Note)
def update_stats_on_note(sender, instance, **kwargs):
    """
    Update uploader stats whenever note is saved.
    """
    update_user_stats(instance.uploaded_by)

# DOWNLOADS
@receiver(post_save, sender=Download)
def download_points(sender, instance, created, **kwargs):
    """
    Award points when someone's note is downloaded.
    """
    if created and instance.is_download:
        if instance.note.uploaded_by != instance.user:
            award_points(
                user=instance.note.uploaded_by,
                points=1,
                reason='Note downloaded',
                related_note=instance.note
            )


@receiver(post_save, sender=Download)
def update_stats_on_download(sender, instance, **kwargs):
    """
    Update downloader stats and uploader stats.
    """
    update_user_stats(instance.user)
    update_user_stats(instance.note.uploaded_by)

# RATINGS
@receiver(pre_save, sender=Rating)
def cache_old_rating_value(sender, instance, **kwargs):
    """
    Cache old rating value so we can detect a real change to 5 stars.
    """
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._old_rating = old.rating if old else None
    else:
        instance._old_rating = None


@receiver(post_save, sender=Rating)
def rating_points(sender, instance, created, **kwargs):
    """
    Award points for rating activity:
    - Reviewer gets 2 pts for writing any rating (once per note)
    - Reviewer gets 1 extra pt for writing a review (with text)
    - Note uploader gets 3 pts when they receive a 4 or 5-star rating (once per reviewer)
    - Note uploader gets 1 pt for any rating (once per reviewer)
    """
    old_rating = getattr(instance, '_old_rating', None)

    # Award reviewer on first submission only
    if created:
        # Base points for the reviewer submitting any rating
        award_points(
            user=instance.user,
            points=2,
            reason='Wrote a rating',
            related_note=instance.note,
            related_rating=instance
        )
        # Bonus if they included a written review
        if instance.review and instance.review.strip():
            award_points(
                user=instance.user,
                points=1,
                reason='Wrote a review',
                related_note=instance.note,
                related_rating=instance
            )

    # Award note uploader on new rating OR when rating improves to 4+
    if instance.note.uploaded_by != instance.user:
        should_award_uploader = False
        if created:
            should_award_uploader = True
        elif not created and instance.rating != old_rating:
            should_award_uploader = True  # rating changed

        if should_award_uploader:
            if instance.rating >= 4:
                # High rating bonus
                award_points(
                    user=instance.note.uploaded_by,
                    points=3,
                    reason=f'Received {instance.rating}-star rating',
                    related_note=instance.note,
                    related_rating=instance
                )
            else:
                # Any rating still counts
                award_points(
                    user=instance.note.uploaded_by,
                    points=1,
                    reason=f'Received {instance.rating}-star rating',
                    related_note=instance.note,
                    related_rating=instance
                )


@receiver(post_save, sender=Rating)
def update_stats_on_rating(sender, instance, **kwargs):
    """
    Update reviewer stats and uploader stats.
    """
    update_user_stats(instance.user)
    update_user_stats(instance.note.uploaded_by)

# HELPFUL MARKS
@receiver(post_save, sender=RatingHelpful)
def helpful_review_points(sender, instance, created, **kwargs):
    """
    Award points when a review is marked helpful.
    """
    if created and instance.rating.user != instance.user:
        award_points(
            user=instance.rating.user,
            points=2,
            reason='Review marked helpful',
            related_rating=instance.rating
        )
        update_user_stats(instance.rating.user)

# REQUEST RESPONSES
@receiver(pre_save, sender=NoteRequestResponse)
def cache_old_response_helpful(sender, instance, **kwargs):
    """
    Cache old helpful/best-answer state.
    """
    if instance.pk:
        old = sender.objects.filter(pk=instance.pk).first()
        instance._old_is_helpful = old.is_helpful if old else False
    else:
        instance._old_is_helpful = False


@receiver(post_save, sender=NoteRequestResponse)
def request_fulfilled_points(sender, instance, created, **kwargs):
    """
    Award points when user responds to a request.
    """
    if created:
        award_points(
            user=instance.responder,
            points=15,
            reason='Fulfilled note request'
        )
        update_user_stats(instance.responder)


@receiver(post_save, sender=NoteRequestResponse)
def best_answer_points(sender, instance, created, **kwargs):
    """
    Award bonus points only when response becomes best answer.
    """
    old_is_helpful = getattr(instance, '_old_is_helpful', False)

    if not created and instance.is_helpful and not old_is_helpful:
        award_points(
            user=instance.responder,
            points=20,
            reason='Marked as best answer'
        )
        update_user_stats(instance.responder)

# BOOKMARKS
@receiver(post_save, sender=Bookmark)
def update_stats_on_bookmark(sender, instance, **kwargs):
    """
    Update bookmarker stats.
    """
    update_user_stats(instance.user)