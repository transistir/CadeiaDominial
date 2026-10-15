from django.apps import AppConfig


class IaOcrConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ia_ocr'
    verbose_name = 'IA OCR'

    def ready(self):
        from django.core import checks

        from ia_ocr import checks as checks_ocr

        checks.register(
            checks_ocr.conferir_configuracao_ocr, tags=['settings']
        )
