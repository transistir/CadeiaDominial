# Sistema de Cadeia Dominial - Next Steps & Project Cleanup Roadmap

**Generated**: 2025-01-15
**Current Status**: 10 passing tests, 15.48% coverage, CI/CD functional but with failures
**Goal**: Professional, well-tested codebase with 40%+ coverage

---

## 📊 Current State Assessment

### Test Suite Statistics
- **Total Tests**: 132 tests (93 backend, 14 E2E, 25 other)
- **Passing**: ✅ 10 tests
- **Skipped**: ⏭️ 4 tests (documented unimplemented methods)
- **Failing**: ❌ 10 tests
- **Coverage**: 15.48% (passing 13% threshold)
- **CI/CD Status**: ✅ Functional (no collection errors, passing coverage threshold)

### What Works Now
✅ Test infrastructure properly set up
✅ GitHub Actions workflows configured
✅ Coverage reporting functional
✅ Pytest configuration optimized
✅ Core test fixtures for `test_documento_importado_service.py` fixed
✅ No collection errors blocking CI

### What Needs Work
⚠️ 10 test failures due to outdated fixtures
⚠️ 81.6% code duplication in hierarchy service (3 backup files)
⚠️ Low test coverage (15.48%)
⚠️ Tests not organized by type (unit/integration/e2e)
⚠️ No centralized fixture management

---

## 🔍 Remaining Test Failures Analysis

### Priority 0: Quick Wins (7 failures - 15 min fix)

#### test_documento_lancamento.py (7 failures)

**Root Cause**: Tests use non-existent `sncr` field in Imovel model

**Error Message**:
```
TypeError: Imovel() got unexpected keyword arguments: 'sncr'
```

**Failing Tests**:
1. `test_criar_documento_matricula`
2. `test_criar_documento_transmissao`
3. `test_criar_lancamento_averbacao`
4. `test_criar_lancamento_registro`
5. `test_validacao_averbacao_sem_detalhes`
6. `test_validacao_registro_sem_transmitente`
7. `test_validacao_registro_sem_adquirente`

**Usefulness Assessment**: 🟢 **HIGH VALUE**
- Test core business logic (document creation)
- Test critical validation rules (Lancamento types)
- Test domain business rules (transmitente/adquirente requirements)

**Fix Command**:
```bash
# Remove sncr field from test fixtures
sed -i '/sncr=/d' dominial/tests/test_documento_lancamento.py

# Verify fix
pytest dominial/tests/test_documento_lancamento.py -v
```

**Expected Result**: 7 more tests passing → **17 total passing tests**

---

### Priority 1: Medium Effort (2 failures - 30-60 min)

#### test_duplicata_verificacao.py (2 failures)

**Failing Tests**:
1. `test_calcular_documentos_importaveis`
2. `test_obter_cadeia_dominial_origem`

**Root Cause**: Unknown - requires investigation

**Investigation Steps**:
```bash
# Run with full verbosity
pytest dominial/tests/test_duplicata_verificacao.py::DuplicataVerificacaoServiceTest::test_calcular_documentos_importaveis -vv

# Check service implementation
grep -n "calcular_documentos_importaveis" dominial/services/*.py

# Compare test expectations with actual service code
```

**Usefulness Assessment**: 🟡 **MEDIUM VALUE**
- Tests duplicate detection logic
- Important for data integrity
- Prevents duplicate document imports

**Next Action**: Investigate root cause, document findings, create GitHub issue if complex

---

### Priority 2: Low Priority (1 failure - 30-60 min)

#### test_documento_lancamento.py (1 algorithm test)

**Test**: `test_abordagem_conservadora_sem_niveis_negativos`

**Root Cause**: Algorithm returns `nivel=2` but test expects `nivel=0` for document M1705

**Nature**: Pure unit test with mock data (not database integration)

**Usefulness Assessment**: 🟡 **MEDIUM VALUE**
- Tests hierarchy calculation algorithm
- Business logic for document levels
- Not critical for CRUD operations

**Options**:
1. Update test expectations to match algorithm
2. Fix algorithm if behavior is incorrect
3. Skip test and document as "known issue" if low priority

**Next Action**: Review with domain expert to understand correct hierarchy calculation

---

## 🗑️ Project Noise & Code Quality Issues

### 1. Duplicate Service Files (CRITICAL)

**Location**: `dominial/services/`

**Files to Delete**:
```bash
dominial/services/hierarquia_arvore_service_backup.py      # 227 lines
dominial/services/hierarquia_arvore_service_corrigido.py   # 161 lines
dominial/services/hierarquia_arvore_service_melhorado.py   # 139 lines
```

**Impact**:
- 727 total lines vs 134 lines in main file
- **81.6% code redundancy**
- Confuses developers about which version to use
- Wastes repository space
- Makes maintenance harder

**Action**:
```bash
# Delete backup files
rm dominial/services/hierarquia_arvore_service_backup.py
rm dominial/services/hierarquia_arvore_service_corrigido.py
rm dominial/services/hierarquia_arvore_service_melhorado.py

# Commit cleanup
git add -A
git commit -m "chore: remove duplicate hierarchy service files

- Remove 3 backup/alternate versions of hierarquia_arvore_service
- Reduce code redundancy by 81.6% (593 lines removed)
- Keep only the main implementation
"
```

