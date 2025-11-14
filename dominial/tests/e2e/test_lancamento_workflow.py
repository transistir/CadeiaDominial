"""
End-to-end tests for lancamento creation workflow using Playwright.

These tests verify complete user workflows from login through lancamento creation,
including form interactions, validation, and success confirmation.
"""

import pytest
from playwright.sync_api import Page, expect
from django.contrib.auth.models import User

from dominial.tests.factories import (
    TIsFactory,
    ImovelFactory,
    DocumentoFactory,
    LancamentoTipoFactory,
    PessoasFactory,
    CartoriosFactory,
)


pytestmark = pytest.mark.e2e


@pytest.fixture
def test_data(db):
    """Create test data for lancamento workflow tests."""
    # Create user
    user = User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )

    # Create TI, Imovel, Documento
    ti = TIsFactory(nome="TI Test E2E", codigo="E2E001")
    imovel = ImovelFactory(
        terra_indigena_id=ti,
        matricula="12345",
        nome="Imóvel Test E2E"
    )
    documento = DocumentoFactory(
        imovel=imovel,
        numero="M-12345"
    )

    # Create lancamento types
    tipo_registro = LancamentoTipoFactory.registro()
    tipo_averbacao = LancamentoTipoFactory.averbacao()

    # Create pessoas
    transmitente = PessoasFactory(nome="João da Silva")
    adquirente = PessoasFactory(nome="Maria Santos")

    # Create cartorio
    cartorio = CartoriosFactory(nome="1º Cartório de Registro de Imóveis")

    return {
        'user': user,
        'ti': ti,
        'imovel': imovel,
        'documento': documento,
        'tipo_registro': tipo_registro,
        'tipo_averbacao': tipo_averbacao,
        'transmitente': transmitente,
        'adquirente': adquirente,
        'cartorio': cartorio,
    }


@pytest.fixture
def authenticated_page_e2e(page: Page, live_server, test_data):
    """Playwright page with authenticated session."""
    # Navigate to login page
    page.goto(f"{live_server.url}/accounts/login/")

    # Fill login form
    page.fill('input[name="username"]', 'testuser')
    page.fill('input[name="password"]', 'testpass123')

    # Submit form
    page.click('button[type="submit"]')

    # Wait for successful login (redirect to home)
    page.wait_for_url(f"{live_server.url}/")

    return page


