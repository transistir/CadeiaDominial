# Correção da identidade de documentos registrais

Este diretório controla o desenvolvimento da correção que impede que matrículas ou transcrições com o mesmo número, mas de cartórios diferentes, sejam confundidas.

## Regra invariável

A identidade de um documento é:

```text
tipo + número normalizado + cartório
```

O número sozinho nunca pode criar vínculos, escolher documentos, importar cadeias ou alterar cartórios. Prefixos `M` e `T` são apresentação; o tipo deve ser um dado estruturado. Zeros à esquerda devem ser preservados até existir decisão de negócio em contrário.

## Documentos de acompanhamento

- [CHECKPOINT_ATUAL.md](CHECKPOINT_ATUAL.md): ponto exato para retomar o trabalho.
- [TAREFAS.md](TAREFAS.md): backlog, dependências, estado e evidências de cada entrega.
- [AUDITORIA_CONSULTAS.md](AUDITORIA_CONSULTAS.md): inventário inicial das consultas inseguras.
- [PLANO_TESTES.md](PLANO_TESTES.md): estratégia, comandos, níveis e portões de qualidade.
- [MATRIZ_TESTES.md](MATRIZ_TESTES.md): casos obrigatórios e registro da execução.
- [DIARIO.md](DIARIO.md): decisões, bloqueios e histórico cronológico.
- [REVISAO_GERAL_2026-07-13.md](REVISAO_GERAL_2026-07-13.md): revisão do commit reconstruído, achados e critérios para retomada.
- [DECISAO_PERSISTENCIA_CANONICA.md](DECISAO_PERSISTENCIA_CANONICA.md): decisão arquitetural da R01 para a proteção canônica no banco.

## Fluxo de trabalho

1. Escolha somente uma tarefa desbloqueada em `TAREFAS.md`.
2. Troque seu estado de `PENDENTE` para `EM ANDAMENTO`.
3. Registre no `DIARIO.md` o início, hipótese e arquivos pretendidos.
4. Faça a menor alteração capaz de atender ao aceite.
5. Crie ou ajuste os testes indicados na matriz.
6. Registre comandos e resultados reais; não marque teste não executado como aprovado.
7. Marque a tarefa `EM REVISÃO` e preencha suas evidências.
8. Só use `CONCLUÍDA` após todos os critérios de aceite e testes obrigatórios passarem.

Enquanto houver item `RXX` pendente, ele tem prioridade sobre a próxima tarefa
funcional. As tarefas corretivas existem para reabrir critérios que uma revisão
posterior demonstrou ainda não estarem atendidos, sem apagar o histórico da
implementação original.

## Estados permitidos

| Estado | Significado |
|---|---|
| `PENDENTE` | Ainda não iniciada |
| `EM ANDAMENTO` | Há trabalho ativo |
| `BLOQUEADA` | Depende de decisão ou correção externa registrada no diário |
| `EM REVISÃO` | Implementada, aguardando conferência dos critérios |
| `CONCLUÍDA` | Aceite atendido e evidências registradas |

## Restrições de segurança

- Não apagar, unir ou corrigir dados de produção automaticamente.
- Migrações de constraint devem auditar conflitos e falhar com mensagem clara.
- Não substituir uma consulta ambígua por outro `.first()`.
- Pesquisa textual pode usar apenas o número; relacionamento de negócio não pode.
- Alteração de cartório deve ser operação administrativa explícita, nunca efeito colateral de “Início de Matrícula”.
- Cada tarefa deve ser pequena e resultar em uma alteração revisável separadamente.

## Interrupção segura para tarefa urgente

Antes de trocar de assunto, branch ou ferramenta de IA:

1. Atualize `CHECKPOINT_ATUAL.md`, `TAREFAS.md` e `DIARIO.md`.
2. Execute ao menos os testes focados e `git diff --check`.
3. Adicione somente arquivos conhecidos; nunca use `git add -A` neste repositório.
4. Crie um commit de checkpoint na branch da funcionalidade.
5. Confirme o commit com `git log -1 --oneline` e o escopo restante com `git status --short`.
6. Só então crie outra branch para a urgência, a partir do commit salvo.

Para retomar, volte à branch registrada no checkpoint e leia primeiro
`CHECKPOINT_ATUAL.md`. Dumps SQL, bancos locais, caches, dependências e outros
arquivos não rastreados não fazem parte deste desenvolvimento e não devem ser
incluídos por engano.

## Definição global de pronto

O trabalho termina quando criação, consulta, reutilização, importação, tabela, árvore e origens estruturadas modeladas usam a identidade completa; os testes CT-01 a CT-20 estão aprovados; a auditoria não encontra consultas de relacionamento por número isolado; e o roteiro de implantação foi validado em homologação.
