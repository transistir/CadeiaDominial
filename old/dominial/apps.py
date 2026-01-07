from django.apps import AppConfig


class DominialConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dominial'
    
    def ready(self):
        import dominial.signals