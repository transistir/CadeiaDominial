# Testing Gaps - Maintainability Analysis

## Executive Summary

This document identifies **testing gaps** in the Sistema de Cadeia Dominial codebase. While the project has 8 test files, there are significant areas lacking test coverage that could lead to regressions and make refactoring risky.

**Current Test Coverage:**
- **Test Files:** 8 files
- **Largest Test:** `test_documento_lancamento.py` (23KB)
- **Focus Areas:** Document/lancamento relationships, duplicate verification
- **Gaps:** Many services, views, and critical workflows untested

---

## 1. Test Coverage Overview

### Current Test Files

| Test File | Size | Coverage Area |
|-----------|------|---------------|
| `test_documento_lancamento.py` | 23KB | Document-lancamento relationships |
| `test_duplicata_verificacao.py` | 14KB | Duplicate detection |
| `test_fase2_duplicata_integracao.py` | 13KB | Duplicate integration workflows |
| `test_api_views.py` | Small | API endpoints |
| `test_imports.py` | Small | Import functionality |
| Others | Small | Various specific features |

### Coverage Estimation

Based on file analysis:
- **Models:** ~60% covered (basic CRUD, relationships)
- **Services:** ~30% covered (only some services tested)
- **Views:** ~15% covered (mostly untested)
- **Frontend:** ~0% covered (no JavaScript tests)

---

## 2. Critical Gaps by Layer

### 2.1 Service Layer Gaps 🔴 Critical

**Untested Services (0% coverage):**

1. **`hierarquia_arvore_service.py` (351 lines)**
   - Tree building logic
   - Complex origin traversal
   - Multiple recursion paths
   - **Risk:** Bugs in tree visualization

2. **`cadeia_dominial_tabela_service.py` (554 lines)**
   - Table data generation
   - Filter application
   - Complex grouping logic
   - **Risk:** Incorrect data in reports

3. **`lancamento_criacao_service.py` (423 lines)**
   - Lancamento creation workflow
   - Critical business logic
   - Multiple validation paths
   - **Risk:** Data corruption

4. **`lancamento_origem_service.py` (517 lines)**
   - Origin detection
   - Complex parsing logic
   - Document linking
   - **Risk:** Broken chain links

5. **`cadeia_completa_service.py` (423 lines)**
   - Complete chain generation
   - PDF/Excel data preparation
   - **Risk:** Incorrect exports

**Recommended Test Coverage:**

```python
# tests/test_hierarquia_arvore_service.py
import pytest
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.models import Documento, Lancamento

class TestHierarquiaArvoreService:
    """Test suite for tree building service"""

    def test_build_simple_chain(self, db):
        """Test building a simple 2-document chain"""
        # Given: Two linked documents
        doc1 = create_documento(numero="M-001")
        doc2 = create_documento(numero="M-002")
        create_lancamento(documento=doc2, documento_origem=doc1)

        # When: Building tree
        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc2.id)

        # Then: Tree has 2 levels
        assert tree is not None
        assert len(tree['children']) == 1
        assert tree['children'][0]['id'] == f"doc_{doc1.id}"

    def test_build_complex_chain_with_multiple_origins(self, db):
        """Test building chain with multiple possible origins"""
        # Given: Document with 2 possible origins
        doc1 = create_documento(numero="M-001")
        doc2 = create_documento(numero="M-002")
        doc3 = create_documento(numero="M-003")

        lancamento = create_lancamento(documento=doc3)
        # Reference both doc1 and doc2 in origem field
        lancamento.origem = "Origem: M-001 ou M-002"
        lancamento.save()

        # When: Building tree
        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc3.id)

        # Then: Tree shows both branches
        assert len(tree['children']) == 2

    def test_circular_reference_prevention(self, db):
        """Test that circular references are handled"""
        # Given: Circular reference A -> B -> A
        doc1 = create_documento(numero="M-001")
        doc2 = create_documento(numero="M-002")

        lanc1 = create_lancamento(documento=doc2, documento_origem=doc1)
        lanc2 = create_lancamento(documento=doc1, documento_origem=doc2)

        # When: Building tree
        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc1.id)

        # Then: Should not infinite loop
        assert tree is not None
        # Should detect and break circular reference

    def test_end_of_chain_detection(self, db):
        """Test end-of-chain node creation"""
        # Given: Document with end-of-chain origin
        doc = create_documento(numero="M-001")
        lanc = create_lancamento(documento=doc)
        lanc.origem = "Destacamento Público: INCRA"
        lanc.save()

        # When: Building tree
        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(doc.id)

        # Then: Tree has end-of-chain node
        assert tree['children'][0]['tipo'] == 'fim_cadeia'
        assert 'INCRA' in tree['children'][0]['nome']

    def test_performance_with_large_chain(self, db):
        """Test performance with 100-document chain"""
        # Given: Chain of 100 documents
        docs = [create_documento(numero=f"M-{i:03d}") for i in range(100)]
        for i in range(1, 100):
            create_lancamento(documento=docs[i], documento_origem=docs[i-1])

        # When: Building tree (should complete in reasonable time)
        import time
        start = time.time()
        tree = HierarquiaArvoreService.construir_arvore_cadeia_dominial(docs[-1].id)
        elapsed = time.time() - start

        # Then: Completes within 5 seconds
        assert elapsed < 5.0
        assert tree is not None
```

