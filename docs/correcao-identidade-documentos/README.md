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

## Fluxo de trabalho

1. Escolha somente uma tarefa desbloqueada em `TAREFAS.md`.
2. Troque seu estado de `PENDENTE` para `EM ANDAMENTO`.
3. Registre no `DIARIO.md` o início, hipótese e arquivos pretendidos.
4. Faça a menor alteração capaz de atender ao aceite.
5. Crie ou ajuste os testes indicados na matriz.
6. Registre comandos e resultados reais; não marque teste não executado como aprovado.
7. Marque a tarefa `EM REVISÃO` e preencha suas evidências.
8. Só use `CONCLUÍDA` após todos os critérios de aceite e testes obrigatórios passarem.

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

## Definição global de pronto

O trabalho termina quando criação, consulta, reutilização, importação, tabela, árvore e origens estruturadas modeladas usam a identidade completa; os testes CT-01 a CT-20 estão aprovados; a auditoria não encontra consultas de relacionamento por número isolado; e o roteiro de implantação foi validado em homologação.
