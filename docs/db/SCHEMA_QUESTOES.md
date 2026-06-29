# Questões detalhadas do schema (Q1–Q25)

Este documento lista **perguntas técnicas e de coluna** levantadas durante a revisão cega do schema v2. As respostas estão em `docs/db/SCHEMA_RESPOSTAS.md`.

> 📌 **Decisões de arquitetura de alto nível** (Q1–Q15 + Q11b: cascade, soft-delete, cardinalidade de fim de cadeia, criptografia, validação de CPF/CNPJ, visualização no React Flow, MOVE, delete compartilhado, etc.) estão em `docs/db/SCHEMA_DECISOES_PENDENTES.md`. Não confunda os dois documentos — este aqui é o detalhamento, o outro é a arquitetura.

Status: **resolvidas** em `docs/db/SCHEMA_RESPOSTAS.md`.

Formato sugerido para responder cada item:

- **Decisao:** opcao escolhida
- **Justificativa:** curta
- **Acoes:** ajustes necessarios no schema/docs/migracao

---

## Q1) `documento.sigla_patrimonio_publico`: manter, derivar ou remover?

**Contexto:** o campo existe, mas nao ha definicao clara de significado, regra de preenchimento ou obrigatoriedade.

**Opcoes:**

1. **Manter como campo livre**
   - Pratico, mas aumenta risco de dados inconsistentes.
2. **Derivar automaticamente** (ex: com base em outras colunas)
   - Consistencia maior, mas precisa regra clara.
3. **Remover** (se nao for usado)
   - Simplifica, reduz risco.

**Recomendacao:** se nao houver uso real, **remover**; se houver, **definir regra e origem**.

---

## Q2) `lancamento.cri_origem_id` vs `origem.cri_id`: duplicidade ou fonte unica?

**Contexto:** o CRI da origem pode ficar em `origem.cri_id`. Manter tambem em `lancamento` cria duplicidade.

**Opcoes:**

1. **Remover `lancamento.cri_origem_id`**
   - Fonte unica em `origem`.
   - Simples e consistente.
2. **Manter os dois com regra de sincronismo**
   - Exige trigger/app para garantir igualdade (fragil).
3. **Manter apenas em `lancamento`**
   - Perde granularidade quando houver varias origens.

**Recomendacao:** **remover `lancamento.cri_origem_id`** e usar somente `origem.cri_id`.

---

## Q3) Multiplas origens por lancamento: explicitar regra e exemplos?

**Contexto:** o modelo permite N origens por lancamento, mas isso precisa ficar cristalino.

**Opcoes:**

1. **Documentar com exemplo simples** (ex: 2 origens, indices 0 e 1)
2. **Criar regra rigida** (ex: `origem.indice=0` e unico para inicio_matricula)

**Recomendacao:** **documentar explicitamente** e manter flexibilidade.

---

## Q4) Significado de `origem.numero`

**Contexto:** ambiguidade se o campo e o numero da matricula/transcricao de origem ou outra coisa.

**Opcoes:**

1. **Numero do documento de origem** (matricula/transcricao)
2. **Outro conceito** (precisa campo proprio)

**Recomendacao:** **definir como numero do documento de origem** e deixar isso explicito no doc.

---

## Q5) Vinculo entre documentos criados e suas origens

**Contexto:** `documento.lancamento_origem_id` liga o documento ao lancamento, mas nao identifica **qual origem** gerou o documento quando ha varias origens.

**Opcoes:**

1. **Adicionar `documento.origem_id`** (FK para `origem`)
2. **Regra deterministica** (ex: doc criado a partir de `origem.indice=0`)
3. **Nao vincular** (aceitar ambiguidade)

**Recomendacao:** **opcao 1** (melhor rastreabilidade e deletes corretos).

---

## Q6) Cascades podem apagar documentos de outro imovel?

**Contexto:** com `lancamento` criando documentos, um delete pode apagar documentos de outro imovel caso o lancamento esteja ligado a outro contexto.

**Opcoes:**

1. **Permitir** (assumir que um lancamento so cria docs do mesmo imovel)
2. **Bloquear via regra** (ex: validar `documento.imovel_id == lancamento.documento.imovel_id`)
3. **Remover cascade** e deletar via app

**Recomendacao:** **opcao 2** (regra de consistencia explicita).

---

## Q7) `documento.is_principal`: como garantir "exatamente um"?

**Contexto:** o banco garante "no maximo um" via unique parcial, mas nao garante "pelo menos um".

**Opcoes:**

1. **Trigger/aplicacao** para garantir que sempre exista um principal
2. **Permitir zero** (aceitar estados incompletos)

**Recomendacao:** **opcao 1** para integridade.

---

