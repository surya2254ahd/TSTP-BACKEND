import logging
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from sTest.aws_client import AwsStorageClient
from sTest.permissions import IsAdminOrContentDeveloperOrFaculty, IsAdminOrContentDeveloper, IsAdmin, \
    IsAdminOrContentDeveloperOrFacultyOrStudent
from sTest.utils import get_error_response_for_serializer, get_error_response, CustomPageNumberPagination
from user_manager.serializers import StudentSerializer
from .filters import QuestionFilter, MaterialFilter
from .models import Question, Course, Subject, CourseSubjects, Material, CourseEnrollment, Topic
from .serializers import CreateQuestionSerializer, CourseWithSubjectsSerializer, QuestionListSerializer, \
    CourseSerializer, CreateCourseSerializer, MaterialSerializer, SubjectSerializer, \
    MaterialListSerializer, MaterialDetailsSerializer, TopicSerializer


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.get_all()
    serializer_class = CourseSerializer
    logger = logging.getLogger('Courses')

    @permission_classes([IsAdmin])
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = CreateCourseSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            # Create or get the Course
            course, _ = Course.objects.get_or_create(name=data['name'])

            for subject_data in data['subjects']:
                # Create or get the Subject
                subject, _ = Subject.objects.get_or_create(name=subject_data['name'])

                # Append an ID to each section
                for index, section in enumerate(subject_data['sections']):
                    section['id'] = index + 1  # ID based on index

                # Prepare metadata for CourseSubjects
                metadata = {'sections': subject_data['sections']}

                # Create CourseSubjects entry
                CourseSubjects.objects.create(
                    course=course,
                    subject=subject,
                    metadata=metadata,
                    correct_answer_marks=subject_data['correct_answer_marks'],
                    incorrect_answer_marks=subject_data['incorrect_answer_marks'],
                    order=subject_data['order']
                )

            return Response({"detail": "Course and subjects created successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @permission_classes([IsAdminOrContentDeveloperOrFaculty])
    def list(self, request, *args, **kwargs):
        courses = Course.get_all()
        serializer = CourseWithSubjectsSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @permission_classes([IsAdmin])
    def retrieve(self, request, pk=None, *args, **kwargs):
        course = Course.get_course_by_id(course_id=pk)
        serializer = CourseWithSubjectsSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @permission_classes([IsAdmin])
    @transaction.atomic
    def update(self, request, pk=None, *args, **kwargs):
        course = Course.get_course_by_id(course_id=pk)
        serializer = CreateCourseSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

        data = serializer.validated_data

        # Update the course name if it has changed
        if course.name != data['name']:
            course.name = data['name']
            course.updated_at = timezone.now()
            course.save()

        existing_subjects = CourseSubjects.objects.filter(course=course)
        for subject_data in data['subjects']:
            self.logger.info(f'Processing subject {subject_data} for course {course.id}')
            subject, _ = Subject.objects.get_or_create(name=subject_data['name'])

            # Append an ID to each section
            for index, section in enumerate(subject_data['sections']):
                section['id'] = index + 1

            # Update metadata for CourseSubjects
            metadata = {'sections': subject_data['sections']}

            course_subject = None
            if 'course_subject_id' in subject_data:
                course_subject = CourseSubjects.objects.get(id=subject_data['course_subject_id'])
            else:
                course_subject = CourseSubjects.objects.filter(course=course.id, subject=subject.id).first()

            # Check if we are updating an existing subject in this course
            if course_subject is not None:
                course_subject.course = course
                course_subject.subject = subject
                course_subject.metadata = metadata
                course_subject.correct_answer_marks = subject_data['correct_answer_marks']
                course_subject.incorrect_answer_marks = subject_data['incorrect_answer_marks']
                course_subject.order = subject_data['order']
                course_subject.save()
            else:
                CourseSubjects.objects.create(
                    course=course,
                    subject=subject,
                    metadata=metadata,
                    correct_answer_marks=subject_data['correct_answer_marks'],
                    incorrect_answer_marks=subject_data['incorrect_answer_marks'],
                    order=subject_data['order']
                )
            existing_subjects = existing_subjects.exclude(Q(subject=subject))

        # Delete any remaining old subjects
        existing_subjects.delete()
        return Response({"detail": "Course and subjects updated successfully"}, status=status.HTTP_200_OK)

    @permission_classes([IsAdmin])
    def destroy(self, request, pk=None, *args, **kwargs):
        instance = Course.get_course_by_id(course_id=pk)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        # instance.is_active = False
        # instance.updated_at = timezone.now()
        # instance.save()
        instance.delete()

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin], url_path='deactivate')
    def deactivate_course(self, request, pk=None):
        course = Course.get_course_by_id(course_id=pk)
        # course.is_active = False
        # course.updated_at = timezone.now()
        # course.save()
        course.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['GET'], permission_classes=[AllowAny], url_path='list')
    def list_courses(self, request):
        courses = Course.get_all()
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'], permission_classes=[IsAdminOrContentDeveloperOrFaculty],
            url_path='(?P<course_subject_id>\d+)/questions')
    def list_questions_by_subject(self, request, course_subject_id=None):
        if not course_subject_id:
            self.logger.exception('Error processing the request because no course subject id was provided')
            return get_error_response('Subject is mandatory')

        questions = Question.get_questions_for_subject(course_subject_id=course_subject_id)
        topics = Topic.objects.filter(course_subject_id=course_subject_id)

        # Apply dynamic filtering
        filter_backends = [DjangoFilterBackend]
        filterset = QuestionFilter(request.GET, queryset=questions)
        if not filterset.is_valid():
            return get_error_response('Invalid filter parameters')

        filtered_questions = filterset.qs

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_questions = paginator.paginate_queryset(filtered_questions, request)

        questions_serializer = QuestionListSerializer(paginated_questions, many=True)
        topics_serializer = TopicSerializer(topics, many=True)

        # Return the paginated response with topics
        return paginator.get_paginated_response({
            'questions': questions_serializer.data,
            'topics': topics_serializer.data
        })

    @action(detail=False, methods=['GET'], permission_classes=[IsAdminOrContentDeveloperOrFacultyOrStudent],
            url_path='(?P<course_subject_id>\d+)/topics')
    def list_topics_by_subject(self, request, course_subject_id=None):
        if not course_subject_id:
            self.logger.exception('Error processing the request because no course subject id was provided')
            return get_error_response('Subject is mandatory')

        topics = Topic.objects.filter(course_subject_id=course_subject_id)

        topics_serializer = TopicSerializer(topics, many=True)

        return Response(data=topics_serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'], url_path='students')
    def list_students_for_course(self, request, pk=None, *args, **kwargs):
        course = Course.get_course_by_id(course_id=pk)
        students = course.get_enrolled_students()

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_students = paginator.paginate_queryset(students, request)

        # Serialize page of students
        serializer = StudentSerializer(paginated_students, many=True)

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.get_all()
    serializer_class = SubjectSerializer
    permission_classes = [IsAdmin]

    def create(self, request, *args, **kwargs):
        return super(SubjectViewSet, self).create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return super(SubjectViewSet, self).update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        # instance.is_active = False
        # instance.updated_at = timezone.now()
        # instance.save()
        instance.delete()

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin], url_path='deactivate')
    def deactivate_subject(self, request, pk=None):
        try:
            subject = self.get_object()
            # subject.is_active = False
            # subject.updated_at = timezone.now()
            # subject.save()
            subject.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Subject.DoesNotExist:
            return Response({'detail': 'Subject not found.'}, status=status.HTTP_404_NOT_FOUND)