**Estimated Effort:** 2-3 weeks for all critical services

---

### 2.2 View Layer Gaps 🔴 Critical

**Untested Views (~85% of views):**

1. **`lancamento_views.py` (34KB)** - Largest, most complex view
   - `novo_lancamento` - Complex creation workflow
   - `editar_lancamento` - Edit logic
   - `excluir_lancamento` - Deletion

2. **`cadeia_dominial_views.py` (35KB)**
   - `cadeia_dominial_d3` - Tree visualization
   - `cadeia_dominial_tabela` - Table view
   - `exportar_cadeia_completa_pdf` - PDF export
   - `exportar_cadeia_dominial_excel` - Excel export

3. **`documento_views.py`**
   - Document CRUD operations
   - Auto-creation logic

**Recommended View Tests:**

```python
# tests/test_lancamento_views.py
from django.test import TestCase, Client
from django.urls import reverse
from dominial.models import TIs, Imovel, Documento, Lancamento

class TestLancamentoViews(TestCase):
    """Test suite for lancamento views"""

    def setUp(self):
        self.client = Client()
        self.user = create_user()
        self.client.force_login(self.user)

        self.ti = create_ti()
        self.imovel = create_imovel(ti=self.ti)
        self.documento = create_documento(imovel=self.imovel)

    def test_novo_lancamento_get(self):
        """Test GET request shows form"""
        url = reverse('novo_lancamento', args=[
            self.ti.id, self.imovel.id, self.documento.id
        ])
        response = self.client.get(url)

        assert response.status_code == 200
        assert 'form' in response.context

    def test_novo_lancamento_post_valid_data(self):
        """Test POST with valid data creates lancamento"""
        url = reverse('novo_lancamento', args=[
            self.ti.id, self.imovel.id, self.documento.id
        ])
        data = {
            'tipo_lancamento': create_lancamento_tipo().id,
            'numero_lancamento_simples': '1',
            'data': '2024-01-15',
            'descricao': 'Test lancamento',
        }
        response = self.client.post(url, data)

        # Should redirect on success
        assert response.status_code == 302

        # Lancamento should be created
        assert Lancamento.objects.filter(
            documento=self.documento
        ).exists()

    def test_novo_lancamento_post_duplicate_detection(self):
        """Test duplicate detection shows warning"""
        # Create existing lancamento
        existing = create_lancamento(documento=self.documento)

        # Try to create duplicate
        url = reverse('novo_lancamento', args=[
            self.ti.id, self.imovel.id, self.documento.id
        ])
        data = {
            'tipo_lancamento': existing.tipo.id,
            'numero_lancamento_simples': existing.numero_lancamento,
            'data': str(existing.data),
        }
        response = self.client.post(url, data)

        # Should show duplicate warning
        assert response.status_code == 200
        assert 'duplicata' in response.context

    def test_editar_lancamento_updates_data(self):
        """Test editing lancamento updates fields"""
        lancamento = create_lancamento(documento=self.documento)

        url = reverse('editar_lancamento', args=[
            self.ti.id, self.imovel.id, lancamento.id
        ])
        data = {
            'descricao': 'Updated description',
            # ... other fields
        }
        response = self.client.post(url, data)

        # Refresh from DB
        lancamento.refresh_from_db()
        assert lancamento.descricao == 'Updated description'

    def test_excluir_lancamento_requires_confirmation(self):
        """Test deletion requires POST"""
        lancamento = create_lancamento(documento=self.documento)

        url = reverse('excluir_lancamento', args=[
            self.ti.id, self.imovel.id, lancamento.id
        ])

        # GET should show confirmation page
        response = self.client.get(url)
        assert response.status_code == 200

        # POST should delete
        response = self.client.post(url)
        assert response.status_code == 302
        assert not Lancamento.objects.filter(id=lancamento.id).exists()
```

