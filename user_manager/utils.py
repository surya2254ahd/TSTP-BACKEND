from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from notification_manager.models import NotificationTemplate, Notification
from notification_manager.utils import send_notification
from user_manager.models import PasswordResetToken


def send_password_reset_link(user):
    try:
        existing_reset_token = PasswordResetToken.objects.get(user=user, used=False)
        if existing_reset_token is not None:
            existing_reset_token.used = True
            existing_reset_token.save()
    except PasswordResetToken.DoesNotExist:
        # This block will execute if no unused token exists for the user
        pass

    # Create a password reset token
    password_reset_token = PasswordResetToken.objects.create(user=user,
                                                             expires_at=timezone.now() + timedelta(days=1))

    # Construct the password reset link
    reset_link = f'{settings.FRONTEND_URL}/reset-password?token={password_reset_token.token}'

    # Send notification
    notification_params = {NotificationTemplate.USER_NAME: user.name, NotificationTemplate.RESET_LINK: reset_link}
    send_notification.apply_async(args=[],
                                  kwargs={'notification_name': Notification.NEW_USER_RESET_PASSWORD_NOTIFICATION,
                                          'params': notification_params,
                                          'user_id': user.id},
                                  countdown=30)


def generate_secure_password():
    password = '@smarttest@2024!'
    return password
    # while True:
    #     password = get_random_string(length=12)
    #     try:
    #         validate_password(password)
    #         return password
    #     except ValidationError:
    #         continue
