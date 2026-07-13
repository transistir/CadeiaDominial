# Checkpoint para retomada

Atualizado em: 2026-07-12 16:41 (America/Sao_Paulo).

## Estado atual

- T01: concluída — auditoria das consultas.
- T02: concluída — testes-base aprovados após a constraint da T17.
- T03: concluída — formulário valida tipo+número+cartório.
- T04: concluída — normalização canônica.
- T05: concluída — `DocumentoIdentidade` imutável.
- T06: concluída — resolvedor central com estados explícitos.
- T07: em revisão — implementação e testes automáticos concluídos; falta teste manual no navegador.
- T08: concluída — verificação inicial de duplicata usa a identidade completa.
- T09: concluída — recursão de documentos importáveis respeita a identidade completa.
- T10: concluída — cadeia informativa da origem respeita a identidade completa.
- T11: concluída — criação/reutilização automática não altera homônimo de outro cartório.
- T12: concluída — possibilidade legada de alteração automática de cartório removida.
- T13: concluída — `HierarquiaOrigemService` usa identidade completa e cartório do lançamento.
- T14: concluída — árvore, cadeia completa, importados e tronco usam identidade completa e IDs.
- T15: concluída — comando somente leitura audita conflitos de identidade.
- T16: concluída — verificador somente leitura relata migrações e constraints por ambiente.
- T17: concluída — migração segura da identidade completa de Documento criada e testada; ainda não aplicada ao banco dev compartilhado.
- T18: concluída — constraint do Imovel inclui tipo, número e cartório; migração ainda não aplicada ao banco dev compartilhado.
- T19: concluída — formulário e modelo bloqueiam novas criações sem cartório.
- T20: concluída — migração `NOT NULL` criada e testada; ainda não aplicada ao banco dev compartilhado.
- T21: concluída — modelo estruturado `LancamentoOrigem` criado e testado.
- T22 em diante: pendentes.

## Homologação pendente da T07

O teste manual será executado posteriormente em servidor de testes, em branch separado do `main`, com uma cópia controlada do banco e participação dos usuários. A tarefa permanece em revisão até essa validação.

1. Abrir `http://localhost:8000` e autenticar.
2. Escolher uma cadeia cujo “Início de Matrícula” referencie um número existente em dois cartórios.
3. Acessar `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/`.
4. Confirmar que aparece somente o documento do `cartorio_origem` do lançamento.
5. Confirmar que o homônimo de outro cartório não aparece.
6. Alternar múltiplas origens, se existirem, e atualizar a página.
7. Confirmar que nenhuma escolha muda de cartório ou depende da ordem dos registros.

Após aprovação, marcar T07 como `CONCLUÍDA` em `TAREFAS.md`, atualizar CT-16 em `MATRIZ_TESTES.md` para `PASSOU` e registrar ambiente/resultado no `DIARIO.md`.

## Último resultado automatizado

```text
python manage.py test dominial.tests.test_lancamento_origem_model dominial.tests.test_identidade_documento --noinput
59 testes aprovados.
python manage.py check
Sem erros.
python manage.py makemigrations --check --dry-run
No changes detected.
```

Os comandos foram executados no serviço `web` de `docker-compose.dev.yml`.

## Próxima tarefa de desenvolvimento

T22 — gravar origens estruturadas sem remover o campo textual legado.

## Observações importantes

- A suíte legada completa possui erros preexistentes e está documentada no diário.
- A migração `0026_add_cri_fields_to_documento` foi transformada em no-op porque a `0025` já adicionava os mesmos campos e bancos novos não podiam ser criados.
- Não executar migrações destrutivas nem consolidar dados ambíguos automaticamente.
- O diretório possui arquivos do usuário não relacionados; não limpar nem reverter essas alterações.
- Ao final do desenvolvimento, criar um branch separado do `main` para o servidor de homologação; não publicar nem implantar antes dessa etapa.
