from django.db import models
from django.utils import timezone

from course_manager.models import Course, Subject, CourseSubjects, Question
from notification_manager.models import Notification
from notification_manager.utils import mark_notification_as_read
from user_manager.models import User


class Test(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    PRACTICE = 'PRACTICE'
    EXAM = 'EXAM'
    ASSIGNMENT = 'ASSIGNMENT'
    TEST_TYPE_CHOICES = [
        (PRACTICE, 'Practice'),
        (EXAM, 'Exam'),
        (ASSIGNMENT, 'Assignment'),
    ]
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES, default=EXAM)

    LINEAR = 'LINEAR'
    DYNAMIC = 'DYNAMIC'
    FLAT = 'FLAT'
    FORMAT_CHOICES = [
        (LINEAR, 'Linear'),
        (DYNAMIC, 'Dynamic'),
        (FLAT, 'Flat'),
    ]
    format_type = models.CharField(max_length=20, choices=FORMAT_CHOICES, default=LINEAR)

    students = models.ManyToManyField(User, related_name='tests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests_created')
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tests_updated')
    is_active = models.BooleanField(default=True)
    show_skip_button = models.BooleanField(default=True)
    show_prev_button = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create(cls, course, name, test_type, format_type, created_by, updated_by):
        cls.objects.create(course=course, name=name, test_type=test_type,
                           format_type=format_type, created_by=created_by, updated_by=updated_by)

    @classmethod
    def get_all(cls):
        return cls.objects.filter(is_active=True)

    @classmethod
    def get_test_by_id(cls, test_id):
        return cls.objects.get(id=test_id)


