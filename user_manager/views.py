import logging
import random
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db import transaction
from django.middleware.csrf import get_token, _unmask_cipher_token
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import serializers
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_manager.models import Course, CourseEnrollment
from notification_manager.models import Notification, NotificationTemplate
from notification_manager.utils import send_notification
from sTest.permissions import IsAdmin, ChangePasswordPermission, IsAdminOrMentorOrFaculty
from sTest.utils import get_error_response_for_serializer, CustomPageNumberPagination, get_error_response
from .filters import UserFilter
from .models import Role, User, TempUser, StudentMetadata, PasswordResetToken
from .serializers import UserSerializer, TempUserSerializer, UserCreationSerializer, \
    ApproveStudentSubscriptionSerializer, ChangePasswordSerializer, LoginSerializer, RoleSerializer, \
    UserUpdateSerializer, StudentUpdateSerializer
from .utils import generate_secure_password, send_password_reset_link


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.get_all()
    serializer_class = UserSerializer
    logger = logging.getLogger('Users')

    @permission_classes([IsAdmin])
    def create(self, request, *args, **kwargs):
        serializer = UserCreationSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            details_serializer = UserSerializer(user)
            return Response(details_serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @permission_classes([IsAdmin])
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user_serializer = UserUpdateSerializer(instance, data=request.data, partial=True)

        if user_serializer.is_valid():
            user_serializer.save()
            # If the user is a student, update student-specific data
            if instance.role.name == 'student':
                student_serializer = StudentUpdateSerializer(instance, data=request.data, partial=True)
                if student_serializer.is_valid():
                    student_serializer.save()
                else:
                    return get_error_response_for_serializer(logger=self.logger, serializer=student_serializer,
                                                             data=request.data)
                    # return Response(student_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            return Response(user_serializer.data)
        return get_error_response_for_serializer(logger=self.logger, serializer=user_serializer,
                                                 data=request.data)

    @permission_classes([IsAdmin])
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
    def deactivate_user(self, request, pk=None):
        user = User.get_user_by_id(user_id=pk)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def session_validate(self, request):
        """
            Custom action to check if the user's session is still valid.
        """
        # If the request reaches this point, the user is authenticated
        user = request.user
        response = LoginSerializer(user).data
        response['csrf_token'] = _unmask_cipher_token(get_token(request))
        return Response(data=response, status=status.HTTP_200_OK)


    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def login(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            response = LoginSerializer(user).data
            response['csrf_token'] = _unmask_cipher_token(get_token(request))
            return Response(data=response, status=status.HTTP_200_OK)
        else:
            self.logger.exception("Invalid credentials provided")
            response = {
                'detail': 'Invalid credentials'
            }
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated])
    def logout(self, request):
        logout(request)
        return Response({'detail': 'Logged out successfully'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['GET'], permission_classes=[AllowAny])
    def roles(self, request):
        roles = Role.get_all()
        roles_data = RoleSerializer(roles, many=True).data
        return Response(data=roles_data, status=status.HTTP_200_OK)

    @permission_classes([IsAdminOrMentorOrFaculty])
    def list(self, request):
        user = request.user
        if user.role.name == 'faculty':
            sm = StudentMetadata.objects.filter(faculty=user)
            users = User.filter_users_using_id_and_role(user_ids=sm.values_list('student', flat=True),
                                                        role=Role.get_role_using_name('student').id)
        elif user.role.name == 'mentor':
            sm = StudentMetadata.objects.filter(mentor=user)
            users = User.filter_users_using_id_and_role(user_ids=sm.values_list('student', flat=True),
                                                        role=Role.get_role_using_name('student').id)
        elif user.role.name == 'admin':
            role = request.query_params.get('role', None)
            if role:
                users = User.filter_users_by_role(role_id=role)
            else:
                users = User.filter_users_excluding_role(role_id=Role.get_role_using_name('admin').id)
        else:
            users = []

        # Apply dynamic filtering
        filter_backends = [DjangoFilterBackend]
        filterset = UserFilter(request.GET, queryset=users)
        if not filterset.is_valid():
            return get_error_response('Invalid filter parameters')

        filtered_users = filterset.qs

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_users = paginator.paginate_queryset(filtered_users, request)

        serializer = UserSerializer(paginated_users, many=True)

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)

    @permission_classes([IsAuthenticated])
    def retrieve(self, request, pk=None):
        user = request.user
        if user.role.name == 'admin':
            user = User.get_user_by_id(user_id=pk)
        serializer = UserSerializer(user)
        return Response(data=serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['POST'], permission_classes=[IsAdmin],
            url_path='approve_student_subscription')
    def approve_student_subscription(self, request):
        serializer = ApproveStudentSubscriptionSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            is_temp_user = data['is_temp_user']
            student_metadata = None

            if is_temp_user:
                student_metadata = self._process_temp_user(data)
            else:
                student_metadata = self._update_existing_student_metadata(data)

            if 'error' in student_metadata:
                return get_error_response(student_metadata['error'])

            return Response(data={'detail': 'Student subscription approved successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @action(detail=False, methods=['POST'], permission_classes=[ChangePasswordPermission])
    def change_password(self, request, pk=None):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            # Check old password
            if not user.check_password(serializer.validated_data['old_password']):
                return get_error_response("Wrong password provided.")
            # set_password also hashes the password that the user will get
            user.set_change_password(False)
            user.set_password(serializer.validated_data['new_password'])
            user.save()

            login(request, user)
            response = LoginSerializer(user).data
            response['csrf_token'] = _unmask_cipher_token(get_token(request))
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request)

    @action(detail=False, methods=['GET'], permission_classes=[IsAdmin], url_path='upcoming-subscription-or-free')
    def upcoming_subscription_or_free(self, request, pk=None):
        upcoming_month_date = datetime.now().date() + timedelta(days=30)

        # Filter student role users
        student_role_users = User.filter_users_by_role(role_id=Role.get_role_using_name('student').id)

        # Fetch CourseEnrollment instances meeting the criteria
        qualified_enrollments = CourseEnrollment.objects.filter(
            student__in=student_role_users,
            subscription_end_date__lte=upcoming_month_date
        ) | CourseEnrollment.objects.filter(
            student__in=student_role_users,
            subscription_type=CourseEnrollment.FREE
        )

        # Distinctly select students
        qualified_students = User.objects.filter(
            id__in=qualified_enrollments.values_list('student', flat=True)
        ).distinct()

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_users = paginator.paginate_queryset(qualified_students, request)

        serializer = UserSerializer(paginated_users, many=True)

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def forgot_password(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return get_error_response('User not found.')

        try:
            existing_reset_token = PasswordResetToken.objects.get(user=user, used=False)
            if existing_reset_token is not None:
                existing_reset_token.used = True
                existing_reset_token.save()
        except PasswordResetToken.DoesNotExist:
            pass

        # Create a password reset token
        password_reset_token = PasswordResetToken.objects.create(user=user,
                                                                 expires_at=timezone.now() + timedelta(hours=1))

        # Construct the password reset link
        reset_link = f'{settings.FRONTEND_URL}/reset-password?token={password_reset_token.token}'

        # Send notification
        notification_params = {NotificationTemplate.RESET_LINK: reset_link}

        send_notification.delay(notification_name=Notification.FORGOT_PASSWORD_NOTIFICATION,
                                params=notification_params,
                                user_id=user.id)

        return Response({"detail": "Password reset email sent."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny])
    def reset_password(self, request):
        token = request.data.get('token')
        password = request.data.get('password')

        try:
            password_reset_token = PasswordResetToken.objects.get(token=token, used=False)
        except PasswordResetToken.DoesNotExist:
            return get_error_response('Invalid or expired token.')

        if password_reset_token.is_expired():
            return get_error_response('Token has expired.')

        user = password_reset_token.user
        user.set_password(password)
        user.change_password = False
        user.save()

        password_reset_token.used = True
        password_reset_token.save()

        return Response(status=status.HTTP_200_OK)

    @transaction.atomic
    def _process_temp_user(self, data):
        temp_user_data = TempUser.get_temp_user_using_id(data['student'])

        user_data = {
            'email': temp_user_data.email,
            'phone_number': temp_user_data.phone_number,
            'name': temp_user_data.name,
            'role': Role.get_role_using_name('student').id,
        }
        user_serializer = UserSerializer(data=user_data)

        try:
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
            user.set_password(temp_user_data.password)
            user.save()
        except Exception as e:
            error = ''
            for field_name, field_errors in user_serializer.errors.items():
                error += str.capitalize(field_errors[0]) + '<br/>'
            return {'error': error}

        # Extract the StudentMetadata details from the data received in the API
        faculty = User.get_user_by_id(data['faculty'])
        mentor = User.get_user_by_id(data['mentor'])

        try:
            parent_user_data = self._prepare_parent_data(data=data, is_temp_user=True)
        except serializers.ValidationError as e:
            return {'error': str(e)}

        student_metadata_data = {
            'student': user,
            'faculty': faculty,
            'mentor': mentor,
            **parent_user_data
        }

        student_metadata = StudentMetadata.create_metadata(**student_metadata_data)

        # Extract course details received in the API
        for course_data in data['courses']:
            course = Course.objects.get(name=course_data['course'])
            CourseEnrollment.objects.create(
                student=user,
                course=course,
                subscription_start_date=course_data['subscription_start_date'],
                subscription_end_date=course_data['subscription_end_date'],
                subscription_type=course_data['subscription_type']
            )

        temp_user_data.delete()
        return {'Student subscription approved successfully'}

    def _prepare_parent_data(self, data, is_temp_user):
        parent_user_data = {}
        if 'father_id' in data or 'mother_id' in data or 'father_email' in data or 'mother_email' in data:
            for parent_type in ['father', 'mother']:
                if f'{parent_type}_id' in data:
                    parent_user = User.get_user_by_id(data[f'{parent_type}_id'])
                    parent_user_data[parent_type] = parent_user
                elif f'{parent_type}_email' in data:
                    parent_creation_response = self._create_parent_user(data, parent_type)
                    if 'error' in parent_creation_response:
                        raise serializers.ValidationError(parent_creation_response['error'])
                    parent_user_data[parent_type] = parent_creation_response['user']
        elif is_temp_user:
            raise serializers.ValidationError(
                "At least one of father or mother details are required for a temporary user.")

        return parent_user_data

    def _create_parent_user(self, data, parent_type):
        # Common code to create parent user (either father or mother)
        parent_user_data = {
            'email': data[f'{parent_type}_email'],
            'phone_number': data[f'{parent_type}_phone_number'],
            'name': data[f'{parent_type}_name'],
            'role': Role.get_role_using_name('parent').id,
        }
        parent_user_serializer = UserSerializer(data=parent_user_data)

        try:
            parent_user_serializer.is_valid(raise_exception=True)
            parent_user = parent_user_serializer.save()
            parent_user.set_change_password(True)
            parent_user.set_password(generate_secure_password())
            parent_user.save()

            send_password_reset_link(parent_user)
            return {'user': parent_user}
        except Exception as e:
            error = f'{str.capitalize(parent_type)} - '
            for field_name, field_errors in parent_user_serializer.errors.items():
                try:
                    if len(field_errors) > 1:
                        for sub_field in field_errors:
                            for dict_field_name, dict_field_errors in sub_field.items():
                                error += str.capitalize(dict_field_name) + ': ' + str.capitalize(
                                    dict_field_errors[0]) + '<br/>'
                    else:
                        error += str.capitalize(field_name) + ': ' + str.capitalize(field_errors[0]) + '<br/>'
                except Exception as e:
                    self.logger.info(f'Error processing error for - {field_name} because of {e}')
            if error == '':
                error = 'Oops! Something went wrong.'
            return {'error': error}

    @transaction.atomic
    def _update_existing_student_metadata(self, data):
        student_metadata = StudentMetadata.get_student_metadata_using_id(data['student'])

        if 'faculty' not in data:
            faculty = None
        else:
            faculty = User.get_user_by_id(data['faculty'])
        if 'mentor' not in data:
            mentor = None
        else:
            mentor = User.get_user_by_id(data['mentor'])

        student_metadata.update_metadata(
            faculty=faculty,
            mentor=mentor
        )

        try:
            if 'father_email' in data:
                if student_metadata.father is None:
                    father_creation_response = self._create_parent_user(data=data, parent_type='father')
                    if 'error' in father_creation_response:
                        raise Exception(father_creation_response['error'])

                    father_user = father_creation_response['user']
                    student_metadata.update_metadata(father=father_user)
                else:
                    father_user = student_metadata.father
                    father_user.email = data['father_email']
                    father_user.phone_number = data['father_phone_number']
                    father_user.name = data['father_name']
                    father_user.save()
            elif 'father_id' in data:
                father_user = User.get_user_by_id(data['father_id'])
                student_metadata.father = father_user
                student_metadata.save()

            if 'mother_email' in data:
                if student_metadata.mother is None:
                    mother_creation_response = self._create_parent_user(data=data, parent_type='mother')
                    if 'error' in mother_creation_response:
                        raise serializers.ValidationError(mother_creation_response['error'])

                    mother_user = mother_creation_response['user']
                    student_metadata.update_metadata(mother=mother_user)
                else:
                    mother_user = student_metadata.mother
                    mother_user.email = data['mother_email']
                    mother_user.phone_number = data['mother_phone_number']
                    mother_user.name = data['mother_name']
                    mother_user.save()
            elif 'mother_id' in data:
                mother_user = User.get_user_by_id(data['mother_id'])
                student_metadata.mother = mother_user
                student_metadata.save()
        except Exception as e:
            return {'error': str(e)}

        CourseEnrollment.objects.filter(student=student_metadata.student).delete()
        for course_data in data['courses']:
            course = Course.objects.get(name=course_data['course'])
            CourseEnrollment.objects.create(
                student=student_metadata.student,
                course=course,
                subscription_start_date=course_data['subscription_start_date'],
                subscription_end_date=course_data['subscription_end_date'],
                subscription_type=course_data['subscription_type']
            )

        return {'Student subscription approved successfully'}


class TempUserViewSet(viewsets.ModelViewSet):
    queryset = TempUser.get_all()
    serializer_class = TempUserSerializer
    logger = logging.getLogger('Temp User')

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny], url_path='register')
    def register(self, request):
        serializer = TempUserSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            # Set the role to 'student'
            # student_role = Role.get_role_using_name(name='student')
            # user_instance = serializer.save(role=student_role)
            user_instance = serializer.save()

            # Set the password
            password = request.data.get('password')
            user_instance.set_password(password)
            user_instance.save()

            otp = random.randint(100000, 999999)  # Generate a 6-digit OTP
            cache.set(f"otp_{user_instance.email}", otp, timeout=6000)

            # Send notification
            notification_params = {NotificationTemplate.USER_NAME: request.data.get("name"),
                                   NotificationTemplate.OTP: str(otp)}
            send_notification.delay(notification_name=Notification.REGISTRATION_OTP_NOTIFICATION,
                                    params=notification_params,
                                    user_id=user_instance.id)

            return Response({"message": "OTP sent to email. Please verify to complete registration."},
                            status=status.HTTP_200_OK)
        except Exception as e:
            return get_error_response_for_serializer(logger=self.logger, serializer=serializer, data=request.data)

    @action(detail=False, methods=['POST'], permission_classes=[AllowAny], url_path='verify-otp')
    def verify_otp(self, request):
        email = request.data.get('email')
        user_otp = request.data.get('otp')

        if not email or not user_otp:
            return get_error_response('Email and OTP are required')

        stored_otp = cache.get(f"otp_{email}")

        if stored_otp is None:
            return get_error_response('OTP has expired or is invalid')

        if str(user_otp) == str(stored_otp):
            temp_user = TempUser.objects.get(email=email)
            temp_user.is_active = True
            temp_user.save()

            notification_params = {NotificationTemplate.USER_NAME: temp_user.name}

            send_notification.delay(notification_name=Notification.REGISTRATION_NOTIFICATION,
                                    params=notification_params,
                                    user_id=temp_user.id)

            return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)
        else:
            return get_error_response('Invalid OTP')

    @action(detail=False, methods=['GET'], permission_classes=[IsAdmin], url_path='registered')
    def registered_users(self, request):
        temp_users = TempUser.get_all()

        # Apply pagination
        paginator = CustomPageNumberPagination()
        paginator.page_size = 15
        paginated_temp_users = paginator.paginate_queryset(temp_users, request)

        serializer = TempUserSerializer(paginated_temp_users, many=True)

        # Return the paginated response
        return paginator.get_paginated_response(serializer.data)
