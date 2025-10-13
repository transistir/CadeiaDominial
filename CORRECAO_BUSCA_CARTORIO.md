# Correção: Busca de Documentos Apenas no Cartório de Origem

## Problema Identificado

Na solução inicial para o problema T1004 -> T2822, o código estava buscando documentos em **todos os cartórios** quando não encontrava no cartório de origem especificado. Isso pode causar:

1. **Conexões Incorretas**: Conectar documentos de cartórios diferentes
2. **Violação de Integridade**: Documentos de um cartório sendo associados a outro
3. **Dados Inconsistentes**: Cadeia dominial com documentos de cartórios misturados

## Correção Implementada

### **Regra Principal:**
> **Buscar APENAS no cartório de origem especificado no lançamento**

### **Lógica Corrigida:**

```python
def buscar_documento_origem_robusto(origem_numero, cartorio_origem=None, lancamento=None):
    """
    Busca documento de origem APENAS no cartório de origem especificado
    CORREÇÃO: Não busca em outros cartórios para evitar conexões incorretas
    """
    
    # REGRA: Buscar APENAS no cartório de origem especificado
    if cartorio_origem:
        # Estratégia 1: Buscar exatamente como especificado
        doc = Documento.objects.filter(
            numero=origem_numero,
            cartorio=cartorio_origem
        ).first()
        
        if doc:
            return doc
        
        # Estratégia 2: Buscar por variações do número no MESMO cartório
        numero_limpo = re.sub(r'^[MT]', '', origem_numero)
        if numero_limpo.isdigit():
            # Buscar com prefixo M no mesmo cartório
            doc_m = Documento.objects.filter(
                numero=f'M{numero_limpo}',
                cartorio=cartorio_origem
            ).first()
            if doc_m:
                return doc_m
            
            # Buscar com prefixo T no mesmo cartório
            doc_t = Documento.objects.filter(
                numero=f'T{numero_limpo}',
                cartorio=cartorio_origem
            ).first()
            if doc_t:
                return doc_t
        
        # Se não encontrou no cartório de origem, retorna None
        return None
    
    # Se não tem cartório de origem especificado, não buscar
    return None
```

## Benefícios da Correção

### **1. Integridade dos Dados**
- Garante que documentos só se conectem dentro do mesmo cartório
- Evita mistura de documentos de cartórios diferentes
- Mantém a consistência da cadeia dominial

### **2. Precisão das Conexões**
- Conexões são criadas apenas quando há relação real
- Documentos de cartórios diferentes não são conectados incorretamente
- Cadeia dominial reflete a realidade dos registros

### **3. Segurança**
- Evita criação de conexões espúrias
- Reduz erros de interpretação da cadeia dominial
- Mantém a confiabilidade do sistema

## Casos de Uso

### **Caso 1: Documento Existe no Cartório de Origem**
```
Lançamento: T1004 (Cartório A)
Origem: T2822 (Cartório A)
Resultado: ✅ Conexão criada
```

### **Caso 2: Documento Não Existe no Cartório de Origem**
```
Lançamento: T1004 (Cartório A)
Origem: T2822 (Cartório A) - mas T2822 não existe no Cartório A
Resultado: ❌ Não conecta (correto)
```

### **Caso 3: Documento Existe em Outro Cartório**
```
Lançamento: T1004 (Cartório A)
Origem: T2822 (Cartório A) - mas T2822 existe apenas no Cartório B
Resultado: ❌ Não conecta (correto - evita conexão incorreta)
```

## Implementação

### **Arquivos Corrigidos:**
1. `hierarquia_arvore_service_melhorado.py` - Serviço melhorado
2. `patch_hierarquia_arvore_service.py` - Patch aplicável
3. `testar_conexao_t1004_t2822.py` - Comando de teste

### **Como Usar:**
```bash
# Aplicar patch corrigido
python manage.py aplicar_patch_conexoes

# Testar com a correção
python manage.py testar_conexao_t1004_t2822
```

## Conclusão

A correção garante que:
- ✅ Documentos só se conectem dentro do mesmo cartório
- ✅ Não há busca em cartórios diferentes
- ✅ Integridade dos dados é mantida
- ✅ Conexões são precisas e confiáveis

Esta abordagem é mais conservadora mas garante a integridade e precisão das conexões na cadeia dominial.