class Section(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    course_subject = models.ForeignKey(CourseSubjects, on_delete=models.CASCADE)
    name = models.CharField(max_length=30, null=False)
    order = models.PositiveIntegerField(default=0)
    sub_sections = models.JSONField(default=list)  # name, questions
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']
        unique_together = ['test', 'course_subject']

    def add_sub_section(self, sub_section, question_ids=None):
        if question_ids is None:
            question_ids = []
        if not isinstance(self.sub_sections, list):
            self.sub_sections = []
        sub_section["questions"] = question_ids
        self.sub_sections.append(sub_section)
        self.save()

    @classmethod
    def fetch_section_using_test_course_subject(cls, test, course_subject):
        return cls.objects.filter(test=test, course_subject=course_subject).first()

    @classmethod
    def fetch_sections_using_test(cls, test):
        return cls.objects.filter(test=test)


class TestSubmission(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)

    YET_TO_START = 'YET_TO_START'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (YET_TO_START, 'Yet to start'),
        (IN_PROGRESS, 'In progress'),
        (COMPLETED, 'Completed'),
        (EXPIRED, 'Expired'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=YET_TO_START)

    assigned_date = models.DateTimeField(blank=False)
    expiration_date = models.DateTimeField(blank=False)
    completion_date = models.DateTimeField(null=True, blank=True)
    selected_question_ids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary of question IDs already selected for each section of this test submission."
    )

    class Meta:
        # unique_together = ['test', 'student']
        ordering = ['id']

    def update_submission(self, **kwargs):
        """
            Update fields of an existing TestSubmission instance.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()
        return self

    @classmethod
    def get_students_assigned_to_test(cls, test):
        # Get all TestSubmission instances for the test.
        test_submissions = cls.objects.filter(test=test)

        return test_submissions

    @classmethod
    def get_students_assigned_to_test_with_status(cls, test):
        test_submissions = cls.objects.filter(test=test,
                                              status__in=[TestSubmission.YET_TO_START, TestSubmission.IN_PROGRESS])

        return test_submissions

    @classmethod
    def get_students_assigned_to_test_for_faculty(cls, test, student_ids):
        # Get all TestSubmission instances for the test.
        test_submissions = cls.objects.filter(test=test, student__in=student_ids)

        return test_submissions


class Result(models.Model):
    correct_answer_count = models.IntegerField()
    incorrect_answer_count = models.IntegerField()
    time_taken = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    test_submission = models.OneToOneField(TestSubmission, on_delete=models.CASCADE)
    detailed_view = models.JSONField(default=dict)

    def update_detailed_view(self, test, course_subject, section_id, question_id, answer_data, time_taken,
                             correct_answer, is_skipped, is_marked_for_review):
        test_subjects = Section.fetch_sections_using_test(test=test)
        test_subject_section = None
        # Ensure that 'answers' key exists
        if "answers" not in self.detailed_view:
            self.detailed_view["answers"] = {}

            for test_subject in test_subjects:
                result_subject = self.detailed_view["answers"].get(str(test_subject.course_subject_id), {})
                for test_section in test_subject.sub_sections:
                    result_section = {
                        "questions_answered": {},
                        "time_taken": 0,
                        "total_questions": test_section["no_of_questions"]
                    }
                    result_subject[str(test_section['id'])] = result_section

                    if test_section["id"] == section_id:
                        test_subject_section = test_section

                self.detailed_view["answers"][str(test_subject.course_subject_id)] = result_subject

        test_submission = self.test_submission

        # Get the subject, if it does not exist, initialize it
        subject = self.detailed_view["answers"].get(str(course_subject))

        # Get the section, if it does not exist, initialize it
        section = subject.get(str(section_id))

        # Check if the question has been answered before
        previous_answer = section["questions_answered"].get(str(question_id))

        # Update the section
        # section["questions_answered"][str(question_id)] = {
        #     'selected_option_index': -1 if is_skipped else option_index,
        #     'is_skipped': is_skipped
        # }
        # Update the question's answer
        question_answered = {
            'answer_data': answer_data if not is_skipped else [],
            'is_skipped': is_skipped,
            'is_correct': correct_answer,
            'is_marked_for_review': is_marked_for_review,
            'first_time_taken': previous_answer.get('first_time_taken',
                                                    0) if previous_answer is not None else time_taken,
            'time_taken': previous_answer.get('time_taken',
                                              0) + time_taken if previous_answer is not None else time_taken,
            'times_visited': previous_answer.get('times_visited', 0) + 1 if previous_answer is not None else 1,
        }

        section["questions_answered"][str(question_id)] = question_answered
        section["time_taken"] += time_taken

        # Update correct and incorrect counts
        if previous_answer is not None and not is_skipped:
            # Adjust counts based on previous answer
            if previous_answer['is_correct'] and not correct_answer:
                self.correct_answer_count -= 1
                self.incorrect_answer_count += 1
            elif not previous_answer['is_correct'] and correct_answer:
                self.correct_answer_count += 1
                self.incorrect_answer_count -= 1
        else:
            # First time answering this question
            if not is_skipped and not correct_answer:
                self.incorrect_answer_count += 1
            elif not is_skipped and correct_answer:
                self.correct_answer_count += 1

        # Update back to the `detailed_view`
        subject[section_id] = section
        self.detailed_view["answers"][course_subject] = subject

        # Update overall time taken
        self.time_taken = self.time_taken + time_taken

        # Check for test completion and update the status accordingly
        all_answered = all(
            len(sec["questions_answered"]) == sec["total_questions"]
            for subj in self.detailed_view["answers"].values()
            for sec in subj.values()
        )
        if all_answered:
            test_submission.status = TestSubmission.COMPLETED
            test_submission.completion_date = timezone.now()
            mark_notification_as_read.delay(user_id=test_submission.student.id, category=Notification.TEST,
                                            reference_id=test_submission.id)
        else:
            test_submission.status = TestSubmission.IN_PROGRESS

        # Save the changes
        test_submission.save()
        self.save()


class PracticeTest(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='practice_tests')
    course_subject = models.ForeignKey(CourseSubjects, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class PracticeTestResult(models.Model):
    practice_test = models.OneToOneField(PracticeTest, on_delete=models.CASCADE, related_name='result')
    correct_answer_count = models.IntegerField()
    incorrect_answer_count = models.IntegerField()
    time_taken = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    detailed_view = models.JSONField(default=dict)

    def update_detailed_view(self, question_id, answer_data, time_taken, correct_answer, is_skipped,
                             is_marked_for_review):
        # Check if 'answers' key exists
        if "answers" not in self.detailed_view:
            self.detailed_view["answers"] = {}

        previous_answer = self.detailed_view["answers"].get(str(question_id))

        # Update the question's answer
        question_answered = {
            'answer_data': answer_data if not is_skipped else [],
            'is_skipped': is_skipped,
            'is_correct': correct_answer,
            'is_marked_for_review': is_marked_for_review,
            'first_time_taken': previous_answer.get('first_time_taken',
                                                    0) if previous_answer is not None else time_taken,
            'time_taken': previous_answer.get('time_taken',
                                              0) + time_taken if previous_answer is not None else time_taken,
            'times_visited': previous_answer.get('times_visited', 0) + 1 if previous_answer is not None else 1,
        }

        if previous_answer is not None and not is_skipped:
            if previous_answer['is_correct'] and not correct_answer:
                self.correct_answer_count -= 1
                self.incorrect_answer_count += 1
            elif not previous_answer['is_correct'] and correct_answer:
                self.correct_answer_count += 1
                self.incorrect_answer_count -= 1
        else:
            # Update correct and incorrect counts
            if not is_skipped and not correct_answer:
                self.incorrect_answer_count += 1
            elif not is_skipped and correct_answer:
                self.correct_answer_count += 1

        # Update the detailed view with the question's answer
        self.detailed_view["answers"][str(question_id)] = question_answered
        self.time_taken += time_taken

        self.save()


class AnsweredQuestions(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    course_subject = models.ForeignKey(CourseSubjects, on_delete=models.CASCADE)
    questions = models.JSONField(default=list)

    class Meta:
        unique_together = ['student', 'course_subject']

    def __str__(self):
        return f"{self.student.name} - {self.course_subject}"
