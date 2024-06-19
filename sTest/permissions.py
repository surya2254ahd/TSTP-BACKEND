from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow access to admin role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role.name == "admin")


class IsStudent(permissions.BasePermission):
    """
    Custom permission to only allow access to student role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role.name == "student")


class IsFaculty(permissions.BasePermission):
    """
    Custom permission to only allow access to faculty role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role.name == "faculty")


class IsMentor(permissions.BasePermission):
    """
    Custom permission to only allow access to mentor role users.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role.name == "mentor"


class IsParent(permissions.BasePermission):
    """
    Custom permission to only allow access to parent role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role.name == "parent")


class IsContentDeveloper(permissions.BasePermission):
    """
    Custom permission to only allow access to content developer role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role.name == "content_developer")


class IsAdminOrContentDeveloper(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or content_developer role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
                request.user.role.name == "content_developer" or request.user.role.name == "admin"))


class IsAdminOrFaculty(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or faculty role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.role.name == "admin" or request.user.role.name == "faculty"))


class IsAdminOrMentor(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or mentor role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.role.name == "admin" or request.user.role.name == "mentor"))


class IsAdminOrParent(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or parent role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.role.name == "admin" or request.user.role.name == "parent"))


class IsAdminOrStudentOrParent(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or mentor role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.role.name == "admin" or request.user.role.name == "student"
                     or request.user.role_name == "parent"))


class IsAdminOrMentorOrFaculty(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or mentor or faculty role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
                request.user.role.name == "admin" or request.user.role.name == "mentor"
                or request.user.role.name == "faculty"))


class IsAdminOrContentDeveloperOrFaculty(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or content developer or faculty role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
                request.user.role.name == "content_developer" or request.user.role.name == "admin" or request.user.role.name == "faculty"))


class IsAdminOrMentorOrStudentOrParent(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or mentor role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.role.name == "admin" or request.user.role.name == "mentor"
                     or request.user.role.name == "student" or request.user.role.name == "parent"))


class IsAdminOrContentDeveloperOrFacultyOrStudent(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or content developer or faculty or student role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
                request.user.role.name == "content_developer" or request.user.role.name == "admin" or request.user.role.name == "faculty" or request.user.role.name == "student"))


class IsAdminOrMentorOrFacultyOrStudentOrParent(permissions.BasePermission):
    """
    Custom permission to only allow access to admin or mentor or faculty or student or parent role users.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (
                request.user.role.name == "admin" or request.user.role.name == "mentor"
                or request.user.role.name == "faculty" or request.user.role.name == "student"
                or request.user.role.name == "parent"))


class ChangePasswordPermission(permissions.BasePermission):
    """
    Allow users to change only their own password unless they are an admin.
    """

    def has_object_permission(self, request, view, obj):
        # Allow user to change their own password
        if obj == request.user:
            return True

        # Allow admin to change any user's password
        if request.user.role.name == "admin":
            return True

        # If neither condition is met, deny access
        return False
