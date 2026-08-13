"""
Regression test for write-on-read URL prefix bug in MaintenanceMiddleware.

The app mounts dominial URLs under /dominial/, but the WRITE_ON_READ_PATTERNS
originally matched ^/tis/... (without the prefix). This meant GET-based
mutations like /dominial/tis/<id>/imovel/<id>/arquivar/ bypassed the
maintenance write freeze.

Greptile review of PR #142 flagged this as P1.
"""

import json
import os
import tempfile

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings


def _write_flag_file(flag_dict):
    """Create a temp file with the given maintenance config and return its path."""
    fd, path = tempfile.mkstemp(suffix='.json')
    with os.fdopen(fd, 'w') as f:
        json.dump(flag_dict, f)
    return path


@override_settings()
class MaintenanceMiddlewareWriteOnReadTest(TestCase):
    """Verify that /dominial/-prefixed write-on-read GETs are blocked (503)
    during maintenance — the exact bug from the PR review."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='manut', password='manutpass'
        )

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        # Flag file marking maintenance as active
        flag = {"ativo": True, "mensagem": "Teste", "fim_estimado": ""}
        self.flag_path = _write_flag_file(flag)

    def tearDown(self):
        if os.path.exists(self.flag_path):
            os.remove(self.flag_path)
        super().tearDown()

    def _run_middleware(self, path):
        """Instantiate MaintenanceMiddleware with a dummy get_response that
        returns 200, then call it with the given GET path."""
        from dominial.middleware import MaintenanceMiddleware

        dummy_response = HttpResponseOK()

        def get_response(request):
            return dummy_response

        middleware = MaintenanceMiddleware(get_response)
        request = self.factory.get(path)
        request.user = self.user
        return middleware(request)

    @override_settings(MANUTENCAO_FILE_PATH='__placeholder__')
    def test_arquivar_get_blocked_during_maintenance(self):
        """GET to /dominial/tis/<id>/imovel/<id>/arquivar/ must return 503
        when maintenance is active."""
        # Override settings per-test so setUp's temp file path is used
        from django.conf import settings
        settings.MANUTENCAO_FILE_PATH = self.flag_path

        response = self._run_middleware(
            '/dominial/tis/1/imovel/1/arquivar/'
        )
        self.assertEqual(response.status_code, 503)

    @override_settings(MANUTENCAO_FILE_PATH='__placeholder__')
    def test_criar_documento_get_blocked_during_maintenance(self):
        """GET to /dominial/tis/<id>/imovel/<id>/criar-documento/ must return
        503 when maintenance is active."""
        from django.conf import settings
        settings.MANUTENCAO_FILE_PATH = self.flag_path

        response = self._run_middleware(
            '/dominial/tis/1/imovel/1/criar-documento/'
        )
        self.assertEqual(response.status_code, 503)

    @override_settings(MANUTENCAO_FILE_PATH='__placeholder__')
    def test_non_prefixed_tis_url_not_double_blocked(self):
        """Sanity check: the old pattern ^/tis/... (without /dominial/) is no
        longer matched, so such a request would pass through to the normal
        response. This confirms the prefix is actually required."""
        from django.conf import settings
        settings.MANUTENCAO_FILE_PATH = self.flag_path

        response = self._run_middleware(
            '/tis/1/imovel/1/arquivar/'
        )
        self.assertEqual(response.status_code, 200)


class HttpResponseOK:
    """Minimal stand-in response object for the dummy get_response."""
    status_code = 200
