from django.core.management.base import BaseCommand
from django.db import transaction
from notes.models import Institution, Course, Subject, Semester


class Command(BaseCommand):
    help = 'Set up institutions, courses and subjects'

    def handle(self, *args, **options):
        with transaction.atomic():
            self._setup_semesters()
            self._clean_institutions()
            self._setup_herald()
            self._setup_islington()
            self._setup_plus2()
        self.stdout.write(self.style.SUCCESS('\nDone.'))

    # Semesters
    def _setup_semesters(self):
        semesters = {
            1: 'Semester 1', 2: 'Semester 2', 3: 'Semester 3',
            4: 'Semester 4', 5: 'Semester 5', 6: 'Semester 6',
            7: 'Grade 11',   8: 'Grade 12',
        }
        for number, name in semesters.items():
            Semester.objects.update_or_create(number=number, defaults={'name': name})
        # Remove any other semesters
        Semester.objects.exclude(number__in=semesters.keys()).delete()
        self.stdout.write(f'  Semesters: {Semester.objects.count()} total')

    #  Remove old institutions 
    def _clean_institutions(self):
        keep = {'Herald College Kathmandu', 'Islington College', '+2 / High School (Nepal)'}
        removed = Institution.objects.exclude(name__in=keep).delete()
        self.stdout.write(f'  Removed old institutions: {removed[0]}')

    #  Herald College 
    def _setup_herald(self):
        from django.utils.text import slugify

        herald, _ = Institution.objects.get_or_create(
            name='Herald College Kathmandu',
            defaults={
                'short_name': 'Herald',
                'location':   'Kathmandu, Nepal',
                'website':    'https://www.heraldcollege.edu.np',
                'is_active':  True,
            }
        )

        course, _ = Course.objects.get_or_create(
            name='BSc (Hons) Computer Science',
            defaults={
                'code':        'BSc.CS',
                'description': 'Bachelor of Science with Honours in Computer Science — Herald College / University of Wolverhampton',
                'slug':        'bsc-hons-computer-science',
            }
        )

        subjects = [
            # Level 4 — Semester 1
            (1, 'Introductory Programming and Problem Solving', '4CS001'),
            (1, 'Fundamentals of Computing',                    '4CS015'),
            (1, 'Internet Software Architecture and Databases', '4CS017'),
            # Level 4 — Semester 2
            (2, 'Interactive 3D Applications and Academic Skills', '4CS020'),
            (2, 'Introduction to Object-Oriented Programming',     '4CS021'),
            (2, 'Computational Mathematics',                        '4MM013'),
            # Level 5 — Semester 3
            (3, 'Object-Oriented Design and Programming', '5CS019'),
            (3, 'Human-Computer Interaction',             '5CS020'),
            (3, 'Concepts and Technologies of AI',        '5CS037'),
            # Level 5 — Semester 4
            (4, 'Numerical Methods and Concurrency',         '5CS021'),
            (4, 'Distributed and Cloud Systems Programming', '5CS022'),
            (4, 'Collaborative Development',                 '5CS024'),
            # Level 6 — Semester 5
            (5, 'Complex Systems',             '6CS014'),
            (5, 'High Performance Computing',  '6CS005'),
            (5, 'Project and Professionalism', '6CS007'),
            # Level 6 — Semester 6
            (6, 'Artificial Intelligence and Machine Learning', '6CS012'),
            (6, 'Big Data',                                     '6CS030'),
            (6, 'Project and Professionalism',                  '6CS007'),
        ]

        created = 0
        for sem_num, name, code in subjects:
            semester = Semester.objects.get(number=sem_num)
            slug = slugify(f'{code}-{name}')[:50]
            _, was_created = Subject.objects.get_or_create(
                name=name, course=course, semester=semester,
                defaults={'code': code, 'slug': slug},
            )
            if was_created:
                created += 1

        self.stdout.write(f'  Herald: {course.name} — {created} subjects created')

    # Islington College 
    def _setup_islington(self):
        Institution.objects.get_or_create(
            name='Islington College',
            defaults={
                'short_name': 'Islington',
                'location':   'Kathmandu, Nepal',
                'website':    'https://www.islington.edu.np',
                'is_active':  True,
            }
        )
        self.stdout.write('  Islington College: ready (add courses when available)')

    # +2 / High School 
    def _setup_plus2(self):
        from django.utils.text import slugify

        institution, _ = Institution.objects.get_or_create(
            name='+2 / High School (Nepal)',
            defaults={
                'short_name': '+2',
                'location':   'Nepal',
                'website':    '',
                'is_active':  True,
            }
        )

        # Two streams with shared and stream-specific subjects
        streams = [
            {
                'name':        '+2 Science',
                'code':        'PLUS2.SCI',
                'description': 'Higher Secondary Level — Science Stream (NEB Nepal)',
                'slug':        'plus2-science',
                'subjects': [
                    # Grade 11 — Semester 7
                    (7, 'English',          'ENG'),
                    (7, 'Nepali',           'NEP'),
                    (7, 'Mathematics',      'MATH'),
                    (7, 'Physics',          'PHY'),
                    (7, 'Chemistry',        'CHEM'),
                    (7, 'Biology',          'BIO'),
                    (7, 'Computer Science', 'CS'),
                    (7, 'Economics',        'ECO'),
                    # Grade 12 — Semester 8
                    (8, 'English',          'ENG'),
                    (8, 'Nepali',           'NEP'),
                    (8, 'Mathematics',      'MATH'),
                    (8, 'Physics',          'PHY'),
                    (8, 'Chemistry',        'CHEM'),
                    (8, 'Biology',          'BIO'),
                    (8, 'Computer Science', 'CS'),
                    (8, 'Economics',        'ECO'),
                ],
            },
            {
                'name':        '+2 Management',
                'code':        'PLUS2.MGT',
                'description': 'Higher Secondary Level — Management Stream (NEB Nepal)',
                'slug':        'plus2-management',
                'subjects': [
                    # Grade 11 — Semester 7
                    (7, 'English',     'ENG'),
                    (7, 'Nepali',      'NEP'),
                    (7, 'Mathematics', 'MATH'),
                    (7, 'Accounts',    'ACC'),
                    (7, 'Business',    'BUS'),
                    (7, 'Marketing',   'MKT'),
                    (7, 'Computer Science', 'CS'),
                    (7, 'Economics',    'ECO'),
                    # Grade 12 — Semester 8
                    (8, 'English',     'ENG'),
                    (8, 'Nepali',      'NEP'),
                    (8, 'Mathematics', 'MATH'),
                    (8, 'Accounts',    'ACC'),
                    (8, 'Business',    'BUS'),
                    (8, 'Marketing',   'MKT'),
                    (8, 'Computer Science', 'CS'),
                    (8, 'Economics',    'ECO'),
                ],
            },
        ]

        total_created = 0
        for stream in streams:
            course, _ = Course.objects.get_or_create(
                name=stream['name'],
                defaults={
                    'code':        stream['code'],
                    'description': stream['description'],
                    'slug':        stream['slug'],
                }
            )
            for sem_num, name, code in stream['subjects']:
                semester = Semester.objects.get(number=sem_num)
                slug = slugify(f"{stream['code']}-{code}-{name}")[:50]
                _, was_created = Subject.objects.get_or_create(
                    name=name, course=course, semester=semester,
                    defaults={'code': code, 'slug': slug},
                )
                if was_created:
                    total_created += 1

        self.stdout.write(
            f'  +2 High School: 2 streams (Science + Management) — '
            f'{total_created} subjects created'
        )