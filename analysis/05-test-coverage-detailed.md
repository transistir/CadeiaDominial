# Test Coverage Analysis & Testing Strategy

## Current Test Coverage Status

### Overview Statistics

**Production Code:**
- **97 Python files** (excluding migrations)
- **~16,107 lines** of production code

**Test Code:**
- **7 test files** (only)
- **~1,465 lines** of test code
- **Test-to-code ratio:** ~9% (very low - industry standard is 50-200%)

### Existing Test Files

| Test File | Lines | Coverage Area | Quality |
|-----------|-------|---------------|---------|
| `test_documento_lancamento.py` | 510 | Document-lancamento relationships | Good |
| `test_duplicata_verificacao.py` | 388 | Duplicate detection logic | Good |
| `test_fase2_duplicata_integracao.py` | 343 | Duplicate integration workflows | Good |
| `test_documento_importado_service.py` | 180 | Document import service | Moderate |
| `test_api_cnj.py` | 17 | CNJ API integration | Basic |
| `test_onr_post.py` | 19 | ONR POST requests | Basic |
| `test_onr_request.py` | 8 | ONR requests | Minimal |

### Coverage Estimate by Layer

Based on file analysis:

```
┌─────────────────────────────────────────────────────┐
│ Layer          │ Files │ Tested │ Coverage │ Status │
├─────────────────────────────────────────────────────┤
│ Models         │  7    │  ~4    │   ~60%   │   🟡   │
│ Services       │ 30+   │  ~3    │   ~10%   │   🔴   │
│ Views          │  7    │  ~1    │   ~15%   │   🔴   │
│ Forms          │  5    │  ~0    │    ~0%   │   🔴   │
│ Utils          │  3    │  ~1    │   ~30%   │   🟠   │
│ Admin          │  1    │  ~0    │    ~0%   │   🔴   │
│ Frontend (JS)  │  7    │   0    │    0%    │   🔴   │
│ Templates      │ 40+   │   0    │    0%    │   🔴   │
├─────────────────────────────────────────────────────┤
│ OVERALL        │ 100+  │  ~8    │  ~15%    │   🔴   │
└─────────────────────────────────────────────────────┘
```

**Status:** 🔴 Critical Gap - Well below acceptable coverage

---

## Critical Gaps - Untested Code

### 1. Untested Services (30+ services, ~90% untested) 🔴

**High-Risk Untested Services:**

#### `hierarquia_arvore_service.py` (351 lines) - 0% coverage
**Why Critical:** Core tree visualization logic
**Risk:** Broken chain visualization, incorrect hierarchy
**Test Priority:** P0 (Highest)

**Needed Tests:**
```python
# test_hierarquia_arvore_service.py

class TestHierarquiaArvoreService:
    """Critical service - tree building logic"""

    def test_build_simple_chain(self, db):
        """Test building 2-document chain"""
        doc1 = DocumentoFactory(numero="M-001")
        doc2 = DocumentoFactory(numero="M-002")
        LancamentoFactory(documento=doc2, documento_origem=doc1)

        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc2.id)

        assert tree['id'] == f"doc_{doc2.id}"
        assert len(tree['children']) == 1
        assert tree['children'][0]['id'] == f"doc_{doc1.id}"

    def test_circular_reference_handling(self, db):
        """Test that circular references don't cause infinite loop"""
        doc1 = DocumentoFactory(numero="M-001")
        doc2 = DocumentoFactory(numero="M-002")

        # Create circular reference
        LancamentoFactory(documento=doc2, documento_origem=doc1)
        LancamentoFactory(documento=doc1, documento_origem=doc2)

        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc1.id)

        assert tree is not None
        # Should detect and break cycle

    def test_multiple_origins_handling(self, db):
        """Test document with multiple possible origins"""
        doc1 = DocumentoFactory(numero="M-001")
        doc2 = DocumentoFactory(numero="M-002")
        doc3 = DocumentoFactory(numero="M-003")

        lancamento = LancamentoFactory(documento=doc3)
        lancamento.origem = "Origem: M-001 ou M-002"
        lancamento.save()

        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc3.id)

        assert len(tree.get('children', [])) >= 1

    def test_end_of_chain_detection(self, db):
        """Test end-of-chain node creation"""
        doc = DocumentoFactory(numero="M-001")
        lanc = LancamentoFactory(documento=doc)
        lanc.origem = "Destacamento Público: INCRA"
        lanc.save()

        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc.id)

        # Should have end-of-chain node
        assert any('fim_cadeia' in str(child) for child in tree.get('children', []))

    def test_performance_large_chain(self, db):
        """Test performance with 50-document chain"""
        docs = [DocumentoFactory(numero=f"M-{i:03d}") for i in range(50)]

        # Link documents in chain
        for i in range(1, 50):
            LancamentoFactory(documento=docs[i], documento_origem=docs[i-1])

        import time
        start = time.time()
        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(docs[-1].id)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Too slow: {elapsed}s"
        assert tree is not None
```