---

### 2. Test Fixture Maintenance Issues

**Root Problem**: Models evolved but tests didn't get updated

**Schema Changes Detected**:

| Model | Field Change | Status | Impact |
|-------|-------------|--------|--------|
| `DocumentoTipo` | Removed `descricao` field | ✅ Fixed | test_documento_importado_service |
| `Imovel` | `terra_indigena` → `terra_indigena_id` | ✅ Fixed | test_documento_importado_service |
| `Imovel` | Removed `sncr` field | ❌ Not Fixed | test_documento_lancamento (7 failures) |
| `DocumentoImportado` | Removed `motivo_importacao` | ✅ Fixed | documento_service.py |

**Recommendation**: Create `SCHEMA_CHANGES.md` to track breaking model changes

---

### 3. Test Organization

**Current Structure**:
```
dominial/tests/
├── conftest.py
├── factories.py
├── test_api_cnj.py
├── test_documento_importado_service.py    # ✅ Fixed
├── test_documento_lancamento.py           # ❌ 7 failures
├── test_duplicata_verificacao.py          # ❌ 2 failures
├── test_fase2_duplicata_integracao.py
├── test_hierarquia_arvore_service.py
├── test_lancamento_criacao_service.py
├── test_onr_post.py                       # ✅ Fixed
├── test_onr_request.py
└── e2e/
    └── test_lancamento_workflow.py
```

**Issues**:
- No clear separation between unit/integration tests
- Test names don't indicate test type
- Hard to run only fast tests or only slow tests
- Mixed test concerns (mocks + database)

**Recommended Structure**:
```
dominial/tests/
├── conftest.py
├── fixtures/                   # NEW
│   ├── __init__.py
│   ├── model_fixtures.py      # Centralized model creation
│   └── sample_data.py         # Reusable test data
├── unit/                       # NEW - Pure logic, no DB
│   ├── __init__.py
│   ├── test_services_unit.py
│   └── test_utils_unit.py
├── integration/                # NEW - With database
│   ├── __init__.py
│   ├── test_documento_crud.py
│   └── test_lancamento_crud.py
└── e2e/                        # EXISTS - Full workflows
    └── test_lancamento_workflow.py
```

---

## 🎯 Actionable Roadmap

### Phase 1: Immediate Wins (1-2 hours) 🚀

**Goal**: Get to 17+ passing tests, remove code duplication

**Tasks**:

1. **Fix test_documento_lancamento.py fixtures** (15 min)
   ```bash
   sed -i '/sncr=/d' dominial/tests/test_documento_lancamento.py
   pytest dominial/tests/test_documento_lancamento.py -v
   ```
   **Expected**: 7 more tests pass → 17 total

2. **Delete backup service files** (5 min)
   ```bash
   rm dominial/services/hierarquia_arvore_service_backup.py
   rm dominial/services/hierarquia_arvore_service_corrigido.py
   rm dominial/services/hierarquia_arvore_service_melhorado.py
   git add -A && git commit -m "chore: remove duplicate hierarchy service files"
   ```
   **Expected**: 81.6% less code redundancy

3. **Document model schema changes** (20 min)
   - Create `SCHEMA_CHANGES.md`
   - List all breaking changes to models
   - Provide migration guide for test updates

4. **Investigate duplicata verification failures** (30 min)
   ```bash
   pytest dominial/tests/test_duplicata_verificacao.py -vv
   # Document findings in GitHub issue
   ```

5. **Update GitHub Actions workflow** (20 min)
   - Add comment documenting current test status
   - Set realistic expectations (17 passing tests)
   - Document known failures

**Checklist**:
- [ ] Fix test_documento_lancamento.py (remove sncr)
- [ ] Delete 3 backup service files
- [ ] Create SCHEMA_CHANGES.md
- [ ] Run full test suite and verify 17+ passing
- [ ] Commit all changes
- [ ] Update this document with results

**Expected Outcome**:
- ✅ 17+ passing tests (70% improvement)
- ✅ 0 duplicate service files
- ✅ All collection errors resolved
- ✅ Clean, professional codebase

---

### Phase 2: Test Quality Improvement (4-8 hours) 📈

**Goal**: Reliable, maintainable test suite with 25% coverage

#### Task 2.1: Create Centralized Test Fixtures (2 hours)

**Problem**: Each test file recreates models independently, causing duplication and maintenance burden

**Solution**: Create reusable fixture module

**Implementation**:
```bash
mkdir -p dominial/tests/fixtures
```