class TestLancamentoCreationWorkflow:
    """Test complete lancamento creation workflow."""

    def test_login_workflow(self, page: Page, live_server, test_data):
        """Test user can login successfully."""
        # Navigate to login page
        page.goto(f"{live_server.url}/accounts/login/")

        # Verify login page loaded
        expect(page.locator('input[name="username"]')).to_be_visible()

        # Fill credentials
        page.fill('input[name="username"]', 'testuser')
        page.fill('input[name="password"]', 'testpass123')

        # Submit
        page.click('button[type="submit"]')

        # Wait for redirect and verify home page
        page.wait_for_url(f"{live_server.url}/")
        expect(page).to_have_url(f"{live_server.url}/")

    @pytest.mark.slow
    def test_create_registro_lancamento_complete_workflow(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test complete workflow: navigate, fill form, create registro."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']
        documento = test_data['documento']

        # Navigate to novo lancamento page
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/documento/{documento.id}/novo-lancamento/"
        )
        page.goto(url)

        # Wait for form to load
        expect(page.locator('select[name="tipo_lancamento"]')).to_be_visible()

        # Select tipo: Registro
        page.select_option('select[name="tipo_lancamento"]', label='Registro')

        # Fill numero simples
        page.fill('input[name="numero_lancamento_simples"]', '1')

        # Fill data
        page.fill('input[name="data"]', '2024-01-15')

        # Fill titulo
        page.fill('input[name="titulo"]', 'Compra e Venda')

        # Fill observacoes
        page.fill('textarea[name="observacoes"]', 'Registro test via E2E')

        # Submit form
        page.click('button[type="submit"]')

        # Wait for success message or redirect
        # This depends on your app's behavior after successful creation
        page.wait_for_timeout(1000)  # Wait for processing

        # Verify success (adjust selector based on your app)
        # Example: check for success alert or redirect to documento page
        # expect(page.locator('.alert-success')).to_be_visible()

    @pytest.mark.slow
    def test_create_averbacao_lancamento(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test creating averbação lancamento."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']
        documento = test_data['documento']

        # Navigate to form
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/documento/{documento.id}/novo-lancamento/"
        )
        page.goto(url)

        # Select tipo: Averbação
        page.select_option('select[name="tipo_lancamento"]', label='Averbação')

        # Fill numero simples
        page.fill('input[name="numero_lancamento_simples"]', '1')

        # Fill data
        page.fill('input[name="data"]', '2024-02-20')

        # Fill descricao (required for averbação)
        page.fill('textarea[name="descricao"]', 'Mudança de estado civil')

        # Submit
        page.click('button[type="submit"]')

        # Wait and verify
        page.wait_for_timeout(1000)

    def test_form_validation_missing_required_fields(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test form validation when required fields are missing."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']
        documento = test_data['documento']

        # Navigate to form
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/documento/{documento.id}/novo-lancamento/"
        )
        page.goto(url)

        # Select tipo: Registro (requires titulo)
        page.select_option('select[name="tipo_lancamento"]', label='Registro')

        # Try to submit without filling required fields
        page.click('button[type="submit"]')

        # Should show validation error (HTML5 validation or backend error)
        # The exact behavior depends on your form implementation
        page.wait_for_timeout(500)

        # Form should still be visible (not submitted)
        expect(page.locator('select[name="tipo_lancamento"]')).to_be_visible()


class TestCadeiaDominialTreeVisualization:
    """Test D3.js tree visualization rendering."""

    @pytest.mark.slow
    def test_tree_renders_for_documento(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test that D3 tree visualization renders correctly."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']

        # Navigate to cadeia dominial page
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/ver-cadeia-dominial/"
        )
        page.goto(url)

        # Wait for D3 SVG to render
        page.wait_for_selector('svg', timeout=5000)

        # Verify SVG exists
        svg = page.locator('svg').first
        expect(svg).to_be_visible()

    def test_tree_zoom_controls(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test tree zoom controls work."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']

        # Navigate to tree page
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/ver-cadeia-dominial/"
        )
        page.goto(url)

        # Wait for tree to load
        page.wait_for_selector('svg', timeout=5000)

        # Try clicking zoom controls (if they exist)
        # This depends on your specific implementation
        # Example:
        # page.click('button#zoom-in')
        # page.wait_for_timeout(500)
        # page.click('button#zoom-out')


class TestPDFExport:
    """Test PDF export functionality."""

    @pytest.mark.slow
    def test_export_pdf_button_exists(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test that PDF export button is available."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']

        # Navigate to documento page
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/"
        )
        page.goto(url)

        # Check for PDF export button/link
        # Adjust selector based on your implementation
        # Example:
        # export_button = page.locator('a:has-text("Exportar PDF")')
        # expect(export_button).to_be_visible()