## Q8) Normalizacao de `documento.numero` (apenas digitos) pode gerar colisao?

**Contexto:** numeros com letras podem colidir apos normalizacao.

**Opcoes:**

1. **Normalizar e resolver colisao manualmente**
2. **Manter campo bruto paralelo** (`numero_raw`)
3. **Nao normalizar**

**Recomendacao:** **opcao 2** (preserva rastreio).

---

## Q9) `numero_lancamento` obrigatorio: como migrar dados legados?

**Contexto:** a constraint exige valor > 0 e unico por documento.

**Opcoes:**

1. **Preencher com ordem por data/id**
2. **Permitir NULL temporariamente** e depois backfill
3. **Gerar automaticamente se vazio**

**Recomendacao:** **opcao 2** (migra com menos risco).

---

## Q10) `lancamento_tipo.requer_*_origem`: significado e uso

**Contexto:** flags sao para UI/validacao, nao para DB. Ainda assim, precisam de definicao.

**Opcoes:**

1. **Definir que se aplicam a cada origem**
2. **Definir que se aplicam ao lancamento (como um todo)**
3. **Remover flags**

**Recomendacao:** **opcao 1** (coerente com tabela `origem`).

---

## Q11) `cartorio_transmissao`: entrada livre vs tabela controlada

**Contexto:** campo e "manual", mas FK exige registro.

**Opcoes:**

1. **Criar registro automaticamente se nao existir**
2. **Obrigar cadastro previo**

**Recomendacao:** **opcao 1** (melhor UX).

---

## Q12) Fonte de verdade: doc completo ou resumo?

**Contexto:** `SCHEMA_CONSOLIDATED.md` hoje e resumo; ERD contem inventario completo.

**Opcoes:**

1. **Manter doc como resumo** e ERD como inventario completo
2. **Expandir doc** com todas as colunas do ERD

**Recomendacao:** **opcao 1**, com nota explicita (ja adicionada).

---

## Q13) Inconsistência de nomenclatura: `imovel.cartorio_id` vs `documento.cri_id`

**Contexto:** ambos apontam para a tabela `cri`, mas usam nomes diferentes (`cartorio_id` em imovel, `cri_id` em documento e origem). Isso cria confusão e dificulta entendimento.

**Opcoes:**

1. **Renomear `imovel.cartorio_id` para `imovel.cri_id`**
   - Consistência total com demais FKs para `cri`.
2. **Manter como está** e documentar a exceção
   - Menor impacto na migração, mas confuso.
3. **Renomear ambos para `cartorio_id`**
   - Volta à convenção antiga; exige mais mudanças.

**Recomendacao:** **opcao 1** (consistência e clareza).

---

## Q14) `lancamento_pessoa.tipo`: valores válidos não definidos

**Contexto:** o campo `tipo` existe na tabela `lancamento_pessoa`, mas não há CHECK ou documentação dos valores válidos. Exemplos prováveis: `transmitente`, `adquirente`.

**Opcoes:**

1. **Definir CHECK** com valores explícitos (ex: `transmitente`, `adquirente`)
2. **Manter como texto livre** (mais flexível, menos seguro)
3. **Criar tabela de lookup** `lancamento_pessoa_tipo`

**Recomendacao:** **opcao 1** (simplicidade e integridade).

---

## Q15) `lancamento_pessoa`: precedência entre `pessoa_id` e `nome_digitado`

**Contexto:** ambos campos existem, mas não há regra clara de quando usar cada um. Cenários: pessoa existente (usa `pessoa_id`) vs pessoa não cadastrada (usa `nome_digitado`)?

**Opcoes:**

1. **`pessoa_id` obrigatório**, `nome_digitado` apenas como cache/display
2. **`pessoa_id` opcional**, `nome_digitado` como fallback quando NULL
3. **Regra XOR**: exatamente um dos dois deve estar preenchido

**Recomendacao:** **opcao 2** (flexibilidade com rastreabilidade).

---

## Q16) `origem.indice`: constraint CHECK >= 0 ausente

**Contexto:** a documentação diz que `indice` deve ser >= 0 e contíguo por lançamento, mas não há CHECK explícito no ERD ou no doc. A contiguidade depende de trigger/aplicação.

**Opcoes:**

1. **Adicionar CHECK (`indice >= 0`)** no banco + validação de contiguidade na aplicação
2. **Não adicionar CHECK**, deixar tudo para a aplicação

**Recomendacao:** **opcao 1** (banco garante mínimo, app garante contiguidade).

---

## Q17) ERD não visualiza constraints importantes

**Contexto:** o ERD mostra estrutura e FKs, mas não exibe UNIQUE, CHECK, NOT NULL, nem regras ON DELETE. Isso pode induzir implementadores a erro.

**Opcoes:**

