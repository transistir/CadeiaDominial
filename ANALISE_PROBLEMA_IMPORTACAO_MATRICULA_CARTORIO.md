# Análise: Problema de Importação Automática de Matrícula de Cartório Incorreto

## Problema Relatado

**Queixa do usuário:**
> "Em uma cadeia que estou montando, o sistema está importando automaticamente uma matrícula de outro cartório, relacionado à outra TI, que nada tem a ver com minha cadeia. Elas possuem a mesma numeração, M2655, mas são de cartórios distintos. Já verifiquei diversas vezes, e mesmo cadastrando a origem como CRI de Dourados, o sistema importa essa matrícula de Guaíra."

## Contexto Histórico

No commit `671ba47eae7a54922ab0ee015e9b60e3a11693f6`, foi implementada a correção para que **matrículas fossem únicas por cartório** (não globalmente). Isso permitiu que diferentes cartórios tivessem matrículas com o mesmo número (ex: M2655 em Dourados e M2655 em Guaíra).

**Problema atual:** Embora o modelo de dados agora permita matrículas com mesmo número em cartórios diferentes, a **lógica de busca e importação de documentos** ainda não está considerando o cartório corretamente em vários pontos do código.

## Análise do Problema

### Causa Raiz

O sistema está buscando documentos para importação/expansão da cadeia dominial **apenas pelo número do documento**, sem filtrar pelo **cartório de origem** (`lancamento.cartorio_origem`). Isso faz com que ele encontre a primeira matrícula com aquele número, que pode ser de um cartório diferente.

### Locais Críticos Identificados

#### 1. **`duplicata_verificacao_service.py` - Linha 103-105**

**Problema:** Ao calcular documentos importáveis, busca documento sem filtro de cartório:

```python
# Buscar documento com este número (independente do cartório)
documento_anterior = Documento.objects.filter(
    numero=origem_numero
).first()
```

**Correção necessária:** Deve buscar considerando o `lancamento.cartorio_origem`:

```python
# Buscar documento com este número NO CARTÓRIO DE ORIGEM ESPECIFICADO
documento_anterior = Documento.objects.filter(
    numero=origem_numero,
    cartorio=lancamento.cartorio_origem  # ← ADICIONAR ESTE FILTRO
).first()
```

**Impacto:** Este é o serviço que calcula quais documentos podem ser importados quando há duplicatas. Se ele não considerar o cartório, pode sugerir importar documentos do cartório errado.

---

#### 2. **`hierarquia_utils.py` - Linha 191-195**

**Problema:** Ao identificar documentos importados, busca sem filtro de cartório:

```python
doc_compartilhado = Documento.objects.filter(
    numero=codigo
).exclude(
    imovel=imovel  # Excluir documentos do imóvel atual
).select_related('cartorio', 'tipo', 'imovel').first()
```

**Correção necessária:** Deve considerar o cartório do lançamento que referenciou esta origem. O problema aqui é que a função `identificar_documentos_importados()` não recebe informações sobre os lançamentos, apenas o imóvel.

**Impacto:** Esta função é usada para identificar documentos compartilhados que devem aparecer na cadeia dominial. Se não considerar o cartório, pode incluir documentos do cartório errado.

---

#### 3. **`cadeia_dominial_tabela_service.py` - Múltiplos locais**

Este serviço tem **vários pontos** onde busca documentos sem considerar o cartório:

##### 3.1. Linha 306-308 (`extrair_origens_disponiveis`)

```python
doc_existente = Documento.objects.filter(
    numero=codigo
).first()
```

**Correção necessária:** Deve considerar o cartório do lançamento que contém esta origem.

##### 3.2. Linha 351-355 (`_expandir_tronco_com_importados`)

```python
doc_importado = Documento.objects.filter(
    numero=origem_numero
).exclude(
    imovel=imovel
).select_related('cartorio', 'tipo').first()
```

**Correção necessária:** Deve filtrar pelo `lancamento.cartorio_origem`:

```python
doc_importado = Documento.objects.filter(
    numero=origem_numero,
    cartorio=lancamento.cartorio_origem  # ← ADICIONAR ESTE FILTRO
).exclude(
    imovel=imovel
).select_related('cartorio', 'tipo').first()
```

**Impacto:** Este método expande o tronco principal incluindo documentos importados. Se não considerar o cartório, pode importar documentos do cartório errado.

##### 3.3. Linha 373-375 (`_expandir_tronco_com_importados`)

```python
doc_origem_escolhido = Documento.objects.filter(
    numero=escolha_especifica
).select_related('cartorio', 'tipo').first()
```

**Correção necessária:** Deve considerar o cartório do documento importado ou do lançamento que o referenciou.

##### 3.4. Linha 414-416 (`_obter_documento_origem_mais_alto`)

```python
doc_origem = Documento.objects.filter(
    numero=origem_numero
).select_related('cartorio', 'tipo').first()
```

**Correção necessária:** Deve considerar o `lancamento.cartorio_origem`.