**Estimated Effort:** 3-4 days

---

#### `lancamento_criacao_service.py` (423 lines) - 0% coverage
**Why Critical:** Transaction creation workflow, data integrity
**Risk:** Data corruption, duplicate records, broken chains
**Test Priority:** P0 (Highest)

**Needed Tests:**
```python
# test_lancamento_criacao_service.py

class TestLancamentoCriacaoService:
    """Critical service - lancamento creation"""

    def test_create_registro_with_valid_data(self, db):
        """Test creating registro with all required fields"""
        documento = DocumentoFactory()
        tipo_registro = LancamentoTipoFactory(tipo='registro')

        data = {
            'tipo_lancamento': tipo_registro.id,
            'numero_lancamento_simples': 'R-1',
            'data': '2024-01-15',
            'transmitente': [PessoasFactory().id],
            'adquirente': [PessoasFactory().id],
            'titulo': 'Compra e Venda',
        }

        # Mock request
        request = MockRequest(POST=data)

        result = LancamentoCriacaoService.criar_lancamento_completo(
            request, TIsFactory(), ImovelFactory(), documento
        )

        assert result is not None
        # Verify lancamento created
        assert Lancamento.objects.filter(documento=documento).exists()

    def test_create_with_missing_required_field_fails(self, db):
        """Test that missing required fields cause validation error"""
        documento = DocumentoFactory()
        tipo_registro = LancamentoTipoFactory(tipo='registro')

        data = {
            'tipo_lancamento': tipo_registro.id,
            'numero_lancamento_simples': 'R-1',
            'data': '2024-01-15',
            # Missing: transmitente (required for registro)
        }

        request = MockRequest(POST=data)

        result = LancamentoCriacaoService.criar_lancamento_completo(
            request, TIsFactory(), ImovelFactory(), documento
        )

        # Should fail validation
        assert result[0] is None  # No lancamento created
        assert 'obrigatório' in result[1].lower()

    def test_duplicate_detection_prevents_creation(self, db):
        """Test that duplicate lancamento is detected"""
        documento = DocumentoFactory()
        existing = LancamentoFactory(
            documento=documento,
            numero_lancamento='R-1'
        )

        data = {
            'tipo_lancamento': existing.tipo.id,
            'numero_lancamento_simples': 'R-1',
            'data': str(existing.data),
        }

        request = MockRequest(POST=data)

        result = LancamentoCriacaoService.criar_lancamento_completo(
            request, TIsFactory(), ImovelFactory(), documento
        )

        # Should detect duplicate
        assert isinstance(result[0], dict)
        assert result[0].get('tipo') == 'duplicata_encontrada'

    def test_origin_processing(self, db):
        """Test automatic origin document linking"""
        imovel = ImovelFactory()
        doc_origem = DocumentoFactory(imovel=imovel, numero="M-001")
        doc_atual = DocumentoFactory(imovel=imovel, numero="M-002")

        data = {
            'tipo_lancamento': LancamentoTipoFactory(tipo='registro').id,
            'numero_lancamento_simples': 'R-1',
            'data': '2024-01-15',
            'origem_completa[]': [f'Origem: Matrícula {doc_origem.numero}'],
            'cartorio_origem[]': [str(doc_origem.cartorio.id)],
        }

        request = MockRequest(POST=data)

        result = LancamentoCriacaoService.criar_lancamento_completo(
            request, imovel.terra_indigena_id, imovel, doc_atual
        )

        # Verify origin linked
        lancamento = Lancamento.objects.get(documento=doc_atual)
        assert lancamento.documento_origem == doc_origem
```

**Estimated Effort:** 4-5 days

---