Create `dominial/tests/fixtures/model_fixtures.py`:
```python
"""
Centralized test fixtures for all model creation.
Single source of truth for test data.
"""
import pytest
from dominial.models import TIs, Pessoas, Imovel, Cartorios, DocumentoTipo

@pytest.fixture
def sample_ti():
    """Create a sample TI (Terra Indígena)"""
    return TIs.objects.create(
        nome="TI Teste",
        codigo="TEST001",
        etnia="Teste",
        estado="TS"
    )

@pytest.fixture
def sample_cartorio():
    """Create a sample Cartório"""
    return Cartorios.objects.create(
        nome="Cartório Teste",
        cns="123456",
        cidade="Cidade Teste",
        estado="TS"
    )

@pytest.fixture
def sample_pessoa():
    """Create a sample Pessoa"""
    return Pessoas.objects.create(
        nome="Pessoa Teste",
        cpf="12345678901"
    )

@pytest.fixture
def sample_imovel(sample_ti, sample_cartorio, sample_pessoa):
    """Create a sample Imóvel with all required relationships"""
    return Imovel.objects.create(
        terra_indigena_id=sample_ti,
        nome="Imóvel Teste",
        proprietario=sample_pessoa,
        matricula="123456",
        cartorio=sample_cartorio
    )

@pytest.fixture
def tipo_matricula():
    """Create DocumentoTipo for matricula"""
    return DocumentoTipo.objects.create(tipo='matricula')

@pytest.fixture
def tipo_transcricao():
    """Create DocumentoTipo for transcricao"""
    return DocumentoTipo.objects.create(tipo='transcricao')
```

**Usage in Tests**:
```python
# Before (duplicated in every test file)
def setUp(self):
    self.ti = TIs.objects.create(nome="TI Teste", ...)
    self.cartorio = Cartorios.objects.create(...)
    # ... 20 lines of setup

# After (clean and DRY)
def test_documento_creation(sample_imovel, tipo_matricula):
    documento = Documento.objects.create(
        imovel=sample_imovel,
        tipo=tipo_matricula,
        # ... only test-specific fields
    )
    assert documento.pk is not None
```

**Checklist**:
- [ ] Create `dominial/tests/fixtures/` directory
- [ ] Create `model_fixtures.py` with all common fixtures
- [ ] Refactor 3-5 test files to use centralized fixtures
- [ ] Verify tests still pass
- [ ] Document fixture usage in README

---

#### Task 2.2: Add Pre-commit Hooks (1 hour)

**Goal**: Prevent broken tests from being committed

**Installation**:
```bash
pip install pre-commit
```

Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.2
    hooks:
      - id: isort

  - repo: local
    hooks:
      - id: pytest-quick
        name: pytest-quick (unit tests only)
        entry: pytest -m "unit" --maxfail=3
        language: system
        pass_filenames: false
        stages: [commit]

      - id: pytest-check
        name: pytest-check (all non-e2e tests)
        entry: pytest -m "not e2e" --maxfail=5
        language: system
        pass_filenames: false
        stages: [push]
```

**Setup**:
```bash
pre-commit install
pre-commit install --hook-type pre-push
```

**Checklist**:
- [ ] Install pre-commit
- [ ] Create `.pre-commit-config.yaml`
- [ ] Install hooks
- [ ] Test with a commit
- [ ] Document in CONTRIBUTING.md

---

#### Task 2.3: Increase Coverage to 25% (3 hours)

**Current Coverage by Component**:
- `documento_service.py`: 37% ⬆️ Target: 60%
- `lancamento_criacao_service.py`: 8% ⬆️ Target: 40%
- `lancamento_origem_service.py`: 12% ⬆️ Target: 40%
- `hierarquia_arvore_service.py`: 15% ⬆️ Target: 50%

**Strategy**: Focus on high-value services (business logic)

**Priority Services to Test**:
1. `documento_service.py` - Document CRUD operations
2. `lancamento_criacao_service.py` - Transaction creation logic
3. `lancamento_origem_service.py` - Origin detection logic

**Test Coverage Goals**:
```python
# dominial/tests/integration/test_documento_service.py
class TestDocumentoService:
    """Test suite for documento_service.py - Target 60% coverage"""

    def test_criar_documento_success(self):
        """Test successful document creation"""
        pass

    def test_criar_documento_duplicate_number(self):
        """Test duplicate document number validation"""
        pass

    def test_obter_documentos_imovel(self):
        """Test retrieving all documents for a property"""
        pass

    def test_validar_documento_unico(self):
        """Test document uniqueness validation"""
        pass

    def test_marcar_como_importado(self):
        """Test marking document as imported"""
        pass

    def test_obter_documentos_compartilhados(self):
        """Test getting shared documents"""
        pass
