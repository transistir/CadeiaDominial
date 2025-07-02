# Refatoração - Estrutura Modular

## Visão Geral

Este documento descreve a nova estrutura modular implementada na Fase 1 da refatoração do projeto Cadeia Dominial.

## Nova Estrutura de Diretórios

```
dominial/
├── views/                    # Views organizadas por domínio
│   ├── __init__.py
│   ├── tis_views.py         # Views de Terras Indígenas
│   ├── imovel_views.py      # Views de Imóveis
│   ├── documento_views.py   # Views de Documentos
│   ├── lancamento_views.py  # Views de Lançamentos
│   ├── cadeia_dominial_views.py  # Views da Cadeia Dominial
│   ├── api_views.py         # Views de API
│   └── autocomplete_views.py # Views de Autocomplete
├── models/                   # Models organizados por domínio
│   ├── __init__.py
│   ├── tis_models.py        # Models de Terras Indígenas
│   ├── pessoa_models.py     # Models de Pessoas
│   ├── imovel_models.py     # Models de Imóveis
│   ├── documento_models.py  # Models de Documentos
│   ├── lancamento_models.py # Models de Lançamentos
│   └── alteracao_models.py  # Models de Alterações
├── services/                 # Lógica de negócio
│   ├── __init__.py
│   ├── hierarquia_service.py    # Lógica de hierarquia
│   ├── documento_service.py     # Operações com documentos
│   ├── lancamento_service.py    # Operações com lançamentos
│   └── validacao_service.py     # Validações complexas
├── forms/                    # Forms organizados por domínio
│   ├── __init__.py
│   ├── tis_forms.py         # Forms de Terras Indígenas
│   ├── imovel_forms.py      # Forms de Imóveis
│   ├── documento_forms.py   # Forms de Documentos
│   └── lancamento_forms.py  # Forms de Lançamentos
├── utils/                    # Utilitários
│   ├── __init__.py
│   ├── hierarquia_utils.py  # Utilitários de hierarquia
│   ├── validacao_utils.py   # Utilitários de validação
│   └── formatacao_utils.py  # Utilitários de formatação
└── templates/dominial/       # Templates organizados
    ├── components/           # Componentes reutilizáveis
    ├── js/                  # JavaScript separado
    └── css/                 # CSS separado
```

## Benefícios da Nova Estrutura

### 1. **Modularidade**
- Cada domínio tem seus próprios arquivos
- Fácil localização de código
- Redução de conflitos de merge

### 2. **Manutenibilidade**
- Código mais organizado e legível
- Responsabilidades bem definidas
- Facilita debugging e correções

### 3. **Escalabilidade**
- Estrutura preparada para crescimento
- Fácil adição de novos domínios
- Separação clara de responsabilidades

### 4. **Testabilidade**
- Funções menores e mais focadas
- Facilita criação de testes unitários
- Melhor cobertura de código

## Compatibilidade

A nova estrutura mantém total compatibilidade com o código existente através de:

1. **Imports automáticos** no `__init__.py` principal
2. **Estrutura de exports** em cada pacote
3. **Nomes de classes e funções** preservados

## Próximos Passos

### Fase 2: Refatoração das Views
- Separar views por domínio
- Extrair lógica de negócio para services
- Criar mixins para funcionalidades comuns

### Fase 3: Refatoração dos Templates
- Extrair componentes reutilizáveis
- Separar JavaScript e CSS
- Reduzir tamanho dos templates

### Fase 4: Implementação de Services
- Completar implementação dos services
- Adicionar validações complexas
- Implementar lógica de hierarquia otimizada

## Como Usar

### Importando Models
```python
# Antes (ainda funciona)
from dominial.models import TIs, Imovel

# Novo (recomendado)
from dominial.models.tis_models import TIs
from dominial.models.imovel_models import Imovel
```

### Importando Forms
```python
# Antes (ainda funciona)
from dominial.forms import TIsForm

# Novo (recomendado)
from dominial.forms.tis_forms import TIsForm
```

### Importando Services
```python
from dominial.services import HierarquiaService, DocumentoService
```

### Importando Utils
```python
from dominial.utils import validar_cpf, formatar_cpf
```

## Migração Gradual

A refatoração foi implementada de forma que:
1. **Código existente continua funcionando** sem alterações
2. **Novos desenvolvimentos** podem usar a nova estrutura
3. **Migração pode ser feita gradualmente** sem quebrar funcionalidades

## Padrões de Nomenclatura

- **Models**: `dominio_models.py` (ex: `tis_models.py`)
- **Views**: `dominio_views.py` (ex: `tis_views.py`)
- **Forms**: `dominio_forms.py` (ex: `tis_forms.py`)
- **Services**: `dominio_service.py` (ex: `hierarquia_service.py`)
- **Utils**: `dominio_utils.py` (ex: `hierarquia_utils.py`) 