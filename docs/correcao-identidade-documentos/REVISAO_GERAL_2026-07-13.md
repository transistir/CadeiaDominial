# Revisão geral do checkpoint reconstruído

Data: 2026-07-13. Revisão: commit local `0ff36d3`, branch
`feature/identidade-documento-cartorio`, comparado com `origin/main` em
`d78a211`.

## Parecer

O checkpoint é executável e preserva a maior parte das entregas T01–T21, mas
não deve ser tratado como pronto para integração ou implantação. A revisão
reabriu T03, T11, T14, T17, T18 e T21 e criou a fila corretiva R01–R07.

É aceitável publicar a branch apenas como backup/WIP, deixando explícito que
os bloqueadores abaixo ainda existem. Não aplicar as migrações 0043–0047 em
ambiente compartilhado antes de R07.

## Achados que reabriram tarefas

### 1. Unicidade canônica não permanece protegida após a migração

- A auditoria considera `M123` e `123` a mesma identidade.
- As constraints de `Documento` e `Imovel` comparam o texto bruto.
- O formulário de imóvel também consulta o texto bruto.
- Depois da migração, uma nova gravação pode recriar o conflito que a auditoria inicial bloqueou.
- O resolvedor passa então a devolver `ambiguo` para uma identidade que deveria ser única.

Impacto: T03, T17 e T18 reabertas. Correção planejada: R01/R02.

### 2. Conexões e níveis da árvore ainda usam número como chave

Os documentos processados usam ID, mas `from`, `to`, deduplicação, visitados e
cálculo de níveis ainda usam `documento.numero`. Dois nós homônimos de cartórios
diferentes podem ter arestas fundidas ou níveis compartilhados.

Impacto: T14 reaberta. Correção planejada: R04.

### 3. O tronco principal ainda escolhe candidatos por número

Depois de carregar documentos locais e importados, o percurso procura a origem
com `doc.numero == codigo`. Se o imóvel atual contiver um homônimo de outro
cartório, ele pode ser escolhido antes da origem indicada por
`lancamento.cartorio_origem`.

Impacto: T14 reaberta. Correção planejada: R03.

### 4. Múltiplas origens perderam herança de livro e folha

O caminho `_criar_documento_automatico_com_cartorio` inicializa livro e folha
como ausentes e grava `0`, sem aplicar a herança usada no caminho de origem
única. Os testes atuais conferem documento/cartório, mas não os metadados.

Impacto: T11 reaberta. Correção planejada: R05.

### 5. Invariantes ainda dependem de chamadas voluntárias a `full_clean()`

`LancamentoOrigem` normaliza em `clean()`, porém gravações diretas pelo ORM não
executam essa validação automaticamente. O resolvedor central também pode
propagar `ValueError` ao encontrar um candidato legado inválido no mesmo
tipo/cartório.

Impacto: T21 reaberta. Correção planejada: R06.

## Validação executada durante a revisão

| Escopo | Resultado |
|---|---|
| `test_lancamento_origem_model` + `test_identidade_documento` | 59 passaram |
| três suítes de migração T17–T20 | 9 passaram |
| `manage.py check` | sem erros |
| `makemigrations --check --dry-run` | nenhuma mudança detectada |
| suíte `dominial.tests` | 122 executados; 47 erros e 1 falha legados já documentados |
| `git diff --check` | uma linha em branco com espaço no fim de `lancamento_origem_service.py` |

Os testes verdes confirmam os cenários existentes, mas não cobrem os cinco
achados acima. A suíte completa continua inadequada como portão isolado até a
dívida legada ser separada ou corrigida.

## Estado seguro para continuidade

- Nenhuma alteração funcional ficou fora do commit local; as mudanças posteriores a ele estão restritas a esta reorganização documental.
- Existem arquivos não rastreados de banco, dumps, dependências e ferramentas. Não usar `git add -A`.
- T07 permanece em revisão e depende do teste manual em homologação.
- T22–T30 continuam pendentes e não devem ser renumeradas.
- O próximo trabalho de código é R01, não T22.