#### `cadeia_dominial_tabela_service.py` (554 lines) - 0% coverage
**Why Critical:** Table data generation for reports
**Risk:** Incorrect data in exports, missing transactions
**Test Priority:** P1 (High)

**Needed Tests:**
```python
# test_cadeia_dominial_tabela_service.py

class TestCadeiaDominialTabelaService:
    """Table generation service tests"""

    def test_generate_table_all_documents(self, db):
        """Test generating table with all documents"""
        imovel = ImovelFactory()
        doc1 = DocumentoFactory(imovel=imovel)
        doc2 = DocumentoFactory(imovel=imovel)

        LancamentoFactory(documento=doc1)
        LancamentoFactory(documento=doc2)

        filtros = {'mostrar_documentos': 'todos'}
        dados = CadeiaDominialTabelaService.obter_dados_tabela(doc1.id, filtros)

        assert len(dados['documentos']) == 2

    def test_filter_own_documents_only(self, db):
        """Test filtering to show only own cartorio documents"""
        imovel = ImovelFactory()
        cartorio1 = CartoriosFactory()
        cartorio2 = CartoriosFactory()

        doc1 = DocumentoFactory(imovel=imovel, cartorio=cartorio1)
        doc2 = DocumentoFactory(imovel=imovel, cartorio=cartorio2)

        filtros = {
            'mostrar_documentos': 'proprios',
            'cartorio_principal': cartorio1.id
        }
        dados = CadeiaDominialTabelaService.obter_dados_tabela(doc1.id, filtros)

        # Should only show doc1
        assert len(dados['documentos']) == 1
        assert dados['documentos'][0].id == doc1.id

    def test_statistics_calculation(self, db):
        """Test that statistics are calculated correctly"""
        documento = DocumentoFactory()

        # Create 3 registros, 2 averbações
        tipo_registro = LancamentoTipoFactory(tipo='registro')
        tipo_averbacao = LancamentoTipoFactory(tipo='averbacao')

        for _ in range(3):
            LancamentoFactory(documento=documento, tipo=tipo_registro)
        for _ in range(2):
            LancamentoFactory(documento=documento, tipo=tipo_averbacao)

        dados = CadeiaDominialTabelaService.obter_dados_tabela(
            documento.id, {}
        )

        assert dados['estatisticas']['total_registros'] == 3
        assert dados['estatisticas']['total_averbacoes'] == 2
        assert dados['estatisticas']['total_lancamentos'] == 5
```

**Estimated Effort:** 3 days

---

### 2. Untested Views (~85% untested) 🔴

**Critical Views to Test:**

#### `lancamento_views.py` - 0% coverage
**Why Critical:** Main user interaction point
**Risk:** Form validation issues, data corruption
**Test Priority:** P1 (High)

**Needed Tests:**
```python
# test_lancamento_views.py

class TestLancamentoViews:
    """View layer tests"""

    def test_novo_lancamento_get_shows_form(self, client, db):
        """Test GET request shows form"""
        user = UserFactory()
        client.force_login(user)

        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)

        url = reverse('novo_lancamento', args=[ti.id, imovel.id, documento.id])
        response = client.get(url)

        assert response.status_code == 200
        assert 'documento' in response.context

    def test_novo_lancamento_post_creates_lancamento(self, client, db):
        """Test POST creates lancamento"""
        user = UserFactory()
        client.force_login(user)

        ti = TIsFactory()
        imovel = ImovelFactory(terra_indigena_id=ti)
        documento = DocumentoFactory(imovel=imovel)
        tipo = LancamentoTipoFactory(tipo='registro')

        url = reverse('novo_lancamento', args=[ti.id, imovel.id, documento.id])
        response = client.post(url, {
            'tipo_lancamento': tipo.id,
            'numero_lancamento_simples': 'R-1',
            'data': '2024-01-15',
            'transmitente[]': [PessoasFactory().id],
            'adquirente[]': [PessoasFactory().id],
        })

        # Should redirect on success
        assert response.status_code == 302

        # Lancamento should exist
        assert Lancamento.objects.filter(documento=documento).exists()

    def test_editar_lancamento_updates_data(self, client, db):
        """Test editing lancamento"""
        user = UserFactory()
        client.force_login(user)

        lancamento = LancamentoFactory()

        url = reverse('editar_lancamento', args=[
            lancamento.documento.imovel.terra_indigena_id.id,
            lancamento.documento.imovel.id,
            lancamento.id
        ])

        new_observacoes = "Updated observations"
        response = client.post(url, {
            # ... other fields
            'observacoes': new_observacoes,
        })

        lancamento.refresh_from_db()
        assert lancamento.observacoes == new_observacoes
```

