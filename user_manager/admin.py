from django.contrib import admin

from user_manager.models import Role, User, TempUser, StudentMetadata

admin.site.register(Role)
admin.site.register(User)
admin.site.register(TempUser)
admin.site.register(StudentMetadata)