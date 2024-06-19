import datetime

from dateutil.relativedelta import relativedelta
from django.db import transaction
from rest_framework import serializers

from course_manager.models import Course, CourseEnrollment
from course_manager.serializers import CourseEnrollmentSerializer, CourseEnrollmentUpdateSerializer
from .models import User, Role, TempUser, StudentMetadata
from .utils import generate_secure_password, send_password_reset_link


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    course_details = serializers.SerializerMethodField()
    role_label = serializers.SerializerMethodField()
    parent_details = serializers.SerializerMethodField()
    faculty_details = serializers.SerializerMethodField()
    mentor_details = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'name',
            'role', 'role_name', 'role_label', 'created_at', 'updated_at',
            'course_details', 'parent_details', 'faculty_details', 'mentor_details',
            'is_active'
        ]
        read_only_fields = ('created_at', 'updated_at', 'is_active')
        extra_kwargs = {'password': {'write_only': True, 'required': False}}

    def get_course_details(self, obj):
        if obj.role.name == 'student':
            course_enrollments = CourseEnrollment.objects.filter(student=obj)
            return CourseEnrollmentSerializer(course_enrollments, many=True).data if course_enrollments else None
        return None

    def get_role_label(self, obj):
        return obj.role.name.replace('_', ' ').capitalize()

    def _get_student_metadata(self, student):
        return StudentMetadata.objects.filter(student=student).first()

    def get_parent_details(self, obj):
        if obj.role.name == 'student':
            student_metadata = self._get_student_metadata(obj)
            if student_metadata:
                return {
                    'father': UserDetailSerializer(student_metadata.father).data if student_metadata.father else None,
                    'mother': UserDetailSerializer(student_metadata.mother).data if student_metadata.mother else None
                }
        return None

    def get_faculty_details(self, obj):
        if obj.role.name == 'student':
            student_metadata = self._get_student_metadata(obj)
            return UserDetailSerializer(
                student_metadata.faculty).data if student_metadata and student_metadata.faculty else None
        return None

    def get_mentor_details(self, obj):
        if obj.role.name == 'student':
            student_metadata = self._get_student_metadata(obj)
            return UserDetailSerializer(
                student_metadata.mentor).data if student_metadata and student_metadata.mentor else None
        return None


class UserDetailSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'phone_number', 'role']

    def get_role(self, obj):
        return obj.role.name.replace('_', ' ').capitalize()


class TempUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TempUser
        fields = ['id', 'email', 'phone_number', 'name', 'courses']


class RoleSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ('id', 'name', 'label')

    def get_label(self, obj):
        return obj.name.replace('_', ' ').capitalize()


class UserCreationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True, required=False)
    courses = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )

    # father_email = serializers.EmailField(write_only=True, required=False, allow_blank=True, allow_null=True)
    # father_phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    # father_name = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    # mother_email = serializers.EmailField(write_only=True, required=False, allow_blank=True, allow_null=True)
    # mother_phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    # mother_name = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'name', 'role', 'courses']

    # def validate(self, data):
    #     role = data.get('role')
    #     if role.name == 'student':
    #         father_details = any([data.get('father_email'), data.get('father_phone_number'), data.get('father_name')])
    #         mother_details = any([data.get('mother_email'), data.get('mother_phone_number'), data.get('mother_name')])
    #
    #         if not father_details and not mother_details:
    #             raise serializers.ValidationError("At least one parent's details must be provided.")
    #
    #     return data

    # def create_parent_user(self, parent_data, role_name):
    #     if not parent_data['email']:
    #         return None
    #
    #     parent_role = Role.objects.get(name='parent')
    #     parent_user = User.objects.create(
    #         email=parent_data['email'],
    #         phone_number=parent_data['phone_number'],
    #         name=parent_data['name'],
    #         role=parent_role,
    #         password=generate_secure_password()
    #     )
    #     parent_user.set_password(generate_secure_password())
    #     parent_user.change_password = True
    #     parent_user.save()
    #     send_password_reset_link(parent_user)
    #     return parent_user

    def create(self, validated_data):
        with transaction.atomic():
            role = validated_data.get('role')

            user = User.objects.create(
                email=validated_data['email'],
                phone_number=validated_data['phone_number'],
                name=validated_data['name'],
                role=role
            )
            user.set_password(generate_secure_password())
            user.change_password = True
            user.save()

            if role.name == 'student':
                # father_data = {
                #     'email': validated_data.pop('father_email', None),
                #     'phone_number': validated_data.pop('father_phone_number', None),
                #     'name': validated_data.pop('father_name', None)
                # }
                # mother_data = {
                #     'email': validated_data.pop('mother_email', None),
                #     'phone_number': validated_data.pop('mother_phone_number', None),
                #     'name': validated_data.pop('mother_name', None)
                # }
                #
                # father_user = self.create_parent_user(father_data, 'parent') if father_data['email'] else None
                # mother_user = self.create_parent_user(mother_data, 'parent') if mother_data['email'] else None

                course_names = validated_data.pop('courses', [])
                for course_name in course_names:
                    course = Course.objects.get(name=course_name)
                    CourseEnrollment.objects.create(
                        student=user,
                        course=course,
                        subscription_start_date=datetime.date.today(),
                        subscription_end_date=datetime.date.today() + relativedelta(months=+4),
                        subscription_type=CourseEnrollment.FREE
                    )

                # StudentMetadata.create_metadata(student=user, father=father_user, mother=mother_user)
                StudentMetadata.create_metadata(student=user)

            send_password_reset_link(user)
            return user


