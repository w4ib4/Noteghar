import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'noteghar.settings'
import django
django.setup()

from notes.models import Course, Semester, Subject, Badge
from django.contrib.sites.models import Site

# Update the default Site
site, _ = Site.objects.get_or_create(id=1)
site.domain = '127.0.0.1:8000'
site.name   = 'NoteGhar'
site.save()
print('  Site configured')

# Courses
courses_data = [
    ('BSc CSIT', 'BSc.CSIT', 'Bachelor of Science in Computer Science and Information Technology'),
    ('BCA',      'BCA',      'Bachelor of Computer Applications'),
    ('BIT',      'BIT',      'Bachelor of Information Technology'),
    ('BE Computer', 'BE.Comp', 'Bachelor of Engineering in Computer'),
    ('MCA',      'MCA',      'Master of Computer Applications'),
    ('BSc',      'BSc',      'Bachelor of Science'),
]
for name, code, desc in courses_data:
    Course.objects.get_or_create(name=name, defaults={'code': code, 'description': desc})
print(f'  {Course.objects.count()} courses')

# Semesters
for i in range(1, 9):
    Semester.objects.get_or_create(number=i, defaults={'name': f'Semester {i}'})
print(f'  {Semester.objects.count()} semesters')

# Subjects (BSc CSIT sample)
csit = Course.objects.filter(code='BSc.CSIT').first()
bca  = Course.objects.filter(code='BCA').first()

subjects = [
    # (course, semester_number, name, code)
    (csit, 1, 'Computer Fundamentals and Applications', 'CFA'),
    (csit, 1, 'Society and Technology', 'ST'),
    (csit, 1, 'Mathematics I', 'MATH1'),
    (csit, 2, 'C Programming', 'CPROG'),
    (csit, 2, 'Digital Logic', 'DL'),
    (csit, 2, 'Mathematics II', 'MATH2'),
    (csit, 3, 'Data Structures and Algorithms', 'DSA'),
    (csit, 3, 'Object Oriented Programming', 'OOP'),
    (csit, 3, 'Computer Architecture', 'CA'),
    (csit, 4, 'Operating System', 'OS'),
    (csit, 4, 'Database Management System', 'DBMS'),
    (csit, 4, 'Computer Networks', 'CN'),
    (csit, 5, 'Theory of Computation', 'TOC'),
    (csit, 5, 'Artificial Intelligence', 'AI'),
    (csit, 5, 'Web Technology', 'WT'),
    (csit, 6, 'Software Engineering', 'SE'),
    (csit, 6, 'Compiler Design', 'CD'),
    (csit, 6, 'Computer Graphics', 'CG'),
    (csit, 7, 'Machine Learning', 'ML'),
    (csit, 7, 'Distributed System', 'DS'),
    (csit, 7, 'Information Security', 'IS'),
    (csit, 8, 'Project Work', 'PROJ'),
    (bca,  1, 'Computer Fundamentals', 'CF'),
    (bca,  2, 'Programming in C', 'PC'),
    (bca,  3, 'Data Structures', 'DST'),
    (bca,  4, 'Database Systems', 'DBS'),
    (bca,  5, 'Web Programming', 'WP'),
    (bca,  6, 'Software Engineering', 'SEB'),
]
count = 0
for course, sem_num, name, code in subjects:
    if course is None:
        continue
    sem = Semester.objects.filter(number=sem_num).first()
    if sem:
        _, created = Subject.objects.get_or_create(
            name=name, course=course, semester=sem,
            defaults={'code': code}
        )
        if created:
            count += 1
print(f'  {count} subjects created ({Subject.objects.count()} total)')

# Badges
badges = [
    ('First Upload',     'first_upload',    'fa-upload',     'bronze', 'Uploaded your first note',                    0),
    ('Note Starter',     'note_starter',    'fa-file-alt',   'bronze', 'Uploaded 5 notes',                           5),
    ('Knowledge Sharer', 'knowledge_sharer','fa-share-alt',  'silver', 'Uploaded 20 notes',                          20),
    ('Top Contributor',  'top_contributor', 'fa-star',       'gold',   'Uploaded 50 notes',                          50),
    ('Popular Note',     'popular_note',    'fa-fire',       'silver', 'One of your notes got 50 downloads',         0),
    ('First Review',     'first_review',    'fa-comment',    'bronze', 'Wrote your first rating/review',             0),
    ('Helpful Reviewer', 'helpful_reviewer','fa-thumbs-up',  'silver', '10 of your reviews marked as helpful',       0),
    ('Quick Learner',    'quick_learner',   'fa-bolt',       'bronze', 'Downloaded 10 notes',                        0),
    ('Bookworm',         'bookworm',        'fa-book',       'silver', 'Bookmarked 25 notes',                        0),
    ('Week Streak',      'week_streak',     'fa-calendar',   'bronze', 'Logged in 7 days in a row',                  0),
    ('Month Streak',     'month_streak',    'fa-calendar-check','gold','Logged in 30 days in a row',                 0),
]
badge_count = 0
for name, slug, icon, tier, desc, threshold in badges:
    _, created = Badge.objects.get_or_create(
        name=name,
        defaults={
            'slug': slug, 'icon': icon, 'tier': tier,
            'description': desc, 'threshold': threshold,
        }
    )
    if created:
        badge_count += 1
print(f'  {badge_count} badges created ({Badge.objects.count()} total)')
