from django.core.management.base import BaseCommand
from notes.models import Badge
 
class Command(BaseCommand):
    help = 'Populate default badges'
 
    def handle(self, *args, **kwargs):
        badges_data = [
            # Contributor Badges
            {
                'name': 'Newbie Contributor',
                'slug': 'newbie-contributor',
                'description': 'Upload your first note',
                'icon': '📚',
                'category': 'contributor',
                'requirement_type': 'upload_count',
                'requirement_value': 1,
                'points_reward': 10,
                'color': 'secondary',
                'order': 1
            },
            {
                'name': 'Regular Contributor',
                'slug': 'regular-contributor',
                'description': 'Upload 5 notes',
                'icon': '📖',
                'category': 'contributor',
                'requirement_type': 'upload_count',
                'requirement_value': 5,
                'points_reward': 25,
                'color': 'info',
                'order': 2
            },
            {
                'name': 'Active Contributor',
                'slug': 'active-contributor',
                'description': 'Upload 10 notes',
                'icon': '📕',
                'category': 'contributor',
                'requirement_type': 'upload_count',
                'requirement_value': 10,
                'points_reward': 50,
                'color': 'primary',
                'order': 3
            },
            {
                'name': 'Super Contributor',
                'slug': 'super-contributor',
                'description': 'Upload 25 notes',
                'icon': '📗',
                'category': 'contributor',
                'requirement_type': 'upload_count',
                'requirement_value': 25,
                'points_reward': 100,
                'color': 'success',
                'order': 4
            },
            {
                'name': 'Master Contributor',
                'slug': 'master-contributor',
                'description': 'Upload 50 notes',
                'icon': '📘',
                'category': 'contributor',
                'requirement_type': 'upload_count',
                'requirement_value': 50,
                'points_reward': 250,
                'color': 'warning',
                'order': 5
            },
            {
                'name': 'Elite Contributor',
                'slug': 'elite-contributor',
                'description': 'Upload 100+ notes',
                'icon': '👑',
                'category': 'contributor',
                'requirement_type': 'upload_count',
                'requirement_value': 100,
                'points_reward': 500,
                'color': 'danger',
                'order': 6
            },
            {
                'name': 'Quality Champion',
                'slug': 'quality-champion',
                'description': '5+ notes with 4.5+ average rating',
                'icon': '⭐',
                'category': 'contributor',
                'requirement_type': 'quality_rating',
                'requirement_value': 5,
                'points_reward': 150,
                'color': 'warning',
                'order': 7
            },
            {
                'name': 'Trending Star',
                'slug': 'trending-star',
                'description': 'Note in top trending 3 times',
                'icon': '🌟',
                'category': 'contributor',
                'requirement_type': 'trending_count',
                'requirement_value': 3,
                'points_reward': 200,
                'color': 'danger',
                'order': 8
            },
            
            # Engagement Badges
            {
                'name': 'Explorer',
                'slug': 'explorer',
                'description': 'View 50 notes',
                'icon': '👀',
                'category': 'engagement',
                'requirement_type': 'view_count',
                'requirement_value': 50,
                'points_reward': 30,
                'color': 'info',
                'order': 1
            },
            {
                'name': 'Collector',
                'slug': 'collector',
                'description': 'Download 100 notes',
                'icon': '📥',
                'category': 'engagement',
                'requirement_type': 'download_count',
                'requirement_value': 100,
                'points_reward': 50,
                'color': 'primary',
                'order': 2
            },
            {
                'name': 'Reviewer',
                'slug': 'reviewer',
                'description': 'Leave 10 reviews',
                'icon': '💬',
                'category': 'engagement',
                'requirement_type': 'review_count',
                'requirement_value': 10,
                'points_reward': 40,
                'color': 'success',
                'order': 3
            },
            {
                'name': 'Helpful Hand',
                'slug': 'helpful-hand',
                'description': '50 helpful marks on your reviews',
                'icon': '❤️',
                'category': 'engagement',
                'requirement_type': 'helpful_marks',
                'requirement_value': 50,
                'points_reward': 100,
                'color': 'danger',
                'order': 4
            },
            {
                'name': 'Curator',
                'slug': 'curator',
                'description': 'Bookmark 25 notes',
                'icon': '🔖',
                'category': 'engagement',
                'requirement_type': 'bookmark_count',
                'requirement_value': 25,
                'points_reward': 30,
                'color': 'warning',
                'order': 5
            },
            
            # Community Badges
            {
                'name': 'Helper',
                'slug': 'helper',
                'description': 'Fulfill 5 note requests',
                'icon': '🤝',
                'category': 'community',
                'requirement_type': 'request_fulfilled',
                'requirement_value': 5,
                'points_reward': 75,
                'color': 'success',
                'order': 1
            },
        ]
        
        created_count = 0
        for badge_data in badges_data:
            badge, created = Badge.objects.get_or_create(
                slug=badge_data['slug'],
                defaults=badge_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created badge: {badge.icon} {badge.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Badge already exists: {badge.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Created {created_count} new badges!')
        )
        self.stdout.write(
            self.style.SUCCESS(f'📊 Total badges: {Badge.objects.count()}')
        )
 