class QuestionViewSet(viewsets.ModelViewSet):
    queryset = Question.get_all()
    serializer_class = CreateQuestionSerializer
    logger = logging.getLogger('Questions')

    @permission_classes([IsAdminOrContentDeveloper])
    def create(self, request, *args, **kwargs):
        data = request.data
        data['created_by'] = request.user.id
        data['updated_by'] = request.user.id
        data['is_active'] = request.user.role.name == 'admin'

        # Extract question_type from the request data
        question_type = data.get('question_type')

        # Pass question_type in the context
        context = {'request': request, 'question_type': question_type}
        serializer = CreateQuestionSerializer(data=data, context=context)

        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @permission_classes([IsAdminOrContentDeveloper])
    @action(detail=False, methods=['post'], url_path='create-multiple')
    def create_multiple_questions(self, request, *args, **kwargs):
        data = request.data
        common_description = data.get('description')
        common_options = data.get('options')
        common_reading_comprehension_passage = data.get('reading_comprehension_passage', None)
        common_question_type = data.get('question_type')
        questions_data = data.get('questions_data', [])  # List of dictionaries for each course_subject

        # Context to pass the question_type to the serializer
        context = {'request': request, 'question_type': common_question_type}

        created_questions = []

        try:
            for question_data in questions_data:
                course_subject_id = question_data.get('course_subject')
                individual_data = {
                    'course_subject': course_subject_id,
                    'description': common_description,
                    'options': common_options,
                    'reading_comprehension_passage': common_reading_comprehension_passage,
                    'question_type': common_question_type,
                    'difficulty': question_data.get('difficulty'),
                    'test_type': question_data.get('test_type'),
                    'topic': question_data.get('topic'),
                    'sub_topic': question_data.get('sub_topic', None),
                    'created_by': request.user.id,
                    'updated_by': request.user.id,
                    'is_active': question_data.get('is_active', True if request.user.role.name == 'admin' else False),
                    'show_calculator': question_data.get('show_calculator', False),
                }

                serializer = CreateQuestionSerializer(data=individual_data, context=context)
                serializer.is_valid(raise_exception=True)
                created_question = serializer.save()
                created_questions.append(created_question)

            return Response(CreateQuestionSerializer(created_questions, many=True, context=context).data,
                            status=status.HTTP_201_CREATED)
        except Exception as e:
            self.logger.error(f'Error in create_multiple_questions: {e}')
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @permission_classes([IsAdmin])
    def update(self, request, pk=None, *args, **kwargs):
        instance = Question.objects.get(id=pk)

        # Extract question_type from the request data if available, otherwise use existing instance's type
        question_type = request.data.get('question_type', instance.question_type)

        # Pass question_type in the context
        context = {'request': request, 'question_type': question_type}
        serializer = self.get_serializer(instance, data=request.data, partial=True, context=context)

        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user, updated_at=timezone.now())

    @permission_classes([IsAdminOrContentDeveloperOrFaculty])
    def retrieve(self, request, pk=None, *args, **kwargs):
        instance = Question.get_question_by_id(question_id=pk)
        serializer = QuestionListSerializer(instance=instance)
        topics = Topic.objects.filter(course_subject_id=instance.course_subject)
        topics_serializer = TopicSerializer(topics, many=True)
        return Response({'detail': serializer.data, 'topics': topics_serializer.data}, status=status.HTTP_200_OK)

    @permission_classes([IsAdminOrContentDeveloper])
    def destroy(self, request, pk=None, *args, **kwargs):
        instance = Question.get_question_by_id(question_id=pk)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        # instance.is_active = False
        # instance.updated_at = timezone.now()
        # instance.save()
        instance.delete()

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrContentDeveloper], url_path='deactivate')
    def deactivate_question(self, request, pk=None):
        question = Question.get_question_by_id(question_id=pk)
        # question.is_active = False
        # question.updated_at = timezone.now()
        # question.save()
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin], url_path='activate')
    def activate_question(self, request, pk=None):
        question = Question.get_question_by_id(question_id=pk)
        question.is_active = True
        question.updated_at = timezone.now()
        question.save()
        return Response(status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminOrContentDeveloperOrFacultyOrStudent],
            url_path='details')
    def get_questions_details(self, request):
        question_ids = request.data.get('question_ids', [])

        # Convert all question_ids to integers, handle invalid inputs
        try:
            question_ids = [int(id) for id in question_ids]
        except ValueError:
            return Response({"error": "Invalid question ID in the list, must be all integers."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not question_ids:
            return Response({"error": "No question IDs provided."}, status=status.HTTP_400_BAD_REQUEST)

        questions = Question.get_questions_for_ids(question_ids)

        # Create a dictionary to reorder questions as per the IDs provided
        question_dict = {question.id: question for question in questions}
        ordered_questions = [question_dict[question_id] for question_id in question_ids if
                             question_id in question_dict]

        serializer = QuestionListSerializer(ordered_questions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    logger = logging.getLogger('Material')
    aws_storage_client = AwsStorageClient(logger=logger)
    source = 'study_material'

    @permission_classes([IsAdminOrContentDeveloper])
    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['created_by'] = request.user.id
        data['updated_by'] = request.user.id

        if data.get('url', None) is None:
            file_uploaded = request.FILES['file']
            fs = FileSystemStorage()  # defaults to MEDIA_ROOT
            temp_file_name = file_uploaded.name.split('.')
            file_name = temp_file_name[0] + '_' + str(uuid.uuid4().hex)[:6] + '.' + temp_file_name[1]
            saved_file_name = fs.save(file_name, file_uploaded)
            full_path_to_file = settings.MEDIA_ROOT + '/' + saved_file_name

            data['file_name'] = file_uploaded.name
            data['uploaded_file_name'] = saved_file_name
            self.aws_storage_client.upload_file_from_fs(source=self.source, filename=saved_file_name,
                                                        full_path_to_file=full_path_to_file,
                                                        content_type=file_uploaded.content_type)
            fs.delete(saved_file_name)

        serializer = MaterialSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
        except Exception as e:
            if isinstance(e, ValidationError):
                return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=data)
            else:
                self.logger.exception(f'Exception {e}')
                return get_error_response(message='An unexpected error occurred.')

        return Response({'detail': 'File uploaded successfully'}, status=status.HTTP_200_OK)

    @permission_classes([IsAdminOrContentDeveloperOrFacultyOrStudent])
    def list(self, request, *args, **kwargs):
        user = request.user
        course_subject_filter = self.request.query_params.get('course_subject_id', None)

        if user.role.name == 'student':
            course_subject = CourseSubjects.get_course_subject_by_id(course_subject_filter)
            course_enrollment = CourseEnrollment.get_student_enrollment_using_student_course(student_id=user.id,
                                                                                             course_id=course_subject.course_id)
            if course_enrollment.subscription_type == CourseEnrollment.FREE:
                qs = self.queryset.filter(access_type=Material.FREE_ACCESS_TYPE)
            else:
                qs = self.queryset.all()
        else:
            qs = self.queryset.all()

        if course_subject_filter is not None:
            qs = qs.filter(course_subject_id=course_subject_filter)

        # Apply dynamic filtering
        filter_backends = [DjangoFilterBackend]
        filterset = MaterialFilter(request.GET, queryset=qs, request=request)
        if not filterset.is_valid():
            return get_error_response('Invalid filter parameters')

        materials = filterset.qs

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_materials = paginator.paginate_queryset(materials, request)

        serializer = MaterialListSerializer(paginated_materials, many=True)

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)

    @permission_classes([IsAdminOrContentDeveloperOrFacultyOrStudent])
    def retrieve(self, request, pk=None, *args, **kwargs):
        material = Material.get_material_by_id(material_id=pk)
        serializer = MaterialDetailsSerializer(material)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @permission_classes([IsAdminOrContentDeveloper])
    def destroy(self, request, pk=None, *args, **kwargs):
        instance = Material.get_material_by_id(material_id=pk)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        self.aws_storage_client.delete_file(source=self.source, filename=instance.uploaded_file_name)
        instance.delete()

    @action(detail=True, methods=['patch'], permission_classes=[IsAdminOrContentDeveloper], url_path='deactivate')
    def deactivate_material(self, request, pk=None):
        material = Material.get_material_by_id(material_id=pk)
        self.perform_destroy(material)
        return Response(status=status.HTTP_204_NO_CONTENT)
