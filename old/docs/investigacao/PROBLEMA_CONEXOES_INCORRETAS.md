# Problema: Conexões Incorretas na Cadeia Dominial

## Descrição do Problema

**Data de Identificação:** Janeiro 2025  
**Status:** ✅ RESOLVIDO  
**Severidade:** Alta  

### Cenário do Problema

O usuário reportou que na visualização da cadeia dominial, a matrícula **M9712** estava sendo incorretamente conectada à **M19905**, quando na verdade:

- **M9716** é origem da **M19905** ✅ (correto)
- **M9712** é origem da **M9716** ✅ (correto)
- **M9712** → **M19905** ❌ (incorreto - conexão que não deveria existir)

### Estrutura Correta Esperada

```
M9712 → M9716 → M19905
```

### Estrutura Incorreta Encontrada

```
M9712 → M9716 → M19905
M9712 → M19905 (conexão incorreta)
```

## Investigação Realizada

### Dados das Matrículas

#### M9716 (Documento ID: 308)
- **Tipo:** Matrícula
- **Imóvel:** M19905
- **Cartório:** Registro de Imóveis de Guaira
- **Origem:** "Criado automaticamente a partir de origem: M9716"
- **Lançamentos:** 4
  - AV7M9716 (Averbação)
  - R2M9716 (Registro)
  - AV1M9716 (Averbação)
  - M9716 (Início de Matrícula) - **Origem: M9712**

#### M9712 (Documento ID: 309)
- **Tipo:** Matrícula
- **Imóvel:** M19905
- **Cartório:** Registro de Imóveis de Guaira
- **Origem:** "Criado automaticamente a partir de origem: M9712"
- **Lançamentos:** 3
  - AV2M9712 (Averbação)
  - AV1M9712 (Averbação)
  - M9712 (Início de Matrícula) - **Origem: M5724; M5629; M3873**

#### M19905 (Documento ID: 307)
- **Tipo:** Matrícula
- **Imóvel:** M19905
- **Cartório:** Registro de Imóveis de Guaira
- **Origem:** "Matrícula atual do imóvel"
- **Lançamentos:** 2
  - AV1M19905 (Averbação)
  - M19905 (Início de Matrícula) - **Origem: M9716**

### Causa Raiz Identificada

O problema estava no método `_processar_origem_documento` do serviço `HierarquiaArvoreService`. Este método processa as origens dos documentos e cria conexões na árvore da cadeia dominial.

**Problema específico:**
```python
# LÓGICA PROBLEMÁTICA REMOVIDA
if not origens and 'matrícula' in documento.origem.lower():
    # Procurar por documentos que podem ser a matrícula atual
    for outro_doc in documentos_por_numero.values():
        if outro_doc['tipo'] == 'matricula' and outro_doc['numero'] != documento.numero:
            origens = [outro_doc['numero']]
            break
```

**Por que causava problemas:**
1. O documento M19905 tem origem "Matrícula atual do imóvel"
2. A lógica detectava a palavra "matrícula" 
3. Procurava por outros documentos de tipo "matrícula" 
4. Encontrava M9712 e criava uma conexão M9712 → M19905
5. Esta conexão era **incorreta** porque não havia relação direta entre os documentos

## Solução Implementada

### 1. Correção do Código

**Arquivo:** `dominial/services/hierarquia_arvore_service.py`

**Mudança:** Remoção da lógica problemática que criava conexões baseadas apenas na presença da palavra "matrícula"

```python
@staticmethod
def _processar_origem_documento(arvore, documento, documentos_por_numero):
    """
    Processa origem de um documento específico
    Lógica: documento referenciado como origem → documento atual
    """
    # Extrair códigos de origem (M ou T seguidos de números)
    origens = re.findall(r'[MT]\d+', documento.origem)
    
    # Se não encontrou padrões M/T, tentar extrair números
    if not origens:
        numeros = re.findall(r'\d+', documento.origem)
        origens = numeros
    
    # CORREÇÃO: Remover lógica problemática que criava conexões incorretas
    # A lógica anterior criava conexões baseadas apenas na presença da palavra "matrícula"
    # Isso causava conexões incorretas como M9712 → M19905
    
    for origem in origens:
        # Evitar auto-referências
        if origem != documento.numero and origem in documentos_por_numero:
            conexao = {
                'from': origem,  # Documento de origem
                'to': documento.numero,  # Documento atual
                'tipo': 'origem'
            }
            arvore['conexoes'].append(conexao)
```

### 2. Comandos de Investigação Criados

#### `investigar_conexoes_incorretas`
- Analisa matrículas específicas
- Identifica conexões problemáticas
- Corrige automaticamente conexões incorretas

#### `testar_construcao_arvore`
- Testa a construção da árvore da cadeia dominial
- Analisa documentos e conexões
- Identifica problemas específicos

## Resultados da Correção

### Antes da Correção:
- **Total de conexões:** 17
- **Conexão incorreta:** M9712 → M19905 (tipo: `origem`) ❌
- **Status:** ❌ PROBLEMA ENCONTRADO!

### Depois da Correção:
- **Total de conexões:** 16 (reduziu em 1)
- **Conexão incorreta:** NENHUMA ✅
- **Status:** ✅ Nenhuma conexão incorreta encontrada

### Estrutura Correta Confirmada:
```
M9712 → M9716 → M19905
```

## Comandos de Investigação Utilizados

### 1. Investigação de Matrícula Específica
```bash
python manage.py investigar_matricula M9716 --detalhes
python manage.py investigar_matricula M9712 --detalhes
python manage.py investigar_matricula M19905 --detalhes
```

### 2. Investigação de Conexões Incorretas
```bash
python manage.py investigar_conexoes_incorretas --matriculas M9716 M9712 M19905
```

### 3. Teste de Construção da Árvore
```bash
python manage.py testar_construcao_arvore --imovel M19905
```

## Prevenção de Problemas Similares

### 1. Validação de Origem
- Implementar validação no momento da criação de lançamentos
- Verificar se as origens fazem sentido hierarquicamente
- Alertar usuário sobre possíveis conexões incorretas

### 2. Testes Automatizados
- Criar testes para cenários de cadeia dominial complexa
- Validar que conexões seguem regras de negócio
- Testar casos edge com múltiplas origens

### 3. Monitoramento
- Implementar alertas para conexões suspeitas
- Logs detalhados de criação de conexões
- Dashboard de saúde da cadeia dominial

## Arquivos Modificados

- `dominial/services/hierarquia_arvore_service.py` (correção)
- `dominial/management/commands/investigar_conexoes_incorretas.py` (novo)
- `dominial/management/commands/testar_construcao_arvore.py` (novo)

## Próximos Passos

1. ✅ Implementar comando de investigação
2. ✅ Identificar causa raiz do problema
3. ✅ Corrigir lógica problemática
4. ✅ Testar correção
5. ✅ Documentar problema e solução
6. 🔄 Implementar validações preventivas
7. 🔄 Criar testes automatizados
8. 🔄 Implementar monitoramento contínuo

## Referências

- [Lógica da Cadeia Dominial em Tabela](../cadeia-dominial/LOGICA_CADEIA_DOMINIAL_TABELA.md)
- [Investigação de Duplicatas](../verificacao-duplicatas/README.md)
- [Comandos de Investigação](../../dominial/management/commands/)

## Commit da Correção

```
fix: corrige conexões incorretas na árvore da cadeia dominial - remove lógica problemática que criava conexões baseadas apenas na presença da palavra 'matrícula'
```

**Hash:** `fec60b1`