1. **Criar seção de constraints no ERD** (usando notes ou comentários no Mermaid)
2. **Criar documento separado** `SCHEMA_CONSTRAINTS.md` com todas as constraints
3. **Manter apenas no doc** e aceitar que ERD é simplificado

**Recomendacao:** **opcao 2** (clareza sem poluir o ERD).

---

## Q18) `origem.tipo`: CHECK constraint ausente no doc

**Contexto:** a seção 3.2 menciona `tipo` (`matricula`, `transcricao`) brevemente, mas não lista explicitamente o CHECK na definição detalhada como faz para `documento.tipo`.

**Opcoes:**

1. **Adicionar CHECK explícito** na definição de `origem` (seção 3.2)
2. **Remover a restrição** e permitir outros tipos

**Recomendacao:** **opcao 1** (consistência com `documento.tipo`).

---

## Q19) `origem.cri_id`: quando obrigatório?

**Contexto:** o ERD mostra `cri_id` como opcional (`o|--o{`). Mas para `inicio_matricula`, faz sentido exigir CRI de origem. A regra não está explícita.

**Opcoes:**

1. **Obrigatório apenas para `inicio_matricula`** (regra condicional)
2. **Sempre opcional** (app decide)
3. **Sempre obrigatório** (simplifica, mas pode ser restritivo)

**Recomendacao:** **opcao 1** (coerente com semântica de início de matrícula).

---

## Q20) Convenção de nomes: `pessoas` (plural) vs outras tabelas (singular)

**Contexto:** a tabela `pessoas` está no plural, enquanto outras (`cri`, `documento`, `lancamento`, `imovel`, `origem`) estão no singular. Isso quebra a consistência.

**Opcoes:**

1. **Renomear para `pessoa`** (singular, consistente)
2. **Manter `pessoas`** e aceitar a exceção

**Recomendacao:** **opcao 1** (consistência de convenção).

---

## Q21) ERD usa `bool` mas SQLite usa `INTEGER`

**Contexto:** o ERD mostra `bool arquivado`, `bool is_principal`, etc. SQLite não tem tipo BOOLEAN nativo; usa INTEGER (0/1). Isso pode confundir implementadores.

**Opcoes:**

1. **Mudar ERD para `int` com nota** indicando 0/1
2. **Manter `bool` no ERD** e documentar conversão no doc

**Recomendacao:** **opcao 2** (ERD legível, doc com detalhes técnicos).

---

## Q22) Ciclo de FK: `documento ↔ lancamento`

**Contexto:** `documento.lancamento_origem_id → lancamento` e `lancamento.documento_id → documento` criam um ciclo de FKs. Combinado com `ON DELETE CASCADE` em ambos, pode causar comportamento inesperado ou erro de constraint.

**Opcoes:**

1. **Remover CASCADE de `documento.lancamento_origem_id`** (usar SET NULL ou deletar via app)
2. **Manter CASCADE em ambos** e aceitar que a exclusão propaga
3. **Bloquear exclusão de lancamento** quando há documentos criados por ele

**Recomendacao:** **opcao 1** (evita cascades cruzados imprevisíveis).

---

## Q23) `tis.terra_referencia_id` vs `terra_indigena_referencia`

**Contexto:** no ERD, o campo é `terra_referencia_id`, mas a tabela se chama `terra_indigena_referencia`. A relação está correta, mas o nome do campo é abreviado inconsistentemente.

**Opcoes:**

1. **Renomear para `terra_indigena_referencia_id`** (mais explícito)
2. **Manter `terra_referencia_id`** (mais curto, já em uso)

**Recomendacao:** **opcao 2** (praticidade, desde que documentado).

---

## Q24) Migração: como popular `documento.lancamento_origem_id` para dados legados?

**Contexto:** documentos existentes não têm vínculo explícito com o lançamento que os criou (se houver). A migração precisa inferir ou deixar NULL.

**Opcoes:**

1. **Inferir via heurística** (ex: primeiro lançamento do tipo `inicio_matricula` no documento)
2. **Deixar NULL** para legados e preencher apenas para novos
3. **Migração manual/revisão** dos casos ambíguos

**Recomendacao:** **opcao 2** (seguro; evita inferências erradas).

---

## Q25) `lancamento_tipo`: falta campo `nome` legível?

**Contexto:** a tabela `lancamento_tipo` tem apenas `tipo` (valor técnico) e flags. Não há campo para nome/label legível para exibição na UI (ex: "Início de Matrícula", "Registro", "Averbação").

**Opcoes:**

1. **Adicionar campo `nome`** TEXT NOT NULL
2. **Derivar nome no frontend** a partir de `tipo`

**Recomendacao:** **opcao 1** (permite personalização sem mudança de código).
