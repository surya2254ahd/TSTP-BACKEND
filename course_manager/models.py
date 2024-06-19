from django.db import models

from user_manager.models import User


class Course(models.Model):
    name = models.CharField(max_length=30, null=False, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

    @classmethod
    def get_course_by_name(cls, name):
        return cls.objects.get(name=name)

    @classmethod
    def get_course_by_id(cls, course_id):
        return cls.objects.get(id=course_id)

    @classmethod
    def get_all(cls):
        return cls.objects.filter(is_active=True)

    def get_enrolled_students(self):
        return User.objects.filter(course_enrollments__course=self, is_active=True)

    def get_enrolled_students_excluding(self, user_ids):
        return User.objects.exclude(id__in=user_ids).filter(course_enrollments__course=self, is_active=True)


class CourseEnrollment(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')

    subscription_start_date = models.DateField(null=True)
    subscription_end_date = models.DateField(null=True)
    FREE = 'FREE'
    PAID = 'PAID'
    SUBSCRIPTION_TYPE_CHOICES = [
        (FREE, 'Free'),
        (PAID, 'Paid')
    ]
    subscription_type = models.CharField(max_length=10, choices=SUBSCRIPTION_TYPE_CHOICES, default=FREE)

    class Meta:
        unique_together = ['student', 'course']

    def __str__(self):
        return f"{self.student.name} enrolled in {self.course.name}"

    @classmethod
    def get_student_enrollment_using_student_course(cls, student_id, course_id):
        return CourseEnrollment.objects.get(student=student_id, course=course_id)

    @classmethod
    def create_enrollment(cls, **kwargs):
        """
        Create a new CourseEnrollment instance.
        """
        course_enrollment_instance = cls.objects.create(**kwargs)
        return course_enrollment_instance

    def update_enrollment(self, **kwargs):
        """
        Update fields of an existing CourseEnrollment instance.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()
        return self


class Subject(models.Model):
    name = models.CharField(max_length=30, null=False, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_all(cls):
        return cls.objects.filter(is_active=True)


class CourseSubjects(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    metadata = models.JSONField(default=dict)
    order = models.PositiveIntegerField(default=0)
    correct_answer_marks = models.PositiveIntegerField(default=1)
    incorrect_answer_marks = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']
        unique_together = ['course', 'subject']

    @classmethod
    def get_subjects_for_course(cls, course_id):
        return cls.objects.filter(course=course_id)

    @classmethod
    def get_course_subject_by_id(cls, course_subject_id):
        return cls.objects.get(id=course_subject_id)


class Topic(models.Model):
    name = models.CharField(max_length=100)
    course_subject = models.ForeignKey(CourseSubjects, on_delete=models.CASCADE, related_name='topics')

    class Meta:
        unique_together = ('name', 'course_subject')

    def __str__(self):
        return f"{self.name} ({self.course_subject})"


class SubTopic(models.Model):
    name = models.CharField(max_length=100)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='subtopics')

    class Meta:
        unique_together = ('name', 'topic')

    def __str__(self):
        return self.name


class Question(models.Model):
    course_subject = models.ForeignKey(CourseSubjects, on_delete=models.CASCADE)
    description = models.TextField(null=False)

    SINGLE_CHOICE_QUESTION = 'SINGLE_CHOICE'
    MULTI_CHOICE_QUESTION = 'MULTI_CHOICE'
    FILL_IN_BLANKS = 'FILL_IN_BLANKS'
    READING_COMPREHENSION = 'READING_COMPREHENSION'
    QUESTION_TYPE_CHOICES = [
        (SINGLE_CHOICE_QUESTION, 'Single Choice'),
        (MULTI_CHOICE_QUESTION, 'Multi Choice'),
        (FILL_IN_BLANKS, 'Fill in the Blanks'),
        (READING_COMPREHENSION, 'Reading Comprehension'),
    ]
    question_type = models.CharField(max_length=30, choices=QUESTION_TYPE_CHOICES, default=SINGLE_CHOICE_QUESTION)

    reading_comprehension_passage = models.TextField(null=True, blank=True)

    # The options JSONField, structure depends on question type
    options = models.JSONField(default=dict)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='questions_created')
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    has_suggestion = models.BooleanField(default=False)
    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    sub_topic = models.ForeignKey(SubTopic, on_delete=models.SET_NULL, null=True, blank=True)
    show_calculator = models.BooleanField(default=False)

    VERY_EASY_DIFFICULTY = 'VERY_EASY'
    EASY_DIFFICULTY = 'EASY'
    MODERATE_DIFFICULTY = 'MODERATE'
    HARD_DIFFICULTY = 'HARD'
    VERY_HARD_DIFFICULTY = 'VERY_HARD'
    DIFFICULTY_CHOICES = [
        (VERY_EASY_DIFFICULTY, 'Very Easy'),
        (EASY_DIFFICULTY, 'Easy'),
        (MODERATE_DIFFICULTY, 'Moderate'),
        (HARD_DIFFICULTY, 'Hard'),
        (VERY_HARD_DIFFICULTY, 'Very Hard')
    ]
    difficulty = models.CharField(max_length=15, choices=DIFFICULTY_CHOICES, default=MODERATE_DIFFICULTY)

    FULL_LENGTH_TEST_TYPE = 'FULL_LENGTH_TEST'
    SELF_PRACTICE_TEST_TYPE = 'SELF_PRACTICE_TEST'
    TEST_TYPE_CHOICES = [
        (FULL_LENGTH_TEST_TYPE, 'Full Length Test'),
        (SELF_PRACTICE_TEST_TYPE, 'Self Practice Test')
    ]
    test_type = models.CharField(max_length=20, choices=TEST_TYPE_CHOICES, default=FULL_LENGTH_TEST_TYPE)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def get_questions_for_subject(cls, course_subject_id):
        return cls.objects.filter(course_subject_id=course_subject_id)

    @classmethod
    def get_questions_for_subject_test_type(cls, course_subject_id, test_type):
        return cls.objects.filter(course_subject_id=course_subject_id, test_type=test_type)

    @classmethod
    def get_questions_for_ids_for_test(cls, ids, test_type):
        return cls.objects.filter(id__in=ids, test_type=test_type)

    @classmethod
    def get_questions_for_ids(cls, ids):
        return cls.objects.filter(id__in=ids)

    @classmethod
    def get_question_by_id(cls, question_id):
        return cls.objects.get(id=question_id)

    @classmethod
    def get_all(cls):
        return cls.objects.filter(is_active=True)


class Material(models.Model):
    course_subject = models.ForeignKey(CourseSubjects, on_delete=models.CASCADE)
    name = models.CharField(max_length=30)

    MATERIAL_TYPES = [
        ('PDF', 'Pdf'),
        ('VIDEO', 'Video'),
        ('IMAGE', 'Image')
    ]
    material_type = models.CharField(max_length=5, choices=MATERIAL_TYPES)

    FREE_ACCESS_TYPE = 'FREE'
    PAID_ACCESS_TYPE = 'PAID'
    ACCESS_TYPES = [
        (FREE_ACCESS_TYPE, 'Free'),
        (PAID_ACCESS_TYPE, 'Paid'),
    ]
    access_type = models.CharField(max_length=4, choices=ACCESS_TYPES, default=FREE_ACCESS_TYPE)

    file_name = models.CharField(max_length=50, blank=True, null=True)
    uploaded_file_name = models.CharField(max_length=50, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='material_created')
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE)

    topic = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True)
    sub_topic = models.ForeignKey(SubTopic, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

    @classmethod
    def get_material_by_id(cls, material_id):
        return cls.objects.get(id=material_id)


class CombinedScore(models.Model):
    subject_name = models.CharField(max_length=30)
    section1_correct = models.IntegerField()
    section2_correct = models.IntegerField()
    total_score = models.IntegerField()
