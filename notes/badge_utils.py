from django.db.models import Count, Avg, Q
from .models import Badge, UserBadge, UserProfile, Note, Rating, Download, Bookmark, NoteRequestResponse
 
def check_and_award_badges(user):
    """
    Check all badge requirements and award if met
    Returns list of newly earned badges
    """
    newly_earned = []
    
    # Get or create profile
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Get all badges
    badges = Badge.objects.all()
    
    for badge in badges:
        # Skip if already earned
        if UserBadge.objects.filter(user=user, badge=badge).exists():
            continue
        
        # Check requirement
        earned = False
        
        if badge.requirement_type == 'upload_count':
            count = Note.objects.filter(uploaded_by=user, status='approved').count()
            earned = count >= badge.requirement_value
            
        elif badge.requirement_type == 'quality_rating':
            # Quality Champion: 5+ notes with 4.5+ avg rating
            notes_with_good_rating = Note.objects.filter(
                uploaded_by=user,
                status='approved'
            ).annotate(
                avg_rating=Avg('ratings__rating'),
                rating_count=Count('ratings')
            ).filter(
                avg_rating__gte=4.5,
                rating_count__gte=3  # Minimum 3 ratings
            ).count()
            earned = notes_with_good_rating >= badge.requirement_value
            
        elif badge.requirement_type == 'trending_count':
            # Count how many times user's notes were in trending
            # This would need a tracking system - placeholder for now
            earned = False
            
        elif badge.requirement_type == 'view_count':
            count = Download.objects.filter(
                user=user,
                is_download=False
            ).count()
            earned = count >= badge.requirement_value
            
        elif badge.requirement_type == 'download_count':
            count = Download.objects.filter(
                user=user,
                is_download=True
            ).count()
            earned = count >= badge.requirement_value
            
        elif badge.requirement_type == 'review_count':
            count = Rating.objects.filter(
                user=user
            ).exclude(review='').count()
            earned = count >= badge.requirement_value
            
        elif badge.requirement_type == 'helpful_marks':
            # Count helpful marks on user's reviews
            from .models import RatingHelpful
            count = RatingHelpful.objects.filter(
                rating__user=user
            ).count()
            earned = count >= badge.requirement_value
            
        elif badge.requirement_type == 'bookmark_count':
            count = Bookmark.objects.filter(user=user).count()
            earned = count >= badge.requirement_value
            
        elif badge.requirement_type == 'request_fulfilled':
            count = NoteRequestResponse.objects.filter(
                responder=user,
                is_helpful=True  # Marked as best answer
            ).count()
            earned = count >= badge.requirement_value
        
        # Award badge if earned
        if earned:
            UserBadge.objects.create(user=user, badge=badge)
            # Award points
            if badge.points_reward > 0:
                profile.add_points(badge.points_reward, f'Earned badge: {badge.name}')
            newly_earned.append(badge)
    
    return newly_earned
 
 
def award_points(user, points, reason, related_note=None, related_rating=None):
    """
    Award points to user and log transaction
    """
    from .models import PointTransaction
    
    profile, _ = UserProfile.objects.get_or_create(user=user)
    leveled_up = profile.add_points(points, reason)
    
    # Log transaction
    PointTransaction.objects.create(
        user=user,
        points=points,
        reason=reason,
        related_note=related_note,
        related_rating=related_rating
    )
    
    # Check for new badges
    newly_earned = check_and_award_badges(user)
    
    return {
        'leveled_up': leveled_up,
        'new_badges': newly_earned,
        'new_level': profile.level if leveled_up else None
    }
 
 
def update_user_stats(user):
    """
    Update all user statistics in profile
    """
    profile, _ = UserProfile.objects.get_or_create(user=user)
    
    # Update counts
    profile.notes_uploaded = Note.objects.filter(uploaded_by=user, status='approved').count()
    profile.notes_downloaded = Download.objects.filter(user=user, is_download=True).count()
    profile.notes_viewed = Download.objects.filter(user=user, is_download=False).count()
    profile.reviews_written = Rating.objects.filter(user=user).exclude(review='').count()
    profile.bookmarks_count = Bookmark.objects.filter(user=user).count()
    profile.requests_fulfilled = NoteRequestResponse.objects.filter(responder=user, is_helpful=True).count()
    
    # Update helpful marks received
    from .models import RatingHelpful
    profile.helpful_marks_received = RatingHelpful.objects.filter(rating__user=user).count()
    
    profile.save()
    
    # Check for new badges
    check_and_award_badges(user)
 