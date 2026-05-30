import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0004_badge_pointtransaction_userprofile_userbadge'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='note',
            name='assigned_moderator',
            field=models.ForeignKey(
                blank=True,
                help_text='Moderator assigned to review this note',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='assigned_notes',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]