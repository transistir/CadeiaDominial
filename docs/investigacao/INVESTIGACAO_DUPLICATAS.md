# Guia de Investigação de Duplicatas

Este guia explica como investigar e corrigir duplicatas de matrículas/transcrições no sistema.

## 🔍 Problema Identificado

O sistema está permitindo criar o mesmo número de matrícula/transcrição para o mesmo cartório, o que é um erro grave. Nunca pode ter duas matrículas (ou transcrições) com o mesmo número no mesmo cartório.

## 🛠️ Ferramentas de Investigação

### 1. Admin do Django Melhorado

O admin do Django foi melhorado para facilitar a investigação:

- **Contagem de Lançamentos**: Mostra quantos lançamentos cada documento tem
- **Status do Documento**: Indica se o documento está vazio, ativo ou com muitos lançamentos
- **Ações Customizadas**: Permite investigar duplicatas e verificar documentos vazios

**Acesso**: https://cadeiadominial.com.br/admin/dominial/documento/

### 2. Comandos de Management

#### Investigar Duplicatas Gerais
```bash
python manage.py investigar_duplicatas_documentos
```

**Opções:**
- `--tipo matricula` ou `--tipo transcricao`: Filtrar por tipo
- `--cartorio "Nome do Cartório"`: Filtrar por cartório
- `--exportar`: Exportar resultados para CSV

#### Investigar Matrícula Específica
```bash
python manage.py investigar_matricula M123
```

**Opções:**
- `--cartorio "Nome do Cartório"`: Filtrar por cartório
- `--detalhes`: Mostrar detalhes completos dos lançamentos
- `--comparar`: Comparar documentos duplicados

#### Listar Duplicatas para Escolha Manual
```bash
python manage.py listar_duplicatas
```

**Opções:**
- `--tipo matricula` ou `--tipo transcricao`: Filtrar por tipo
- `--cartorio "Nome do Cartório"`: Filtrar por cartório
- `--detalhes`: Mostrar detalhes dos lançamentos

## 📋 Processo de Investigação

### Passo 1: Identificar Duplicatas
```bash
# Listar todas as duplicatas
python manage.py listar_duplicatas

# Investigar uma matrícula específica
python manage.py investigar_matricula M123 --detalhes --comparar
```

### Passo 2: Analisar Detalhes
Para cada duplicata encontrada, analise:

1. **Número de Lançamentos**: Qual documento tem mais lançamentos?
2. **Data**: Qual documento é mais recente?
3. **Livro/Folha**: Qual documento tem livro e folha preenchidos?
4. **Completude**: Qual documento tem lançamentos mais completos?
5. **Lançamentos Duplicados**: Há lançamentos iguais entre os documentos?

### Passo 3: Escolher Documento Principal
Critérios de prioridade:

1. **Mais Lançamentos**: Documento com mais lançamentos
2. **Data Mais Recente**: Documento com data mais recente
3. **Livro/Folha Preenchidos**: Documento com livro e folha válidos
4. **Lançamentos Completos**: Documento com informações mais completas

### Passo 4: Corrigir Manualmente

#### Via Admin do Django:
1. Acesse https://cadeiadominial.com.br/admin/dominial/documento/
2. Encontre os documentos duplicados
3. Analise os lançamentos de cada documento
4. Escolha qual documento manter
5. Mova lançamentos importantes se necessário
6. Remova documentos incorretos

#### Via Comandos SQL (Apenas para Administradores):
```sql
-- Verificar duplicatas
SELECT numero, cartorio_id, COUNT(*) as total
FROM dominial_documento 
GROUP BY numero, cartorio_id 
HAVING COUNT(*) > 1;

-- Ver lançamentos de um documento específico
SELECT * FROM dominial_lancamento WHERE documento_id = X;

-- Mover lançamentos (substitua X e Y pelos IDs corretos)
UPDATE dominial_lancamento SET documento_id = X WHERE documento_id = Y;

-- Remover documento incorreto (apenas após mover lançamentos)
DELETE FROM dominial_documento WHERE id = Y;
```

## 🚨 Exemplos de Uso

### Exemplo 1: Investigar Matrícula M123
```bash
python manage.py investigar_matricula M123 --detalhes --comparar
```

**Saída esperada:**
```
🔍 INVESTIGANDO MATRÍCULA: M123
============================================================

📊 RESUMO ENCONTRADO:
   Total de documentos: 2

🏛️ CARTÓRIO: Registro de Imóveis de São Paulo
----------------------------------------
⚠️ ATENÇÃO: 2 documentos encontrados neste cartório!

   📄 Documento 1:
      ID: 123
      Tipo: Matrícula
      Data: 2024-01-15
      Livro: 1
      Folha: 1
      Imóvel: M123
      TIs: Terra Indígena X
      Lançamentos: 3

   📄 Documento 2:
      ID: 124
      Tipo: Matrícula
      Data: 2024-01-10
      Livro: 0
      Folha: 0
      Imóvel: M123
      TIs: Terra Indígena X
      Lançamentos: 1

🚨 PROBLEMA IDENTIFICADO:
   Existem 2 documentos com o mesmo número!
```

### Exemplo 2: Listar Todas as Duplicatas
```bash
python manage.py listar_duplicatas --detalhes
```

**Saída esperada:**
```
📋 LISTANDO DUPLICATAS PARA ESCOLHA MANUAL
============================================================
📊 Encontradas 3 combinações duplicadas

🔍 DUPLICATA 1: M123 - Registro de Imóveis de São Paulo
--------------------------------------------------
   Encontrados 2 documentos:

   📄 Documento 1 (ID: 123):
      Tipo: Matrícula
      Data: 2024-01-15
      Livro/Folha: 1/1
      Imóvel: M123
      TIs: Terra Indígena X
      Lançamentos: 3

   📄 Documento 2 (ID: 124):
      Tipo: Matrícula
      Data: 2024-01-10
      Livro/Folha: 0/0
      Imóvel: M123
      TIs: Terra Indígena X
      Lançamentos: 1

   💡 SUGESTÕES PARA ESCOLHA:
      📊 Por número de lançamentos:
         1. Documento ID 123: 3 lançamentos
         2. Documento ID 124: 1 lançamentos
```

## ⚠️ Importante

- **NUNCA** use correção automática sem verificar os dados
- **SEMPRE** faça backup antes de qualquer correção
- **ANALISE** cuidadosamente cada duplicata antes de decidir
- **TESTE** as correções em ambiente de desenvolvimento primeiro

## 🔧 Prevenção

Para evitar duplicatas no futuro:

1. **Validação no Modelo**: O modelo já tem `unique_together = ('numero', 'cartorio')`
2. **Validação no Formulário**: Adicionar validação antes de criar documentos
3. **Validação no Service**: Verificar unicidade antes de salvar
4. **Interface Melhorada**: Mostrar avisos quando tentar criar duplicata

## 📞 Suporte

Se encontrar problemas durante a investigação:

1. Documente o que encontrou
2. Faça screenshots do admin
3. Salve a saída dos comandos
4. Entre em contato com a equipe de desenvolvimento 