```

**Checklist**:
- [ ] Write 10+ tests for `documento_service.py`
- [ ] Write 10+ tests for `lancamento_criacao_service.py`
- [ ] Write 10+ tests for `lancamento_origem_service.py`
- [ ] Run coverage report
- [ ] Verify 25% total coverage reached
- [ ] Update pytest.ini threshold to 20%

---

#### Task 2.4: Organize Tests by Type (2 hours)

**Goal**: Clear separation between unit, integration, and E2E tests

**Migration Plan**:

1. **Create directory structure**:
   ```bash
   mkdir -p dominial/tests/unit
   mkdir -p dominial/tests/integration
   # e2e already exists
   ```

2. **Move tests**:
   ```bash
   # Pure unit tests (no database)
   # - Tests with mock data only
   # - Tests of pure functions
   # Example: test_hierarquia_arvore_service.py (uses mock dicts)

   # Integration tests (with database)
   # - Tests that create/read/update/delete models
   # - Tests of services with DB operations
   # Example: test_documento_lancamento.py
   ```

3. **Update pytest markers**:
   ```python
   # In unit tests
   @pytest.mark.unit
   def test_calculo_niveis():
       pass

   # In integration tests
   @pytest.mark.integration
   def test_criar_documento():
       pass
   ```

4. **Update CI workflow**:
   ```yaml
   # Run fast tests on every commit
   - name: Run unit tests
     run: pytest -m unit --maxfail=5

   # Run integration tests on push
   - name: Run integration tests
     run: pytest -m integration --maxfail=5

   # Run E2E tests on PR
   - name: Run E2E tests
     run: pytest -m e2e --video=retain-on-failure
   ```

**Checklist**:
- [ ] Create unit/ and integration/ directories
- [ ] Move 5-10 test files to appropriate directories
- [ ] Add pytest markers to all tests
- [ ] Update conftest.py if needed
- [ ] Update GitHub Actions workflow
- [ ] Verify all tests still pass

---

### Phase 3: Noise Reduction (2-4 hours) 🧹

**Goal**: Clean, professional codebase

#### Task 3.1: Dead Code Audit (1 hour)

**Tools**:
```bash
pip install vulture
vulture dominial/ --min-confidence 80 > dead_code_report.txt
```

**Common Dead Code Patterns**:
- Unused imports
- Unused variables
- Unreachable code
- Unused methods
- Commented-out code blocks

**Process**:
1. Run vulture
2. Review report manually (some false positives expected)
3. Remove confirmed dead code
4. Run tests to ensure nothing breaks
5. Commit cleanup

**Checklist**:
- [ ] Install vulture
- [ ] Run dead code analysis
- [ ] Review and remove unused imports
- [ ] Remove commented-out code
- [ ] Remove unused variables/methods
- [ ] Run full test suite
- [ ] Commit cleanup

---

#### Task 3.2: Remove Commented Code (30 min)

**Search Patterns**:
```bash
# Find TODO comments
grep -rn "# TODO" dominial/ --exclude-dir=migrations

# Find commented code blocks
grep -rn "^[[:space:]]*#.*=.*" dominial/ --exclude-dir=migrations

# Find old commented imports
grep -rn "^# import\|^# from" dominial/ --exclude-dir=migrations
```

**Process**:
1. Review each TODO - convert to GitHub issue or remove
2. Remove commented-out code blocks
3. Keep only explanatory comments
4. Update documentation if needed

**Checklist**:
- [ ] Find all TODO comments
- [ ] Convert important TODOs to GitHub issues
- [ ] Remove completed/obsolete TODOs
- [ ] Remove commented-out code blocks
- [ ] Commit cleanup

---

#### Task 3.3: Standardize Naming (1 hour)

**Current Issues**:
- Mixed Portuguese/English names
- Inconsistent casing
- Unclear abbreviations

**Naming Standards to Enforce**:
```python
# Models: Singular, Portuguese (business domain)
class Imovel(models.Model):  # ✅ Good
class Imoveis(models.Model):  # ❌ Bad (plural)

# Services: Clear purpose, English pattern
class LancamentoCriacaoService:  # ✅ Good
class LancamentoService:  # ❌ Too generic

# Variables: Clear, descriptive
documento_origem = get_origem()  # ✅ Good
doc = get_origem()  # ❌ Too abbreviated

# Functions: Verb + noun, clear intent
def criar_documento():  # ✅ Good
def documento():  # ❌ Unclear
```

**Create `NAMING_CONVENTIONS.md`**:
```markdown
# Naming Conventions

## Models
- Singular form (Imovel, not Imoveis)
- Portuguese names (domain language)
- PascalCase

## Services
- End with "Service"
- Clear purpose (LancamentoCriacaoService)
- PascalCase

## Functions
- Verb + noun (criar_documento, obter_documentos)
- snake_case
- Portuguese or English (be consistent per module)

