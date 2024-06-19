from django.contrib import admin

from course_manager.models import Course, Subject, Question, Material

admin.site.register(Course)
admin.site.register(Subject)
admin.site.register(Question)
admin.site.register(Material)