**Estimated Effort:** 2-3 weeks

---

### 2.3 Model Validation Gaps 🟡 High

**Missing Model Tests:**

1. **Unique constraints**
   - Test CPF uniqueness in Pessoas
   - Test (numero, cartorio) uniqueness in Documento
   - Test CNS uniqueness in Cartorios

2. **Foreign key constraints**
   - Test CASCADE deletion behavior
   - Test PROTECT prevention

3. **Custom validation**
   - Test model.clean() methods
   - Test field validators

**Recommended Model Tests:**

```python
# tests/test_models.py
import pytest
from django.db import IntegrityError
from django.core.exceptions import ValidationError

class TestPessoasModel:
    """Test Pessoas model"""

    def test_cpf_must_be_unique(self, db):
        """Test that duplicate CPF raises error"""
        create_pessoa(cpf="12345678901")

        with pytest.raises(IntegrityError):
            create_pessoa(cpf="12345678901")

    def test_pessoa_without_cpf_is_valid(self, db):
        """Test pessoa can be created without CPF"""
        pessoa = create_pessoa(cpf=None)
        assert pessoa.id is not None

class TestDocumentoModel:
    """Test Documento model"""

    def test_numero_cartorio_must_be_unique(self, db):
        """Test (numero, cartorio) uniqueness"""
        cartorio = create_cartorio()
        create_documento(numero="M-001", cartorio=cartorio)

        with pytest.raises(IntegrityError):
            create_documento(numero="M-001", cartorio=cartorio)

    def test_same_numero_different_cartorio_is_valid(self, db):
        """Test same numero in different cartorio is allowed"""
        cartorio1 = create_cartorio(cns="BA0001")
        cartorio2 = create_cartorio(cns="BA0002")

        doc1 = create_documento(numero="M-001", cartorio=cartorio1)
        doc2 = create_documento(numero="M-001", cartorio=cartorio2)

        assert doc1.id != doc2.id

    def test_cascade_delete_lancamentos(self, db):
        """Test deleting documento deletes lancamentos"""
        documento = create_documento()
        lanc1 = create_lancamento(documento=documento)
        lanc2 = create_lancamento(documento=documento)

        documento.delete()

        assert not Lancamento.objects.filter(id=lanc1.id).exists()
        assert not Lancamento.objects.filter(id=lanc2.id).exists()

class TestLancamentoModel:
    """Test Lancamento model"""

    def test_clean_validates_required_fields_by_type(self, db):
        """Test model validation enforces type-specific requirements"""
        tipo_registro = create_lancamento_tipo(tipo='registro')

        # Registro requires transmitente
        lancamento = Lancamento(
            tipo=tipo_registro,
            documento=create_documento(),
            data='2024-01-15'
            # Missing transmitente!
        )

        with pytest.raises(ValidationError):
            lancamento.full_clean()
```

