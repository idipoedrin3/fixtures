from django.apps import AppConfig


class InstitutionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "institution"

    def ready(self):
        import institution.signals


class SystemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "institution"

    def ready(self):
        import institution.signals
