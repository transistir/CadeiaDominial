# CadeiaDominial — Plano Geral de Desenvolvimento (Sprints)

> ⚠️ **HISTÓRICO — não planejar por este arquivo.** A fila ativa é o
> **`docs/produto-3/ROADMAP.md`** (R1–R9, reordenada 04/09 por sequência
> lógica de desenvolvimento). Este plano fica como registro do
> levantamento original de 02/09 e das reavaliações.

**Data:** 02/09/2026 · **Base:** 42 issues abertas · **Escopo:** Django/develop (v2 #61–#72 fora do plano)
**Cadência:** Sprints de 2 semanas · **Processo por issue:** implement → review 3 modelos (Opus 5 + Codex GPT-5.6 + GLM/Fable) → aprovação luandro → merge em develop

> **↻ Reavaliação 04/09/2026 (status por sprint abaixo).** A fila real seguiu o
> `docs/produto-3/ROADMAP.md` (feedback Umbelino 01/09 + Maurício 03–04/09):
> **Sprint 5 concluído por inteiro + Sprint 1 concluído**, com Sprints 2–4
> ainda não executados. Item que ficou para trás: **#13** (S5) e todo o **Sprint 6
> do ROADMAP produto-3: #179 (XLS consolidado por TI no formato do PDF) — nunca iniciado**.

---

## Levantamento — 30 issues Django em 6 temas

| Tema | Issues | Natureza |
|---|---|---|
| A. Documento compartilhado / multi-cadeia | #152 #155 #175 #176 | Bug produção + navegação |
| B. Formulário de lançamento (follow-ups PR #158) | #159 #160 #161 #162 | Bugs de persistência/UX |
| C. Integridade de dados / cartórios | #141 #144 #149 #150 #151 #110 #113 #135 #114 | Bugs + data quality + decisão |
| D. UX Umbelino (doc 01/09/2026) | #164–#176 (11 issues) | Melhorias de usabilidade |
| E. Exportação | #145 #13 #166 #171 #172 | Bugs + melhorias PDF/planilha |
| F. Débitos técnicos + features grandes | #105 #108 #116 #139 #123 #132 | Refactor, CI, features |

**Priorização:** bugs de produção → bugs de formulário → integridade → UX → débitos → features grandes.

---

## Sprint 1 — Estabilização (semanas 1–2) — ✅ CONCLUÍDO
**Objetivo:** zerar os bugs que afetam usuários em produção hoje.
**Reavaliada em 02/09:** v1.0.8 = develop (tudo em prod). #152 já fixado (v1.0.7, PR #154), #145 causa raiz fixada (v1.0.6, mesma do #146).
**↻ Status 04/09:** todos os itens entregues — #108 (PR #177), #145 fix PDF averbações (PR #181), #159–#162 (PR #178). #152 aguarda só validação em test server p/ fechar a issue.

1. **#108** ✅ CI: deploy-develop quebra com squash merge → reset --hard (PR #177, 03/09)
2. **#152** ✅ ~~implementar~~ → **validar** caso real (doc 3168/imóvel 491) no test server; fechar se OK *(fix PR #154/v1.0.7; issue OPEN só pela validação)*
3. **#145** ✅ ~~implementar~~ → **revalidar** se as 7 averbações do imóvel 499 aparecem no PDF pós-v1.0.6 *(fix averbações em transcrições: PR #181, 04/09; issue OPEN aguarda validação)*
4. **#159** ✅ Herança: área 0 no GET → grava 0.0 em vez de None (PR #178, 03/09)
5. **#160** ✅ preservar_título não deixa limpar título (PR #178)
6. **#161** ✅ Re-render de erro não preserva origens e fim_cadeia do POST (PR #178)
7. **#162** ✅ Traceback completo exposto em messages.error *(segurança/info-leak)* (PR #178)

*Sinergia: #159–#162 são todos follow-ups do review r5 do PR #158 (mesma área de código; bugs pré-existentes no merge-base).*

## Sprint 2 — Integridade de dados / cartórios I (semanas 3–4)
**Objetivo:** fechar as brechas que permitem dados duplicados/inconsistentes de documentos.

1. **#144** Origem lançada (T585) não aparece na árvore — regressão v1.0.3→v1.0.5
2. **#114** criar_documento_matricula_automatico permite cartório None
3. **#141** Tratar IntegrityError em criar/editar documento (duplicidade canônica)
4. **#149** Avisar quando doc de mesmo tipo+número em cartório diferente
5. **#110** Levantar cartórios fantasmas + plano de merge *(data quality — alimenta S3)*

## Sprint 3 — UX Umbelino I: rapid wins + CRI (semanas 5–6)
**Objetivo:** entregar as melhorias de baixo esforço/alto impacto do doc Umbelino (01/09).

1. **#168** TAB não deve parar no campo da sigla *(P)*
2. **#169** Janela de fim de cadeia não fecha *(P)*
3. **#170** Botão Adicionar Lançamento no topo *(P)*
4. **#164** Reduzir quadro azul de infos da M/T a uma linha *(P)*
5. **#173** Aumentar campo proprietário (255→500 + migração) *(P)*
6. **#166** Planilha: 'CRI' no lugar de 'Cartório de Registro de Imóveis' *(P)*
7. **#165** CRI obrigatório junto ao nº de M/T em todo o sistema *(M — maior do bloco)*
8. **#113** Constraint de identidade + relatório de cartórios suspeitos *(usa saída da #110)*

## Sprint 4 — Multi-cadeia + decisões de negócio (semanas 7–8)
**Objetivo:** fechar a família documento compartilhado e as 3 issues com decisão assumida.

1. **#155** Detectar doc compartilhado via lancamento.documento_origem (gap)
2. **#175** Retornar à cadeia de trabalho ao voltar da árvore (lançamento importado)
3. **#176** Botão retornar à relação de imóveis da TI *(depende de #175)*
4. **#150** Delimitar CRI vs cartório de transmissão no banco *(G — migração de modelo+dados; proposta da issue assumida)*
5. **#172** Suprimir 'tronco principal' na cadeia exportada *(P — proposta assumida)*
6. **#151** Avisar/exigir arquivamento quando origem referencia imóvel ativo *(proposta assumida; revisar com Umbelino durante a sprint)*
7. **#135** Cartório 3574 fase 2 *(depende de #113 da S3)*

## Sprint 5 — Exportação + informatividade (semanas 9–10) — ✅ QUASE CONCLUÍDO (04/09, faltou #13)

1. **#171** ✅ Ver a árvore na tela 'Selecionar Sequência de Exportação' (PR #183, 04/09)
2. **#174** ✅ Marcação de cadeia finalizada na relação de imóveis da TI (PR #184, 04/09)
3. **#167** ✅ Visualizar a M anterior na sequência do lançamento (quebra sucessória) (PRs #185, #186, #188, 04/09)
4. **#13** ⏳ **PENDENTE** Área em ha perde formato brasileiro (0,0000) nas tabelas → movido p/ Sprint 6 do produto-3 (junto com #179, mesma área de exportação)

## Sprint 6 — Débitos técnicos + certificação fundiária (semanas 11–12)
**Objetivo:** limpar débitos que atrapalham manutenção; primeira feature grande de cadastro.

1. **#105** _processar_campos_inicio_matricula indexa por posição
2. **#116** Fixtures usam Imovel.sncr removido
3. **#139** Renomear 'transacao' → 'transmissão' em todo o sistema
4. **#123** Campos de certificação fundiária (SNCR, CCIR, CNIR, CIB, SIGEF, SNCI, CAR)

## Sprint 7 — Segregação por usuário (semanas 13–14)
**Objetivo:** a maior feature em aberto — multi-tenancy leve.

1. **#132** Segregação de dados por usuário (múltiplos usuários, cada um com seus imóveis)
   - Semana 1: design de schema + middleware/filtros (Opus 5 no design)
   - Semana 2: implementação gradual + testes de isolamento

---

## Fora do escopo (backlog v2)
#61–#72 (12 issues TypeScript/Cloudflare/D1) — retomar quando o Django estabilizar. #1 'Pacote de mudanças' fica aberta como guarda-chuva dos relatos antigos (itens pendentes migram p/ issues próprias, como já ocorreu com #174).

## Dependências críticas
- #108 primeiro de tudo (CI quebra em todo squash merge)
- #110 → #113 → #135 (cadeia data-quality, atravessa S2–S4)
- #175 → #176 (navegação multi-cadeia)
- #150 é a maior migração do plano — design Opus 5 antes de implementar
- #144 e #152 envolvem produção real (dados Maurício) — validar em test server antes

## Riscos
1. **#150 (CRI vs transmissão)** toca todas as FKs de cartório — risco alto de regressão; pedir spike de 1–2 dias no início da S4
2. **#132 (multi-usuário)** muda o modelo mental do sistema — decisões de produto do luandro necessárias no kickoff da S7
3. Capacidade real por sprint é incerta (time = luandro + agentes AI com ciclo de review 3 modelos) — replanejar ao fim de cada sprint
4. Novos relatos de Maurício/Umbelino podem entrar a qualquer momento — reserva de ~20% da capacidade por sprint
