# Lógica da Cadeia Dominial em Tabela

## Visão Geral

A funcionalidade de cadeia dominial em tabela permite visualizar a hierarquia completa de documentos de um imóvel, incluindo documentos importados de outras cadeias dominiais. A implementação segue uma lógica de expansão recursiva que respeita escolhas do usuário e mantém a ordem hierárquica correta.

## Componentes Principais

### 1. CadeiaDominialTabelaService

Serviço central responsável por:
- Obter o tronco principal da cadeia dominial
- Expandir documentos importados
- Processar escolhas de origem do usuário
- Manter ordem hierárquica

### 2. Expansão Recursiva

#### Conceito
Quando um documento tem múltiplas origens, apenas **uma origem é expandida por vez**:
- **Padrão**: Origem de maior número (matrícula > transcrição)
- **Escolha do usuário**: Origem selecionada via botões na interface

#### Ordem de Prioridade das Origens
1. **Matrículas** (M): Maior número primeiro
2. **Transcrições** (T): Maior número primeiro
3. **Outros tipos**: Ordem alfabética

#### Exemplo de Ordenação
Para origens: `M999, T344, M555, T76`
Resultado ordenado: `M999, M555, T344, T76`

### 3. Fluxo de Processamento

```
1. Obter tronco principal (documentos do imóvel atual)
2. Para cada documento no tronco:
   a. Verificar se tem origens importadas
   b. Se sim, expandir apenas a origem escolhida/padrão
   c. Recursivamente expandir a subcadeia da origem
3. Retornar cadeia completa processada
```

## Detalhamento Técnico

### Método Principal: `get_cadeia_dominial_tabela()`

```python
def get_cadeia_dominial_tabela(self, tis_id, imovel_id, session=None):
```

**Parâmetros:**
- `tis_id`: ID da Terra Indígena
- `imovel_id`: ID do Imóvel
- `session`: Sessão do usuário (contém escolhas de origem)

**Processo:**
1. Extrair escolhas de origem da sessão (`origem_documento_X`)
2. Obter tronco principal via `HierarquiaService`
3. Expandir com documentos importados via `_expandir_tronco_com_importados()`
4. Processar cada documento para incluir:
   - Lançamentos
   - Origens disponíveis
   - Flag de documento importado
   - Escolha atual

### Expansão de Documentos Importados: `_expandir_tronco_com_importados()`

```python
def _expandir_tronco_com_importados(self, imovel, tronco_principal, escolhas_origem=None):
```

**Lógica:**
1. Para cada documento no tronco principal:
   - Adicionar o documento atual
   - Buscar documentos importados referenciados
   - Para cada documento importado:
     - Verificar se há escolha específica na sessão
     - Se sim, usar a origem escolhida
     - Se não, usar origem de maior número
     - Expandir recursivamente a subcadeia da origem

### Expansão Recursiva: `_expandir_cadeia_recursiva()`

```python
def _expandir_cadeia_recursiva(self, documento, documentos_processados, escolhas_origem=None):
```

**Características:**
- **Expansão única**: Só expande a origem escolhida/padrão
- **Ordenação hierárquica**: Matrículas > Transcrições (ambas do maior para o menor)
- **Prevenção de loops**: Usa `documentos_processados` para evitar duplicatas
- **Recursão**: Expande subcadeias até não haver mais origens

## Exemplo Prático

### Cenário: Imóvel 6701 com M3214 importado

**Tronco Principal:**
```
6701 (matrícula atual)
├── M555 (origem escolhida)
└── M1299 (origem M3214)
```

**Expansão do M3214 (importado):**
```
M3214 (documento importado)
├── M449 (origem padrão - maior número)
│   ├── T344 (origem padrão - maior número)
│   │   ├── T2350 (origem padrão)
│   │   └── T13274 (origem de T2350)
│   └── T76 (só aparece se escolhido)
│       ├── T1699 (origem de T76)
│       └── T5550 (origem de T76)
└── M329 (só aparece se escolhido)
```

**Resultado Final:**
```
1. 6701 (matrícula atual)
2. M555 (origem escolhida)
3. M1299 (origem M3214)
4. M3214 (documento importado)
5. M449 (origem padrão do M3214)
6. T344 (origem padrão do M449)
7. T2350 (origem de T344)
8. T13274 (origem de T2350)
```

## Gestão de Estado

### Sessão do Usuário

**Chaves de sessão:**
- `origem_documento_X`: Origem escolhida para documento ID X
- Exemplo: `origem_documento_2: 'M329'`

**Comportamento:**
- Se não há escolha na sessão: usa origem padrão (maior número)
- Se há escolha: usa a origem escolhida
- Botão "Limpar Escolhas": remove todas as escolhas da sessão

### Botões de Origem

**Renderização:**
- Só aparecem para documentos com múltiplas origens
- Ordenados: matrículas maiores > transcrições maiores
- Botão ativo: origem atualmente escolhida/exibida

**Funcionamento:**
- Clique em botão: salva escolha na sessão e atualiza cadeia
- Cadeia anterior é substituída pela nova subcadeia

## Indicadores Visuais

### Documentos Importados

**CSS Classes:**
- `.documento-importado`: Borda verde esquerda, fundo verde claro
- `.importado-badge`: Badge "Importado" com ícone

**Lógica:**
- `is_importado = documento.imovel != imovel_atual`

### Estados dos Botões

**CSS Classes:**
- `.origem-btn`: Botão padrão
- `.origem-btn.ativo`: Botão da origem atualmente escolhida

## Performance

### Otimizações Implementadas

1. **Prefetch Related**: Carregamento eficiente de relacionamentos
2. **Select Related**: Redução de queries para cartório e tipo
3. **Set de Processados**: Prevenção de duplicatas sem queries extras
4. **Cache de Sessão**: Reutilização de escolhas do usuário

### Complexidade

- **Tempo**: O(n) onde n = número de documentos na cadeia
- **Espaço**: O(n) para armazenar documentos processados
- **Queries**: Minimizadas via prefetch e select_related

## Casos de Uso

### 1. Visualização Padrão
- Usuário acessa cadeia dominial
- Sistema mostra origem de maior número para cada documento
- Ordem hierárquica mantida

### 2. Escolha de Origem
- Usuário clica em botão de origem alternativa
- Sistema salva escolha na sessão
- Cadeia é atualizada mostrando nova subcadeia

### 3. Limpeza de Escolhas
- Usuário clica em "Limpar Escolhas"
- Sistema remove todas as escolhas da sessão
- Cadeia volta ao estado padrão

### 4. Documentos Importados
- Sistema detecta documentos de outros imóveis
- Aplica indicadores visuais
- Permite navegação completa da cadeia

## Manutenção

### Logs de Debug
- Removidos logs de debug da versão de produção
- Manter logs apenas durante desenvolvimento

### Testes
- Testar expansão recursiva com documentos complexos
- Verificar ordenação hierárquica
- Validar gestão de sessão

### Extensões Futuras
- Cache de cadeias completas
- Paginação para cadeias muito grandes
- Exportação de cadeias
- Comparação entre cadeias 