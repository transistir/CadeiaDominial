# Relatório de Análise dos Cartórios Atuais

## 📊 **Resumo Geral**

- **Total de cartórios**: 724
- **Estrutura atual**: 8 campos (id, nome, cns, endereco, telefone, email, estado, cidade)
- **Qualidade dos dados**: 99.9% dos CNS são válidos

## 🏛️ **Distribuição por Estado**

| Estado | Total | Percentual |
|--------|-------|------------|
| SP     | 296   | 40.9%      |
| PE     | 190   | 26.2%      |
| AL     | 72    | 9.9%       |
| AM     | 70    | 9.7%       |
| MS     | 59    | 8.1%       |
| AC     | 19    | 2.6%       |
| AP     | 16    | 2.2%       |
| N/A    | 2     | 0.3%       |

## 📋 **Tipos de Cartórios Identificados**

### 1. **Cartórios de Registro de Imóveis (CRI)**
- **Padrão**: "Registro de Imóveis de [Cidade]"
- **Exemplos**:
  - Registro de Imóveis de Assis Brasil
  - Registro de Imóveis de Bujari
  - 1º Registro de Imóveis de Rio Branco
  - 2º Registro de Imóveis de Rio Branco

### 2. **Cartórios Mistas (Registro + Tabelionato)**
- **Padrão**: "Serviço de Registro de Imóveis, Títulos e Documentos e Civil das Pessoas Jurídicas e Tabelionato de Protestos"
- **Total encontrado**: 4 cartórios
- **Estados**: MS (3), PR (1)

### 3. **Cartórios de Notas**
- **Resultado**: **NENHUM cartório específico de notas encontrado**
- **Busca por palavras-chave**:
  - "nota/notas": 0 resultados
  - "tabelião/tabelionato": 4 resultados (mas são mistos)
  - "ofício": 0 resultados

## ⚠️ **Problemas Identificados**

### 1. **Dados Problemáticos**
- **Cartório genérico**: ID 784 - "cartorio" (CNS: 0)
- **Duplicatas**: 10 grupos com cartórios duplicados
- **Estados nulos**: 2 cartórios sem estado

### 2. **Duplicatas Encontradas**
```
Nome: Registro de Imóveis de Autazes, Cidade: AUTAZES, Estado: AM, Total: 2
Nome: 3º Registro de Imóveis de Recife, Cidade: Recife, Estado: PE, Total: 2
Nome: Registro de Imóveis de Maraial, Cidade: Maraial, Estado: PE, Total: 2
Nome: Registro de Imóveis de Cachoeirinha, Cidade: Cachoeirinha, Estado: PE, Total: 2
Nome: Registro de Imóveis de São José do Belmonte, Cidade: Sao Jose do Belmonte, Estado: PE, Total: 2
Nome: Registro de Imóveis de Mundo Novo, Cidade: Mundo Novo, Estado: MS, Total: 2
Nome: Registro de Imóveis de Toritama, Cidade: Toritama, Estado: PE, Total: 2
Nome: Registro de Imóveis de Panelas, Cidade: Panelas, Estado: PE, Total: 2
Nome: Registro de Imóveis de Flores, Cidade: Flores, Estado: PE, Total: 2
Nome: Registro de Imóveis de Chã de Alegria, Cidade: CHA DE ALEGRIA, Estado: PE, Total: 2
```

### 3. **Falta de Cartórios de Notas**
- **Problema crítico**: Não há cartórios específicos de notas no banco
- **Impacto**: Implementação da separação CRI vs Notas será desafiadora

## 🎯 **Recomendações para Implementação**

### 1. **Migração de Dados**
```python
# Regras de classificação para dados existentes:
CRI_KEYWORDS = ['registro de imóveis', 'imovel', 'imoveis', 'imobiliario']
NOTAS_KEYWORDS = ['nota', 'notas', 'tabelionato', 'tabelião', 'ofício']

# Classificação:
# - 99% dos cartórios serão classificados como CRI
# - Cartórios mistos podem ser classificados como CRI (mais comum)
# - Necessário importar cartórios de notas específicos
```

### 2. **Limpeza Necessária**
- **Remover duplicatas**: 20 cartórios duplicados
- **Corrigir dados problemáticos**: Cartório genérico (ID 784)
- **Padronizar estados**: 2 cartórios sem estado

### 3. **Importação de Cartórios de Notas**
- **Fonte**: API do CNJ ou dados oficiais
- **Filtros**: Buscar por "tabelionato", "notas", "ofício"
- **Estados prioritários**: SP, PE, AM, AL, MS

### 4. **Estratégia de Implementação**

#### **Fase 1: Preparação**
1. Limpar dados existentes (duplicatas, dados problemáticos)
2. Classificar todos os cartórios existentes como CRI
3. Importar cartórios de notas específicos

#### **Fase 2: Implementação**
1. Adicionar campo `tipo` ao modelo
2. Migrar dados com classificação automática
3. Implementar validações por tipo

#### **Fase 3: Validação**
1. Verificar se todos os CRI estão corretos
2. Validar cartórios de notas importados
3. Testar funcionalidades por tipo

## 📈 **Estimativas para Implementação**

### **Cartórios por Tipo (Estimado)**
- **CRI**: ~700 cartórios (97%)
- **Cartórios de Notas**: ~24 cartórios (3%) - **necessário importar**

### **Tempo Estimado**
- **Limpeza de dados**: 1 dia
- **Importação de notas**: 2-3 dias
- **Implementação da separação**: 1 semana
- **Testes e validação**: 3-5 dias

## 🔍 **Próximos Passos**

1. **Limpar dados problemáticos** (duplicatas, cartório genérico)
2. **Importar cartórios de notas** de fontes oficiais
3. **Implementar migração** com classificação automática
4. **Testar separação** por tipo em todos os formulários

---

**Status**: Análise concluída
**Próximo**: Iniciar limpeza de dados e importação de cartórios de notas 