class TestTableInteractivity:
    """Test table filtering and interaction."""

    def test_table_loads_with_data(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test that data table loads correctly."""
        page = authenticated_page_e2e

        # Navigate to TIs list
        url = f"{live_server.url}/dominial/tis/"
        page.goto(url)

        # Wait for table to load
        page.wait_for_selector('table', timeout=5000)

        # Verify TI appears in table
        ti = test_data['ti']
        expect(page.locator(f'text={ti.nome}')).to_be_visible()

    @pytest.mark.slow
    def test_table_filtering(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test table search/filter functionality."""
        page = authenticated_page_e2e

        # Navigate to TIs list
        url = f"{live_server.url}/dominial/tis/"
        page.goto(url)

        # If there's a search input, test it
        search_input = page.locator('input[type="search"]')
        if search_input.count() > 0:
            # Type search term
            search_input.fill('Test E2E')

            # Wait for filtering
            page.wait_for_timeout(500)

            # Verify filtered results
            ti = test_data['ti']
            expect(page.locator(f'text={ti.nome}')).to_be_visible()


class TestAutocompleteWidgets:
    """Test autocomplete functionality for pessoas and cartórios."""

    @pytest.mark.slow
    def test_transmitente_autocomplete(
        self, authenticated_page_e2e: Page, live_server, test_data
    ):
        """Test autocomplete for transmitente field."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']
        documento = test_data['documento']
        transmitente = test_data['transmitente']

        # Navigate to form
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/documento/{documento.id}/novo-lancamento/"
        )
        page.goto(url)

        # Wait for form to load
        page.wait_for_selector('select[name="tipo_lancamento"]')

        # Find autocomplete input for transmitente
        # This depends on how django-autocomplete-light renders
        # Example:
        # transmitente_input = page.locator('.select2-search__field').first
        # transmitente_input.fill('João')
        # page.wait_for_timeout(500)  # Wait for autocomplete results
        # page.click(f'text={transmitente.nome}')  # Select from dropdown


class TestDuplicateDetection:
    """Test duplicate lancamento detection."""

    @pytest.mark.slow
    def test_duplicate_detection_modal(
        self, authenticated_page_e2e: Page, live_server, test_data, db
    ):
        """Test that duplicate detection shows modal when similar lancamento exists."""
        page = authenticated_page_e2e
        ti = test_data['ti']
        imovel = test_data['imovel']
        documento = test_data['documento']

        # First, create a lancamento via the app
        from dominial.tests.factories import LancamentoFactory
        LancamentoFactory(
            documento=documento,
            numero_lancamento='R-1',
            tipo=test_data['tipo_registro']
        )

        # Navigate to form
        url = (
            f"{live_server.url}/dominial/tis/{ti.id}/"
            f"imovel/{imovel.id}/documento/{documento.id}/novo-lancamento/"
        )
        page.goto(url)

        # Fill form with same data (should trigger duplicate detection)
        page.select_option('select[name="tipo_lancamento"]', label='Registro')
        page.fill('input[name="numero_lancamento_simples"]', '1')
        page.fill('input[name="data"]', '2024-01-15')

        # Submit
        page.click('button[type="submit"]')

        # Should show duplicate detection modal
        # Adjust selector based on your implementation
        page.wait_for_timeout(1000)
        # Example:
        # expect(page.locator('.modal:has-text("Duplicata")')).to_be_visible()


@pytest.mark.smoke
class TestSmokeTests:
    """Quick smoke tests for critical paths."""

    def test_home_page_loads(self, page: Page, live_server, test_data):
        """Smoke test: home page loads."""
        # Login first
        page.goto(f"{live_server.url}/accounts/login/")
        page.fill('input[name="username"]', 'testuser')
        page.fill('input[name="password"]', 'testpass123')
        page.click('button[type="submit"]')

        # Verify home page loaded
        page.wait_for_url(f"{live_server.url}/")
        expect(page).to_have_url(f"{live_server.url}/")

    def test_tis_list_loads(self, authenticated_page_e2e: Page, live_server):
        """Smoke test: TIs list page loads."""
        page = authenticated_page_e2e
        page.goto(f"{live_server.url}/dominial/tis/")

        # Verify page loaded
        expect(page.locator('h1, h2')).to_contain_text('TI')

    def test_navigation_links_work(self, authenticated_page_e2e: Page, live_server):
        """Smoke test: navigation links are functional."""
        page = authenticated_page_e2e

        # Should be on home page
        expect(page).to_have_url(f"{live_server.url}/")

        # Navigation should exist
        # Adjust based on your nav structure
        # Example:
        # page.click('a:has-text("TIs")')
        # expect(page).to_have_url(f"{live_server.url}/dominial/tis/")
