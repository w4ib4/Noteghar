from django.core.management.base import BaseCommand
from django.db import transaction
from notes.models import Institution, Course, Subject, Semester


class Command(BaseCommand):
    help = 'Clean up and set up only Herald College and Islington College data'

    def handle(self, *args, **options):
        with transaction.atomic():
            self._setup_semesters()
            self._clean_courses_and_subjects()
            self._clean_institutions()
            self._setup_herald()
            self._setup_islington()
        self.stdout.write(self.style.SUCCESS('\nDone.'))

    # ── Semesters 1-6 only ───────────────────────────────────────────────────
    def _setup_semesters(self):
        needed = {
            1: 'Semester 1', 2: 'Semester 2', 3: 'Semester 3',
            4: 'Semester 4', 5: 'Semester 5', 6: 'Semester 6',
        }
        for number, name in needed.items():
            Semester.objects.update_or_create(
                number=number, defaults={'name': name}
            )
        # Remove extra semesters (7, 8, etc.)
        removed = Semester.objects.exclude(number__in=needed.keys()).delete()
        self.stdout.write(f'  Semesters: kept 1-6, removed extras: {removed[0]}')

    # ── Remove all existing courses and subjects ─────────────────────────────
    def _clean_courses_and_subjects(self):
        subj_count = Subject.objects.count()
        course_count = Course.objects.count()
        Subject.objects.all().delete()
        Course.objects.all().delete()
        self.stdout.write(
            f'  Removed {subj_count} subject(s) and {course_count} course(s)'
        )

    # ── Remove all institutions except the two we want ───────────────────────
    def _clean_institutions(self):
        keep = {'Herald College Kathmandu', 'Islington College'}
        removed = Institution.objects.exclude(name__in=keep).delete()
        self.stdout.write(f'  Removed old institutions: {removed[0]}')

    # ── Herald College ────────────────────────────────────────────────────────
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
        self.stdout.write(f'  Course: {course.name}')

        # (semester_number, name, code)
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
                name=name,
                course=course,
                semester=semester,
                defaults={'code': code, 'slug': slug},
            )
            if was_created:
                created += 1

        total = Subject.objects.filter(course=course).count()
        self.stdout.write(f'  Subjects: {created} created ({total} total)')

    # ── Islington College (placeholder — no courses yet) ─────────────────────
    def _setup_islington(self):
        islington, created = Institution.objects.get_or_create(
            name='Islington College',
            defaults={
                'short_name': 'Islington',
                'location':   'Kathmandu, Nepal',
                'website':    'https://www.islington.edu.np',
                'is_active':  True,
            }
        )
        status = 'created' if created else 'already exists'
        self.stdout.write(f'  Islington College: {status}')