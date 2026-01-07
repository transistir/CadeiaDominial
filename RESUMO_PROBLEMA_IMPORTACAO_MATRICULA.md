# Resumo: Problema de Importação de Matrícula de Cartório Incorreto

## Problema Identificado ✅

O sistema está **buscando documentos apenas pelo número** (ex: M2655) **sem considerar o cartório**, mesmo quando o usuário cadastra a origem como "CRI de Dourados". Isso faz com que o sistema encontre a primeira matrícula M2655 que aparecer na busca, que pode ser de Guaíra quando deveria ser de Dourados.

## Causa Raiz

Após a correção do commit `671ba47` que permitiu matrículas com mesmo número em cartórios diferentes, a **lógica de busca/importação não foi atualizada** para considerar o cartório. O sistema ainda busca como se houvesse apenas uma matrícula M2655 no banco.

## Locais Críticos no Código

### 🔴 **CRÍTICO - `duplicata_verificacao_service.py` (linha 103)**
```python
# ❌ ERRADO - Busca sem cartório
documento_anterior = Documento.objects.filter(numero=origem_numero).first()

# ✅ CORRETO - Deve ser:
documento_anterior = Documento.objects.filter(
    numero=origem_numero,
    cartorio=lancamento.cartorio_origem  # ← ADICIONAR
).first()
```

### 🔴 **CRÍTICO - `cadeia_dominial_tabela_service.py` (linha 351)**
```python
# ❌ ERRADO - Busca sem cartório
doc_importado = Documento.objects.filter(numero=origem_numero).exclude(imovel=imovel).first()

# ✅ CORRETO - Deve ser:
doc_importado = Documento.objects.filter(
    numero=origem_numero,
    cartorio=lancamento.cartorio_origem  # ← ADICIONAR
).exclude(imovel=imovel).first()
```

### 🟡 **IMPORTANTE - `hierarquia_utils.py` (linha 191)**
Busca documentos compartilhados sem considerar cartório. Precisa passar informação do lançamento para a função.

### 🟡 **IMPORTANTE - `cadeia_dominial_tabela_service.py` (múltiplas linhas)**
Vários outros pontos (306, 373, 414, 507, 538) também buscam sem cartório.

## Fluxo do Erro

```
1. Usuário cadastra: Origem = M2655, Cartório = Dourados
   → lancamento.cartorio_origem = Dourados ✅

2. Sistema busca documento para importar:
   → Documento.objects.filter(numero='M2655').first() ❌
   → Encontra M2655 de Guaíra (primeiro resultado)

3. Sistema importa M2655 de Guaíra ❌
   → Deveria importar M2655 de Dourados ✅
```

## Solução Conceitual

**Regra:** Sempre que buscar documento por número para importação, **SEMPRE** filtrar pelo `lancamento.cartorio_origem`:

```python
# Padrão correto:
Documento.objects.filter(
    numero=origem_numero,
    cartorio=lancamento.cartorio_origem  # ← SEMPRE incluir
).first()
```

## Arquivos que Precisam Correção

1. `dominial/services/duplicata_verificacao_service.py` - Linha 103
2. `dominial/services/cadeia_dominial_tabela_service.py` - Linhas 306, 351, 373, 414, 507, 538
3. `dominial/utils/hierarquia_utils.py` - Linha 191 (e possivelmente linha 118)

## ⚠️ Aviso Importante

Como mencionado, a questão dos cartórios está implementada de forma confusa. Antes de fazer alterações:

- ✅ Mapear todas as dependências
- ✅ Testar cada correção isoladamente  
- ✅ Validar com o caso real (M2655 Dourados vs Guaíra)
- ✅ Considerar testes automatizados

## Relação com Problema Anterior

✅ **Antes:** Matrícula única globalmente → Não havia risco (só existia uma M2655)  
✅ **Depois da correção:** Matrícula única por cartório → Agora pode haver M2655 em vários cartórios  
❌ **Problema atual:** Busca ainda não considera cartório → Encontra a primeira M2655 (cartório errado)

---

**Status:** Análise completa. Problema identificado e mapeado. Aguardando decisão sobre implementação das correções.