**Estimated Effort:** 4-5 days

---

### 3. Frontend Tests (0% coverage) 🔴

**No JavaScript tests exist!**

#### Setup Playwright for E2E Tests

**Recommended Setup:**

```bash
# Install Playwright
pip install pytest-playwright
playwright install
```

**Configuration:**
```python
# conftest.py (add Playwright fixtures)
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()

@pytest.fixture
def page(browser, live_server):
    context = browser.new_context()
    page = context.new_page()
    page.goto(live_server.url)
    yield page
    context.close()
```

**Critical E2E Tests Needed:**

```python
# tests/e2e/test_lancamento_creation_flow.py

class TestLancamentoCreationE2E:
    """End-to-end tests for lancamento creation"""

    def test_complete_lancamento_creation_workflow(self, page, live_server, db):
        """Test complete user workflow: login -> create lancamento"""
        # Setup test data
        user = UserFactory(username='testuser', password='testpass')
        ti = TIsFactory(nome="TI Test")
        imovel = ImovelFactory(terra_indigena_id=ti, matricula="M-001")
        documento = DocumentoFactory(imovel=imovel, numero="M-001")

        # 1. Login
        page.goto(f"{live_server.url}/accounts/login/")
        page.fill('input[name="username"]', 'testuser')
        page.fill('input[name="password"]', 'testpass')
        page.click('button[type="submit"]')

        # Wait for redirect to home
        page.wait_for_url(f"{live_server.url}/")

        # 2. Navigate to TI
        page.click(f'text="{ti.nome}"')

        # 3. Navigate to Imovel
        page.click(f'text="{imovel.matricula}"')

        # 4. Click "Novo Lançamento"
        page.click('text="Novo Lançamento"')

        # 5. Fill form
        page.select_option('select[name="tipo_lancamento"]', label='Registro')
        page.fill('input[name="numero_lancamento_simples"]', 'R-1')
        page.fill('input[name="data"]', '2024-01-15')

        # Use autocomplete for transmitente
        page.fill('input[name="transmitente_nome[]"]', 'João Silva')
        page.wait_for_selector('.select2-results')
        page.click('.select2-results__option:has-text("João Silva")')

        # 6. Submit form
        page.click('button[type="submit"]')

        # 7. Verify success
        page.wait_for_selector('text="Lançamento criado com sucesso"')

        # Verify in database
        assert Lancamento.objects.filter(
            documento=documento,
            numero_lancamento='R-1'
        ).exists()

    def test_duplicate_detection_shows_warning(self, page, live_server, db):
        """Test that duplicate detection shows modal"""
        # Setup
        user = UserFactory(username='testuser')
        documento = DocumentoFactory()
        existing = LancamentoFactory(documento=documento, numero_lancamento='R-1')

        # Login
        page.goto(f"{live_server.url}/accounts/login/")
        # ... login steps ...

        # Navigate to new lancamento form
        # ... navigation steps ...

        # Fill form with duplicate data
        page.fill('input[name="numero_lancamento_simples"]', 'R-1')
        page.fill('input[name="data"]', str(existing.data))

        # Submit
        page.click('button[type="submit"]')

        # Should show duplicate modal
        page.wait_for_selector('.modal:has-text("Duplicata")')

        # Modal should have options
        assert page.is_visible('button:has-text("Cancelar")')
        assert page.is_visible('button:has-text("Importar")')

    def test_tree_visualization_renders(self, page, live_server, db):
        """Test D3 tree visualization renders correctly"""
        # Setup chain: doc1 -> doc2 -> doc3
        user = UserFactory()
        imovel = ImovelFactory()
        doc1 = DocumentoFactory(imovel=imovel, numero="M-001")
        doc2 = DocumentoFactory(imovel=imovel, numero="M-002")
        doc3 = DocumentoFactory(imovel=imovel, numero="M-003")

        LancamentoFactory(documento=doc2, documento_origem=doc1)
        LancamentoFactory(documento=doc3, documento_origem=doc2)

        # Login and navigate
        # ... login/navigation ...

        # Go to chain view
        page.goto(f"{live_server.url}/tis/{imovel.terra_indigena_id.id}/imovel/{imovel.id}/cadeia-dominial/")

        # Wait for D3 to render
        page.wait_for_selector('svg#tree-svg')

        # Verify nodes exist
        nodes = page.query_selector_all('.node')
        assert len(nodes) == 3

        # Test zoom controls
        page.click('#zoom-in')
        # Verify zoom changed (check transform attribute)

        # Test node click
        nodes[0].click()
        # Should show details or modal

    def test_table_view_filtering(self, page, live_server, db):
        """Test table view filter controls"""
        # Setup
        user = UserFactory()
        documento = DocumentoFactory()

        # Create mix of registros and averbações
        tipo_registro = LancamentoTipoFactory(tipo='registro')
        tipo_averbacao = LancamentoTipoFactory(tipo='averbacao')

        for _ in range(3):
            LancamentoFactory(documento=documento, tipo=tipo_registro)
        for _ in range(2):
            LancamentoFactory(documento=documento, tipo=tipo_averbacao)

        # Navigate to table view
        # ... navigation ...

        # Initially should show all (5 rows)
        rows = page.query_selector_all('tr.lancamento-row')
        assert len(rows) == 5

        # Filter to only registros
        page.select_option('select[name="mostrar_lancamentos"]', 'registros')
        page.click('button:has-text("Filtrar")')

        # Should show only 3 rows
        page.wait_for_selector('tr.lancamento-row')
        rows = page.query_selector_all('tr.lancamento-row')
        assert len(rows) == 3

    def test_pdf_export_downloads(self, page, live_server, db):
        """Test PDF export triggers download"""
        # Setup
        user = UserFactory()
        imovel = ImovelFactory()

        # Navigate to chain view
        # ... navigation ...

        # Click export PDF
        with page.expect_download() as download_info:
            page.click('button:has-text("Exportar PDF")')

        download = download_info.value
        assert download.suggested_filename.endswith('.pdf')

    def test_excel_export_downloads(self, page, live_server, db):
        """Test Excel export triggers download"""
        # Setup
        user = UserFactory()
        imovel = ImovelFactory()

        # Navigate to chain view
        # ... navigation ...

        # Click export Excel
        with page.expect_download() as download_info:
            page.click('button:has-text("Exportar Excel")')

        download = download_info.value
        assert download.suggested_filename.endswith('.xlsx')
```