**Estimated Effort:** 1 week

---

### 2.4 Integration Test Gaps 🟡 High

**Missing Integration Tests:**

1. **Complete Workflow Tests**
   - End-to-end lancamento creation
   - Complete chain building
   - PDF/Excel generation

2. **User Journey Tests**
   - Create TI → Imovel → Documento → Lancamento
   - View chain → Select origin → Re-view chain
   - Import duplicate → Merge → Verify

**Recommended Integration Tests:**

```python
# tests/test_integration_workflows.py
class TestLancamentoCreationWorkflow:
    """Integration test for complete lancamento creation"""

    def test_create_lancamento_end_to_end(self, db, client):
        """Test complete workflow from TI to lancamento"""
        # Setup
        user = create_user()
        client.force_login(user)

        # 1. Create TI
        ti = create_ti(nome="TI Test", codigo="TST001")

        # 2. Create Imovel
        imovel = create_imovel(
            terra_indigena_id=ti,
            matricula="M-001"
        )

        # 3. Create Documento
        documento = create_documento(
            imovel=imovel,
            numero="M-001"
        )

        # 4. Create Lancamento via view
        url = reverse('novo_lancamento', args=[ti.id, imovel.id, documento.id])
        response = client.post(url, {
            'tipo_lancamento': create_lancamento_tipo(tipo='registro').id,
            'numero_lancamento_simples': 'R-1',
            'data': '2024-01-15',
            'transmitente[]': [create_pessoa().id],
            'adquirente[]': [create_pessoa().id],
            'titulo': 'Compra e Venda',
        })

        # Verify
        assert response.status_code == 302  # Redirect on success
        assert Lancamento.objects.filter(documento=documento).exists()

        lancamento = Lancamento.objects.get(documento=documento)
        assert lancamento.numero_lancamento == 'R-1'
        assert lancamento.tipo.tipo == 'registro'

class TestCadeiaDominialWorkflow:
    """Integration test for chain visualization"""

    def test_view_complete_chain(self, db, client):
        """Test viewing complete property chain"""
        # Setup: Create chain A -> B -> C
        user = create_user()
        client.force_login(user)

        ti = create_ti()
        imovel = create_imovel(ti=ti)

        doc_a = create_documento(imovel=imovel, numero="M-001")
        doc_b = create_documento(imovel=imovel, numero="M-002")
        doc_c = create_documento(imovel=imovel, numero="M-003")

        create_lancamento(documento=doc_b, documento_origem=doc_a)
        create_lancamento(documento=doc_c, documento_origem=doc_b)

        # View chain
        url = reverse('cadeia_dominial_d3', args=[ti.id, imovel.id])
        response = client.get(url)

        assert response.status_code == 200
        assert 'tree_data' in response.context

        # Verify tree structure
        tree_data = response.context['tree_data']
        assert tree_data['id'] == f"doc_{doc_c.id}"
        assert len(tree_data['children']) == 1
        assert tree_data['children'][0]['id'] == f"doc_{doc_b.id}"
```

**Estimated Effort:** 2 weeks

---

### 2.5 Frontend Test Gaps 🟡 High

**No JavaScript Tests (0% coverage):**

1. **`cadeia_dominial_d3.js` (600+ lines)** - Tree visualization
2. **`lancamento_form.js` (400+ lines)** - Form behavior
3. **`cadeia_dominial_tabela.js`** - Table interactivity
4. **Other JS files** - Various features

**Recommended JavaScript Tests:**

