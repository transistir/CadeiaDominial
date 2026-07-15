# T01 — Auditoria de identidade nas consultas de Documento

Data: 2026-07-11. Escopo: código Python em `dominial/`. Esta auditoria não considera uma pesquisa textual por número como erro enquanto ela não criar vínculos nem escolher um registro.

## Resumo

| Classe | Quantidade/grupos | Risco |
|---|---:|---|
| Relacionamento por número isolado em fluxo ativo | 8 grupos | crítico |
| Relacionamento parcialmente qualificado | 5 grupos | alto |
| Estruturas internas indexadas por número | 3 implementações | alto |
| Pesquisa/diagnóstico intencional | 8 grupos | seguro ou médio |
| Código alternativo/backup | 3 arquivos | não ativo, mas perigoso se reativado |

## Críticos — fluxo ativo

| Arquivo e linha inicial | Trecho/comportamento | Fluxo afetado | Correção prevista |
|---|---|---|---|
| `services/cadeia_dominial_tabela_service.py:306` | `filter(numero=codigo).first()` | lista origem disponível | T07 |
| `services/cadeia_dominial_tabela_service.py:351,373,414,507,538` | resolve origens/escolhas só por número | tabela e expansão recursiva | T07/T14 |
| `services/duplicata_verificacao_service.py:103,171` | `filter(numero=origem_numero).first()` | documentos importáveis e cadeia recursiva | T09/T10 |
| `services/lancamento_origem_service.py:302,408` | procura mesmo número no imóvel antes do cartório | criação e possível alteração de cartório | T11/T12 |
| `services/hierarquia_arvore_service.py:183,197` | origem pai escolhida somente por número | árvore usada pelas views | T14 |
| `services/cadeia_completa_service.py:138` | origem expandida somente por número | cadeia completa e PDF | T14 |
| `utils/hierarquia_utils.py:191,336,345` | documento compartilhado/existente por número | criação e relacionamento de hierarquia | T13/T14 |
| `management/commands/corrigir_cartorios_origem.py:33` | escolhe origem por número | comando que grava correções | corrigir antes de reutilizar |

## Altos — há cartório ou imóvel, mas falta parte da identidade

| Arquivo e linha inicial | Situação | Risco |
|---|---|---|
| `services/duplicata_verificacao_service.py:35` | usa número+cartório, sem tipo | matrícula e transcrição homônimas |
| `services/hierarquia_origem_service.py:61,98` | usa número+cartório, sem tipo; cartório pode vir do documento atual | tipo ou CRI de origem incorreto |
| `services/lancamento_origem_service.py:276,327,382,433` | usa número+cartório, sem tipo em parte do fluxo | colisão entre tipos |
| `services/lancamento_campos_service.py:278` | usa número+cartório, sem tipo | origem associada ao tipo errado |
| `services/documento_service.py:50,64` e duplicado `documento_service_consolidado.py` | número+cartório, sem tipo | API de serviço conceitualmente incompleta |

## Estruturas internas perigosas

| Arquivo | Estrutura | Problema |
|---|---|---|
| `services/hierarquia_arvore_service.py:103,118` | `documentos_por_numero[documento.numero]` | um nó sobrescreve homônimo de outro cartório |
| `services/hierarquia_arvore_service.py:156-194` | conjunto processado recebe número de origem | homônimos são descartados como já processados |
| `services/hierarquia_arvore_service_melhorado.py:172-196,270-286` | mesma estratégia por número | implementação alternativa repete o defeito |

O uso de `documento.id` em conjuntos de processados é seguro e deve ser preservado.

## Pesquisa e diagnóstico

Estas ocorrências podem procurar por número porque retornam coleções, investigam duplicatas ou implementam busca textual. Elas não devem ser reaproveitadas para criar relações:

- `admin.py:297,310`: ação administrativa lista todos por número/cartório.
- `services/documento_service.py:180-184` e versão consolidada: pesquisa textual; quando `cartorio` é informado, filtra por ele.
- `management/commands/listar_duplicatas.py` e `investigar_duplicatas_documentos.py`: agrupamento diagnóstico por número+cartório.
- `management/commands/investigar_documentos_duplicados.py`, `investigar_conexoes_incorretas.py` e `verificar_documentos.py`: diagnóstico explícito.
- `management/commands/testar_conexao_t1004_t2822.py`: comando ad hoc; é ambíguo, mas não integra fluxo de usuário.
- `views/documento_views.py:220`: verificação limitada ao imóvel atual; precisa incluir tipo/cartório se passar a criar relacionamento.

