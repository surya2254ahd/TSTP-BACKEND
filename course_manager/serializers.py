from rest_framework import serializers

from sTest.aws_client import AwsStorageClient
from .models import Course, Question, CourseSubjects, CourseEnrollment, Subject, Material, SubTopic, Topic


class CourseSubjectsSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='subject.id', read_only=True)
    name = serializers.CharField(source='subject.name', read_only=True)
    course_subject_id = serializers.IntegerField(source='id', read_only=True)
    sections = serializers.SerializerMethodField()

    class Meta:
        model = CourseSubjects
        fields = ('id', 'course_subject_id', 'name', 'order', 'correct_answer_marks', 'incorrect_answer_marks', 'sections')

    def get_sections(self, obj):
        return obj.metadata['sections']


class CourseWithSubjectsSerializer(serializers.ModelSerializer):
    subjects = CourseSubjectsSerializer(source='coursesubjects_set', many=True)

    class Meta:
        model = Course
        fields = ['id', 'name', 'subjects']


class CourseSubjectsSerializerForUserDetails(serializers.ModelSerializer):
    id = serializers.IntegerField(source='subject.id', read_only=True)
    name = serializers.CharField(source='subject.name', read_only=True)
    course_subject_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = CourseSubjects
        fields = ('id', 'course_subject_id', 'name', 'order')


class CourseWithSubjectsSerializerForUserDetails(serializers.ModelSerializer):
    subjects = CourseSubjectsSerializerForUserDetails(source='coursesubjects_set', many=True)

    class Meta:
        model = Course
        fields = ['id', 'name', 'subjects']


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'name']


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name']


class CreateOptionSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        # Depending on the context, handle as list of strings or list of dicts
        question_type = self.context.get('question_type')
        if question_type == Question.FILL_IN_BLANKS:
            # Expect data to be just the answer string
            return data
        else:
            # For other question types, expect data as a dictionary
            return {
                'description': data.get('description'),
                'is_correct': data.get('is_correct', False)
            }

    def to_representation(self, instance):
        # Handle representation based on instance type (string or dict)
        if isinstance(instance, str):
            return instance  # for fill in the blanks
        else:
            return {  # for other question types
                'description': instance['description'],
                'is_correct': instance.get('is_correct', False)
            }


class CreateQuestionSerializer(serializers.ModelSerializer):
    options = serializers.JSONField()
    topic = serializers.CharField(write_only=True)
    sub_topic = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Question
        fields = ['id', 'course_subject', 'description', 'reading_comprehension_passage', 'options', 'question_type',
                  'topic', 'sub_topic', 'difficulty', 'test_type', 'created_by', 'updated_by', 'is_active',
                  'show_calculator']

    def validate(self, data):
        # Validation logic for different question types
        if data['question_type'] == Question.READING_COMPREHENSION and not data.get('reading_comprehension_passage'):
            raise serializers.ValidationError("Reading comprehension passage is required.")
        elif data['question_type'] == Question.FILL_IN_BLANKS:
            # Validate that options are a list of strings for fill in the blanks
            if not isinstance(data.get('options', []), list) or not all(
                    isinstance(opt, str) for opt in data['options']):
                raise serializers.ValidationError("Options for fill in the blanks must be a list of strings.")
        elif data['question_type'] in [Question.SINGLE_CHOICE_QUESTION, Question.MULTI_CHOICE_QUESTION,
                                       Question.READING_COMPREHENSION]:
            # Validate that at least one option is marked as correct for choice questions
            correct_options = [opt for opt in data.get('options', []) if opt.get('is_correct')]
            if not correct_options:
                raise serializers.ValidationError("At least one option must be marked as correct.")
        return data

    def create(self, validated_data):
        topic_name = validated_data.pop('topic')
        sub_topic_name = validated_data.pop('sub_topic', None)

        topic, _ = Topic.objects.get_or_create(name=topic_name, course_subject=validated_data['course_subject'])
        sub_topic = None
        if sub_topic_name:
            sub_topic, _ = SubTopic.objects.get_or_create(name=sub_topic_name, topic=topic)

        question = Question.objects.create(**validated_data, topic=topic, sub_topic=sub_topic)
        return question

    def update(self, instance, validated_data):
        topic_name = validated_data.pop('topic', None)
        sub_topic_name = validated_data.pop('sub_topic', None)

        if topic_name:
            topic, _ = Topic.objects.get_or_create(name=topic_name, course_subject=validated_data.get('course_subject',
                                                                                                      instance.course_subject))
            instance.topic = topic
        if sub_topic_name:
            sub_topic, _ = SubTopic.objects.get_or_create(name=sub_topic_name, topic=instance.topic)
            instance.sub_topic = sub_topic

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class QuestionDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'description', 'reading_comprehension_passage', 'question_type', 'options', 'show_calculator']