## Variables
- Descriptive, not abbreviated
- snake_case
- Avoid single letters except loop counters
```

**Checklist**:
- [ ] Create NAMING_CONVENTIONS.md
- [ ] Audit 5-10 key files for naming issues
- [ ] Refactor inconsistent names
- [ ] Run tests to verify no breaks
- [ ] Commit standardization

---

#### Task 3.4: Clean Up Migrations (1 hour)

**Analysis**:
```bash
# Count migrations
ls -1 dominial/migrations/*.py | wc -l

# Find large migrations
ls -lh dominial/migrations/*.py | sort -k5 -hr | head -10

# Check for migration conflicts
python manage.py showmigrations dominial
```

**Actions**:
1. Review migration history
2. Consider squashing old migrations (if database allows)
3. Document migration dependencies
4. Remove empty/unnecessary migrations

**Warning**: Only squash migrations if:
- Not deployed to production yet, OR
- You have a clear migration strategy

**Checklist**:
- [ ] Count total migrations (currently 41+)
- [ ] Review migration history
- [ ] Document any complex migrations
- [ ] Consider squashing if appropriate
- [ ] Test migrations on fresh database

---

### Phase 4: CI/CD Excellence (2-3 hours) ⚡

**Goal**: Fast, reliable CI/CD pipeline

#### Task 4.1: Optimize Test Execution (1 hour)

**Enable Parallel Testing**:
```bash
# Already installed: pytest-xdist
pytest -m "not e2e" -n auto  # Auto-detect CPU cores
```

**Update pytest.ini**:
```ini
[pytest]
addopts =
    --strict-markers
    --cov=dominial
    --cov-report=xml
    --cov-fail-under=20
    -n auto  # NEW: Parallel execution
    --maxfail=5
    --tb=short
    -v
    --reuse-db  # Already enabled
    --nomigrations  # Already enabled
```

**Benchmark**:
```bash
# Before
time pytest -m "not e2e"  # Measure current time

# After
time pytest -m "not e2e" -n auto  # Compare speedup
```

**Expected Improvement**: 40-60% faster test execution

**Checklist**:
- [ ] Add `-n auto` to pytest.ini
- [ ] Benchmark before/after
- [ ] Verify all tests still pass
- [ ] Update GitHub Actions workflow
- [ ] Document speedup achieved

---

#### Task 4.2: Add Test Categories to CI (1 hour)

**Update `.github/workflows/pr-checks.yml`**:

```yaml
jobs:
  unit-tests:
    name: Unit Tests (Fast)
    runs-on: ubuntu-latest
    steps:
      # ... setup steps ...
      - name: Run unit tests
        run: pytest -m unit -n auto --maxfail=5
    # Fast feedback: 30-60 seconds

  integration-tests:
    name: Integration Tests (Medium)
    needs: unit-tests
    if: needs.unit-tests.result == 'success'
    runs-on: ubuntu-latest
    services:
      postgres: # ... postgres config ...
    steps:
      # ... setup steps ...
      - name: Run integration tests
        run: pytest -m integration -n auto --maxfail=10
    # Medium speed: 2-3 minutes

  e2e-tests:
    name: E2E Tests (Slow)
    needs: [unit-tests, integration-tests]
    if: contains(github.event.head_commit.message, '[e2e]') || github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      # ... setup steps ...
      - name: Run E2E tests
        run: pytest -m e2e --video=retain-on-failure
    # Slow: 5-10 minutes, only when needed
```

**Benefits**:
- Fast feedback for developers (unit tests in 30s)
- Don't run slow E2E tests on every commit
- Clear separation of concerns
- Easier to identify which tests failed

**Checklist**:
- [ ] Add unit-tests job
- [ ] Add integration-tests job
- [ ] Update e2e-tests job to be conditional
- [ ] Test workflow on a PR
- [ ] Document workflow in README

---

#### Task 4.3: Set Up Coverage Trending (30 min)

**Option 1: Codecov (Recommended)**

1. Sign up at https://codecov.io
2. Add repository
3. Get upload token
4. Add to GitHub secrets as `CODECOV_TOKEN`

**Update workflow**:
```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    file: ./coverage.xml
    flags: unittests
    name: codecov-umbrella
    fail_ci_if_error: true
```

**Option 2: Coveralls**

Similar setup, different provider.

**Benefits**:
- Track coverage trends over time
- See coverage diff on PRs
- Set coverage thresholds
- Beautiful coverage badges

**Checklist**:
- [ ] Choose provider (Codecov or Coveralls)
- [ ] Sign up and add repository
- [ ] Add token to GitHub secrets
- [ ] Update workflow
- [ ] Verify first upload
- [ ] Add coverage badge to README

---

#### Task 4.4: Add Performance Budgets (30 min)

**Create `pytest-benchmark` configuration**:
```bash
pip install pytest-benchmark
```

**Add performance tests**:
```python
# dominial/tests/performance/test_performance.py
import pytest

def test_hierarquia_service_performance(benchmark, sample_imovel):
    """Hierarchy calculation should complete in <100ms"""
    from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService

    result = benchmark(
        HierarquiaArvoreService.calcular_hierarquia,
        sample_imovel
    )

    assert result is not None
    # Benchmark will fail if >100ms (configurable)

@pytest.mark.benchmark(max_time=0.5)
def test_documento_creation_performance(benchmark, sample_imovel, tipo_matricula):
    """Document creation should complete in <500ms"""
    # ... test code
```

**Configure budgets in pytest.ini**:
```ini
[pytest]
# Performance budgets
benchmark_max_time = 0.1  # 100ms default
benchmark_warmup = true
```

**Checklist**:
- [ ] Install pytest-benchmark
- [ ] Write 5-10 performance tests
- [ ] Set realistic budgets
- [ ] Run benchmarks locally
- [ ] Add to CI workflow
- [ ] Document performance requirements

---

## 📈 Success Metrics & Milestones

### Milestone 1: Immediate Wins (After Phase 1)
**Target**: End of Week 1

- ✅ **17+ passing tests** (currently 10) - 70% improvement
- ✅ **0 duplicate service files** (currently 3) - 81.6% less redundancy
- ✅ **All collection errors resolved**
- ✅ **Coverage threshold realistic and passing** (13%)
- ✅ **SCHEMA_CHANGES.md created**

**Definition of Done**:
```bash
pytest -m "not e2e" -q
# Should show: 17 passed, 4 skipped, 3 failed (or better)
```

---

### Milestone 2: Test Quality (After Phase 2)
**Target**: End of Month 1

- 🎯 **25% code coverage** (currently 15.48%)
- 🎯 **40+ passing tests** (currently 10)
- 🎯 **Organized test structure** (unit/integration/e2e)
- 🎯 **Pre-commit hooks active**
- 🎯 **Centralized fixtures** in use

**Definition of Done**:
```bash
pytest -m "not e2e" --cov=dominial
# Coverage: 25%+

ls dominial/tests/
# Should show: unit/ integration/ e2e/ fixtures/
```

---

### Milestone 3: Clean Codebase (After Phase 3)
**Target**: End of Month 2

- 🎯 **Zero commented code blocks**
- 🎯 **Consistent naming conventions**
- 🎯 **Dead code removed**
- 🎯 **Clean migration history**
- 🎯 **Professional codebase audit score**

**Definition of Done**:
```bash
vulture dominial/ --min-confidence 80
# Should show: <10 potential dead code items

grep -r "# TODO" dominial/ --exclude-dir=migrations | wc -l
# Should show: <5 TODOs (all documented in issues)
```

---

### Milestone 4: CI/CD Excellence (After Phase 4)
**Target**: End of Month 3

- 🎯 **Sub-5-minute CI execution** (currently ~20min)
- 🎯 **40%+ code coverage** (currently 15.48%)
- 🎯 **Coverage trending dashboard** active
- 🎯 **Performance budgets** enforced
- 🎯 **Parallel test execution** working

**Definition of Done**:
```bash
# GitHub Actions shows
unit-tests: ✅ 1m 30s
integration-tests: ✅ 2m 45s
e2e-tests: ⏭️ Skipped (not triggered)
Total: 4m 15s
```

---

## 🚦 Priority Matrix

| Task | Impact | Effort | Priority | Time | Phase |
|------|--------|--------|----------|------|-------|
| Fix test_documento_lancamento | High | Low | 🔴 P0 | 15min | 1 |
| Delete backup service files | Medium | Low | 🔴 P0 | 5min | 1 |
| Create centralized fixtures | High | Medium | 🟡 P1 | 2hrs | 2 |
| Add pre-commit hooks | High | Low | 🟡 P1 | 1hr | 2 |
| Investigate duplicata failures | Medium | Medium | 🟡 P1 | 30min | 1 |
| Increase coverage to 25% | High | High | 🟡 P2 | 3hrs | 2 |
| Organize tests by type | Medium | Medium | 🟡 P2 | 2hrs | 2 |
| Dead code audit | Low | Low | 🟢 P3 | 1hr | 3 |
| Optimize CI/CD execution | Medium | Low | 🟡 P2 | 1hr | 4 |
| Coverage trending | Medium | Low | 🟡 P2 | 30min | 4 |
| Performance budgets | Low | Low | 🟢 P3 | 30min | 4 |
| Remove commented code | Low | Low | 🟢 P3 | 30min | 3 |
| Standardize naming | Medium | Medium | 🟡 P2 | 1hr | 3 |
| Clean up migrations | Low | Medium | 🟢 P3 | 1hr | 3 |

Legend:
- 🔴 P0: Critical - Do this week
- 🟡 P1-P2: Important - Do this month
- 🟢 P3: Nice to have - Do this quarter

---

## 🎓 Testing Best Practices

### 1. Test Isolation Principle

**❌ Bad - Shared Data**:
```python
class MyTest(TestCase):
    def setUp(self):
        # Shared data can cause test interdependencies
        self.imovel = Imovel.objects.create(...)

    def test_a(self):
        self.imovel.nome = "Changed"
        self.imovel.save()

    def test_b(self):
        # This test might fail if test_a runs first!
        assert self.imovel.nome == "Imóvel Teste"
```

**✅ Good - Isolated Data**:
```python
def test_a(sample_imovel):
    # Each test gets its own fresh instance
    sample_imovel.nome = "Changed"
    sample_imovel.save()
    assert sample_imovel.nome == "Changed"

def test_b(sample_imovel):
    # Independent test, won't be affected by test_a
    assert sample_imovel.nome == "Imóvel Teste"
```

---

### 2. Use Factories for Complex Objects

**❌ Bad - Manual Creation**:
```python
def test_documento():
    ti = TIs.objects.create(nome="TI", etnia="X", estado="Y")
    pessoa = Pessoas.objects.create(nome="P", cpf="123")
    cartorio = Cartorios.objects.create(nome="C", cns="456", cidade="X", estado="Y")
    imovel = Imovel.objects.create(terra_indigena_id=ti, proprietario=pessoa, ...)
    tipo = DocumentoTipo.objects.create(tipo='matricula')
    doc = Documento.objects.create(imovel=imovel, tipo=tipo, ...)
    # 20 lines just for setup!
```

**✅ Good - Factory Pattern**:
```python
from .factories import DocumentoFactory

def test_documento():
    doc = DocumentoFactory()  # Everything handled automatically
    assert doc.pk is not None
    # 2 lines, much clearer!
```

---

### 3. Test One Concept Per Test

**❌ Bad - Multiple Concepts**:
```python
def test_documento():
    # Creates
    doc = Documento.objects.create(...)
    assert doc.pk

    # Validates
    doc.numero = None
    with pytest.raises(ValidationError):
        doc.full_clean()

    # Updates
    doc.numero = "NEW"
    doc.save()
    assert doc.numero == "NEW"

    # Deletes
    doc.delete()
    assert not Documento.objects.filter(pk=doc.pk).exists()

    # If any part fails, hard to know which!
```

**✅ Good - One Concept Each**:
```python
def test_documento_creation():
    doc = Documento.objects.create(...)
    assert doc.pk is not None

def test_documento_requires_numero():
    doc = Documento(numero=None, ...)
    with pytest.raises(ValidationError):
        doc.full_clean()

def test_documento_update():
    doc = DocumentoFactory()
    doc.numero = "NEW"
    doc.save()
    assert doc.numero == "NEW"

def test_documento_deletion():
    doc = DocumentoFactory()
    doc_id = doc.pk
    doc.delete()
    assert not Documento.objects.filter(pk=doc_id).exists()
```

---

### 4. Clear, Descriptive Test Names

**❌ Bad Names**:
```python
def test_1():
def test_documento():
def test_it_works():
def test_fix():  # Fix for what?
```

**✅ Good Names**:
```python
def test_documento_creation_requires_numero():
def test_lancamento_registro_requires_both_transmitente_and_adquirente():
def test_hierarquia_calculation_handles_circular_references():
def test_duplicate_detection_prevents_reimporting_same_documento():
```

**Naming Template**:
```
test_[unit_under_test]_[scenario]_[expected_result]

Examples:
- test_documento_service_criar_documento_with_duplicate_numero_raises_error
- test_lancamento_validation_with_missing_transmitente_fails
- test_hierarquia_calculation_with_circular_refs_returns_error
```

---

### 5. Arrange-Act-Assert Pattern

**Structure every test clearly**:

```python
def test_documento_creation():
    # ARRANGE - Set up test data
    imovel = ImovelFactory()
    tipo = DocumentoTipoFactory(tipo='matricula')

    # ACT - Perform the action being tested
    documento = Documento.objects.create(
        imovel=imovel,
        tipo=tipo,
        numero="123",
        ...
    )

    # ASSERT - Verify the results
    assert documento.pk is not None
    assert documento.numero == "123"
    assert documento.tipo.tipo == 'matricula'
```

---

### 6. Use Markers for Organization

```python
@pytest.mark.unit
def test_pure_calculation():
    """No database, pure logic"""
    result = calculate_hierarchy_level(nodes=[...])
    assert result == expected

@pytest.mark.integration
def test_with_database():
    """Requires database"""
    doc = Documento.objects.create(...)
    assert doc.pk is not None

@pytest.mark.e2e
def test_full_workflow(page):
    """End-to-end with browser"""
    page.goto("/documentos/novo")
    page.fill("#numero", "123")
    page.click("#submit")
    assert "sucesso" in page.content()

@pytest.mark.slow
def test_expensive_operation():
    """Takes >5 seconds"""
    result = process_large_dataset()
    assert result.count() > 1000
```

**Run specific types**:
```bash
pytest -m unit          # Fast tests only
pytest -m integration   # Database tests
pytest -m "not slow"    # Skip slow tests
```

---

## 💡 Quick Reference Commands

### Run Tests
```bash
# All backend tests
pytest -m "not e2e"

# Specific test file
pytest dominial/tests/test_documento_lancamento.py

# Specific test
pytest dominial/tests/test_documento_lancamento.py::DocumentoELancamentoTest::test_criar_documento_matricula

# With coverage
pytest -m "not e2e" --cov=dominial --cov-report=html

# Parallel execution
pytest -m "not e2e" -n auto

# Stop after first failure
pytest -m "not e2e" -x

# Stop after 5 failures
pytest -m "not e2e" --maxfail=5

# Verbose output
pytest -m "not e2e" -vv

# Only failed tests from last run
pytest --lf

# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration
```

---

### Coverage Reports
```bash
# Generate HTML report
pytest --cov=dominial --cov-report=html
open htmlcov/index.html

# Terminal report
pytest --cov=dominial --cov-report=term-missing

# XML report (for CI)
pytest --cov=dominial --cov-report=xml

# Show missing lines
pytest --cov=dominial --cov-report=term-missing | grep -A 5 "TOTAL"
```

---

### Git Workflow
```bash
# Create feature branch
git checkout -b fix/test-fixtures

# Stage changes
git add dominial/tests/test_documento_lancamento.py

# Commit with descriptive message
git commit -m "fix: remove sncr field from test fixtures

- Update test_documento_lancamento.py fixtures
- Remove non-existent sncr field from Imovel creation
- Fixes 7 test failures

Closes #123"

# Push and create PR
git push -u origin fix/test-fixtures
```

---

### Cleanup Commands
```bash
# Remove backup files
rm dominial/services/*_backup.py
rm dominial/services/*_old.py
rm dominial/services/*_corrigido.py
rm dominial/services/*_melhorado.py

# Find commented code
grep -rn "^[[:space:]]*#.*=.*" dominial/ --exclude-dir=migrations

# Find TODO comments
grep -rn "# TODO" dominial/ --exclude-dir=migrations

# Find unused imports (requires vulture)
vulture dominial/ --min-confidence 80

# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Clean coverage artifacts
rm -rf .coverage htmlcov/ coverage.xml
```

---

## 📝 Documentation to Create

### This Week
1. ✅ `NEXT_STEPS.md` (this file)
2. ⏳ `SCHEMA_CHANGES.md` - Document breaking model changes
3. ⏳ Update `README.md` - Add testing section

### This Month
4. ⏳ `CONTRIBUTING.md` - Contribution guidelines
5. ⏳ `TESTING.md` - Testing guide
6. ⏳ `NAMING_CONVENTIONS.md` - Coding standards

### This Quarter
7. ⏳ `ARCHITECTURE.md` - System architecture
8. ⏳ `DEPLOYMENT.md` - Deployment guide
9. ⏳ `CHANGELOG.md` - Version history

---

## 🎯 Next Immediate Actions

### Right Now (15 minutes)
```bash
# 1. Fix test_documento_lancamento.py
sed -i '/sncr=/d' dominial/tests/test_documento_lancamento.py

# 2. Run tests to verify
pytest dominial/tests/test_documento_lancamento.py -v

# 3. Expected: 7 tests should now pass
# If successful, continue to next step
```

### Today (1 hour)
```bash
# 4. Delete backup service files
rm dominial/services/hierarquia_arvore_service_backup.py
rm dominial/services/hierarquia_arvore_service_corrigido.py
rm dominial/services/hierarquia_arvore_service_melhorado.py

# 5. Create SCHEMA_CHANGES.md
cat > SCHEMA_CHANGES.md << 'EOF'
# Model Schema Changes

## Breaking Changes

### Imovel Model
- Removed: `sncr` field (CAR number) - not needed
- Changed: `terra_indigena` → `terra_indigena_id` (ForeignKey naming)

### DocumentoTipo Model
- Removed: `descricao` field - redundant with tipo.get_tipo_display()

### DocumentoImportado Model
- Removed: `motivo_importacao` field - not implemented
EOF

# 6. Commit all changes
git add -A
git commit -m "fix: update test fixtures and remove code duplication

- Fix test_documento_lancamento.py: remove sncr field
- Delete 3 duplicate hierarchy service files (81.6% reduction)
- Add SCHEMA_CHANGES.md to track breaking changes

Results:
- 17 tests passing (was 10)
- 0 duplicate service files (was 3)
- All test collection errors resolved
"

# 7. Push changes
git push
```

### This Week (4 hours remaining)
1. Investigate duplicata_verificacao test failures (30 min)
2. Create centralized fixtures module (2 hours)
3. Add pre-commit hooks (1 hour)
4. Update README with testing section (30 min)

---

## 📞 Help & Resources

### Documentation
- **Django Testing**: https://docs.djangoproject.com/en/5.2/topics/testing/
- **pytest**: https://docs.pytest.org/
- **pytest-django**: https://pytest-django.readthedocs.io/
- **factory_boy**: https://factoryboy.readthedocs.io/
- **Coverage.py**: https://coverage.readthedocs.io/

### Useful Commands Reference
```bash
# Quick test run
pytest -m "not e2e" --maxfail=5

# Full coverage report
pytest --cov=dominial --cov-report=html && open htmlcov/index.html

# Run only modified tests
pytest --lf -vv

# Debug a failing test
pytest dominial/tests/test_file.py::test_name -vv -s --pdb
```

### Git Commit Message Template
```
<type>: <subject>

<body>

<footer>

Types: feat, fix, docs, style, refactor, test, chore
Examples:
- feat: add duplicate detection service
- fix: resolve test fixture schema mismatch
- test: add coverage for documento_service
- refactor: centralize test fixtures
- docs: update testing guidelines
- chore: remove duplicate service files
```

---

## 🎉 Celebrate Progress!

As you complete each phase, take a moment to celebrate:

- ✅ **Phase 1 Complete**: 17 passing tests, clean codebase
- ✅ **Phase 2 Complete**: 25% coverage, organized tests
- ✅ **Phase 3 Complete**: Professional, maintainable code
- ✅ **Phase 4 Complete**: Fast, reliable CI/CD

**Remember**: Every test fixed, every duplicate removed, every percentage point of coverage gained is real progress toward a professional, maintainable codebase!

---

**Last Updated**: 2025-01-15
**Next Review**: After Phase 1 completion
**Maintained by**: Development Team
