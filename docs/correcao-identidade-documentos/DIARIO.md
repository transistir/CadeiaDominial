# Diário de desenvolvimento

Use entradas curtas e cronológicas. Decisões não podem existir apenas em conversa, comentário de código ou memória da IA.

## Decisões já estabelecidas

### 2026-07-11 — Identidade canônica

- Documento é identificado por tipo, número normalizado e cartório.
- Número sozinho serve apenas para pesquisa textual.
- CNS é o identificador estável preferido para apresentar o cartório ao usuário.
- Zeros à esquerda serão preservados.
- “Início de Matrícula” não pode alterar automaticamente o cartório de outro documento.
- Correção de dados será precedida por auditoria e não fará consolidação automática de ambiguidades.

## Modelo de nova entrada

```text
### AAAA-MM-DD HH:MM — TXX — título
- Estado inicial:
- Responsável/IA:
- Hipótese ou objetivo:
- Arquivos pretendidos:
- Decisões tomadas:
- Comandos executados:
- Resultado dos testes:
- Bloqueios/riscos:
- Próximo passo pequeno:
```

## Histórico

### 2026-07-12 16:41 — T21 — modelo estruturado `LancamentoOrigem`

- Estado final: CONCLUÍDA.
- O novo model preserva a origem por lançamento com índice, tipo documental, número normalizado, cartório e metadados de livro/folha.
- A validação normaliza o número com a mesma regra do restante do sistema e converte inconsistências em `ValidationError`.
- Foi criada a migração 0046 e o ajuste de estado 0047 para estabilizar a chave primária sob `DEFAULT_AUTO_FIELD = BigAutoField`.
- Testes cobriram múltiplas origens no mesmo lançamento, cartórios distintos, normalização e bloqueio de duplicidade estrutural.
- Regressão conjunta com a suíte de identidade: 59 testes aprovados; `manage.py check`, `makemigrations --check --dry-run` e `git diff --check` sem erros.
- A nova tabela ainda não foi aplicada ao banco dev compartilhado.
- Próximo passo: T22, gravar origens estruturadas.

### 2026-07-12 16:34 — T20 — cartório `NOT NULL`

- Estado final: CONCLUÍDA.
- A migração 0045 lista e bloqueia imóveis sem cartório antes de alterar a coluna.
- Em schema avançado, o banco rejeita `NULL`; a reversão restaura tecnicamente a coluna anulável.
- Regressão conjunta T17–T20: 64 testes aprovados; modelos sincronizados, `manage.py check` e `git diff --check` sem erros.
- As migrações 0043–0045 não foram aplicadas ao banco dev compartilhado e exigem nova auditoria no ambiente alvo.
- Próximo passo: T21, modelo estruturado `LancamentoOrigem`.

### 2026-07-12 15:15 — T19 — impedir novas ausências de cartório

- Estado final: CONCLUÍDA; CT-07 aprovado.
- `Imovel.clean()` e a criação via `save()` recusam novos registros sem cartório, preservando atualização temporária de legados até T20.
- `cartorio` foi incluído em `ImovelForm.Meta.fields`, corrigindo a cópia do campo selecionado antes da validação do modelo.
- Suíte focada e regressão T17/T18: 61 testes aprovados.
- Operações em massa/SQL direto ficaram deliberadamente para o bloqueio de banco da T20.

### 2026-07-12 15:11 — T18 — constraint de identidade do Imovel

- Estado final: CONCLUÍDA.
- A constraint `unique_imovel_identidade_registral` usa `(tipo_documento_principal, matricula, cartorio)`.
- A migração 0044 audita conflitos canônicos antes do avanço e conflitos com a constraint antiga antes da reversão.
- A obrigatoriedade de cartório não foi antecipada: prevenção de novos `NULL` pertence à T19 e alteração de coluna à T20.
- Testes cobriram avanço limpo, bloqueio por conflito, coexistência de tipos homônimos, duplicata exata e reversão incompatível.
- Execução conjunta T17/T18: 59 testes aprovados; `--expect-final` aprovado no schema de teste; modelos sincronizados e `manage.py check` sem erros.
- A migração 0044 não foi aplicada ao banco dev compartilhado.
- Próximo passo: T19/CT-07, impedir novos registros sem cartório.