## Código alternativo ou legado

- `hierarquia_arvore_service_backup.py` contém várias escolhas globais com `.first()` e índices por número.
- `hierarquia_arvore_service_corrigido.py` ainda usa número como chave/conjunto, apesar do nome.
- `hierarquia_arvore_service_melhorado.py` tenta variações `M`/`T`, mas ainda escolhe globalmente por número.

A view ativa importa `services.hierarquia_arvore_service.HierarquiaArvoreService`. Os arquivos alternativos não devem ser corrigidos junto com T14 sem primeiro decidir se serão removidos ou formalmente desativados.

## Conclusão

O problema é sistêmico e alcança tabela, importação, cadeia completa, árvore e criação automática. A ordem T06 → T07/T09/T11/T13 → T14 reduz o risco porque fornece uma única resolução antes de substituir consultas. A auditoria final T28 deve repetir esta busca e classificar qualquer ocorrência nova.

## Reavaliação em 2026-07-13

A revisão do commit `0ff36d3` confirmou que as consultas ORM mais críticas
catalogadas acima foram substituídas nos serviços alterados, mas encontrou
identidade implícita por número em estruturas Python ainda ativas:

| Local | Comportamento restante | Correção |
|---|---|---|
| `utils/hierarquia_utils.py` — tronco principal | escolhe o próximo documento com `doc.numero == codigo` | R03 |
| `services/hierarquia_arvore_service.py` — conexões | `from`, `to` e deduplicação usam número | R04 |
| `services/hierarquia_arvore_service.py` — níveis | mapas e visitados usam número | R04 |

Por isso T14 voltou para `EM REVISÃO`. A auditoria T28 continua pendente e deve
examinar tanto consultas ORM quanto chaves, conjuntos, mapas e payloads de
conexão.

Reavaliação após R03/R04: os três comportamentos da tabela acima foram
corrigidos. O tronco resolve a identidade contextual; o serviço ativo e seu
consumidor D3 usam IDs em conexões, deduplicação, visitados e níveis. T14
permanece `EM REVISÃO` somente até a regressão consolidada da R07; as
implementações alternativas continuam fora do fluxo ativo e serão
reclassificadas na T28.

## Fechamento R07 em 2026-07-13

A repetição da busca estática e da regressão confirmou que os fluxos ativos
reabertos não resolvem relacionamentos nem indexam arestas/níveis por número
isolado. O tronco usa identidade contextual; arestas, deduplicação, visitados e
níveis usam IDs; a criação e a verificação usam tipo, número canônico e cartório.

As ocorrências restantes foram classificadas sem ampliação indevida da R07:

- buscas administrativas, textuais e comandos de diagnóstico que retornam ou inspecionam coleções, sem criar relacionamento;
- `hierarquia_arvore_service_backup.py`, `hierarquia_arvore_service_corrigido.py` e `hierarquia_arvore_service_melhorado.py`, que não são importados pelo fluxo ativo e continuam reservados à decisão da T28;
- pontos funcionais não reabertos, como escrita estruturada e serviços legados auxiliares, que permanecem catalogados para T22–T28.

Com os testes CR-01 a CR-09 e CT-08/CT-18 aprovados, T14 pode voltar a
`CONCLUÍDA`. Esta conclusão não substitui a auditoria final T28, que deve decidir
remoção ou desativação formal das implementações alternativas e repetir a busca
em todo o código produzido por T22–T27.

Reavaliação T24: os consumidores relacionais ativos de duplicata/importação,
tronco, árvore, cadeia completa, tabela e hierarquia passaram a usar
`LancamentoOrigemLeituraService`. Havendo estrutura, o texto contraditório é
ignorado; sem estrutura, o fallback textual mantém o contexto explícito do
cartório do lançamento. Apresentação, comandos legados e implementações
alternativas continuam reservados à T25–T28.
