"""
Playwright configuration for E2E testing.

This configuration integrates Playwright with pytest-django for end-to-end testing
of the Sistema de Cadeia Dominial web application.
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Playwright configuration
PLAYWRIGHT_CONFIG = {
    # Browser settings
    'browser': 'chromium',  # Can be 'chromium', 'firefox', or 'webkit'
    'headless': True,  # Run in headless mode for CI/CD
    'slow_mo': 0,  # Slow down operations (ms) for debugging

    # Viewport settings
    'viewport': {
        'width': 1920,
        'height': 1080,
    },

    # Screenshot and video settings
    'screenshot_on_failure': True,
    'video_on_failure': True,

    # Timeout settings (in milliseconds)
    'timeout': 30000,  # 30 seconds
    'navigation_timeout': 30000,

    # Base URL for tests
    'base_url': os.getenv('PLAYWRIGHT_BASE_URL', 'http://localhost:8000'),

    # Artifacts directory
    # SECURITY NOTE: Ensure test-results/ is in .gitignore and CI artifact
    # uploads have proper access controls. Artifacts may contain sensitive
    # UI states or data from seeded fixtures.
    'artifacts_dir': BASE_DIR / 'test-results',
    'screenshots_dir': BASE_DIR / 'test-results' / 'screenshots',
    'videos_dir': BASE_DIR / 'test-results' / 'videos',
    'traces_dir': BASE_DIR / 'test-results' / 'traces',
}

# Test data configuration
TEST_USER = {
    'username': 'testuser',
    'password': 'testpass123',
    'email': 'test@example.com',
}

# Selectors (for maintainability)
SELECTORS = {
    # Login page
    'login': {
        'username_input': 'input[name="username"]',
        'password_input': 'input[name="password"]',
        'submit_button': 'button[type="submit"]',
    },

    # Navigation
    'nav': {
        'home_link': 'a[href="/"]',
        'tis_link': 'a:has-text("TIs")',
        'logout_button': 'a:has-text("Sair")',
    },

    # Lancamento form
    'lancamento_form': {
        'tipo_select': 'select[name="tipo_lancamento"]',
        'numero_input': 'input[name="numero_lancamento_simples"]',
        'data_input': 'input[name="data"]',
        'titulo_input': 'input[name="titulo"]',
        'observacoes_textarea': 'textarea[name="observacoes"]',
        'submit_button': 'button[type="submit"]',
        'transmitente_autocomplete': '#transmitente-autocomplete',
        'adquirente_autocomplete': '#adquirente-autocomplete',
    },

    # Tree visualization
    'tree': {
        'svg_container': 'svg#cadeia-tree',
        'document_nodes': 'g.node',
        'connections': 'path.link',
        'zoom_in_button': 'button#zoom-in',
        'zoom_out_button': 'button#zoom-out',
        'reset_zoom_button': 'button#reset-zoom',
    },

    # Alerts and messages
    'messages': {
        'success_alert': '.alert-success',
        'error_alert': '.alert-danger',
        'warning_alert': '.alert-warning',
        'info_alert': '.alert-info',
    },
}