### 2026-07-12 14:48 — T17 — constraint de identidade de Documento

- Estado final: CONCLUÍDA; T02 também saiu de revisão.
- O modelo e a migração 0043 usam unicidade `(tipo, numero, cartorio)`.
- A migração audita identidades canônicas antes da alteração e interrompe conflitos/entradas inválidas sem consolidar dados.
- A reversão audita previamente se a constraint antiga `(numero, cartorio)` comporta os dados atuais e interrompe com mensagem clara quando não comporta.
- Testes separados cobriram avanço limpo, avanço bloqueado, constraint efetiva e reversão bloqueada.
- Execução conjunta: 56 testes aprovados, sem falhas esperadas; `makemigrations --check --dry-run` sem mudanças e `manage.py check` sem erros.
- A migração 0043 não foi aplicada ao banco dev compartilhado; no ambiente alvo, executar primeiro `auditar_identidade_documentos --fail-on-conflict`.
- Próximo passo: T18, constraint do documento principal de Imovel.

### 2026-07-12 14:31 — T16 — verificador estrutural por ambiente

- Estado final: CONCLUÍDA.
- Criado `verificar_estrutura_ambiente`, com seleção de `--database`, saída `--json`, `--fail-on-problem` e `--expect-final`.
- O comando informa migrações pendentes, migrações aplicadas sem arquivo, constraints únicas atuais e atendimento das constraints finais planejadas.
- Teste com captura de queries e auditoria estática confirmaram ausência de escrita ou execução de migrações.
- Suíte focada: 53 testes, 52 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- Banco dev PostgreSQL: zero migrações pendentes/desconhecidas; Documento ainda usa `(numero, cartorio_id)` e Imovel usa `(matricula, cartorio_id)`.
- `--expect-final` falha intencionalmente até as T17/T18 criarem as constraints com tipo.
- Próximo passo: T17, constraint de Documento.

### 2026-07-12 13:42 — T15 — auditoria somente leitura

- Estado final: CONCLUÍDA.
- Criado `auditar_identidade_documentos`, com saída humana ou `--json` e opção `--fail-on-conflict`.
- O comando agrupa por tipo, número normalizado e cartório; relata conflitos, números inválidos e documentos sem cartório sem escolher correções.
- Teste com captura de queries confirmou ausência de SQL de escrita; a auditoria estática também não encontrou chamadas de gravação.
- Suíte focada: 51 testes, 50 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- No banco dev, foram auditados 1.220 documentos: zero conflitos, zero inválidos e zero sem cartório.
- O comando deve ser repetido no banco espelhado de homologação antes das migrações.
- Próximo passo: T16, verificador de migrações e constraints por ambiente.

### 2026-07-12 13:38 — T14 — serviços ativos de árvore

- Estado final: CONCLUÍDA.
- Foi criado um resolvedor contextual de aresta por lançamento, reutilizado no tronco, importados, árvore e cadeia completa.
- Origens são resolvidas por tipo, número normalizado e `cartorio_origem`; ausências e ambiguidades não escolhem `.first()`.
- Conjuntos de processados, conexões e cálculo de níveis passaram a usar IDs de documentos.
- CT-18 cobriu pais da árvore, expansão da cadeia completa, documentos importados e tronco principal.
- Suíte focada: 48 testes, 47 aprovados e uma falha esperada de T17; `manage.py check` e auditoria estática sem erros.
- No banco dev, o imóvel 5 agora segue `M9443` para `M9442` de Amambai (ID 163), sem entrar em `T16921` ou nos homônimos de Ponta Porã.
- Próximo passo: T15, comando somente leitura de auditoria de dados.

### 2026-07-12 13:23 — T13 — `HierarquiaOrigemService`

- Estado final: CONCLUÍDA.
- Resolução e criação passaram a priorizar `lancamento.cartorio_origem`, com fallback explícito para o cartório do documento apenas quando ausente.
- A identidade inclui tipo, número normalizado e cartório; resultados ambíguos não são escolhidos nem recriados.
- A chave de origens processadas passou a incluir também o cartório.
- CT-16/CT-19 confirmaram resolução e criação em B sem selecionar ou alterar A.
- Suíte focada: 44 testes, 43 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- Próximo passo: T14/CT-18.