class QuestionListSerializer(serializers.ModelSerializer):
    topic = serializers.CharField(source='topic.name')
    sub_topic = serializers.CharField(source='sub_topic.name', allow_null=True)

    class Meta:
        model = Question
        fields = ['id', 'description', 'course_subject', 'reading_comprehension_passage', 'question_type', 'options', 'has_suggestion',
                  'topic', 'sub_topic', 'difficulty', 'test_type', 'is_active', 'show_calculator']


class CourseEnrollmentSerializer(serializers.ModelSerializer):
    course = CourseWithSubjectsSerializerForUserDetails()

    class Meta:
        model = CourseEnrollment
        fields = ['course', 'subscription_start_date', 'subscription_end_date', 'subscription_type']


class SectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=30)
    no_of_questions = serializers.IntegerField()
    time_limit = serializers.IntegerField()


class CourseSubjectSerializer(serializers.Serializer):
    course_subject_id = serializers.IntegerField(required=False)
    name = serializers.CharField(max_length=30)
    order = serializers.IntegerField()
    correct_answer_marks = serializers.IntegerField()
    incorrect_answer_marks = serializers.IntegerField()
    sections = SectionSerializer(many=True)


class CreateCourseSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=30)
    subjects = CourseSubjectSerializer(many=True)


class MaterialSerializer(serializers.ModelSerializer):
    file = serializers.FileField(read_only=True, required=False)
    topic = serializers.CharField(write_only=True)
    sub_topic = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Material
        fields = ['course_subject', 'name', 'file', 'access_type', 'material_type', 'file_name', 'uploaded_file_name',
                  'url', 'created_by', 'updated_by', 'topic', 'sub_topic']

    def create(self, validated_data):
        topic_name = validated_data.pop('topic')
        sub_topic_name = validated_data.pop('sub_topic', None)

        topic, _ = Topic.objects.get_or_create(name=topic_name, course_subject=validated_data['course_subject'])
        sub_topic = None
        if sub_topic_name:
            sub_topic, _ = SubTopic.objects.get_or_create(name=sub_topic_name, topic=topic)

        material = Material.objects.create(**validated_data, topic=topic, sub_topic=sub_topic)
        return material


class MaterialListSerializer(serializers.ModelSerializer):
    # course = serializers.SerializerMethodField()
    # subject = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    topic = serializers.CharField(source='topic.name')
    sub_topic = serializers.CharField(source='sub_topic.name', allow_null=True)

    class Meta:
        model = Material
        fields = ['id', 'course_subject', 'name', 'material_type', 'access_type', 'file_name',
                  'uploaded_at', 'created_by', 'topic', 'sub_topic']

    # def get_course(self, obj):
    #     return obj.course_subject.course.name
    #
    # def get_subject(self, obj):
    #     return obj.course_subject.subject.name

    def get_created_by(self, obj):
        return obj.created_by.name


class MaterialDetailsSerializer(serializers.ModelSerializer):
    material_url = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()
    topic = serializers.CharField(source='topic.name')
    sub_topic = serializers.CharField(source='sub_topic.name', allow_null=True)

    class Meta:
        model = Material
        fields = ['id', 'course_subject', 'name', 'material_type', 'access_type', 'file_name',
                  'material_url', 'uploaded_at', 'created_by', 'topic', 'sub_topic']

    def get_material_url(self, obj):
        if obj.url is None:
            aws_storage_client = AwsStorageClient()
            return aws_storage_client.get_url(source='study_material', filename=obj.uploaded_file_name)
        else:
            return obj.url

    def get_created_by(self, obj):
        return obj.created_by.name


class SubTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTopic
        fields = ['id', 'name']


class TopicSerializer(serializers.ModelSerializer):
    subtopics = SubTopicSerializer(many=True, read_only=True)

    class Meta:
        model = Topic
        fields = ['id', 'name', 'subtopics']


class CourseEnrollmentUpdateSerializer(serializers.ModelSerializer):
    course_id = serializers.IntegerField()

    class Meta:
        model = CourseEnrollment
        fields = ['course_id', 'subscription_start_date', 'subscription_end_date', 'subscription_type']

    def update(self, instance, validated_data):
        # course_data = validated_data.pop('course', {})
        course_id = validated_data.get('course_id')

        if course_id is not None:
            instance.course = Course.objects.get(id=course_id)

        instance.subscription_start_date = validated_data.get('subscription_start_date',
                                                              instance.subscription_start_date)
        instance.subscription_end_date = validated_data.get('subscription_end_date', instance.subscription_end_date)
        instance.subscription_type = validated_data.get('subscription_type', instance.subscription_type)

        instance.save()
        return instance
