from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from notes.models import Note, Download, Rating, RatingHelpful, NoteRequestResponse, UserProfile, PointTransaction
from notes.badge_utils import check_and_award_badges

User = get_user_model()

class Command(BaseCommand):
    help = 'Backfill points for all existing actions (one-time migration)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made\n'))
        
        # Clear existing point transactions to avoid duplicates
        if not dry_run:
            confirm = input('⚠️  This will clear existing point transactions and recalculate. Continue? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('❌ Aborted'))
                return
            
            self.stdout.write('Clearing existing point transactions...')
            PointTransaction.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✅ Cleared\n'))
        
        total_points_awarded = 0
        total_badges_awarded = 0
        
        # 1. AWARD POINTS FOR NOTE UPLOADS
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📚 Processing Note Uploads...')
        self.stdout.write('='*60)
        
        notes = Note.objects.select_related('uploaded_by').all()
        upload_points = 0
        approve_points = 0
        
        for note in notes:
            user = note.uploaded_by
            profile, _ = UserProfile.objects.get_or_create(user=user)
            
            # +10 points for upload
            if not dry_run:
                PointTransaction.objects.create(
                    user=user,
                    points=10,
                    reason='Uploaded note',
                    related_note=note
                )
                profile.total_points += 10
            upload_points += 10
            
            # +5 points if approved
            if note.status == 'approved':
                if not dry_run:
                    PointTransaction.objects.create(
                        user=user,
                        points=5,
                        reason='Note approved',
                        related_note=note
                    )
                    profile.total_points += 5
                approve_points += 5
            
            if not dry_run:
                profile.save()
        
        self.stdout.write(f'   Upload points: {upload_points}')
        self.stdout.write(f'   Approval points: {approve_points}')
        total_points_awarded += upload_points + approve_points
        
        # 2. AWARD POINTS FOR DOWNLOADS
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📥 Processing Downloads...')
        self.stdout.write('='*60)
        
        downloads = Download.objects.filter(is_download=True).select_related('note', 'user', 'note__uploaded_by')
        download_points = 0
        
        for download in downloads:
            uploader = download.note.uploaded_by
            # Don't award points for downloading own notes
            if uploader != download.user:
                profile, _ = UserProfile.objects.get_or_create(user=uploader)
                if not dry_run:
                    PointTransaction.objects.create(
                        user=uploader,
                        points=1,
                        reason='Note downloaded',
                        related_note=download.note
                    )
                    profile.total_points += 1
                    profile.save()
                download_points += 1
        
        self.stdout.write(f'   Download points: {download_points}')
        total_points_awarded += download_points
        
        # 3. AWARD POINTS FOR 5-STAR RATINGS
        self.stdout.write('\n' + '='*60)
        self.stdout.write('⭐ Processing 5-Star Ratings...')
        self.stdout.write('='*60)
        
        five_star_ratings = Rating.objects.filter(rating=5).select_related('note', 'user', 'note__uploaded_by')
        rating_points = 0
        
        for rating in five_star_ratings:
            uploader = rating.note.uploaded_by
            # Don't award for rating own notes
            if uploader != rating.user:
                profile, _ = UserProfile.objects.get_or_create(user=uploader)
                if not dry_run:
                    PointTransaction.objects.create(
                        user=uploader,
                        points=3,
                        reason='Received 5-star rating',
                        related_note=rating.note,
                        related_rating=rating
                    )
                    profile.total_points += 3
                    profile.save()
                rating_points += 3
        
        self.stdout.write(f'   5-Star rating points: {rating_points}')
        total_points_awarded += rating_points
        
        # 4. AWARD POINTS FOR HELPFUL MARKS
        self.stdout.write('\n' + '='*60)
        self.stdout.write('❤️  Processing Helpful Marks...')
        self.stdout.write('='*60)
        
        helpful_marks = RatingHelpful.objects.select_related('rating', 'rating__user', 'user')
        helpful_points = 0
        
        for mark in helpful_marks:
            reviewer = mark.rating.user
            # Don't award for marking own review helpful
            if reviewer != mark.user:
                profile, _ = UserProfile.objects.get_or_create(user=reviewer)
                if not dry_run:
                    PointTransaction.objects.create(
                        user=reviewer,
                        points=2,
                        reason='Review marked helpful',
                        related_rating=mark.rating
                    )
                    profile.total_points += 2
                    profile.save()
                helpful_points += 2
        
        self.stdout.write(f'   Helpful mark points: {helpful_points}')
        total_points_awarded += helpful_points
        
        # 5. AWARD POINTS FOR REQUEST RESPONSES
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🤝 Processing Request Responses...')
        self.stdout.write('='*60)
        
        responses = NoteRequestResponse.objects.select_related('responder')
        response_points = 0
        best_answer_points = 0
        
        for response in responses:
            profile, _ = UserProfile.objects.get_or_create(user=response.responder)
            
            # +15 for responding
            if not dry_run:
                PointTransaction.objects.create(
                    user=response.responder,
                    points=15,
                    reason='Fulfilled note request'
                )
                profile.total_points += 15
            response_points += 15
            
            # +20 bonus if marked as best answer
            if response.is_helpful:
                if not dry_run:
                    PointTransaction.objects.create(
                        user=response.responder,
                        points=20,
                        reason='Marked as best answer'
                    )
                    profile.total_points += 20
                best_answer_points += 20
            
            if not dry_run:
                profile.save()
        
        self.stdout.write(f'   Response points: {response_points}')
        self.stdout.write(f'   Best answer points: {best_answer_points}')
        total_points_awarded += response_points + best_answer_points
        
        # 6. UPDATE LEVELS AND CHECK BADGES
        self.stdout.write('\n' + '='*60)
        self.stdout.write('🏅 Checking Badges and Updating Levels...')
        self.stdout.write('='*60)
        
        all_users = User.objects.all()
        
        for user in all_users:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            
            if not dry_run:
                # Update level based on total points
                profile.level = profile.get_level()
                profile.save()
                
                # Check and award badges
                badges = check_and_award_badges(user)
                if badges:
                    total_badges_awarded += len(badges)
                    self.stdout.write(f'   {user.username}: +{len(badges)} badge(s)')
        
        # SUMMARY
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✅ BACKFILL COMPLETE'))
        self.stdout.write('='*60)
        self.stdout.write(f'📊 Total points awarded: {total_points_awarded}')
        self.stdout.write(f'🏅 Total badges awarded: {total_badges_awarded}')
        self.stdout.write(f'👥 Users processed: {all_users.count()}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  This was a DRY RUN - no changes were made'))
            self.stdout.write('Run without --dry-run to apply changes')