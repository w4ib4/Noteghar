from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from notes.badge_utils import update_user_stats, check_and_award_badges

User = get_user_model()

class Command(BaseCommand):
    help = 'Update stats for all users and check/award badges'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Update stats for specific user only',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        
        if username:
            # Update single user
            try:
                user = User.objects.get(username=username)
                self.stdout.write(f'Updating stats for {user.username}...')
                update_user_stats(user)
                badges = check_and_award_badges(user)
                
                if badges:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Awarded {len(badges)} new badge(s):')
                    )
                    for badge in badges:
                        self.stdout.write(f'   {badge.icon} {badge.name}')
                else:
                    self.stdout.write(self.style.SUCCESS('✅ Stats updated, no new badges'))
                
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ User "{username}" not found')
                )
                return
        else:
            # Update all users
            users = User.objects.all()
            total = users.count()
            updated = 0
            total_badges = 0
            
            self.stdout.write(f'Updating stats for {total} users...\n')
            
            for user in users:
                self.stdout.write(f'Processing: {user.username}...', ending=' ')
                
                update_user_stats(user)
                badges = check_and_award_badges(user)
                
                if badges:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ +{len(badges)} badge(s)')
                    )
                    total_badges += len(badges)
                else:
                    self.stdout.write(self.style.SUCCESS('✅'))
                
                updated += 1
            
            self.stdout.write('\n' + '='*50)
            self.stdout.write(
                self.style.SUCCESS(f'✅ Updated {updated}/{total} users')
            )
            self.stdout.write(
                self.style.SUCCESS(f'🏅 Awarded {total_badges} total badges')
            )