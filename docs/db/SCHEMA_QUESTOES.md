# Questoes abertas e decisoes pendentes (Schema Consolidado)

Este documento consolida pontos ambiguos, riscos e decisoes pendentes do schema.  
Use-o para registrar respostas e alinhar o time.

Formato sugerido para responder cada item:
- **Decisao:** opcao escolhida
- **Justificativa:** curta
- **Acoes:** ajustes necessarios no schema/docs/migracao

---

## Q1) `documento.sigla_patrimonio_publico`: manter, derivar ou remover?
**Contexto:** o campo existe, mas nao ha definicao clara de significado, regra de preenchimento ou obrigatoriedade.

**Opcoes:**
1) **Manter como campo livre**  
   - Pratico, mas aumenta risco de dados inconsistentes.
2) **Derivar automaticamente** (ex: com base em outras colunas)  
   - Consistencia maior, mas precisa regra clara.
3) **Remover** (se nao for usado)  
   - Simplifica, reduz risco.

**Recomendacao:** se nao houver uso real, **remover**; se houver, **definir regra e origem**.

---

## Q2) `lancamento.cri_origem_id` vs `origem.cri_id`: duplicidade ou fonte unica?
**Contexto:** o CRI da origem pode ficar em `origem.cri_id`. Manter tambem em `lancamento` cria duplicidade.

**Opcoes:**
1) **Remover `lancamento.cri_origem_id`**  
   - Fonte unica em `origem`.  
   - Simples e consistente.
2) **Manter os dois com regra de sincronismo**  
   - Exige trigger/app para garantir igualdade (fragil).
3) **Manter apenas em `lancamento`**  
   - Perde granularidade quando houver varias origens.

**Recomendacao:** **remover `lancamento.cri_origem_id`** e usar somente `origem.cri_id`.

---

## Q3) Multiplas origens por lancamento: explicitar regra e exemplos?
**Contexto:** o modelo permite N origens por lancamento, mas isso precisa ficar cristalino.

**Opcoes:**
1) **Documentar com exemplo simples** (ex: 2 origens, indices 0 e 1)  
2) **Criar regra rigida** (ex: `origem.indice=0` e unico para inicio_matricula)

**Recomendacao:** **documentar explicitamente** e manter flexibilidade.

---

## Q4) Significado de `origem.numero`
**Contexto:** ambiguidade se o campo e o numero da matricula/transcricao de origem ou outra coisa.

**Opcoes:**
1) **Numero do documento de origem** (matricula/transcricao)  
2) **Outro conceito** (precisa campo proprio)

**Recomendacao:** **definir como numero do documento de origem** e deixar isso explicito no doc.

---

## Q5) Vinculo entre documentos criados e suas origens
**Contexto:** `documento.lancamento_origem_id` liga o documento ao lancamento, mas nao identifica **qual origem** gerou o documento quando ha varias origens.

**Opcoes:**
1) **Adicionar `documento.origem_id`** (FK para `origem`)  
2) **Regra deterministica** (ex: doc criado a partir de `origem.indice=0`)  
3) **Nao vincular** (aceitar ambiguidade)

**Recomendacao:** **opcao 1** (melhor rastreabilidade e deletes corretos).

---

## Q6) Cascades podem apagar documentos de outro imovel?
**Contexto:** com `lancamento` criando documentos, um delete pode apagar documentos de outro imovel caso o lancamento esteja ligado a outro contexto.

**Opcoes:**
1) **Permitir** (assumir que um lancamento so cria docs do mesmo imovel)  
2) **Bloquear via regra** (ex: validar `documento.imovel_id == lancamento.documento.imovel_id`)  
3) **Remover cascade** e deletar via app

**Recomendacao:** **opcao 2** (regra de consistencia explicita).

---

## Q7) `documento.is_principal`: como garantir "exatamente um"?
**Contexto:** o banco garante "no maximo um" via unique parcial, mas nao garante "pelo menos um".

**Opcoes:**
1) **Trigger/aplicacao** para garantir que sempre exista um principal  
2) **Permitir zero** (aceitar estados incompletos)  

**Recomendacao:** **opcao 1** para integridade.

---

## Q8) Normalizacao de `documento.numero` (apenas digitos) pode gerar colisao?
**Contexto:** numeros com letras podem colidir apos normalizacao.

**Opcoes:**
1) **Normalizar e resolver colisao manualmente**  
2) **Manter campo bruto paralelo** (`numero_raw`)  
3) **Nao normalizar**

**Recomendacao:** **opcao 2** (preserva rastreio).

---

## Q9) `numero_lancamento` obrigatorio: como migrar dados legados?
**Contexto:** a constraint exige valor > 0 e unico por documento.

**Opcoes:**
1) **Preencher com ordem por data/id**  
2) **Permitir NULL temporariamente** e depois backfill  
3) **Gerar automaticamente se vazio**

**Recomendacao:** **opcao 2** (migra com menos risco).

---

## Q10) `lancamento_tipo.requer_*_origem`: significado e uso
**Contexto:** flags sao para UI/validacao, nao para DB. Ainda assim, precisam de definicao.

**Opcoes:**
1) **Definir que se aplicam a cada origem**  
2) **Definir que se aplicam ao lancamento (como um todo)**  
3) **Remover flags**

**Recomendacao:** **opcao 1** (coerente com tabela `origem`).

---

## Q11) `cartorio_transmissao`: entrada livre vs tabela controlada
**Contexto:** campo e "manual", mas FK exige registro.

**Opcoes:**
1) **Criar registro automaticamente se nao existir**  
2) **Obrigar cadastro previo**  

**Recomendacao:** **opcao 1** (melhor UX).

---

## Q12) Fonte de verdade: doc completo ou resumo?
**Contexto:** `SCHEMA_CONSOLIDATED.md` hoje e resumo; ERD contem inventario completo.

**Opcoes:**
1) **Manter doc como resumo** e ERD como inventario completo  
2) **Expandir doc** com todas as colunas do ERD  

**Recomendacao:** **opcao 1**, com nota explicita (ja adicionada).