```javascript
// static/dominial/js/tests/test_cadeia_dominial_d3.js
describe('CadeiaDominialTree', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.id = 'tree-container';
        document.body.appendChild(container);
    });

    afterEach(() => {
        document.body.removeChild(container);
    });

    test('renders simple tree', () => {
        const data = {
            id: 'doc_1',
            numero: 'M-001',
            tipo: 'matricula',
            children: [{
                id: 'doc_2',
                numero: 'M-002',
                tipo: 'matricula',
                children: []
            }]
        };

        const tree = new CadeiaDominialTree('#tree-container', data);

        // Verify tree was rendered
        const svg = container.querySelector('svg');
        expect(svg).not.toBeNull();

        // Verify nodes were created
        const nodes = svg.querySelectorAll('.node');
        expect(nodes.length).toBe(2);
    });

    test('handles node click', () => {
        const data = {
            id: 'doc_1',
            numero: 'M-001',
            tipo: 'matricula',
            children: []
        };

        const tree = new CadeiaDominialTree('#tree-container', data);

        // Click node
        const node = container.querySelector('.node');
        node.click();

        // Should trigger handleNodeClick
        // (Verify modal opened, etc.)
    });

    test('zoom controls work', () => {
        const data = { id: 'doc_1', numero: 'M-001', children: [] };
        const tree = new CadeiaDominialTree('#tree-container', data);

        const initialTransform = tree.getTransform();

        tree.zoomIn();
        const afterZoomIn = tree.getTransform();

        expect(afterZoomIn.scale).toBeGreaterThan(initialTransform.scale);
    });
});

// static/dominial/js/tests/test_lancamento_form.js
describe('LancamentoForm', () => {
    test('shows correct fields for tipo', () => {
        const form = new LancamentoForm();

        // Select 'registro' type
        form.updateFieldVisibility('registro');

        // Should show transmitente/adquirente
        expect(document.getElementById('transmitente-field').style.display).not.toBe('none');
        expect(document.getElementById('adquirente-field').style.display).not.toBe('none');

        // Should hide descricao (averbacao field)
        expect(document.getElementById('descricao-field').style.display).toBe('none');
    });

    test('validates required fields', () => {
        const form = new LancamentoForm();

        // Set type to 'registro'
        document.getElementById('tipo_lancamento').value = 'registro';

        // Submit without transmitente
        const isValid = form.validateForm();

        expect(isValid).toBe(false);
        expect(form.getErrors()).toContain('Transmitente é obrigatório');
    });
});
```

**Setup Required:**
1. **Test Framework:** Jest or Mocha
2. **Test Runner:** Karma or Jest
3. **Test Utilities:** jsdom for DOM simulation
4. **Coverage Tool:** Istanbul

**Estimated Effort:** 2-3 weeks

---

## 3. Test Infrastructure Gaps

### 3.1 Missing Test Fixtures

**No centralized test fixtures:**

```python
# Currently: Duplicated setup in each test
def test_something():
    ti = TIs.objects.create(nome="Test TI", codigo="TST001")
    imovel = Imovel.objects.create(terra_indigena_id=ti, matricula="M-001")
    # Repeat in every test!

# Recommended: Shared fixtures
# tests/fixtures/factories.py
import factory

class TIsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TIs

    nome = factory.Sequence(lambda n: f"TI Test {n}")
    codigo = factory.Sequence(lambda n: f"TST{n:03d}")
    etnia = "Test Etnia"
    estado = "BA"

class ImovelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Imovel

    terra_indigena_id = factory.SubFactory(TIsFactory)
    matricula = factory.Sequence(lambda n: f"M-{n:03d}")
    proprietario = factory.SubFactory(PessoasFactory)

# Usage
def test_something():
    ti = TIsFactory()
    imovel = ImovelFactory(terra_indigena_id=ti)
    # Much cleaner!
```

**Recommended:**
- Use `factory_boy` for model factories
- Create fixtures file for each model domain
- Share fixtures across tests

**Estimated Effort:** 1 week

---

### 3.2 Missing Test Database

**No separate test database configuration:**

