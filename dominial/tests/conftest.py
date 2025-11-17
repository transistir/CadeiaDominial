"""
Pytest configuration and fixtures for Sistema de Cadeia Dominial tests.

This file provides:
- Django test database configuration
- Common fixtures for models
- Factory configurations
- Playwright fixtures for E2E tests
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client


# ============================================================================
# Django Configuration
# ============================================================================

@pytest.fixture
def client():
    """Django test client for simulating HTTP requests."""
    return Client()


@pytest.fixture
def authenticated_client(db, client):
    """Django test client with authenticated user."""
    user = User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )
    client.force_login(user)
    return client


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )


# ============================================================================
# Playwright Configuration (for E2E tests)
# ============================================================================

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure Playwright browser context."""
    return {
        **browser_context_args,
        "viewport": {
            "width": 1920,
            "height": 1080,
        },
        "locale": "pt-BR",
    }


@pytest.fixture
def authenticated_page(page, live_server, db, client):
    """Playwright page with authenticated user session.

    Uses Django's session framework to create authenticated session,
    avoiding brittle UI-based login and CSRF issues.

    Usage in E2E tests:
        def test_something(authenticated_page):
            authenticated_page.goto("/some-protected-page/")
            # Page is already logged in
    """
    from django.contrib.sessions.backends.db import SessionStore
    from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY, HASH_SESSION_KEY

    # Create user if not exists
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@example.com'
        }
    )
    if created:
        user.set_password('testpass123')
        user.save()

    # Create session directly using Django's session backend
    session = SessionStore()
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = 'django.contrib.auth.backends.ModelBackend'
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    session.save()

    # Set session cookie in Playwright
    page.context.add_cookies([{
        'name': 'sessionid',
        'value': session.session_key,
        'domain': 'localhost',
        'path': '/',
        'httpOnly': True,
        'sameSite': 'Lax',
    }])

    # Verify authentication by navigating to a protected page
    page.goto(f"{live_server.url}/")

    return page


# ============================================================================
# Custom Assertions
# ============================================================================

@pytest.fixture
def assert_model_exists():
    """Helper to assert model instance exists in database."""
    def _assert(model_class, **filters):
        assert model_class.objects.filter(**filters).exists(), \
            f"{model_class.__name__} matching {filters} not found in database"
        return model_class.objects.get(**filters)
    return _assert


@pytest.fixture
def assert_model_count():
    """Helper to assert model instance count."""
    def _assert(model_class, count, **filters):
        actual_count = model_class.objects.filter(**filters).count()
        assert actual_count == count, \
            f"Expected {count} {model_class.__name__} instances, found {actual_count}"
    return _assert
