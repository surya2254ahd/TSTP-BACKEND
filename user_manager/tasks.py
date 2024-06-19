from django.utils import timezone

from course_manager.models import CourseEnrollment
from sTest.celery import app
from test_manager.models import TestSubmission


@app.task
def check_and_update_subscriptions():
    enrollments = CourseEnrollment.objects.filter(subscription_type=CourseEnrollment.PAID,
                                                  subscription_end_date__lt=timezone.now())
    for enrollment in enrollments:
        enrollment.subscription_type = CourseEnrollment.FREE
        enrollment.save()


@app.task
def update_expired_test_submissions():
    now = timezone.now()
    expired_submissions = TestSubmission.objects.filter(
        expiration_date__lt=now,
        status__in=[TestSubmission.YET_TO_START, TestSubmission.IN_PROGRESS]
    )

    for submission in expired_submissions:
        submission.status = TestSubmission.EXPIRED
        submission.save()
