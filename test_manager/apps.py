from django.apps import AppConfig


class TestManagerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "test_manager"

    def ready(self):
        import test_manager.signals
