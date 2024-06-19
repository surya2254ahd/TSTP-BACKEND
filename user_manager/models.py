import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

phone_regex = RegexValidator(regex=r'^\d{10}$',
                             message="Phone number must be entered in the format: '9#########'. Up to 10 digits allowed.")


class Role(models.Model):
    name = models.CharField(max_length=30, unique=True, null=False)
    description = models.TextField()
    create_date = models.DateTimeField(auto_now_add=True)
    last_updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @classmethod
    def get_all(cls):
        return cls.objects.all()

    @classmethod
    def get_roles_excluding(cls, name):
        return cls.objects.exclude(name=name)

    @classmethod
    def get_role_using_name(cls, name):
        return cls.objects.get(name=name)


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(validators=[phone_regex], max_length=10, unique=True)
    name = models.CharField(max_length=30, blank=True)
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='users')
    is_active = models.BooleanField(default=True)
    change_password = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def set_role(self, role):
        self.role = role

    def set_change_password(self, change_password):
        self.change_password = change_password
        self.save()

    @classmethod
    def get_all(cls):
        return cls.objects.filter(is_active=True, is_staff=False)

    @classmethod
    def filter_users_by_role(cls, role_id):
        return cls.objects.filter(role__id=role_id, is_active=True)

    @classmethod
    def filter_users_excluding_role(cls, role_id):
        return cls.objects.exclude(role__id=role_id).filter(is_staff=False)

    @classmethod
    def get_user_by_id(cls, user_id):
        return cls.objects.get(id=user_id, is_active=True)

    @classmethod
    def filter_users_using_id_and_role(cls, user_ids, role):
        return cls.objects.filter(id__in=user_ids, role=role, is_active=True, is_staff=False)


class TempUserManager(UserManager):
    pass


class TempUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    phone_number = models.CharField(validators=[phone_regex], max_length=10, unique=True)
    name = models.CharField(max_length=30, blank=True)
    courses = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=False)

    objects = TempUserManager()

    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def set_role(self, role):
        self.role = role
        self.save()

    @classmethod
    def get_all(cls):
        return cls.objects.filter(is_active=True)

    @classmethod
    def get_temp_user_using_id(cls, temp_user_id):
        return cls.objects.get(id=temp_user_id)


class StudentMetadata(models.Model):
    student = models.OneToOneField(User, related_name="student_metadata", on_delete=models.CASCADE)
    father = models.ForeignKey(User, related_name="father_of", on_delete=models.CASCADE, null=True, blank=True)
    mother = models.ForeignKey(User, related_name="mother_of", on_delete=models.CASCADE, null=True, blank=True)
    faculty = models.ForeignKey(User, related_name="faculty_students", on_delete=models.SET_NULL, null=True)
    mentor = models.ForeignKey(User, related_name="mentor_students", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_student_metadata_using_id(cls, student_id):
        return StudentMetadata.objects.get(student=student_id)

    @classmethod
    def create_metadata(cls, **kwargs):
        """
        Create a new StudentMetadata instance with updated logic.
        """
        # if 'father' not in kwargs and 'mother' not in kwargs:
        #     raise ValueError("At least one of father or mother must be provided.")
        metadata_instance = cls.objects.create(**kwargs)
        return metadata_instance

    def update_metadata(self, **kwargs):
        """
        Update fields of an existing StudentMetadata instance.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()
        return self


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def is_expired(self):
        return self.expires_at < timezone.now()
