---
tracker:
  kind: linear
  api_key: $LINEAR_API_KEY
  project_slug: "b589976f0398"
  active_states:
    - Todo
    - In Progress
    - Merging
    - Rework
  terminal_states:
    - Closed
    - Cancelled
    - Canceled
    - Duplicate
    - Done
polling:
  interval_ms: 5000
workspace:
  root: ~/dev/cadeia-dominial/workspaces
server:
  port: 4000
  host: "0.0.0.0"
hooks:
  after_create: |
    git clone --depth 1 https://github.com/transistir/CadeiaDominial.git .
    git config user.email "hiurequeiroz@gmail.com"
    git config user.name "Hiure Queiroz"
    python -m venv .venv
    . .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
agent:
  # Debian 13 server has 2 vCPU and 3.7 GiB RAM; keep concurrency conservative.
  max_concurrent_agents: 2
  max_turns: 20
codex:
  command: codex --config shell_environment_policy.inherit=all --config plugins.github@openai-curated.enabled=false app-server
  approval_policy: never
  thread_sandbox: workspace-write
  turn_sandbox_policy:
    type: workspaceWrite
---

Você está trabalhando na issue Linear `{{ issue.identifier }}` do projeto **Cadeia Dominial**.

{% if attempt %}
Contexto de continuação:
- Esta é a tentativa de retry #{{ attempt }} porque o ticket ainda está em estado ativo.
- Continue a partir do estado atual do workspace em vez de reiniciar do zero.
{% endif %}

**Contexto da issue:**
- Identificador: {{ issue.identifier }}
- Título: {{ issue.title }}
- Status atual: {{ issue.state }}
- Labels: {{ issue.labels }}
- URL: {{ issue.url }}

**Descrição:**
{% if issue.description %}
{{ issue.description }}
{% else %}
Nenhuma descrição fornecida.
{% endif %}

## Sobre o projeto

O **Cadeia Dominial** é um sistema Django 5.2 para gerenciamento de cadeia dominial de imóveis.
Stack: Django + PostgreSQL + Gunicorn + Docker.

## Instruções

1. Esta é uma sessão de orquestração autônoma. Não peça intervenção humana.
2. Trabalhe apenas no repositório fornecido no workspace.
3. Use o workpad (`## Codex Workpad`) como fonte de verdade para progresso.
4. Mantenha o status do ticket atualizado no Linear.
5. Antes de mover para `Human Review`, garanta que:
   - Todos os testes passam
   - O código segue os padrões do projeto (ver COMMIT_CONVENTION.md)
   - PR criado com label `symphony`
   - Link do PR e resumo de validação registrados no workpad

## Fluxo de status

- `Todo` → mover para `In Progress` e começar trabalho
- `In Progress` → implementar, testar, criar PR
- `Human Review` → aguardar revisão humana
- `Merging` → executar merge via `land` skill
- `Rework` → recomeçar com base no feedback
- `Done` → estado terminal

## Validação

Antes de cada push, execute:
```bash
. .venv/bin/activate 2>/dev/null || true
python manage.py check
python manage.py test
```