### 2026-07-12 13:21 — T12 — proibir alteração automática de cartório

- Estado final: CONCLUÍDA.
- Foram removidos os métodos legados que classificavam um homônimo sem lançamentos como edição válida e gravavam outro cartório nele.
- CT-20 confirmou que o início de matrícula em B preserva cartório e observações do documento homônimo em A.
- Suíte focada: 42 testes, 41 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A auditoria não encontrou definições, chamadas ou marcações de observação da antiga alteração automática.
- Próximo passo: T13/CT-16 e CT-19.

### 2026-07-12 13:07 — T11 — criação automática de origem

- Estado final: CONCLUÍDA.
- A validação e os dois caminhos de criação passaram a resolver tipo, número normalizado e cartório antes de criar ou reutilizar uma origem.
- O fluxo não interpreta mais um homônimo de outro cartório como edição do registro existente.
- CT-19 confirmou a criação em B sem alterar A e a ausência de duplicação quando B já existe.
- Suíte focada: 41 testes, 40 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- Os métodos legados capazes de alterar cartório ficaram sem chamadores e serão removidos na T12.
- Próximo passo: T12/CT-20.

### 2026-07-12 13:03 — T10 — obtenção da cadeia de origem

- Estado final: CONCLUÍDA.
- A cadeia informativa passou a reutilizar a resolução contextual criada para a T09.
- CT-18/T10 confirmou que a cadeia contém a origem do `cartorio_origem` e exclui o homônimo de outro cartório.
- Suíte focada: 39 testes, 38 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A auditoria estática não encontrou mais consultas de `Documento` por número isolado em `duplicata_verificacao_service.py`.
- Próximo passo: T11/CT-19.

### 2026-07-12 13:01 — T09 — recursão de documentos importáveis

- Estado final: CONCLUÍDA.
- O cálculo recursivo passou a resolver cada origem pelo tipo do prefixo, número normalizado e `lancamento.cartorio_origem`.
- Origem sem cartório, inexistente ou ambígua não é selecionada automaticamente.
- CT-18/T09 confirmou que o homônimo de outro cartório não entra na lista de importáveis.
- Suíte focada: 38 testes, 37 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A busca isolada restante no serviço está em `obter_cadeia_dominial_origem` e pertence à T10.
- Próximo passo: T10/CT-18.

### 2026-07-12 13:00 — T08 — verificação inicial de duplicata

- Estado final: CONCLUÍDA.
- A busca inicial passou a resolver a origem por tipo do prefixo, número normalizado e cartório, sem selecionar homônimo de outro cartório.
- CT-17 e casos de normalização/distinção de tipo foram adicionados à suíte atual de identidade.
- Suíte focada: 37 testes, 36 aprovados e uma falha esperada de T17; `manage.py check` sem erros.
- A suíte legada `dominial.tests.test_duplicata_verificacao` tem 18 erros preexistentes antes dos testes, pois usa `DocumentoTipo(descricao=...)`, campo inexistente no modelo atual.
- As consultas recursivas por número isolado foram mantidas intencionalmente para T09 e T10.
- Próximo passo: T09/CT-18.

### 2026-07-12 12:50 — decisão de homologação

- O teste manual da T07 foi adiado para um servidor de testes com cópia controlada do banco e participação dos usuários.
- T07 permanece EM REVISÃO; o teste manual não foi declarado como aprovado.
- Ao final do desenvolvimento será criado um branch separado do `main` para implantação e validação nesse servidor.
- O caso local do imóvel 5 revelou que a carga inicial ainda pode oferecer uma origem inexistente no `cartorio_origem`; o achado permanece pendente de correção/reclassificação antes da aprovação da T07.

### 2026-07-11 11:10 — checkpoint solicitado

- Trabalho salvo para retomada em `CHECKPOINT_ATUAL.md`.
- T07 permanece em revisão aguardando o teste manual da tabela.
- Próxima tarefa prevista após a validação: T08/CT-17.

### 2026-07-11 11:09 — T07 — tabela da cadeia