**Estimated Effort:** 2-3 weeks for comprehensive E2E tests

---

## Test Infrastructure Recommendations

### 1. Setup pytest and fixtures

```bash
pip install pytest pytest-django pytest-cov factory-boy pytest-playwright
```

**Create test configuration:**

```python
# pytest.ini
[pytest]
DJANGO_SETTINGS_MODULE = cadeia_dominial.settings
python_files = tests.py test_*.py *_tests.py
testpaths = dominial/tests tests/e2e
addopts =
    --strict-markers
    --cov=dominial
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=60
```

### 2. Create Factory Classes

```python
# dominial/tests/factories.py
import factory
from factory.django import DjangoModelFactory
from dominial.models import TIs, Imovel, Documento, Lancamento, Pessoas, Cartorios

class TIsFactory(DjangoModelFactory):
    class Meta:
        model = TIs

    nome = factory.Sequence(lambda n: f"TI Test {n}")
    codigo = factory.Sequence(lambda n: f"TST{n:03d}")
    etnia = "Test Etnia"
    estado = "BA"

class PessoasFactory(DjangoModelFactory):
    class Meta:
        model = Pessoas

    nome = factory.Faker('name', locale='pt_BR')
    cpf = factory.Sequence(lambda n: f"{n:011d}")

class CartoriosFactory(DjangoModelFactory):
    class Meta:
        model = Cartorios

    nome = factory.Sequence(lambda n: f"CRI Test {n}")
    cns = factory.Sequence(lambda n: f"BA{n:04d}")
    cidade = "Salvador"
    estado = "BA"

class ImovelFactory(DjangoModelFactory):
    class Meta:
        model = Imovel

    terra_indigena_id = factory.SubFactory(TIsFactory)
    proprietario = factory.SubFactory(PessoasFactory)
    matricula = factory.Sequence(lambda n: f"M-{n:03d}")
    nome = factory.Faker('company', locale='pt_BR')
    cartorio = factory.SubFactory(CartoriosFactory)

class DocumentoFactory(DjangoModelFactory):
    class Meta:
        model = Documento

    imovel = factory.SubFactory(ImovelFactory)
    tipo = factory.SubFactory('dominial.tests.factories.DocumentoTipoFactory')
    numero = factory.Sequence(lambda n: f"M-{n:03d}")
    data = factory.Faker('date_this_decade')
    cartorio = factory.SubFactory(CartoriosFactory)
    livro = factory.Sequence(lambda n: f"Livro {n}")
    folha = factory.Sequence(lambda n: f"{n}")

class LancamentoFactory(DjangoModelFactory):
    class Meta:
        model = Lancamento

    documento = factory.SubFactory(DocumentoFactory)
    tipo = factory.SubFactory('dominial.tests.factories.LancamentoTipoFactory')
    numero_lancamento = factory.Sequence(lambda n: f"R-{n}")
    data = factory.Faker('date_this_year')
```