##### 3.5. Linha 507-509 (`_expandir_cadeia_recursiva`)

```python
doc_origem = Documento.objects.filter(
    numero=origem_escolhida
).select_related('cartorio', 'tipo').first()
```

**Correção necessária:** Deve considerar o cartório do documento atual ou do lançamento.

##### 3.6. Linha 538-540 (`_garantir_todos_documentos_incluidos`)

```python
doc_origem = Documento.objects.filter(
    numero=origem_numero
).select_related('cartorio', 'tipo').first()
```

**Correção necessária:** Deve considerar o `lancamento.cartorio_origem`.

**Impacto geral:** Este serviço é responsável por construir a cadeia dominial em formato de tabela. Se não considerar o cartório em nenhum desses pontos, pode incluir documentos de cartórios incorretos na cadeia.

---

#### 4. **`hierarquia_utils.py` - Linha 118 (dentro de `identificar_tronco_principal`)**

**Problema:** Ao buscar documentos que são origens, não considera o cartório:

```python
doc_existente = next((doc for doc in documentos if doc.numero == codigo), None)
```

**Correção necessária:** Deve considerar o `lancamento.cartorio_origem` ao buscar documentos externos.

**Impacto:** Esta função identifica o tronco principal da cadeia dominial. Se não considerar o cartório, pode incluir documentos do cartório errado no tronco.

---

## Relação com o Problema Anterior

O problema atual está **diretamente relacionado** à correção feita no commit mencionado:

1. **Antes da correção:** Matrículas eram únicas globalmente, então não havia risco de buscar a matrícula errada (só existia uma M2655).

2. **Depois da correção:** Matrículas podem ter o mesmo número em cartórios diferentes, então agora **é essencial** considerar o cartório ao buscar documentos.

3. **Problema atual:** A lógica de busca/importação não foi atualizada para considerar o cartório, então ainda busca apenas pelo número, encontrando a primeira matrícula com aquele número (que pode ser do cartório errado).

## Fluxo do Problema (Cenário do Usuário)

1. Usuário cadastra origem como **CRI de Dourados** → `lancamento.cartorio_origem = Dourados`
2. Sistema busca documento M2655 para importar → `Documento.objects.filter(numero='M2655').first()`
3. Sistema encontra M2655 de **Guaíra** (primeiro resultado da query)
4. Sistema importa M2655 de Guaíra (cartório errado)
5. Usuário vê matrícula de Guaíra na cadeia que deveria ser de Dourados

## Solução Proposta (Conceitual)

### Princípio Geral

**SEMPRE que buscar um documento por número para importação/expansão de cadeia, deve-se filtrar pelo cartório de origem do lançamento que referenciou aquela origem.**

### Padrão de Correção

1. **Identificar o lançamento** que contém a origem sendo buscada
2. **Obter o `cartorio_origem`** desse lançamento
3. **Adicionar filtro de cartório** na query de busca:

```python
# ANTES (ERRADO)
doc = Documento.objects.filter(numero=origem_numero).first()

# DEPOIS (CORRETO)
doc = Documento.objects.filter(
    numero=origem_numero,
    cartorio=lancamento.cartorio_origem  # ← SEMPRE incluir este filtro
).first()
```

### Desafios Técnicos

1. **Contexto perdido:** Algumas funções não têm acesso direto ao `lancamento` que contém a origem. Será necessário:
   - Passar o `lancamento` como parâmetro
   - Ou buscar o lançamento que contém aquela origem antes de buscar o documento

2. **Fallback quando não há cartório:** Alguns lançamentos podem não ter `cartorio_origem` definido. Nesses casos:
   - Usar o cartório do documento atual
   - Ou não buscar/importar (mais seguro)

3. **Propagação do cartório:** Quando expandir recursivamente uma cadeia, o cartório deve ser propagado para as buscas subsequentes.

## Arquivos que Precisam de Correção

1. ✅ `dominial/services/duplicata_verificacao_service.py` - Linhas 103-105
2. ✅ `dominial/utils/hierarquia_utils.py` - Linha 191-195 e linha 118
3. ✅ `dominial/services/cadeia_dominial_tabela_service.py` - Múltiplas linhas (306, 351, 373, 414, 507, 538)

## Observações Importantes

⚠️ **ATENÇÃO:** O usuário mencionou que a questão dos cartórios está implementada de maneira confusa. Antes de fazer qualquer alteração, é recomendado:

1. **Mapear todas as dependências** entre os serviços
2. **Testar cada correção isoladamente** antes de aplicar todas
3. **Validar com dados reais** (especialmente o caso M2655 de Dourados vs Guaíra)
4. **Considerar criar testes automatizados** para garantir que não haverá regressão

## Conclusão

O problema está claramente identificado: **a lógica de busca de documentos não está considerando o cartório de origem**, mesmo após a correção que permitiu matrículas com mesmo número em cartórios diferentes. A correção requer atualizar todos os pontos de busca para incluir o filtro de cartório, mas deve ser feita com cuidado devido à complexidade e interdependência do código.