- Estado: EM REVISÃO, aguardando teste manual.
- Todas as resoluções de Documento no serviço da tabela passaram a usar tipo, número normalizado e `cartorio_origem` do lançamento.
- Origem sem cartório ou ambígua não é selecionada automaticamente.
- A expansão de importados, escolha específica, maior origem, recursão e garantia de documentos usam o mesmo resolvedor contextual.
- Suíte focada: 35 testes, 34 aprovados e uma falha esperada de T17.
- Auditoria estática não encontrou mais `Documento.objects.filter(numero=...)` no serviço da tabela.
- Teste manual solicitado na rota `tis/<tis_id>/imovel/<imovel_id>/cadeia-tabela/`.

### 2026-07-11 10:59 — T06 — resolvedor central

- Estado final: CONCLUÍDA.
- Criado serviço com resultados explícitos `nao_encontrado`, `encontrado` e `ambiguo`.
- A consulta sempre restringe tipo e cartório; candidatos são comparados pelo número normalizado.
- Dados legados `M123` e canônicos `123` juntos geram ambiguidade, sem seleção por `.first()`.
- Suíte focada: 30 testes, 29 aprovados e uma falha esperada de T17.
- Não há alteração visual nem teste manual de navegador nesta tarefa.

### 2026-07-11 10:54 — T05 — DocumentoIdentidade

- Estado final: CONCLUÍDA.
- Criado valor imutável e comparável com tipo, número normalizado e `cartorio_id`.
- Tipo e formatos equivalentes são normalizados na construção.
- Identidade sem tipo/cartório e IDs não positivos são recusados.
- Suíte focada: 24 testes, 23 aprovados e uma falha esperada de T17.
- Não há alteração visual nem teste manual de navegador nesta tarefa.

### 2026-07-11 10:50 — T04 — normalização do número documental

- Estado final: CONCLUÍDA.
- Criada função pura que remove prefixo compatível e espaços de apresentação.
- Zeros à esquerda, pontuação e espaços internos são preservados.
- Prefixo incompatível, tipo desconhecido, texto vazio e prefixo sem número produzem erros explícitos.
- Suíte focada: 17 testes, 16 aprovados e uma falha esperada já conhecida de T17.
- Não há alteração visual nem teste manual de navegador nesta tarefa.

### 2026-07-11 10:46 — T02/T03 — testes-base e formulário

- Banco de testes passou a ser criado do zero após o ajuste da migração 0026.
- A suíte legada executou 54 testes, com 47 erros e 1 falha preexistentes; principais causas: fixtures com campos removidos (`descricao`, `sncr`), dependência `pytest` ausente e `test_onr_post.py` inválido.
- Foi criada uma suíte isolada com oito testes: sete passaram e um é falha esperada da constraint a ser corrigida em T17.
- Os testes revelaram que `clean_matricula()` lia `cartorio` cedo demais e não validava duplicatas. A validação foi movida para `clean()` e passou a considerar tipo+número+cartório.
- T03 concluída; T02 permanece em revisão até CT-05/T06 e remoção da falha esperada em T17.

### 2026-07-11 10:40 — T01 — auditoria de consultas

- Estado final: CONCLUÍDA.
- Foram classificados fluxos ativos, parcialmente qualificados, pesquisas legítimas e implementações de backup.
- A implementação ativa da árvore é `hierarquia_arvore_service.py`.
- Resultado detalhado em `AUDITORIA_CONSULTAS.md`.

### 2026-07-11 10:41 — Infraestrutura de testes — migração duplicada

- `python manage.py check` passou no contêiner dev.
- A criação limpa do banco de testes falhou porque `0025` e `0026` adicionavam `Documento.cri_atual` e `Documento.cri_origem` duas vezes.
- Decisão: manter `0026` no histórico como no-op; ambientes que já a aplicaram permanecem inalterados e bancos novos passam a ser criáveis.
- O banco dev não foi apagado nem alterado manualmente.

### 2026-07-11 — Criação do acompanhamento

- Foram criados backlog, plano de testes, matriz rastreável e este diário.
- Nenhuma alteração funcional ou migração foi realizada.
- A execução local dos testes ainda depende de um ambiente Python com Django instalado.