class CourseSubscriptionSerializer(serializers.Serializer):
    course = serializers.CharField(required=True)
    subscription_start_date = serializers.DateField(required=True)
    subscription_end_date = serializers.DateField(required=True)
    subscription_type = serializers.ChoiceField(choices=[('FREE', 'Free'), ('PAID', 'Paid')])


class ApproveStudentSubscriptionSerializer(serializers.Serializer):
    student = serializers.IntegerField(required=True)
    courses = CourseSubscriptionSerializer(many=True)
    is_temp_user = serializers.BooleanField(required=True)

    faculty = serializers.IntegerField(required=False)
    mentor = serializers.IntegerField(required=False)

    # Optional parent fields
    father_id = serializers.IntegerField(required=False)
    father_email = serializers.EmailField(required=False)
    father_phone_number = serializers.CharField(max_length=10, required=False)
    father_name = serializers.CharField(max_length=30, required=False)

    mother_id = serializers.IntegerField(required=False)
    mother_email = serializers.EmailField(required=False)
    mother_phone_number = serializers.CharField(max_length=10, required=False)
    mother_name = serializers.CharField(max_length=30, required=False)

    def validate(self, data):
        if data['is_temp_user'] and not TempUser.objects.filter(pk=data['student']).exists():
            raise serializers.ValidationError({"student": "Invalid student ID."})
        if not data['is_temp_user'] and not User.objects.filter(pk=data['student']).exists():
            raise serializers.ValidationError({"student": "Invalid student ID."})
        # if not User.objects.filter(pk=data['faculty']).exists():
        #     raise serializers.ValidationError({"faculty": "Invalid faculty ID."})
        # if not User.objects.filter(pk=data['mentor']).exists():
        #     raise serializers.ValidationError({"mentor": "Invalid mentor ID."})
        if data['is_temp_user']:
            if 'father_id' not in data and 'father_email' not in data and 'mother_id' not in data and 'mother_email' not in data:
                raise serializers.ValidationError(
                    {"parent": "At least one of father or mother details are required for a temporary user."})
            if 'father_email' in data or 'mother_email' in data:
                required_parent_fields = ['email', 'phone_number', 'name']
                for parent_type in ['father', 'mother']:
                    if f'{parent_type}_email' in data:
                        for field in required_parent_fields:
                            full_field_name = f'{parent_type}_{field}'
                            if full_field_name not in data:
                                raise serializers.ValidationError(
                                    {full_field_name: f"{full_field_name} is required for a temporary user."})
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']


class LoginSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    csrf_token = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone_number', 'name', 'role', 'role_name', 'csrf_token', 'change_password']


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'phone_number', 'name']
        extra_kwargs = {'email': {'required': False}, 'phone_number': {'required': False}, 'name': {'required': False}}


class StudentUpdateSerializer(serializers.Serializer):
    faculty = serializers.IntegerField(required=False, allow_null=True)
    mentor = serializers.IntegerField(required=False, allow_null=True)

    courses = CourseSubscriptionSerializer(many=True, required=False)

    def update(self, instance, validated_data):
        # Update faculty and mentor in StudentMetadata
        student_metadata = instance.student_metadata
        faculty = validated_data.get('faculty')
        mentor = validated_data.get('mentor')

        if faculty is not None:
            student_metadata.faculty = User.objects.get(id=faculty) if faculty else None
        if mentor is not None:
            student_metadata.mentor = User.objects.get(id=mentor) if mentor else None

        student_metadata.save()

        if 'courses' in validated_data:
            # Delete all existing course enrollments for the student
            CourseEnrollment.objects.filter(student=instance).delete()

            # Recreate course enrollments based on provided data
            for enrollment_data in validated_data['courses']:
                course = Course.objects.get(name=enrollment_data['course'])
                CourseEnrollment.objects.create(
                    student=instance,
                    course=course,
                    subscription_start_date=enrollment_data.get('subscription_start_date'),
                    subscription_end_date=enrollment_data.get('subscription_end_date'),
                    subscription_type=enrollment_data.get('subscription_type')
                )

        return instance