```python
# settings.py - Add test database config
if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',  # Use in-memory DB for speed
        }
    }
```

**Recommended:**
- Use in-memory SQLite for fast tests
- Separate test settings file
- Auto-reset DB between tests

**Estimated Effort:** 1 day

---

### 3.3 Missing CI/CD Integration

**No automated testing:**

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.11

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-django

    - name: Run tests
      run: |
        pytest --cov=dominial --cov-report=xml

    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

**Recommended:**
- GitHub Actions for CI/CD
- Run tests on every push
- Coverage reports
- Block PRs with failing tests

**Estimated Effort:** 1-2 days

---

## 4. Testing Best Practices to Adopt

### 4.1 Test Organization

```
tests/
├── unit/                    # Unit tests (no DB)
│   ├── services/
│   ├── validators/
│   └── utils/
├── integration/             # Integration tests (with DB)
│   ├── test_workflows.py
│   └── test_api.py
├── fixtures/                # Test data factories
│   ├── factories.py
│   └── sample_data.py
└── conftest.py             # Pytest configuration
```

### 4.2 Test Naming Convention

```python
# Pattern: test_{what}_{expected_behavior}

def test_create_lancamento_with_valid_data_succeeds():
    """Test that creating lancamento with valid data succeeds"""
    pass

def test_create_lancamento_with_duplicate_numero_fails():
    """Test that creating lancamento with duplicate number fails"""
    pass

def test_build_tree_with_circular_reference_breaks_cycle():
    """Test that tree builder handles circular references"""
    pass
```

### 4.3 AAA Pattern (Arrange-Act-Assert)

```python
def test_lancamento_creation():
    # Arrange: Setup test data
    documento = create_documento()
    data = {'numero_lancamento': 'R-1', 'data': '2024-01-15'}

    # Act: Perform action
    lancamento = LancamentoService.criar(data, documento)

    # Assert: Verify results
    assert lancamento is not None
    assert lancamento.numero_lancamento == 'R-1'
```

---

## 5. Testing Roadmap

### Phase 1 (Week 1-2) - Infrastructure
- [ ] Set up test fixtures with factory_boy
- [ ] Configure test database
- [ ] Set up CI/CD with GitHub Actions
- [ ] Add coverage reporting

### Phase 2 (Week 3-5) - Critical Services
- [ ] Test `hierarquia_arvore_service.py`
- [ ] Test `cadeia_dominial_tabela_service.py`
- [ ] Test `lancamento_criacao_service.py`
- [ ] Test `lancamento_origem_service.py`

### Phase 3 (Week 6-8) - Views
- [ ] Test `lancamento_views.py`
- [ ] Test `cadeia_dominial_views.py`
- [ ] Test `documento_views.py`

### Phase 4 (Week 9-11) - Models & Integration
- [ ] Test all model validations
- [ ] Test all foreign key constraints
- [ ] Test complete workflows
- [ ] Test user journeys

### Phase 5 (Week 12-14) - Frontend
- [ ] Set up JavaScript testing framework
- [ ] Test `cadeia_dominial_d3.js`
- [ ] Test `lancamento_form.js`
- [ ] Test other JavaScript files

**Total Estimated Effort:** 14 weeks (3.5 months)

**Target Coverage:** 80% overall
- Models: 90%
- Services: 85%
- Views: 75%
- Frontend: 70%

---

## Summary

**Current State:**
- 8 test files
- ~30-40% estimated coverage
- Critical services untested
- Most views untested
- No frontend tests

**Recommended Actions:**
1. **Immediate:** Set up test infrastructure (2 weeks)
2. **Short-term:** Test critical services (4 weeks)
3. **Medium-term:** Test views and models (4 weeks)
4. **Long-term:** Test frontend and complete integration (4 weeks)

**Total Effort:** ~3.5 months to achieve 80% coverage

**Benefits:**
- Catch bugs early
- Safe refactoring
- Prevent regressions
- Better code quality
- Faster development (long-term)
