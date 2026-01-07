# Melhorias na Visualização D3 da Árvore da Cadeia Dominial

## Problema Identificado

A visualização D3 da árvore da cadeia dominial apresentava problemas de sobreposição de cards quando havia muitos documentos, resultando em uma experiência de usuário ruim e dificuldade de visualização.

## Soluções Implementadas

### 1. Melhoria no Algoritmo de Espaçamento Adaptativo

**Arquivo:** `static/dominial/js/cadeia_dominial_d3.js`

- **Função:** `calcularEspacamentoAdaptativo()`
- **Melhorias:**
  - Aumentou os limites de espaçamento para diferentes quantidades de nós
  - Considera o tamanho real dos cards (140x80px) no cálculo
  - Novos limites:
    - Mais de 20 nós: 400px de espaçamento
    - Mais de 15 nós: 350px de espaçamento
    - Mais de 10 nós: 300px de espaçamento
    - Mais de 6 nós: 250px de espaçamento
    - Padrão: 200px de espaçamento

### 2. Correção de Sobreposições Melhorada

**Função:** `corrigirSobreposicoes()`

- **Melhorias:**
  - Detecta sobreposições reais entre cards
  - Usa espaçamento mínimo baseado no tamanho real dos cards (80px + 40px de margem)
  - Redistribui nós apenas quando necessário
  - Mantém a estrutura hierárquica da árvore

### 3. Espaçamento Adicional Automático

**Função:** `aplicarEspacamentoAdicional()`

- **Funcionalidade:**
  - Aplica espaçamento adicional após o layout inicial
  - Verifica cada nível da árvore individualmente
  - Expande o espaçamento quando detecta que é insuficiente
  - Mantém a proporção e estrutura da árvore

### 4. Botão "Expandir Árvore"

**Arquivo:** `templates/dominial/cadeia_dominial_d3.html`

- **Funcionalidade:**
  - Novo botão ao lado do botão "Reset"
  - Ícone de expansão para indicar a função
  - Permite ao usuário expandir manualmente a árvore
  - Calcula automaticamente o melhor zoom para visualizar todos os cards

**Função:** `expandirArvore()`

- **Características:**
  - Calcula o bounding box real de todos os cards
  - Adiciona margens apropriadas (70px horizontal, 40px vertical)
  - Aplica zoom e translação para enquadrar toda a árvore
  - Transição suave de 600ms

### 5. Melhorias no Layout da Árvore

**Função:** `renderArvoreD3()`

- **Melhorias:**
  - Aumentou a altura disponível para o layout (height * 2.0)
  - Melhorou a função de separação entre nós irmãos
  - Novos limites de separação:
    - Mais de 15 irmãos: 3.0x separação
    - Mais de 10 irmãos: 2.0x separação
    - Mais de 6 irmãos: 1.5x separação
    - Padrão: 1.0x separação

### 6. Melhorias Visuais nos Controles

**Arquivo:** `static/dominial/css/cadeia_dominial_d3.css`

- **Melhorias:**
  - Ajustou o layout dos controles de zoom para acomodar 4 botões
  - Reduziu o tamanho dos botões para melhor aproveitamento do espaço
  - Adicionou flex-wrap para responsividade
  - Melhorou o alinhamento dos ícones

## Como Usar

### Controles Disponíveis

1. **Zoom +** (`+`): Aumenta o zoom da visualização
2. **Zoom -** (`-`): Diminui o zoom da visualização
3. **Reset** (⏱️): Retorna ao zoom padrão
4. **Expandir Árvore** (⬜): Expande automaticamente a árvore para visualizar todos os cards

### Comportamento Automático

- A árvore agora se ajusta automaticamente para evitar sobreposições
- O espaçamento é calculado dinamicamente baseado na quantidade de documentos
- A correção de sobreposições é aplicada automaticamente durante a renderização

## Benefícios

1. **Melhor Visualização**: Cards não se sobrepõem mais
2. **Controle Manual**: Usuário pode expandir a árvore quando necessário
3. **Responsividade**: Funciona bem com diferentes quantidades de documentos
4. **Performance**: Mantém a eficiência do algoritmo D3
5. **Compatibilidade**: Não quebra funcionalidades existentes

## Arquivos Modificados

1. `static/dominial/js/cadeia_dominial_d3.js`
   - Melhorias nas funções de espaçamento
   - Nova função `expandirArvore()`
   - Nova função `aplicarEspacamentoAdicional()`

2. `templates/dominial/cadeia_dominial_d3.html`
   - Adicionado botão "Expandir Árvore"

3. `static/dominial/css/cadeia_dominial_d3.css`
   - Ajustes nos controles de zoom

## Testes Recomendados

1. Testar com poucos documentos (1-5)
2. Testar com muitos documentos (15+)
3. Testar com árvores muito largas (muitos irmãos)
4. Testar com árvores muito profundas (muitos níveis)
5. Verificar se o botão "Expandir Árvore" funciona corretamente
6. Verificar se não há sobreposições em nenhum cenário 