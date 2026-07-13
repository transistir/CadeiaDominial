# Checkpoint para retomada

Atualizado em: 2026-07-13 (America/Sao_Paulo).

## Resumo executivo

O commit reconstruído `0ff36d3` preserva o trabalho realizado até a T21. A
revisão posterior reabriu T03, T11, T14, T17, T18 e T21; a fila corretiva
R01–R07 foi executada e todas essas tarefas voltaram a `CONCLUÍDA` com nova
evidência. T22–T24 também foram concluídas; a próxima tarefa funcional é T25. T07 permanece separadamente em
revisão por depender de homologação manual.

Leitura obrigatória antes de alterar código:

1. `REVISAO_GERAL_2026-07-13.md` — achados e evidências da revisão.
2. `DECISAO_PERSISTENCIA_CANONICA.md` — decisão obrigatória para R02.
3. `TAREFAS.md` — estados, dependências e ordem R01–R07.
4. `PLANO_TESTES.md` e `MATRIZ_TESTES.md` — novos casos CR-01 a CR-09.
5. Entrada mais recente de `DIARIO.md` — decisões e restrições.

## Estado por grupo

- T01–T02 e T04–T06: concluídas; fundação conceitual preservada.
- T03: concluída; lacuna canônica do formulário/banco corrigida na R02 e validada na R07.
- T07: em revisão; automação existente passa, homologação manual pendente.
- T08–T10 e T12–T13: concluídas.
- T11: concluída; múltiplas origens preservam livro/folha após R05/R07.
- T14: concluída; tronco, conexões e níveis corrigidos nas R03/R04 e regredidos na R07.
- T15–T16 e T19–T20: concluídas.
- T17–T18: concluídas; constraints canônicas corrigidas na R02 e validadas na R07.
- T21: concluída; invariável canônica independente de `full_clean()` após R06/R07.
- T22: concluída; escrita textual e estruturada reconciliadas pelo fluxo funcional.
- T23: concluída; comando histórico conservador, idempotente e auditável.
- T24: concluída; estrutura é preferida e o texto funciona como fallback exclusivo.
- T25–T30: pendentes.
- R01: concluída; decisão arquitetural registrada.
- R02: concluída; CR-01 a CR-04 aprovados.
- R03: concluída; CR-05 aprovado.
- R04: concluída; CR-06 aprovado.
- R05: concluída; CR-07 aprovado.
- R06: concluída; CR-08/CR-09 aprovados.
- R07: concluída; regressão e auditoria consolidadas.

## Próxima tarefa: T25

Objetivo: exibir identidade documental completa nas opções apresentadas ao
usuário, distinguindo homônimos antes da seleção.

Critérios mínimos:

- Mostrar tipo e número do documento.
- Mostrar cartório com CNS e localização suficiente para distinguir homônimos.
- Incluir o imóvel/cadeia quando a opção reutiliza documento existente.
- Cobrir o conteúdo na view/template sem ainda mudar o contrato de seleção da T26.
- Não aplicar migrações ao banco compartilhado.

## Ordem de continuidade

1. T25 — identidade completa nas opções.
2. T26–T30 — seguir dependências do backlog.

## Homologação pendente da T07

1. Usar servidor de testes com cópia controlada do banco.
2. Abrir uma cadeia cujo início de matrícula referencie homônimos em cartórios diferentes.
3. Acessar `/tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/`.
4. Confirmar que apenas o documento do `cartorio_origem` aparece.
5. Alternar múltiplas origens e recarregar a página.
6. Confirmar que nenhuma escolha depende da ordem dos registros ou altera cartório.
7. Registrar ambiente, usuário, IDs e resultado na matriz e no diário.

Não concluir T07 apenas com os testes automáticos.

## Última validação conhecida

```text
98 testes integrados de identidade/origem/migrações no PostgreSQL: PASSOU
17 testes focados de leitura/comando/modelo/migração no SQLite: PASSOU
CR-01 a CR-09: PASSOU
Sintaxe do consumidor JavaScript D3: PASSOU
PostgreSQL 15 e criação limpa SQLite 3.40.1: PASSOU
manage.py check: PASSOU
makemigrations --check --dry-run: PASSOU
git diff --check: PASSOU
suíte global (152 testes): 47 erros e 1 falha legados, contagem de falhas inalterada
```

## Restrições operacionais

- Não aplicar migrações 0043–0049 em ambiente compartilhado sem a auditoria e o roteiro de implantação previstos.
- Não apagar, unir ou corrigir identidades ambíguas automaticamente.
- Não alterar arquivos não rastreados nem usar `git add -A`.
- Não marcar CT/CR como aprovado sem executar o cenário correspondente.
- Não declarar a suíte global aprovada enquanto os débitos legados registrados não forem saneados.

## Ponto seguro de versionamento

- Branch de continuidade: `feature/identidade-documento-cartorio`.
- Commit funcional seguro: `ade9ab1` (`feat(dominial): consolida identidade canonica e origens estruturadas`).
- Estado funcional salvo: R01–R07 e T22–T24 concluídas; T25 é a próxima tarefa.
- T07 continua em revisão exclusivamente pela homologação manual documentada.
- `last.md` foi removido por ser uma resposta informal e desatualizada; este arquivo é a fonte oficial de retomada.
- O banco compartilhado não recebeu as migrações 0043–0049 nem o comando de migração histórica.
- A suíte global ainda possui o baseline conhecido de 47 erros e 1 falha legados; os portões focados atuais passaram.

Se surgir uma tarefa urgente, não reutilize esta árvore com alterações soltas.
Confirme primeiro que o checkpoint está commitado, crie uma branch separada para
a urgência e retorne depois a esta branch. Nunca use `git add -A`: existem dumps,
bancos, caches e dependências locais não rastreados que não pertencem ao escopo.
