import logging
import random
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_manager.filters import PracticeQuestionFilter
from course_manager.models import Question, CourseSubjects, CombinedScore
from notification_manager.models import NotificationTemplate, Notification
from notification_manager.utils import send_notification, mark_notification_as_read
from sTest.permissions import IsAdmin, IsAdminOrMentorOrFacultyOrStudentOrParent, \
    IsAdminOrMentorOrFaculty, IsStudent
from sTest.utils import get_error_response_for_serializer, get_error_response, CustomPageNumberPagination
from test_manager.filters import TestFilter
from test_manager.models import Test, Section, TestSubmission, Result, PracticeTest, PracticeTestResult, \
    AnsweredQuestions
from test_manager.serializers import TestSerializer, TestListSerializer, ExistingStudentListSerializer, \
    TestSubmissionSerializer, PracticeTestListSerializer, EligibleStudentSerializer, SectionSerializer
from test_manager.utils import calculate_total_questions_required
from user_manager.models import User, Role, StudentMetadata


class TestViewSet(viewsets.ModelViewSet):
    queryset = Test.get_all()
    serializer_class = TestSerializer
    logger = logging.getLogger('Tests')

    @permission_classes([IsAdmin])
    def create(self, request, *args, **kwargs):
        data = request.data
        data['created_by'] = request.user.id
        data['updated_by'] = request.user.id
        data['test_type'] = Test.EXAM
        serializer = TestSerializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
            test_data = serializer.validated_data
            if test_data['format_type'] == Test.DYNAMIC:
                course_subjects = CourseSubjects.get_subjects_for_course(test_data['course'])
                for course_subject in course_subjects:
                    total_questions_required = calculate_total_questions_required(course_subject)
                    available_questions_count = Question.objects.filter(course_subject=course_subject).count()

                    if available_questions_count < total_questions_required:
                        return get_error_response(
                            f'Insufficient questions for dynamic test format. Required: {total_questions_required}, Available: {available_questions_count} for subject- {course_subject.subject.name}')

            # Create test if enough questions are available
            test = serializer.save()
            return Response(TestSerializer(test).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @permission_classes([IsAdminOrMentorOrFacultyOrStudentOrParent])
    def list(self, request):
        user = request.user
        serializer_class = TestListSerializer
        queryset = None

        if user.role.name in ['admin', 'faculty', 'mentor']:
            # Fetch Tests for admin, faculty, and mentor.
            queryset = Test.get_all()
            serializer_class = TestListSerializer
        elif user.role.name in ['student', 'parent']:
            # Fetch TestSubmissions for students and parents.
            if user.role.name == 'student':
                queryset = TestSubmission.objects.filter(student=user)
            elif user.role.name == 'parent':
                sm = StudentMetadata.objects.filter(Q(father=user) | Q(mother=user))
                queryset = TestSubmission.objects.filter(student__in=sm.values_list('student', flat=True))
            serializer_class = TestSubmissionSerializer

        # Apply dynamic filtering
        filter_backends = [DjangoFilterBackend]
        filterset = TestFilter(request.GET, queryset=queryset)
        if not filterset.is_valid():
            return get_error_response('Invalid filter parameters')

        filtered_tests = filterset.qs

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_objects = paginator.paginate_queryset(filtered_tests, request)

        serializer = serializer_class(paginated_objects, many=True, context={'user': user})

        return paginator.get_paginated_response(serializer.data)

    @permission_classes([IsAdminOrMentorOrFacultyOrStudentOrParent])
    def retrieve(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        serializer = TestSerializer(test)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @permission_classes([IsAdmin])
    def destroy(self, request, pk=None, *args, **kwargs):
        instance = Test.get_test_by_id(test_id=pk)
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        # instance.is_active = False
        # instance.updated_at = timezone.now()
        # instance.save()
        instance.delete()

    @action(detail=True, methods=['patch'], permission_classes=[IsAdmin], url_path='deactivate')
    def deactivate_test(self, request, pk=None):
        test = Test.get_test_by_id(test_id=pk)
        # test.is_active = False
        # test.updated_at = timezone.now()
        # test.save()
        test.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['POST'], permission_classes=[IsAdmin], url_path='add-questions')
    def add_questions_to_test_section(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        course_subject = request.data.get('course_subject_id')
        section_id = request.data.get('section_id')
        question_ids = request.data.get('question_ids', [])

        # Validate that the provided question IDs exist
        if not Question.get_questions_for_ids_for_test(ids=question_ids,
                                                       test_type=Question.FULL_LENGTH_TEST_TYPE).count() == len(
            question_ids):
            return get_error_response(message='One or more questions do not exist.')

        section = Section.fetch_section_using_test_course_subject(test=test, course_subject=course_subject)
        if not section:
            return get_error_response(message='Invalid course or subject provided')

        for sub_section in section.sub_sections:
            if sub_section["id"] == section_id:
                # Check that the number of questions matches "no_of_questions" field
                if len(question_ids) != sub_section["no_of_questions"]:
                    return get_error_response(
                        message=f"Expected exactly {sub_section['no_of_questions']} questions, but {len(question_ids)} were provided.")

                sub_section["questions"] = question_ids
                # sub_section["questions"].extend(question_ids)  # Add the question IDs
                # sub_section["questions"] = list(set(sub_section["questions"]))  # Ensure no duplicates
                section.save()
                break

        return Response({"detail": "Questions added successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'], permission_classes=[IsAdminOrMentorOrFaculty], url_path='assigned-students')
    def get_assigned_students(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        user = request.user
        if user.role.name == 'admin':
            test_submissions = TestSubmission.get_students_assigned_to_test(test=test)
        elif user.role.name == 'faculty':
            sm = StudentMetadata.objects.filter(faculty=user)
            test_submissions = TestSubmission.get_students_assigned_to_test_for_faculty(test=test,
                                                                                        student_ids=sm.values_list(
                                                                                            'student',
                                                                                            flat=True))
        elif user.role.name == 'mentor':
            sm = StudentMetadata.objects.filter(mentor=user)
            test_submissions = TestSubmission.get_students_assigned_to_test_for_faculty(test=test,
                                                                                        student_ids=sm.values_list(
                                                                                            'student',
                                                                                            flat=True))
        else:
            test_submissions = []

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_tests = paginator.paginate_queryset(test_submissions, request)

        serializer = ExistingStudentListSerializer(paginated_tests, many=True)

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['GET'], permission_classes=[IsAdmin], url_path='eligible-students')
    def get_eligible_students(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        course = test.course
        test_students = TestSubmission.get_students_assigned_to_test_with_status(test=test)

        # Start with all students excluding those already assigned to the test
        query = Q(course_enrollments__course=course, is_active=True)
        query = query & ~Q(id__in=test_students.values_list('student', flat=True))

        # Apply filters if present in query parameters
        name = request.query_params.get('name')
        email = request.query_params.get('email')

        if name:
            query = query & Q(name__icontains=name)
        if email:
            query = query & Q(email__icontains=email)

        students = User.objects.filter(query)

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_students = paginator.paginate_queryset(students, request)

        # Pass request context to the serializer to access the request data
        serializer = EligibleStudentSerializer(paginated_students, many=True, context={'request': request})

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['POST'], permission_classes=[IsAdmin], url_path='students')
    @transaction.atomic
    def add_students_to_test(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        student_ids = request.data.get('student_ids', [])

        # Validate that the provided student IDs exist and are actually students
        if not (User.filter_users_using_id_and_role(
                user_ids=student_ids,
                role=Role.get_role_using_name('student').id
        ).count() == len(student_ids)):
            return get_error_response(message='One or more student IDs are invalid.')

        # Add students to the test
        test.students.add(*student_ids)

        # Create TestSubmission entry for each student
        assigned_date = timezone.now()
        expiration_date = assigned_date + timedelta(hours=48)

        submissions = []
        for student_id in student_ids:
            test_submission = TestSubmission.objects.create(
                test=test,
                student_id=student_id,
                assigned_date=assigned_date,
                expiration_date=expiration_date
            )
            submissions.append(test_submission)

            # Send notification
            student = User.get_user_by_id(student_id)
            notification_params = {NotificationTemplate.USER_NAME: student.name,
                                   NotificationTemplate.TEST_NAME: test.name,
                                   NotificationTemplate.REFERENCE_ID: test_submission.id}

            send_notification.delay(notification_name=Notification.TEST_ASSIGNED_NOTIFICATION,
                                    params=notification_params,
                                    user_id=student.id)

        # TestSubmission.objects.bulk_create(submissions)

        return Response(data={"detail": "Students added successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'], url_path='take-test')
    def take_test(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        test_submission_id = request.data.get('test_submission_id')

        existing_submission = TestSubmission.objects.get(id=test_submission_id)

        # Check if the expiration date has already passed
        if existing_submission.status == TestSubmission.EXPIRED:
            return get_error_response(message='Test has expired. Please contact the Admin to reassign the Test.')

        # Check if the user has already submitted this test
        # if existing_submission.status == TestSubmission.COMPLETED:
        #     return get_error_response(message='You have already completed this test.')

        # Extract and validate data
        course_subject = request.data.get('course_subject')
        section_id = request.data.get('section_id')
        question_id, answer_data = list(request.data.get('answer', {}).items())[0]
        is_skipped = request.data.get('is_skipped', False)
        time_taken = request.data.get('time_taken', 0)
        is_marked_for_review = request.data.get('is_marked_for_review', False)

        result, _ = Result.objects.get_or_create(test_submission=existing_submission,
                                                 defaults={"correct_answer_count": 0,
                                                           "incorrect_answer_count": 0,
                                                           "time_taken": 0,
                                                           "detailed_view": {}})

        try:
            question = Question.get_question_by_id(question_id=question_id)
            is_correct = None
            if is_skipped:
                is_correct = False  # Mark skipped questions as incorrect
            elif question.question_type == Question.FILL_IN_BLANKS:
                correct_answers_lower = [ans.lower() for ans in question.options]
                user_answers_lower = [ans.lower() for ans in answer_data]
                is_correct = correct_answers_lower == user_answers_lower
            else:
                correct_options = [index for index, option in enumerate(question.options) if option['is_correct']]
                if not is_skipped:
                    is_correct = set(answer_data) == set(correct_options)

            # Update Result
            result.update_detailed_view(test=test, course_subject=course_subject, section_id=section_id,
                                        question_id=question_id, answer_data=answer_data,
                                        time_taken=time_taken, correct_answer=is_correct, is_skipped=is_skipped,
                                        is_marked_for_review=is_marked_for_review)

        except Question.DoesNotExist:
            return get_error_response(message=f'Question with ID {question_id} does not exist.')

        response = {
            'correct_answer_count': result.correct_answer_count,
            'incorrect_answer_count': result.incorrect_answer_count,
            'time_taken': result.time_taken
        }

        return Response(data=response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'], url_path='skip-section')
    def skip_section(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        test_submission_id = request.data.get('test_submission_id')
        section_id = request.data.get('section_id')
        course_subject_id = request.data.get('course_subject_id')

        test_submission = TestSubmission.objects.get(id=test_submission_id)
        # Fetch the TestSubmission object for the given test_id and student (request.user)
        # test_submission = TestSubmission.objects.filter(test=test, student=request.user).first()

        if not test_submission:
            return get_error_response(message='Test submission not found.')

        if test.format_type == Test.DYNAMIC:
            section_key = f'{course_subject_id}_{section_id}'
            question_ids = test_submission.selected_question_ids.get(section_key, [])
        else:  # For LINEAR test type
            # Find the section using section name and course subject
            section = Section.fetch_section_using_test_course_subject(test=test_submission.test,
                                                                      course_subject=course_subject_id)
            if not section:
                return get_error_response(message='Section not found.')

            # Fetch all questions from the section
            sub_section = next((sec for sec in section.sub_sections if str(sec.get("id")) == str(section_id)), None)

            if sub_section is None:
                return get_error_response(message='Sub-section not found.')
            question_ids = sub_section["questions"]

        # Fetch the Result for the given TestSubmission
        result = Result.objects.filter(test_submission=test_submission).first()

        if not result:
            result, _ = Result.objects.get_or_create(test_submission=test_submission,
                                                     defaults={"correct_answer_count": 0,
                                                               "incorrect_answer_count": 0,
                                                               "time_taken": 0,
                                                               "detailed_view": {}})

            # Update Result
            try:
                result.update_detailed_view(test=test, course_subject=course_subject_id, section_id=section_id,
                                            question_id=sub_section["questions"][0], answer_data=[],
                                            time_taken=0, correct_answer=False, is_skipped=True,
                                            is_marked_for_review=False)
                test_submission.status = TestSubmission.IN_PROGRESS
                test_submission.save()
            except KeyError as e:
                return get_error_response(message=str(e))

        questions = Question.objects.filter(id__in=question_ids).all()

        incorrect_answer_count = result.incorrect_answer_count
        # Iterate over questions, if it's not answered yet, mark it as skipped
        for question in questions:
            if not result.detailed_view["answers"][str(course_subject_id)][str(section_id)]["questions_answered"].get(
                    str(question.id)):
                result.detailed_view["answers"][str(course_subject_id)][str(section_id)]["questions_answered"][
                    str(question.id)] = {
                    "is_skipped": True,
                    "is_correct": False,
                    "answer_data": []
                }
                incorrect_answer_count += 1

        result.incorrect_answer_count = incorrect_answer_count
        result.save()

        all_answered = all(
            len(sec["questions_answered"]) == sec["total_questions"]
            for subj in result.detailed_view["answers"].values()
            for sec in subj.values()
        )
        if all_answered:
            test_submission.status = TestSubmission.COMPLETED
            test_submission.completion_date = timezone.now()
            test_submission.save()
            mark_notification_as_read.delay(user_id=test_submission.student.id, category=Notification.TEST,
                                            reference_id=test_submission.id)

        return Response({"detail": "Section marked as completed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'], url_path='test-progress')
    def get_test_progress(self, request, pk=None, *args, **kwargs):
        test = Test.get_test_by_id(test_id=pk)
        test_submission_id = request.query_params.get('test_submission_id')

        test_submission = TestSubmission.objects.get(id=test_submission_id)
        if not test_submission:
            return get_error_response(message='Test submission not found.')

        # if test_submission.status != TestSubmission.IN_PROGRESS:
        #     return get_error_response(message='Test progress can only be fetched for in-progress tests.')

        sections = Section.objects.filter(test=test)
        serialized_sections = SectionSerializer(sections, many=True).data

        result = Result.objects.filter(test_submission=test_submission).first()
        if not result:
            return Response({
                "test_id": test.id,
                "test_name": test.name,
                "course_name": test.course.name,
                "course_subject_id": 0,
                "subject": serialized_sections,
                "course_subject_index": 0,
                "section_id": 0,
                "section_index": 0,
                "remaining_time": -1,
                "question_id": 0,
                "question_index": 0,
                "answer_map": {}
            }, status=status.HTTP_200_OK)

        for course_subject_idx, section in enumerate(sections):  # subject
            for section_idx, sub_section in enumerate(section.sub_sections):  # section
                if test.format_type == Test.DYNAMIC:
                    section_key = f'{section.course_subject_id}_{sub_section["id"]}'
                    question_ids = test_submission.selected_question_ids.get(section_key, [])
                else:  # For LINEAR test type
                    question_ids = sub_section['questions']

                if not question_ids:
                    return Response({
                        "test_id": test.id,
                        "test_name": test.name,
                        "course_name": test.course.name,
                        "course_subject_id": section.course_subject_id,
                        "subject": serialized_sections,
                        "course_subject_index": course_subject_idx,
                        "section_id": sub_section['id'],
                        "section_index": section_idx,
                        "remaining_time": (sub_section['duration'] * 60),
                        "question_id": 0,
                        "question_index": 0,
                        "answer_map": {}
                    }, status=status.HTTP_200_OK)

                answer_map = {}
                # construct answer map for all the questions answered
                for question_idx, question_id in enumerate(question_ids):
                    questions_answered = result.detailed_view["answers"].get(str(section.course_subject_id)).get(
                        str(sub_section['id'])).get('questions_answered')
                    if questions_answered.get(str(question_id)):
                        question_details = questions_answered.get(str(question_id))
                        is_skipped = question_details.get("is_skipped", False)
                        is_marked_for_review = question_details.get("is_marked_for_review", False)
                        answer_map[str(question_id)] = {
                            "selected_options": {str(key): 1 for key in
                                                 question_details.get("answer_data", [])} if not is_skipped else {},
                            "is_marked_for_review": is_marked_for_review,
                            "is_answered": not is_skipped,
                            "striked_options": {}
                        }

                # construct the response to get the current course, section and question index
                for question_idx, question_id in enumerate(question_ids):
                    # Check if the question is unanswered in the detailed view
                    questions_answered = result.detailed_view["answers"].get(str(section.course_subject_id)).get(
                        str(sub_section['id'])).get('questions_answered')
                    if not questions_answered.get(str(question_id)):
                        time_taken = \
                            result.detailed_view["answers"][str(section.course_subject_id)][str(sub_section['id'])][
                                'time_taken']
                        return Response({
                            "test_id": test.id,
                            "test_name": test.name,
                            "course_name": test.course.name,
                            "course_subject_id": section.course_subject_id,
                            "subject": serialized_sections,
                            "course_subject_index": course_subject_idx,
                            "section_id": sub_section['id'],
                            "section_index": section_idx,
                            "remaining_time": (sub_section['duration'] * 60) - time_taken,
                            "question_id": question_id,
                            "question_index": question_idx,
                            "answer_map": answer_map
                        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'], permission_classes=[IsStudent],
            url_path='section-questions')
    def get_section_questions(self, request, pk=None):
        test_id = pk
        course_subject_id = request.query_params.get('course_subject_id')
        section_id = request.query_params.get('section_id')
        test_submission_id = request.query_params.get('test_submission_id')

        if not course_subject_id or not section_id or not test_submission_id:
            return Response({"error": "course_subject_id and section_id are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            test = Test.get_test_by_id(test_id=test_id)
            test_submission = TestSubmission.objects.get(id=test_submission_id)
            section = Section.fetch_section_using_test_course_subject(test=test_id, course_subject=course_subject_id)
            sub_section = next((ss for ss in section.sub_sections if str(ss['id']) == section_id), None)

            if not sub_section:
                return Response({"error": "Sub-section not found."}, status=status.HTTP_404_NOT_FOUND)

            question_ids = None
            if test.format_type == Test.LINEAR:
                question_ids = sub_section.get('questions', [])
            elif test.format_type == Test.DYNAMIC:
                # Retrieve already selected questions for this test submission, if any
                section_key = f'{course_subject_id}_{section_id}'
                existing_selected_questions = test_submission.selected_question_ids.get(section_key)

                # Logic for selecting questions if not already selected
                if not existing_selected_questions:
                    # Fetch or create an entry in AnsweredQuestions for this student and course_subject
                    answered_questions, _ = AnsweredQuestions.objects.get_or_create(
                        student=test_submission.student,
                        course_subject_id=course_subject_id
                    )

                    question_ids = self.select_questions_for_section(course_subject_id, section, section_id,
                                                                     sub_section, test, test_submission,
                                                                     excluded_question_ids=answered_questions.questions)

                    # Update test_submission with selected question IDs
                    test_submission.selected_question_ids[f'{course_subject_id}_{section_id}'] = question_ids
                    test_submission.save()

                    # Update answered_questions with the new questions
                    answered_questions.questions.extend(question_ids)
                    answered_questions.save()
                else:
                    # Return already selected questions
                    question_ids = existing_selected_questions

            return Response(question_ids, status=status.HTTP_200_OK)
        except Section.DoesNotExist:
            return Response({"error": "Section not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # self.logger.error(f'Error in get_section_questions: {e}')
            return Response({"error": "An error occurred while processing your request."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def select_questions_for_section(self, course_subject_id, section, section_id, sub_section, test, test_submission,
                                     excluded_question_ids):
        question_ids = []
        if test.format_type == Test.LINEAR:
            question_ids = sub_section.get('questions', [])
        elif test.format_type == Test.DYNAMIC:
            # if section_id == "1":  # First section
            if section.order == 1 and section_id == "1":  # First section
                question_ids = self.get_first_section_questions(course_subject_id,
                                                                sub_section['no_of_questions'],
                                                                excluded_question_ids)
            else:
                result = Result.objects.get(test_submission=test_submission) if test_submission else None
                if result:
                    question_ids = self.get_dynamic_section_questions(course_subject_id, result,
                                                                      sub_section['no_of_questions'],
                                                                      excluded_question_ids)
                    result.detailed_view["answers"][str(course_subject_id)][str(section_id)]["total_questions"] = len(
                        question_ids)
                    result.save()
        return question_ids

    def get_first_section_questions(self, course_subject_id, num_questions, excluded_question_ids):
        questions = Question.objects.filter(course_subject_id=course_subject_id).exclude(id__in=excluded_question_ids)
        difficulty_levels = ['MODERATE', 'VERY_EASY', 'HARD', 'EASY', 'VERY_HARD']
        questions_per_difficulty = num_questions // len(difficulty_levels)

        question_ids = []
        for difficulty in difficulty_levels:
            questions_of_difficulty = [q.id for q in questions if q.difficulty == difficulty]
            selected_questions = random.sample(questions_of_difficulty,
                                               min(questions_per_difficulty, len(questions_of_difficulty)))
            question_ids.extend(selected_questions)

        # Distribute any remaining questions
        remaining_questions = num_questions - len(question_ids)
        while remaining_questions > 0:
            added_questions = False
            for difficulty in difficulty_levels:
                questions_of_difficulty = [q.id for q in questions if
                                           q.difficulty == difficulty and q.id not in question_ids]
                if questions_of_difficulty:
                    selected_question = random.choice(questions_of_difficulty)
                    question_ids.append(selected_question)
                    remaining_questions -= 1
                    added_questions = True
                    if remaining_questions == 0:
                        break
            if not added_questions:
                # Break out of the loop if no questions are available at all
                break

        # Ensure the number of questions does not exceed the required count
        question_ids = question_ids[:num_questions]

        return question_ids

    def get_dynamic_section_questions(self, course_subject_id, result, num_questions, excluded_question_ids):
        correct_ratio = result.correct_answer_count / max((result.correct_answer_count + result.incorrect_answer_count),
                                                          1)
        difficulty_ratios = self.get_difficulty_ratios_by_performance(correct_ratio)

        questions = Question.objects.filter(course_subject_id=course_subject_id).exclude(id__in=excluded_question_ids)
        selected_questions = []

        # Select initial questions based on difficulty ratios
        for difficulty, ratio in difficulty_ratios.items():
            num_to_select = int(num_questions * ratio)
            questions_of_difficulty = [q.id for q in questions if q.difficulty == difficulty]
            selected_questions.extend(
                random.sample(questions_of_difficulty, min(num_to_select, len(questions_of_difficulty))))

        # Redistribute remaining questions from available pool
        while len(selected_questions) < num_questions:
            additional_questions_needed = num_questions - len(selected_questions)
            available_questions = [q.id for q in questions if q.id not in selected_questions]

            if not available_questions or len(available_questions) <= additional_questions_needed:
                # Break the loop if no more unique questions are available or if the remaining pool is smaller or equal to the needed count
                selected_questions.extend(available_questions[:additional_questions_needed])
                break

            for difficulty in difficulty_ratios.keys():
                extra_questions = [q.id for q in questions if
                                   q.difficulty == difficulty and q.id not in selected_questions]
                if extra_questions:
                    selected_questions.append(random.choice(extra_questions))
                    if len(selected_questions) == num_questions:
                        break

        # Ensure the number of questions does not exceed the required count
        selected_questions = selected_questions[:num_questions]

        return selected_questions

    def get_difficulty_ratios_by_performance(self, correct_ratio):
        # GMAT-like performance-based difficulty ratios
        if correct_ratio >= 0.80:
            return {'VERY_HARD': 0.4, 'HARD': 0.3, 'MODERATE': 0.2, 'EASY': 0.1, 'VERY_EASY': 0.0}
        elif correct_ratio >= 0.60:
            return {'VERY_HARD': 0.2, 'HARD': 0.4, 'MODERATE': 0.3, 'EASY': 0.1, 'VERY_EASY': 0.0}
        elif correct_ratio >= 0.40:
            return {'VERY_HARD': 0.1, 'HARD': 0.2, 'MODERATE': 0.4, 'EASY': 0.2, 'VERY_EASY': 0.1}

        return {'VERY_HARD': 0.1, 'HARD': 0.2, 'MODERATE': 0.3, 'EASY': 0.2, 'VERY_EASY': 0.2}

    @action(detail=True, methods=['POST'], permission_classes=[IsAdmin], url_path='reassign-expired-test')
    def reassign_expired_test(self, request, pk=None):
        try:
            test_submission = TestSubmission.objects.get(id=pk, status=TestSubmission.EXPIRED)

            # Update expiration_date and status
            test_submission.expiration_date = timezone.now() + timezone.timedelta(hours=48)
            test_submission.status = TestSubmission.YET_TO_START
            test_submission.save()

            # Delete any existing result associated with this test submission
            Result.objects.filter(test_submission=test_submission).delete()

            return Response({"message": "Test reassignment successful."}, status=status.HTTP_200_OK)
        except TestSubmission.DoesNotExist:
            return get_error_response('Test submission not found or not expired.')
        except Exception as e:
            return get_error_response(str(e))


class ResultViewSet(viewsets.ModelViewSet):
    queryset = Result.objects.all()
    logger = logging.getLogger('Results')

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated], url_path='details')
    def get_details(self, request, *args, **kwargs):
        test_submission_id = request.GET.get('test_submission_id')
        test_submission = get_object_or_404(TestSubmission, id=test_submission_id)
        test = test_submission.test
        student = test_submission.student
        result = test_submission.result

        # Initialize the response dictionary
        response_data = {
            'testName': 'Test - ' + test.name,
            'testDate': test_submission.assigned_date.strftime('%Y-%m-%d'),
            'studentName': student.name,
            'total_score': 0,
            'subjects': []
        }

        total_score = 0

        # Loop over sections related to the test
        sections = Section.objects.filter(test=test).order_by('order')
        for section in sections:
            subject_data = {
                'name': section.course_subject.subject.name,
                'selectedSection': 0,
                'subject_correct_count': 0,
                'subject_incorrect_count': 0,
                'subject_blank_count': 0,
                'subject_max_score': 0,
                'subject_min_score': 0,
                'subject_score': 0,
                'sections': []
            }
            section_answer_correct_marks = section.course_subject.correct_answer_marks
            section_answer_incorrect_marks = section.course_subject.incorrect_answer_marks

            section_1_score = 0
            section_2_score = 0

            # Loop over sub-sections defined in the JSONField
            for sub_section in section.sub_sections:
                detailed_section = result.detailed_view.get('answers', {}).get(str(section.course_subject_id), {}).get(
                    str(sub_section['id']), {})

                section_number_of_questions = sub_section.get('no_of_questions', 0)
                section_max_score = (section_number_of_questions * section_answer_correct_marks)
                section_min_score = (section_number_of_questions * section_answer_incorrect_marks * -1)

                section_correct_count = 0
                section_correct_time_taken = 0
                section_incorrect_count = 0
                section_incorrect_time_taken = 0
                section_blank_count = 0
                marked = 0

                time_on_section = detailed_section.get('time_taken', 0)

                questions_data = []
                if test.format_type == Test.DYNAMIC:
                    section_key = f'{section.course_subject.id}_{sub_section.get("id")}'
                    question_ids = test_submission.selected_question_ids.get(section_key, [])
                else:  # For LINEAR test type
                    question_ids = sub_section['questions']

                for index, question_id in enumerate(question_ids):
                    question_details = detailed_section.get('questions_answered', {}).get(str(question_id), {})
                    question_instance = Question.objects.get(id=question_id)

                    question_data = {
                        'sr_no': index + 1,
                        'question_id': question_instance.id,
                        'question_type': question_instance.question_type,
                        'topic': question_instance.topic.name if question_instance.topic else "General",
                        'result': question_details.get('is_correct', False),
                        'total_time': question_details.get('time_taken', 0),
                        'first_time_taken': question_details.get('first_time_taken', 0),
                        'times_visited': question_details.get('times_visited', 0),
                        'marked': question_details.get('is_marked_for_review', False),
                        'is_skipped': question_details.get('is_skipped', False),
                        'selected_options': question_details.get('answer_data', []),
                    }

                    # Aggregations for this sub-section
                    section_correct_count += 1 if question_details.get('is_correct', False) else 0
                    section_correct_time_taken += question_details.get('time_taken', 0) if question_details.get(
                        'is_correct', False) else 0

                    section_incorrect_count += 1 if not question_details.get('is_correct',
                                                                             False) and not question_details.get(
                        'is_skipped', False) else 0
                    section_incorrect_time_taken += question_details.get('time_taken', 0) if not question_details.get(
                        'is_correct', False) and not question_details.get('is_skipped', False) else 0

                    section_blank_count += 1 if question_details.get('is_skipped', False) else 0
                    marked += 1 if question_details.get('is_marked_for_review', False) else 0

                    questions_data.append(question_data)

                section_score = (section_correct_count * section_answer_correct_marks) - (
                        section_incorrect_count * section_answer_incorrect_marks)

                # Construct sub-section data
                section_data = {
                    'name': sub_section['name'],
                    'section_id': sub_section['id'],
                    'course_subject_id': section.course_subject.id,
                    'test_id': test.id,
                    'test_type': "FULL_LENGTH_TEST",
                    'section_correct_count': section_correct_count,
                    'section_correct_time_taken': section_correct_time_taken,
                    'section_incorrect_count': section_incorrect_count,
                    'section_incorrect_time_taken': section_incorrect_time_taken,
                    'section_blank_count': section_blank_count,
                    'marked': marked,
                    'time_on_section': time_on_section,
                    'section_max_score': section_max_score,
                    'section_score': section_score,
                    'questions_data': questions_data,
                }

                if section.course_subject.course.name == 'SAT':
                    if sub_section['id'] == 1:
                        section_1_score = section_correct_count
                    else:
                        section_2_score = section_correct_count

                subject_data['sections'].append(section_data)
                subject_data['subject_correct_count'] += section_correct_count
                subject_data['subject_incorrect_count'] += section_incorrect_count
                subject_data['subject_blank_count'] += section_blank_count
                subject_data['subject_max_score'] += section_max_score
                subject_data['subject_min_score'] += section_min_score
                subject_data['subject_score'] += section_score
                total_score += 0 if section.course_subject.course.name == 'SAT' else section_score

            if section.course_subject.course.name == 'SAT':
                subject_data['subject_min_score'] = 200
                subject_data['subject_max_score'] = 800

                score_record = CombinedScore.objects.get(section1_correct=section_1_score,
                                                         section2_correct=section_2_score,
                                                         subject_name=section.course_subject.subject.name)
                subject_data['subject_score'] = score_record.total_score
                total_score += score_record.total_score

            response_data['subjects'].append(subject_data)

        response_data['total_score'] = total_score
        return JsonResponse(response_data)


class PracticeTestViewSet(viewsets.ModelViewSet):
    queryset = PracticeTest.objects.all()
    logger = logging.getLogger('Practice-Test')

    @action(detail=False, methods=['GET'], permission_classes=[IsStudent],
            url_path='(?P<course_subject_id>\d+)')
    def list_questions_by_subject_for_practice_test(self, request, course_subject_id=None):
        if not course_subject_id:
            self.logger.exception('Error processing the request because no course subject id was provided')
            return get_error_response('Subject is mandatory')

        questions = Question.get_questions_for_subject_test_type(course_subject_id=course_subject_id,
                                                                 test_type=Question.SELF_PRACTICE_TEST_TYPE)

        # Apply dynamic filtering
        filter_backends = [DjangoFilterBackend]
        filterset = PracticeQuestionFilter(request.GET, queryset=questions)
        if not filterset.is_valid():
            return get_error_response('Invalid filter parameters')

        filtered_questions = filterset.qs

        question_ids = [question.id for question in filtered_questions]
        random.shuffle(question_ids)

        return Response(question_ids, status=status.HTTP_200_OK)

    @action(detail=False, methods=['POST'], permission_classes=[IsStudent], url_path='start-practice')
    def start_practice_test(self, request):
        student = request.user
        course_subject_id = request.data.get('course_subject_id')
        if not course_subject_id:
            return get_error_response("course_subject_id is required")

        # Build query filters based on provided data
        query_filters = Q(course_subject_id=course_subject_id, test_type=Question.SELF_PRACTICE_TEST_TYPE)

        topic = request.data.get('topic', '')
        if topic:
            topics = topic.split(',')
            query_filters &= Q(topic__in=topics)

        sub_topic = request.data.get('sub_topic', '')
        if sub_topic:
            sub_topics = sub_topic.split(',')
            query_filters &= Q(sub_topic__in=sub_topics)

        difficulty = request.data.get('difficulty', '')
        if difficulty:
            difficulties = difficulty.split(',')
            query_filters &= Q(difficulty__in=difficulties)

        questions = Question.objects.filter(query_filters)

        # Safely get the CourseSubject instance or return a 404 response
        course_subject = get_object_or_404(CourseSubjects, id=course_subject_id)

        practice_test = PracticeTest.objects.create(student=student, course_subject=course_subject)

        question_ids = [question.id for question in questions]
        random.shuffle(question_ids)

        return Response({'practice_test_id': practice_test.id, 'question_ids': question_ids},
                        status=status.HTTP_201_CREATED)

    @permission_classes([IsAdminOrMentorOrFacultyOrStudentOrParent])
    def list(self, request):
        user = request.user
        if user.role.name == 'student':
            # Filter to include only those practice tests that have results
            practice_tests = PracticeTest.objects.filter(student=user, result__isnull=False).prefetch_related(
                'result')
        elif user.role.name in ['parent', 'faculty', 'mentor']:
            if user.role.name == 'parent':
                sm = StudentMetadata.objects.filter(Q(father=user) | Q(mother=user))
            elif user.role.name == 'faculty':
                sm = StudentMetadata.objects.filter(faculty=user)
            elif user.role.name == 'mentor':
                sm = StudentMetadata.objects.filter(mentor=user)
            else:
                return get_error_response('Access denied')

            # Filter to include only those practice tests that have results
            practice_tests = PracticeTest.objects.filter(
                student__in=sm.values_list('student', flat=True), result__isnull=False).prefetch_related('result')
        else:
            return get_error_response('Access denied')

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_practice_tests = paginator.paginate_queryset(practice_tests, request)

        serializer = PracticeTestListSerializer(paginated_practice_tests, many=True, context={'request': request})

        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=['POST'], permission_classes=[IsStudent], url_path='take-test')
    def take_test(self, request, pk=None):
        practice_test = PracticeTest.objects.get(id=pk)
        question_id, answer_data = list(request.data.get('answer', {}).items())[0]
        is_skipped = request.data.get('is_skipped', False)
        time_taken = request.data.get('time_taken', 0)
        is_marked_for_review = request.data.get('is_marked_for_review', False)

        question = Question.objects.get(id=question_id)
        is_correct = None
        if is_skipped:
            is_correct = False  # Mark skipped questions as incorrect
        elif question.question_type == Question.FILL_IN_BLANKS:
            correct_answers_lower = [ans.lower() for ans in question.options]
            user_answers_lower = [ans.lower() for ans in answer_data]
            is_correct = correct_answers_lower == user_answers_lower
        else:
            correct_options = [index for index, option in enumerate(question.options) if option['is_correct']]
            if not is_skipped:
                is_correct = set(answer_data) == set(correct_options)

        # Fetch or create PracticeTestResult
        result, _ = PracticeTestResult.objects.get_or_create(
            practice_test=practice_test,
            defaults={'correct_answer_count': 0, 'incorrect_answer_count': 0, 'time_taken': 0, 'detailed_view': {}}
        )

        # Update Result
        result.update_detailed_view(
            question_id=question_id,
            answer_data=answer_data,
            time_taken=time_taken,
            correct_answer=is_correct,
            is_skipped=is_skipped,
            is_marked_for_review=is_marked_for_review
        )

        response = {
            'correct_answer_count': result.correct_answer_count,
            'incorrect_answer_count': result.incorrect_answer_count,
            'time_taken': result.time_taken
        }

        return Response(data=response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['GET'], permission_classes=[IsAdminOrMentorOrFacultyOrStudentOrParent],
            url_path='results')
    def get_practice_test_results(self, request, pk=None):
        practice_test_result = PracticeTestResult.objects.filter(practice_test_id=pk).first()
        practice_test = practice_test_result.practice_test
        section_answer_correct_marks = practice_test.course_subject.correct_answer_marks
        section_answer_incorrect_marks = practice_test.course_subject.incorrect_answer_marks
        course = practice_test.course_subject.course
        subject = practice_test.course_subject.subject

        if not practice_test_result:
            return Response({"error": "Results not found for the specified practice test."},
                            status=status.HTTP_404_NOT_FOUND)

        # Construct the response
        section_correct_count = 0
        section_correct_time_taken = 0
        section_incorrect_count = 0
        section_incorrect_time_taken = 0
        section_blank_count = 0
        marked = 0

        questions_data = []
        for index, (question_id, question_details) in enumerate(
                practice_test_result.detailed_view.get("answers", {}).items()):
            question_instance = Question.objects.get(id=question_id)
            question_data = {
                'sr_no': index + 1,
                'question_id': question_instance.id,
                'question_type': question_instance.question_type,
                'topic': question_instance.topic.name if question_instance.topic else "General",
                'result': question_details.get('is_correct', False),
                'total_time': question_details.get('time_taken', 0),
                'first_time_taken': question_details.get('first_time_taken', 0),
                'times_visited': question_details.get('times_visited', 0),
                'marked': question_details.get('is_marked_for_review', False),
                'is_skipped': question_details.get('is_skipped', False),
                'selected_options': question_details.get('answer_data', []),
            }

            section_correct_count += 1 if question_details.get('is_correct', False) else 0
            section_correct_time_taken += question_details.get('time_taken', 0) if question_details.get(
                'is_correct', False) else 0

            section_incorrect_count += 1 if not question_details.get('is_correct', False) and not question_details.get(
                'is_skipped', False) else 0
            section_incorrect_time_taken += question_details.get('time_taken', 0) if not question_details.get(
                'is_correct', False) and not question_details.get('is_skipped', False) else 0

            section_blank_count += 1 if question_details.get('is_skipped', False) else 0
            marked += 1 if question_details.get('is_marked_for_review', False) else 0

            questions_data.append(question_data)
            # Construct sub-section data

        section_data = {
            'name': 'Pratice Test - ' + course.name + ': ' + subject.name,
            'student_name': practice_test.student.name,
            'testDate': practice_test_result.created_at.strftime('%Y-%m-%d'),
            'test_type': "PRACTICE_TEST",
            'section_correct_count': section_correct_count,
            'section_correct_time_taken': section_correct_time_taken,
            'section_incorrect_count': section_incorrect_count,
            'section_incorrect_time_taken': section_incorrect_time_taken,
            'section_blank_count': section_blank_count,
            'marked': marked,
            'time_on_section': practice_test_result.time_taken,
            'section_max_score': len(questions_data) * section_answer_correct_marks,
            'section_score': (section_correct_count * section_answer_correct_marks) - (
                    section_incorrect_count * section_answer_incorrect_marks),
            'questions_data': questions_data
        }

        return JsonResponse(section_data)