### 3. CI/CD Integration

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_cadeia_dominial
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-django pytest-cov factory-boy pytest-playwright
        playwright install chromium

    - name: Run unit tests
      env:
        DATABASE_URL: postgresql://test_user:test_pass@localhost:5432/test_cadeia_dominial
      run: |
        pytest dominial/tests --cov=dominial --cov-report=xml

    - name: Run E2E tests
      env:
        DATABASE_URL: postgresql://test_user:test_pass@localhost:5432/test_cadeia_dominial
      run: |
        pytest tests/e2e --headed=false

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## Testing Roadmap

### Phase 1 (Week 1-2) - Infrastructure ✅
- [ ] Install pytest, factory-boy, playwright
- [ ] Create factories for all models
- [ ] Configure pytest.ini
- [ ] Set up CI/CD

### Phase 2 (Week 3-6) - Critical Services 🔴
- [ ] Test `hierarquia_arvore_service.py` (3-4 days)
- [ ] Test `lancamento_criacao_service.py` (4-5 days)
- [ ] Test `cadeia_dominial_tabela_service.py` (3 days)
- [ ] Test `lancamento_origem_service.py` (3 days)

**Target:** 60%+ service coverage

### Phase 3 (Week 7-10) - Views 🟡
- [ ] Test `lancamento_views.py` (4-5 days)
- [ ] Test `cadeia_dominial_views.py` (4-5 days)
- [ ] Test `documento_views.py` (3 days)
- [ ] Test API views (2 days)

**Target:** 70%+ view coverage

### Phase 4 (Week 11-14) - E2E with Playwright 🔵
- [ ] Setup Playwright (2 days)
- [ ] Test lancamento creation flow (3 days)
- [ ] Test chain visualization (D3 tree) (4 days)
- [ ] Test table filtering (2 days)
- [ ] Test export (PDF/Excel) (2 days)
- [ ] Test duplicate detection flow (2 days)

**Target:** All critical user journeys covered

### Phase 5 (Week 15-16) - Model & Integration ✅
- [ ] Test all model validations (3 days)
- [ ] Test all foreign key constraints (2 days)
- [ ] Integration workflow tests (3 days)

**Target:** 80%+ overall coverage

---

## Summary

**Current State:**
- ❌ Only **7 test files** (very low)
- ❌ ~**15% overall coverage** (critical gap)
- ❌ **0% frontend tests**
- ❌ **90% of services untested**
- ❌ **85% of views untested**

**Recommended Actions:**
1. **Immediate (Week 1-2):** Set up test infrastructure
2. **Priority (Week 3-6):** Test critical services (hierarquia, lancamento creation)
3. **Important (Week 7-10):** Test views
4. **Strategic (Week 11-14):** Add Playwright E2E tests
5. **Comprehensive (Week 15-16):** Models and integration

**Expected Outcome (16 weeks):**
- ✅ **80%+ overall coverage**
- ✅ **100% critical service coverage**
- ✅ **75%+ view coverage**
- ✅ **Complete E2E test suite**
- ✅ **CI/CD with automatic testing**
- ✅ **Confidence to refactor safely**

**Estimated Effort:** 4 months full-time or 6 months part-time

**ROI:** Massive - catch bugs early, safe refactoring, prevent regressions, better code quality
