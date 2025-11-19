# 🛠️ Guia de Desenvolvimento

Guia completo para desenvolvedores contribuindo com o Sistema de Cadeia Dominial.

---

## 📖 Sumário

- [Setup de Desenvolvimento](#-setup-de-desenvolvimento)
- [Executando Testes](#-executando-testes)
- [Arquitetura do Projeto](#-arquitetura-do-projeto)
- [Workflow de Desenvolvimento](#-workflow-de-desenvolvimento)
- [Code Style e Convenções](#-code-style-e-convenções)
- [Debugging e Performance](#-debugging-e-performance)

---

## 🚀 Setup de Desenvolvimento

### Pré-requisitos

- Python 3.8+ (recomendado 3.11+)
- Git
- uv (instalador de pacotes rápido)
- Editor de código (VS Code, PyCharm, ou similar)

### Instalação Rápida

```bash
# Clone o repositório
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial

# Crie ambiente virtual e instale dependências
uv venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Instale dependências de desenvolvimento
uv pip install -r requirements.txt
uv pip install -r requirements-test.txt

# Configure ambiente
cp env.example .env
# Edite .env conforme necessário

# Execute migrações
uv run python manage.py migrate

# Crie tipos de documento e lançamento
uv run python manage.py criar_tipos_documento
uv run python manage.py criar_tipos_lancamento

# Crie superusuário
uv run python manage.py createsuperuser

# Inicie servidor de desenvolvimento
uv run python manage.py runserver
```

---

## 🧪 Executando Testes

### Usando Django Test Runner

```bash
# Execute todos os testes
uv run python manage.py test

# Execute testes de um app específico
uv run python manage.py test dominial

# Execute testes de um módulo específico
uv run python manage.py test dominial.tests.test_hierarquia_arvore_service

# Execute com verbosidade
uv run python manage.py test -v 2

# Execute testes específicos por padrão
uv run python manage.py test dominial.tests.test_duplicata_verificacao

# Mantenha banco de dados de teste (útil para debug)
uv run python manage.py test --keepdb
```

### Usando pytest (Recomendado)

```bash
# Execute todos os testes
uv run pytest

# Execute com relatório de cobertura
uv run pytest --cov=dominial --cov-report=html

# Execute apenas testes unitários (rápidos)
uv run pytest -m "not e2e"

# Execute apenas testes de integração
uv run pytest -m "e2e"

# Execute testes específicos
uv run pytest dominial/tests/test_hierarquia_arvore_service.py

# Execute com verbosidade e saída detalhada
uv run pytest -vv -s

# Execute testes que falharam na última execução
uv run pytest --lf

# Execute testes em paralelo (requer pytest-xdist)
uv run pytest -n auto

# Gere relatório de cobertura HTML
uv run pytest --cov=dominial --cov-report=html
# Abra htmlcov/index.html no navegador
```

### Visualizar Cobertura de Testes

```bash
# Gere relatório
uv run pytest --cov=dominial --cov-report=html

# Abra no navegador
# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html

# Windows
start htmlcov/index.html
```

### Testes por Categoria

**Testes de Modelos:**
```bash
uv run pytest dominial/tests/test_models.py
```

**Testes de Services:**
```bash
uv run pytest dominial/tests/test_*_service.py
```

**Testes de Views:**
```bash
uv run pytest dominial/tests/test_views.py
```

**Testes de Integração:**
```bash
uv run pytest dominial/tests/test_*_integration.py
```

**Testes de Bug Fixes:**
```bash
uv run pytest dominial/tests/test_recent_bugfixes_integration.py
```

### Métricas de Cobertura

**Metas:**
- **Cobertura total:** > 80%
- **Services:** > 90%
- **Models:** > 85%
- **Views:** > 75%

**Verificar cobertura:**
```bash
uv run pytest --cov=dominial --cov-report=term-missing
```

---

## 🏗️ Arquitetura do Projeto

Para documentação completa da arquitetura, veja **[AGENTS.md](../AGENTS.md)**.

### Estrutura de Diretórios

```
CadeiaDominial/
├── cadeia_dominial/         # Projeto Django (settings)
│   ├── settings.py          # Configurações
│   ├── urls.py              # URLs do projeto
│   └── wsgi.py              # WSGI entry point
├── dominial/                # App principal
│   ├── models/              # Modelos do banco de dados
│   │   ├── tis_models.py
│   │   ├── imovel_models.py
│   │   ├── documento_models.py
│   │   └── lancamento_models.py
│   ├── services/            # Lógica de negócio
│   │   ├── hierarquia_arvore_service.py
│   │   ├── cadeia_dominial_tabela_service.py
│   │   ├── lancamento_criacao_service.py
│   │   └── duplicata_verificacao_service.py
│   ├── views/               # Controllers
│   │   ├── tis_views.py
│   │   ├── imovel_views.py
│   │   ├── documento_views.py
│   │   ├── lancamento_views.py
│   │   └── api_views.py
│   ├── forms/               # Formulários Django
│   ├── tests/               # Testes
│   ├── management/commands/ # Comandos personalizados
│   ├── middleware.py        # Middlewares
│   ├── urls.py              # URLs do app
│   └── admin.py             # Admin customizado
├── templates/               # Templates Django
│   └── dominial/
│       ├── components/      # Componentes reutilizáveis
│       └── *.html           # Templates de páginas
├── static/                  # Arquivos estáticos
│   └── dominial/
│       ├── js/              # JavaScript
│       │   ├── cadeia_dominial_d3.js
│       │   └── lancamento_form.js
│       └── css/             # CSS
├── docs/                    # Documentação
├── tests_scripts/           # Scripts de teste
└── requirements.txt         # Dependências Python
```

### Padrões de Arquitetura

#### Service Layer Pattern

**Princípio:** Lógica de negócio separada das views.

**Estrutura:**
```python
# dominial/services/my_service.py
class MyService:
    @staticmethod
    def process_data(params):
        """Lógica de negócio aqui"""
        # Validação
        # Processamento
        # Retorno estruturado
        return result

# dominial/views/my_views.py
from dominial.services.my_service import MyService

def my_view(request):
    result = MyService.process_data(request.POST)
    return render(request, 'template.html', {'result': result})
```

**Benefícios:**
- Views permanecem magras (thin controllers)
- Lógica reutilizável entre views
- Mais fácil de testar
- Separação clara de responsabilidades

#### Domain-Driven Design

**Organização por domínio:**
- Models organizados por entidade de negócio
- Services agrupados por funcionalidade
- Views agrupadas por domínio

---

## 🔄 Workflow de Desenvolvimento

### Estratégia de Branches

```bash
main              # Produção estável
  └─ develop      # Desenvolvimento ativo
      ├─ feature/nome-feature    # Novas funcionalidades
      ├─ bugfix/nome-bug         # Correção de bugs
      └─ hotfix/nome-hotfix      # Correções urgentes
```

### Criar Nova Feature

```bash
# Atualize develop
git checkout develop
git pull origin develop

# Crie branch da feature
git checkout -b feature/minha-feature

# Desenvolva
# ... faça mudanças ...

# Commit
git add .
git commit -m "Add: Nova funcionalidade X"

# Push
git push -u origin feature/minha-feature

# Abra Pull Request para develop
```

### Corrigir Bug

```bash
# Branch de bugfix
git checkout develop
git pull origin develop
git checkout -b bugfix/corrigir-problema

# Corrija o bug
# Adicione testes que reproduzem o bug
# Verifique que fix resolve

# Commit
git commit -m "Fix: Corrige problema Y"

# Push e PR
git push -u origin bugfix/corrigir-problema
```

### Hotfix (Urgente)

```bash
# Branch de main
git checkout main
git pull origin main
git checkout -b hotfix/problema-critico

# Corrija imediatamente
# Teste extensivamente

# Commit
git commit -m "Hotfix: Resolve problema crítico Z"

# Merge em main E develop
git checkout main
git merge hotfix/problema-critico
git push origin main

git checkout develop
git merge hotfix/problema-critico
git push origin develop
```

---

## 📝 Code Style e Convenções

### Python (PEP 8)

```python
# Imports organizados
import os
import sys

from django.db import models
from django.shortcuts import render

from dominial.models import Imovel
from dominial.services import MyService

# Classes: PascalCase
class MinhaClasse:
    pass

# Funções e variáveis: snake_case
def minha_funcao(parametro_um, parametro_dois):
    variavel_local = parametro_um + parametro_dois
    return variavel_local

# Constantes: UPPER_CASE
MAX_TENTATIVAS = 3
TIMEOUT_SEGUNDOS = 30

# Docstrings
def funcao_documentada(param):
    """
    Descrição breve da função.

    Args:
        param (str): Descrição do parâmetro

    Returns:
        dict: Descrição do retorno
    """
    return {'result': param}

# Comprimento de linha: máximo 119 caracteres
# Indentação: 4 espaços (não tabs)
```

### Django Conventions

```python
# Models: Singular
class Pessoa(models.Model):
    nome = models.CharField(max_length=200)

    class Meta:
        verbose_name_plural = "Pessoas"  # Plural no Meta

# Services: End with "Service"
class DocumentoCriacaoService:
    @staticmethod
    def criar_documento(data):
        pass

# Views: Descriptive names
def listar_documentos(request):
    pass

def criar_documento(request):
    pass

def editar_documento(request, documento_id):
    pass

# Templates: snake_case
# templates/dominial/documento_form.html
# templates/dominial/documento_list.html
```

### JavaScript

```javascript
// camelCase para variáveis e funções
const minhaVariavel = "valor";

function minhaFuncao(parametro) {
    return parametro + 1;
}

// PascalCase para classes
class MinhaClasse {
    constructor() {
        this.propriedade = "valor";
    }
}

// Constantes: UPPER_CASE
const MAX_ZOOM = 3;
const MIN_ZOOM = 0.5;

// Use const/let (não var)
const imutavel = "não muda";
let mutavel = "pode mudar";

// ES6+ features encorajados
const array = [1, 2, 3];
const doubled = array.map(x => x * 2);
```

### CSS/SCSS

```css
/* BEM-like naming */
.documento-card {}
.documento-card__header {}
.documento-card__title {}
.documento-card--highlighted {}

/* Component-specific files */
/* static/dominial/css/documento_form.css */
/* static/dominial/css/cadeia_dominial_d3.css */
```

### Commit Messages

**Formato:**
```
Tipo: Descrição curta (50 chars max)

Descrição detalhada opcional (72 chars por linha)
- Bullet points para mudanças
- Referências a issues: #123

Tipos:
- Add: Nova funcionalidade
- Update: Melhoria em funcionalidade existente
- Fix: Correção de bug
- Refactor: Refatoração de código
- Test: Adicionar/modificar testes
- Docs: Documentação
- Style: Formatação (não muda lógica)
- Chore: Manutenção (deps, build, etc)
```

**Exemplos:**
```bash
git commit -m "Add: Funcionalidade de exportação para PDF"
git commit -m "Fix: Corrige MultipleObjectsReturned em Cartório lookup"
git commit -m "Update: Melhora performance da visualização D3"
git commit -m "Test: Adiciona testes de integração para duplicatas"
git commit -m "Docs: Atualiza guia de instalação com uv"
```

---

## 🐛 Debugging e Performance

### Debug com Django Debug Toolbar

**Instalação:**
```bash
uv pip install django-debug-toolbar
```

**Configuração (development):**
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    INTERNAL_IPS = ['127.0.0.1']
```

**Uso:**
- Barra lateral aparece automaticamente
- Mostra queries SQL, tempo de execução, cache hits
- Templates usados, context variables
- Signals enviados

### Logging

```python
# Em qualquer arquivo
import logging

logger = logging.getLogger(__name__)

# Níveis de log
logger.debug("Informação detalhada para debugging")
logger.info("Informação geral")
logger.warning("Algo inesperado, mas não é erro")
logger.error("Erro que precisa atenção")
logger.critical("Erro crítico")

# Com contexto
logger.error(f"Erro ao processar documento {doc_id}", exc_info=True)
```

**Configurar logging (settings.py):**
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'dominial': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
        },
    },
}
```

### Profiling de Performance

**Django Debug Toolbar SQL Panel:**
- Mostra todas as queries executadas
- Destaca queries lentas
- Identifica N+1 queries

**Queries otimizadas:**
```python
# ❌ BAD: N+1 query
for documento in Documento.objects.all():
    print(documento.cartorio.nome)  # Query por cada documento

# ✅ GOOD: Single query
for documento in Documento.objects.select_related('cartorio'):
    print(documento.cartorio.nome)  # Dados já carregados

# ✅ GOOD: Prefetch reverse relationships
imoveis = Imovel.objects.prefetch_related('documentos')
for imovel in imoveis:
    for doc in imovel.documentos.all():  # Não faz query
        print(doc.numero)
```

**Memory profiling:**
```bash
# Instale memory_profiler
uv pip install memory-profiler

# Decore função
from memory_profiler import profile

@profile
def funcao_que_usa_muita_memoria():
    data = [i for i in range(1000000)]
    return data

# Execute
uv run python -m memory_profiler meu_script.py
```

### Common Performance Issues

**1. N+1 Queries**
```python
# Use select_related() para ForeignKeys
# Use prefetch_related() para ManyToMany e reverse FKs
```

**2. Falta de Indexes**
```python
# Adicione indexes em campos frequentemente consultados
class MyModel(models.Model):
    campo = models.CharField(max_length=100, db_index=True)
```

**3. Consultas Grandes sem Paginação**
```python
# Use pagination
from django.core.paginator import Paginator

paginator = Paginator(queryset, 25)  # 25 items por página
page_obj = paginator.get_page(page_number)
```

---

## 🔐 Segurança

### Defensive Programming Patterns

**Documentado em:** [AGENTS.md - Best Practices](../AGENTS.md#-best-practices-and-patterns)

**Padrões chave:**

**1. ORM Safe Queries:**
```python
# ✅ GOOD: Primary key lookup
documento = Documento.objects.get(id=documento_id)

# ⚠️ RISKY: Non-unique field
try:
    cartorio = Cartorios.objects.get(nome__iexact=nome)
except Cartorios.MultipleObjectsReturned:
    logger.warning(f"Multiple found: {nome}")
    cartorio = Cartorios.objects.filter(nome__iexact=nome).first()
```

**2. Sempre inclua IDs em dados serializados:**
```python
# Para reconstrução segura
data = {
    'id': obj.id,  # ✅ Essential
    'numero': obj.numero,
}
```

**3. CSRF Protection:**
```html
<!-- Em todos os forms POST -->
<form method="post">
    {% csrf_token %}
    ...
</form>
```

```javascript
// Em AJAX requests
$.ajaxSetup({
    headers: { "X-CSRFToken": getCookie("csrftoken") }
});
```

**4. SQL Injection Prevention:**
```python
# ✅ GOOD: Django ORM (parametrizado automaticamente)
Documento.objects.filter(numero=user_input)

# ❌ BAD: Raw SQL sem parametrização
cursor.execute(f"SELECT * FROM table WHERE numero = '{user_input}'")

# ✅ GOOD: Raw SQL parametrizado
cursor.execute("SELECT * FROM table WHERE numero = %s", [user_input])
```

---

## 🛠️ Ferramentas Úteis

### Django Extensions

```bash
uv pip install django-extensions
```

**Comandos úteis:**
```bash
# Shell com modelos importados automaticamente
uv run python manage.py shell_plus

# Mostra URLs configuradas
uv run python manage.py show_urls

# Gera diagrama de modelos (requer graphviz)
uv run python manage.py graph_models -a -o models.png

# Valida templates
uv run python manage.py validate_templates
```

### Pre-commit Hooks

```bash
# Instale pre-commit
uv pip install pre-commit

# Configure .pre-commit-config.yaml
# (arquivo já existe no projeto)

# Instale hooks
pre-commit install

# Execute manualmente
pre-commit run --all-files
```

### Database GUI

**DBeaver (recomendado):**
- Free e open-source
- Suporta PostgreSQL e SQLite
- https://dbeaver.io/

**Alternativas:**
- pgAdmin (PostgreSQL)
- DB Browser for SQLite

---

## 📚 Recursos Adicionais

### Documentação

- **Django:** https://docs.djangoproject.com/
- **D3.js:** https://d3js.org/
- **Bootstrap 5:** https://getbootstrap.com/docs/5.1/
- **WeasyPrint:** https://weasyprint.org/
- **Projeto:** [AGENTS.md](../AGENTS.md)

### Livros Recomendados

- **Two Scoops of Django** - Best practices
- **Django for Professionals** - Production-ready Django
- **Fluent Python** - Advanced Python

### Comunidade

- **Django Brasil:** https://t.me/djangobrasil
- **Python Brasil:** https://python.org.br/
- **Stack Overflow:** Tag [django]

---

## 🎯 Checklist do Desenvolvedor

Antes de submeter PR:

- [ ] Código segue PEP 8 e convenções do projeto
- [ ] Testes escritos e passando
- [ ] Cobertura de testes mantida ou melhorada
- [ ] Documentação atualizada (se necessário)
- [ ] Migrações criadas (se alterou models)
- [ ] Sem queries N+1 introduzidas
- [ ] CSRF protection em forms
- [ ] Logs apropriados adicionados
- [ ] Code review interno feito
- [ ] Commit messages descritivos
- [ ] Branch atualizada com develop
- [ ] Sem conflitos de merge

---

**[⬅️ Voltar ao README principal](../README.md)**
