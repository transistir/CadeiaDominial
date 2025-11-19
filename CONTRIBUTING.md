# 🤝 Guia de Contribuição

Obrigado por considerar contribuir com o Sistema de Cadeia Dominial! Este documento fornece diretrizes para contribuir com o projeto.

---

## 📖 Sumário

- [Código de Conduta](#-código-de-conduta)
- [Como Posso Contribuir?](#-como-posso-contribuir)
- [Processo de Desenvolvimento](#-processo-de-desenvolvimento)
- [Padrões de Código](#-padrões-de-código)
- [Processo de Pull Request](#-processo-de-pull-request)
- [Reportando Bugs](#-reportando-bugs)
- [Sugerindo Funcionalidades](#-sugerindo-funcionalidades)

---

## 📜 Código de Conduta

### Nossa Promessa

No interesse de promover um ambiente aberto e acolhedor, nós, como contribuidores e mantenedores, nos comprometemos a tornar a participação em nosso projeto e nossa comunidade uma experiência livre de assédio para todos.

### Padrões

**Comportamentos que contribuem para um ambiente positivo:**
- ✅ Usar linguagem acolhedora e inclusiva
- ✅ Respeitar pontos de vista e experiências diferentes
- ✅ Aceitar críticas construtivas com elegância
- ✅ Focar no que é melhor para a comunidade
- ✅ Mostrar empatia com outros membros da comunidade

**Comportamentos inaceitáveis:**
- ❌ Uso de linguagem ou imagens sexualizadas
- ❌ Comentários insultuosos/depreciativos e ataques pessoais
- ❌ Assédio público ou privado
- ❌ Publicar informações privadas de terceiros sem permissão
- ❌ Outras condutas que possam ser consideradas inapropriadas

---

## 💡 Como Posso Contribuir?

### 1. Reportar Bugs

Encontrou um bug? Ajude-nos a corrigi-lo!

**Antes de reportar:**
- Verifique se já não existe uma issue sobre o bug
- Confirme que é um bug (e não um erro de configuração)
- Colete informações sobre o ambiente (OS, Python version, etc.)

**Como reportar:** Abra uma [Issue](https://github.com/transistir/CadeiaDominial/issues/new) com:
- Título claro e descritivo
- Passos para reproduzir o problema
- Comportamento esperado vs. atual
- Screenshots (se aplicável)
- Ambiente (OS, Python version, Django version)

### 2. Sugerir Funcionalidades

Tem uma ideia para melhorar o sistema?

**Antes de sugerir:**
- Verifique se já não existe uma issue similar
- Confirme que a funcionalidade faz sentido para o projeto

**Como sugerir:** Abra uma [Issue](https://github.com/transistir/CadeiaDominial/issues/new) com:
- Título claro descrevendo a funcionalidade
- Descrição detalhada do que você quer alcançar
- Por que isso seria útil para outros usuários
- Possível implementação (se tiver ideias)

### 3. Melhorar Documentação

Documentação sempre pode ser melhorada!

**Áreas para contribuir:**
- Corrigir erros de digitação
- Melhorar explicações
- Adicionar exemplos
- Traduzir documentação
- Criar tutoriais e guias

### 4. Escrever Código

Contribuições de código são bem-vindas!

**Tipos de contribuições:**
- Correção de bugs
- Novas funcionalidades
- Melhorias de performance
- Refatoração de código
- Testes adicionais

---

## 🔄 Processo de Desenvolvimento

### 1. Configurar Ambiente de Desenvolvimento

```bash
# Fork o repositório no GitHub
# Clone seu fork
git clone https://github.com/SEU-USUARIO/CadeiaDominial.git
cd CadeiaDominial

# Adicione o repositório original como upstream
git remote add upstream https://github.com/transistir/CadeiaDominial.git

# Configure ambiente
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-test.txt

# Configure .env
cp env.example .env
# Edite .env

# Execute migrações
uv run python manage.py migrate
uv run python manage.py criar_tipos_documento
uv run python manage.py criar_tipos_lancamento
```

### 2. Criar Branch para Sua Contribuição

```bash
# Atualize seu repositório
git checkout develop
git pull upstream develop

# Crie branch para sua mudança
# Use prefixos: feature/, bugfix/, docs/, refactor/
git checkout -b feature/nome-da-funcionalidade
# ou
git checkout -b bugfix/nome-do-bug
```

### 3. Faça Suas Mudanças

**Desenvolvimento:**
- Escreva código limpo e bem documentado
- Siga os padrões do projeto (veja abaixo)
- Adicione testes para novas funcionalidades
- Mantenha commits pequenos e focados

**Testes:**
```bash
# Execute os testes
uv run pytest

# Verifique cobertura
uv run pytest --cov=dominial --cov-report=html

# Certifique-se que todos passam
uv run python manage.py test
```

### 4. Commit Suas Mudanças

**Formato de commit:**
```
Tipo: Descrição curta (50 caracteres max)

Descrição detalhada opcional (72 caracteres por linha)
- Explique o que mudou
- Por que mudou
- Referências a issues: #123

Tipos válidos:
- Add: Nova funcionalidade
- Update: Melhoria em funcionalidade existente
- Fix: Correção de bug
- Refactor: Refatoração de código
- Test: Adicionar/modificar testes
- Docs: Documentação
- Style: Formatação (sem mudança de lógica)
- Chore: Manutenção (deps, build, etc)
```

**Exemplos:**
```bash
git commit -m "Add: Sistema de notificações por email"
git commit -m "Fix: Corrige erro ao importar documento duplicado"
git commit -m "Docs: Atualiza guia de instalação com requisitos"
git commit -m "Test: Adiciona testes para verificação de duplicatas"
```

### 5. Push e Pull Request

```bash
# Push para seu fork
git push origin feature/nome-da-funcionalidade

# Abra Pull Request no GitHub
# Compare: upstream/develop <- seu-fork/feature/nome-da-funcionalidade
```

---

## 📋 Padrões de Código

### Python

**Siga PEP 8:**
```python
# Imports organizados
import os
from django.db import models
from dominial.models import Imovel

# Classes: PascalCase
class MinhaClasse:
    pass

# Funções: snake_case
def minha_funcao(parametro):
    return parametro

# Constantes: UPPER_CASE
MAX_TENTATIVAS = 3

# Docstrings para funções públicas
def funcao_publica(param):
    """
    Descrição breve.

    Args:
        param (str): Descrição

    Returns:
        dict: Descrição do retorno
    """
    return {'result': param}

# Linha máxima: 119 caracteres
# Indentação: 4 espaços
```

### Django

```python
# Models: Singular
class Documento(models.Model):
    numero = models.CharField(max_length=50)

    class Meta:
        verbose_name_plural = "Documentos"

# Services: End with "Service"
class DocumentoService:
    @staticmethod
    def processar(data):
        pass

# Views: Nomes descritivos
def listar_documentos(request):
    pass

def criar_documento(request):
    pass
```

### JavaScript

```javascript
// camelCase
const minhaVariavel = "valor";

function minhaFuncao() {
    return true;
}

// PascalCase para classes
class MinhaClasse {
    constructor() {}
}

// Use const/let (não var)
const constante = "imutável";
let variavel = "mutável";

// ES6+ encorajado
const array = [1, 2, 3];
const dobrado = array.map(x => x * 2);
```

### Templates Django

```html
<!-- Indentação consistente -->
{% extends "base.html" %}

{% block content %}
    <div class="container">
        {% for item in items %}
            <div class="item">
                {{ item.nome }}
            </div>
        {% endfor %}
    </div>
{% endblock %}

<!-- CSRF em forms POST -->
<form method="post">
    {% csrf_token %}
    <!-- campos -->
</form>
```

---

## 🔍 Processo de Pull Request

### Checklist Antes de Submeter

- [ ] Código segue os padrões do projeto
- [ ] Todos os testes passam
- [ ] Novos testes adicionados (para novas funcionalidades)
- [ ] Cobertura de testes mantida ou melhorada
- [ ] Documentação atualizada (se necessário)
- [ ] Migrações criadas (se alterou models)
- [ ] Commits bem escritos e descritivos
- [ ] Branch está atualizada com develop
- [ ] Sem conflitos de merge
- [ ] Sem arquivos desnecessários (pycache, .env, etc)

### Template de Pull Request

```markdown
## Descrição
[Descrição clara do que foi mudado]

## Tipo de Mudança
- [ ] Bug fix (correção sem breaking changes)
- [ ] Nova funcionalidade (sem breaking changes)
- [ ] Breaking change (correção ou funcionalidade que quebra código existente)
- [ ] Documentação

## Como Foi Testado?
[Descreva os testes realizados]

## Checklist
- [ ] Código segue padrões do projeto
- [ ] Auto-review do código realizado
- [ ] Comentários adicionados em código complexo
- [ ] Documentação atualizada
- [ ] Sem novos warnings
- [ ] Testes unitários adicionados
- [ ] Testes passam localmente
- [ ] Mudanças dependentes foram mergeadas

## Screenshots (se aplicável)
[Adicione screenshots]

## Issues Relacionadas
Closes #123
Related to #456
```

### Processo de Review

**O que esperamos:**
1. **Code review** por pelo menos 1 mantenedor
2. **Todos os testes** passando (CI/CD)
3. **Sem conflitos** com develop
4. **Aprovação** de pelo menos 1 reviewer

**O que revisamos:**
- Qualidade do código
- Testes adequados
- Documentação
- Performance
- Segurança
- Compatibilidade

**Tempo de resposta:**
- Feedback inicial: 2-3 dias úteis
- Reviews subsequentes: 1-2 dias úteis

---

## 🐛 Reportando Bugs

### Template de Bug Report

```markdown
## Descrição do Bug
[Descrição clara e concisa]

## Como Reproduzir
1. Vá para '...'
2. Clique em '...'
3. Role até '...'
4. Veja o erro

## Comportamento Esperado
[O que deveria acontecer]

## Comportamento Atual
[O que realmente acontece]

## Screenshots
[Se aplicável]

## Ambiente
- OS: [ex: Ubuntu 20.04]
- Python: [ex: 3.11]
- Django: [ex: 5.2.3]
- Browser: [ex: Chrome 120]

## Contexto Adicional
[Qualquer outra informação relevante]

## Possível Solução
[Se você tiver uma ideia]
```

### Severidade de Bugs

**Crítico** 🔴
- Sistema não inicia
- Perda de dados
- Vulnerabilidade de segurança
- Funcionalidade principal quebrada

**Alto** 🟠
- Funcionalidade importante não funciona
- Workaround difícil
- Afeta muitos usuários

**Médio** 🟡
- Funcionalidade secundária não funciona
- Workaround existe
- Afeta alguns usuários

**Baixo** 🟢
- Problema cosmético
- Fácil workaround
- Afeta poucos usuários

---

## ✨ Sugerindo Funcionalidades

### Template de Feature Request

```markdown
## Problema a Resolver
[Descreva o problema que essa funcionalidade resolveria]

## Solução Proposta
[Descrição clara da funcionalidade desejada]

## Alternativas Consideradas
[Outras soluções que você considerou]

## Benefícios
[Por que isso seria útil]
- Benefício 1
- Benefício 2

## Possível Implementação
[Se tiver ideias técnicas]

## Screenshots/Mockups
[Se aplicável]

## Prioridade Sugerida
- [ ] Alta - Funcionalidade essencial
- [ ] Média - Muito útil
- [ ] Baixa - Nice to have
```

---

## 🎯 Boas Práticas

### Commits

**Faça commits atômicos:**
- Um commit = uma mudança lógica
- Facilita code review
- Facilita reverter mudanças específicas

**Escreva boas mensagens:**
```bash
# ✅ BOM
git commit -m "Fix: Corrige erro ao salvar documento sem cartório

- Adiciona validação de cartório obrigatório
- Mostra mensagem de erro clara ao usuário
- Adiciona teste para validação

Fixes #123"

# ❌ RUIM
git commit -m "fix bug"
git commit -m "alterações"
git commit -m "wip"
```

### Código

**Priorize legibilidade:**
```python
# ✅ BOM - Claro e autoexplicativo
def calcular_area_total_propriedades(propriedades):
    """Calcula área total de uma lista de propriedades."""
    area_total = sum(prop.area for prop in propriedades)
    return area_total

# ❌ RUIM - Obscuro
def calc(p):
    return sum(x.a for x in p)
```

**Evite duplicação:**
```python
# ✅ BOM - DRY (Don't Repeat Yourself)
def formatar_cpf(cpf):
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

def exibir_pessoa(pessoa):
    cpf_formatado = formatar_cpf(pessoa.cpf)
    return f"{pessoa.nome} - {cpf_formatado}"

# ❌ RUIM - Repetição
def exibir_pessoa(pessoa):
    cpf = f"{pessoa.cpf[:3]}.{pessoa.cpf[3:6]}.{pessoa.cpf[6:9]}-{pessoa.cpf[9:]}"
    return f"{pessoa.nome} - {cpf}"

def validar_pessoa(pessoa):
    cpf = f"{pessoa.cpf[:3]}.{pessoa.cpf[3:6]}.{pessoa.cpf[6:9]}-{pessoa.cpf[9:]}"
    # ... validação
```

### Testes

**Teste o que importa:**
```python
# ✅ BOM - Testa comportamento
def test_criar_documento_valida_campos_obrigatorios():
    """Sistema deve validar que número e cartório são obrigatórios."""
    with pytest.raises(ValidationError):
        Documento.objects.create(tipo=tipo_matricula)

# ❌ RUIM - Testa implementação
def test_documento_tem_numero_field():
    """Verifica se modelo tem campo numero."""
    assert hasattr(Documento, 'numero')
```

---

## 📚 Recursos para Contribuidores

### Documentação

- **[README.md](README.md)** - Visão geral do projeto
- **[docs/INSTALLATION.md](docs/INSTALLATION.md)** - Guia de instalação
- **[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)** - Guia de desenvolvimento
- **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** - Guia do usuário
- **[AGENTS.md](AGENTS.md)** - Arquitetura detalhada

### Comunidade

- **GitHub Issues:** Para bugs e features
- **GitHub Discussions:** Para perguntas e discussões
- **Code Review:** Aprenda revisando PRs de outros

### Aprendizado

- **[Django Docs](https://docs.djangoproject.com/)** - Documentação oficial Django
- **[PEP 8](https://pep8.org/)** - Style Guide Python
- **[Git Book](https://git-scm.com/book/pt-br/v2)** - Aprenda Git

---

## 🙏 Reconhecimento

Todos os contribuidores serão reconhecidos!

**Formas de reconhecimento:**
- Listado em CONTRIBUTORS.md
- Menção em release notes
- Agradecimento especial para contribuições significativas

---

## ❓ Dúvidas?

**Não sabe por onde começar?**
- Procure issues marcadas com `good first issue`
- Procure issues marcadas com `help wanted`
- Pergunte nas [GitHub Discussions](https://github.com/transistir/CadeiaDominial/discussions)

**Precisa de ajuda?**
- Abra uma issue com suas dúvidas
- Entre em contato com os mantenedores
- Participe das discussões da comunidade

---

## 📄 Licença

Ao contribuir com este projeto, você concorda que suas contribuições serão licenciadas sob a [Licença MIT](LICENSE).

---

**Obrigado por contribuir! 🎉**

Cada contribuição, por menor que seja, ajuda a tornar o Sistema de Cadeia Dominial melhor para todos.

---

**[⬅️ Voltar ao README principal](README.md)**
