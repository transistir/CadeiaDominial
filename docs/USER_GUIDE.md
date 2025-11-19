# 👤 Guia do Usuário

Guia completo para usar o Sistema de Cadeia Dominial.

---

## 📖 Sumário

- [Primeiros Passos](#-primeiros-passos)
- [Conceitos Fundamentais](#-conceitos-fundamentais)
- [Fluxos de Trabalho](#-fluxos-de-trabalho)
- [Funcionalidades](#-funcionalidades)
- [Dicas e Boas Práticas](#-dicas-e-boas-práticas)

---

## 🚀 Primeiros Passos

### Acessando o Sistema

1. **Abra o navegador** e acesse: `http://localhost:8000`
   - Em produção, use o domínio configurado
2. **Faça login** com suas credenciais
   - Use as credenciais do superusuário criado na instalação
3. **Explore a interface** - Navegue pelo menu principal

### Interface Principal

**Menu de Navegação:**
- **TIs** - Terras Indígenas
- **Imóveis** - Propriedades dentro das TIs
- **Documentos** - Matrículas e Transcrições
- **Lançamentos** - Registros, Averbações e Alterações
- **Cartórios** - Cadastro de Cartórios de Registro de Imóveis
- **Pessoas** - Proprietários, Transmitentes e Adquirentes

### Primeiro Acesso

Recomendamos começar nesta ordem:

1. ✅ **Cadastrar Cartórios** - Base de dados de CRIs
2. ✅ **Cadastrar uma TI** - Terra Indígena
3. ✅ **Adicionar Imóvel** - Propriedade dentro da TI
4. ✅ **Cadastrar Documentos** - Matrícula ou Transcrição
5. ✅ **Registrar Lançamentos** - Transações nos documentos
6. ✅ **Visualizar Cadeia** - Árvore da cadeia dominial

---

## 📚 Conceitos Fundamentais

### Terra Indígena (TI)

**O que é:** Terra reconhecida como de ocupação tradicional indígena.

**Informações principais:**
- **Código:** Identificador único (ex: "TI001")
- **Nome:** Nome da terra indígena
- **Etnia:** Povo indígena que a ocupa
- **Área:** Tamanho em hectares
- **Estado:** Unidade federativa
- **Situação Fundiária:** Status legal da terra

**Uso no sistema:** Toda cadeia dominial está associada a uma TI específica.

---

### Imóvel

**O que é:** Propriedade rural dentro dos limites de uma Terra Indígena.

**Informações principais:**
- **Matrícula Principal:** Número da matrícula atual
- **Proprietário Atual:** Pessoa física ou jurídica
- **Terra Indígena:** TI à qual pertence
- **SNCR:** Código do Sistema Nacional de Cadastro Rural (opcional)
- **SIGEF:** Código do Sistema de Gestão Fundiária (opcional)

**Tipos de documento principal:**
- **Matrícula** - Registro moderno (pós-1976)
- **Transcrição** - Registro histórico (pré-1976)

---

### Documentos

#### Matrícula

**O que é:** Sistema de registro imobiliário moderno, instituído pela Lei 6.015/1973.

**Características:**
- Criada a partir de 1976
- Folha única para cada imóvel
- Numeração sequencial por cartório
- Contém todo histórico do imóvel

**Campos obrigatórios:**
- Número da matrícula
- Cartório (CRI)
- Data de abertura
- Livro de registro

#### Transcrição

**O que é:** Sistema de registro anterior às matrículas.

**Características:**
- Usada até 1976
- Cada transação era transcrita em novo documento
- Numeração por livro e folha
- Sistema descontinuado, mas documentos ainda válidos

**Campos obrigatórios:**
- Número da transcrição
- Cartório (CRI)
- Data
- Livro e folha

---

### Lançamentos

**O que são:** Transações ou eventos registrados em um documento.

#### Tipos de Lançamento

**1. Registro**
- Transferência de propriedade (compra/venda)
- Doação
- Herança
- Outras formas de transmissão

**Campos principais:**
- Transmitente (vendedor)
- Adquirente (comprador)
- Valor da transação
- Data do registro
- Documento de origem

**2. Averbação**
- Alterações que não transferem propriedade
- Mudança de estado civil
- Retificação de área
- Alteração de confrontações
- Georreferenciamento

**Campos principais:**
- Tipo de alteração
- Data da averbação
- Observações

**3. Início de Matrícula**
- Abertura de nova matrícula
- Conversão de transcrição em matrícula
- Desmembramento gerando nova matrícula

**Campos principais:**
- Documento de origem (transcrição ou matrícula anterior)
- Data de abertura
- Motivo

---

### Cadeia Dominial

**O que é:** Sequência histórica completa de todos os documentos e transações de um imóvel, desde sua origem até o estado atual.

**Visualizações disponíveis:**
1. **Árvore (D3.js)** - Visualização gráfica interativa
2. **Tabela** - Lista cronológica detalhada

**Documento de Origem:** Primeiro documento da cadeia (geralmente uma transcrição antiga ou título de propriedade original).

**Fim da Cadeia:** Situação atual do imóvel ou ponto onde não há mais documentos anteriores.

**Tipos de fim de cadeia:**
- **Origem Identificada** - Documento de origem encontrado
- **Sem Origem** - Não há documento anterior conhecido
- **Patrimônio Público** - Propriedade do Estado
- **Cadeia Incompleta** - Falta informação

---

## 🔄 Fluxos de Trabalho

### Fluxo 1: Cadastrar Nova Terra Indígena

1. **Acesse:** Menu "TIs" → "Nova TI"
2. **Preencha os dados:**
   - Código (ex: "TI001")
   - Nome da TI
   - Etnia
   - Área em hectares
   - Estado
3. **Salve** o cadastro
4. **Adicione imóveis** à TI criada

---

### Fluxo 2: Cadastrar Imóvel e Documentos

#### Passo 1: Criar o Imóvel

1. **Acesse:** Menu "Imóveis" → "Novo Imóvel"
2. **Selecione a TI** à qual o imóvel pertence
3. **Preencha:**
   - Matrícula principal (número da matrícula atual)
   - Proprietário atual (cadastre pessoa se necessário)
   - SNCR (opcional)
   - SIGEF (opcional)
4. **Salve**

#### Passo 2: Cadastrar Documento Principal

1. **Na página do imóvel**, clique em "Novo Documento"
2. **Escolha o tipo:**
   - **Matrícula** (moderno, pós-1976)
   - **Transcrição** (histórico, pré-1976)
3. **Preencha os dados:**
   - Número do documento
   - Cartório (use o autocomplete)
   - Data
   - Livro e folha (se aplicável)
4. **Salve**

#### Passo 3: Adicionar Lançamentos

1. **No documento criado**, clique em "Novo Lançamento"
2. **Selecione o tipo:**
   - Registro (transferência)
   - Averbação (alteração)
   - Início de Matrícula (abertura)
3. **Preencha os campos obrigatórios:**
   - Para **Registro**: transmitente, adquirente, valor, data
   - Para **Averbação**: tipo de alteração, data
   - Para **Início de Matrícula**: documento de origem
4. **Documento de origem:**
   - Se o lançamento tem origem em outro documento, informe
   - Use o autocomplete para buscar
   - Sistema detecta automaticamente possíveis origens
5. **Salve**

---

### Fluxo 3: Construir Cadeia Dominial Completa

#### Objetivo
Mapear toda a história do imóvel desde a origem até o presente.

#### Passos

**1. Comece pela Matrícula Atual**
- Cadastre o documento mais recente (matrícula vigente)
- Adicione os lançamentos mais recentes

**2. Trabalhe Retroativamente**
- Para cada lançamento, identifique o documento de origem
- Cadastre o documento de origem se ainda não existe
- Adicione lançamentos do documento de origem
- Repita até encontrar o documento original

**3. Identifique Origens Múltiplas**
- Alguns documentos podem ter mais de uma origem (fusão de imóveis)
- O sistema permite selecionar qual origem seguir
- Cadastre todas as origens para cadeia completa

**4. Marque Fim da Cadeia**
- Quando encontrar o documento original, marque como "Origem"
- Se não houver documento anterior, marque como "Sem Origem"
- Se for propriedade pública original, marque como "Patrimônio Público"

**5. Visualize a Cadeia**
- Use a visualização em árvore para ver toda a estrutura
- Use a tabela para análise cronológica detalhada

---

### Fluxo 4: Importar Documentos de Outras Cadeias

**Quando usar:** Quando um documento já cadastrado em outro imóvel também pertence à cadeia do imóvel atual.

**Como fazer:**

1. **Acesse a página do imóvel** que precisa importar documentos
2. **Clique em "Importar Documentos"**
3. **Sistema mostra documentos importáveis:**
   - Documentos detectados como possíveis origens
   - Que ainda não foram importados para este imóvel
4. **Selecione os documentos** a importar
5. **Confirme a importação**
6. **Documentos são vinculados** ao imóvel atual
7. **Cadeia é atualizada** automaticamente

**Verificação de duplicatas:**
- Sistema impede importação duplicada do mesmo documento
- Alerta se documento já foi importado anteriormente

---

## 🎨 Funcionalidades

### 1. Visualização em Árvore (D3.js)

**Como acessar:**
1. Acesse a página de um **Imóvel**
2. Clique em **"Cadeia Dominial"**
3. Escolha **"Visualização em Árvore"**

**Recursos interativos:**

- **Zoom:**
  - Use os botões **+** e **-**
  - Ou use a roda do mouse
  - Zoom máximo e mínimo configuráveis

- **Pan (arrastar):**
  - Clique e arraste para mover a visualização
  - Útil para navegar por cadeias grandes

- **Cards de Documentos:**
  - Cada card representa um documento
  - **Verde:** Matrícula
  - **Azul:** Transcrição
  - **Amarelo:** Origem/fim de cadeia identificado
  - **Vermelho:** Sem origem

- **Conexões:**
  - Linhas conectam documentos relacionados
  - Seguem a hierarquia da cadeia

- **Informações no Card:**
  - Tipo de documento (M para Matrícula, T para Transcrição)
  - Número do documento
  - Cartório
  - Data
  - Quantidade de lançamentos

- **Clique nos Cards:**
  - Clique em um card para ver detalhes
  - Link direto para a página do documento

**Dicas:**
- Para cadeias grandes, use zoom out para visão geral
- Zoom in para ver detalhes de documentos específicos
- Cards ajustam tamanho baseado em conteúdo

---

### 2. Visualização em Tabela

**Como acessar:**
1. Acesse a página de um **Imóvel**
2. Clique em **"Cadeia Dominial"**
3. Escolha **"Visualização em Tabela"**

**Informações exibidas:**
- Lista cronológica de todos os documentos
- Lançamentos de cada documento
- Pessoas envolvidas (transmitente/adquirente)
- Valores de transação
- Datas completas
- Observações

**Funcionalidades:**
- **Ordenação:** Clique nos cabeçalhos para ordenar
- **Filtros:** Filtre por tipo, cartório, período
- **Exportação:** Exporte para Excel ou PDF
- **Busca:** Busque por número, pessoa, etc.

---

### 3. Autocomplete Inteligente

**Onde está disponível:**
- Seleção de Cartórios
- Busca de Pessoas
- Busca de Documentos
- Seleção de TIs

**Como usar:**
1. Comece a digitar no campo
2. Sugestões aparecem automaticamente
3. Use ↑↓ para navegar
4. Enter ou clique para selecionar

**Recursos:**
- Busca parcial (encontra por parte do nome)
- Case-insensitive (não diferencia maiúsculas/minúsculas)
- Mostra informações adicionais (ex: CNS do cartório)

---

### 4. Detecção de Duplicatas

**O sistema detecta automaticamente:**
- Documentos duplicados (mesmo número + cartório)
- Lançamentos duplicados no mesmo documento
- Tentativas de importação duplicada

**Ao criar documento:**
1. Sistema verifica se já existe
2. Se existir, mostra aviso
3. Opção de visualizar documento existente
4. Ou confirmar criação (se legítimo)

**Ao importar documentos:**
- Documentos já importados não aparecem na lista
- Sistema previne reimportação acidental

---

### 5. Seleção de Origem

**Quando aparece:**
Quando um documento tem múltiplas possíveis origens (ex: fusão de dois imóveis).

**Como funciona:**
1. Ao visualizar cadeia, sistema detecta múltiplas origens
2. Modal aparece perguntando qual origem seguir
3. Usuário seleciona a origem desejada
4. Sistema reconstrói árvore com a origem selecionada
5. Escolha é salva na sessão

**Dica:** Você pode trocar a origem selecionada a qualquer momento para explorar diferentes ramificações da cadeia.

---

### 6. Exportação de Dados

**Formatos disponíveis:**
- **Excel (.xlsx)** - Para análise em planilhas
- **PDF** - Para documentação oficial
- **JSON** - Para integração com outros sistemas

**Como exportar:**

**Cadeia completa:**
1. Acesse a visualização de cadeia (árvore ou tabela)
2. Clique em **"Exportar"**
3. Escolha o formato desejado
4. Arquivo é baixado automaticamente

**Lista de documentos:**
1. Na lista de documentos, clique em **"Exportar Lista"**
2. Escolha formato
3. Opcionalmente, aplique filtros antes de exportar

**Dados incluídos na exportação:**
- Todos os documentos da cadeia
- Lançamentos completos
- Pessoas envolvidas
- Datas e valores
- Cartórios
- Observações

---

### 7. Gestão de Cartórios

**Cadastro de Cartórios:**

**Informações obrigatórias:**
- **CNS:** Código Nacional de Serventia
- **Nome:** Nome oficial do cartório
- **Cidade:** Município
- **Estado:** UF
- **Tipo:** CRI (Cartório de Registro de Imóveis)

**Informações opcionais:**
- Endereço completo
- Telefone
- Email
- Site
- Responsável

**Busca de Cartórios:**
- Use o autocomplete por nome
- Busque por CNS
- Filtre por cidade ou estado

---

### 8. Gestão de Pessoas

**Cadastro:**
- Nome completo
- CPF (opcional, mas recomendado)
- Estado civil
- Profissão

**Uso no sistema:**
- Proprietários de imóveis
- Transmitentes (vendedores)
- Adquirentes (compradores)

**Busca:**
- Autocomplete por nome
- Busca por CPF
- Histórico de transações da pessoa

---

## 💡 Dicas e Boas Práticas

### Organização de Dados

1. **Comece pelos dados básicos:**
   - Cadastre cartórios primeiro
   - Depois TIs
   - Depois imóveis

2. **Trabalhe imóvel por imóvel:**
   - Complete a cadeia de um imóvel antes de começar outro
   - Evita confusão e dados incompletos

3. **Use nomenclatura consistente:**
   - Padronize nomes de pessoas (ex: sempre "João da Silva" ou "Silva, João")
   - Padronize nomes de cartórios

4. **Documente observações:**
   - Use campo de observações para informações importantes
   - Registre peculiaridades da cadeia
   - Anote fontes de informação

### Qualidade dos Dados

1. **Sempre informe documento de origem:**
   - Fundamental para construir a cadeia correta
   - Se não souber, deixe em branco (não invente)

2. **Dupla verificação:**
   - Confira número de documentos antes de salvar
   - Verifique datas (formato correto)
   - Confirme cartório correto

3. **Evite duplicatas:**
   - Antes de criar, busque se já existe
   - Use autocomplete para encontrar registros existentes

4. **Mantenha dados atualizados:**
   - Atualize proprietários quando houver mudança
   - Registre todas as averbações
   - Mantenha status da cadeia atualizado

### Resolução de Problemas

**Documento não aparece na árvore:**
- Verifique se está vinculado ao imóvel correto
- Confirme se lançamento tem documento de origem correto
- Verifique se há ciclos na cadeia (erro lógico)

**Cadeia parece incompleta:**
- Verifique se todos os documentos de origem foram cadastrados
- Confirme se lançamentos estão com tipo correto
- Revise seleção de origens (se houver múltiplas)

**Performance lenta com cadeias grandes:**
- Use filtros para reduzir dados exibidos
- Considere visualização em tabela (mais rápida que árvore)
- Exporte para Excel para análise offline

### Atalhos e Produtividade

1. **Use autocomplete sempre:**
   - Mais rápido que digitar completo
   - Evita erros de digitação
   - Previne duplicatas

2. **Salve frequentemente:**
   - Não confie que dados permanecem no formulário
   - Salve antes de navegar para outra página

3. **Aproveite links internos:**
   - Clique em nomes de documentos para ir direto
   - Use breadcrumbs para navegar
   - Atalhos no menu principal

---

## 🎯 Casos de Uso Comuns

### Caso 1: Imóvel com Cadeia Simples

**Cenário:** Imóvel com uma matrícula e 3 registros de transferência.

**Passos:**
1. Crie o imóvel
2. Crie a matrícula atual
3. Adicione o registro mais recente (proprietário atual)
4. Adicione registros anteriores, cada um referenciando o anterior
5. Marque o primeiro documento como "origem"
6. Visualize a cadeia

**Resultado:** Árvore linear mostrando sequência clara de propriedade.

---

### Caso 2: Imóvel com Transcrições Antigas

**Cenário:** Imóvel cuja história começa antes de 1976.

**Passos:**
1. Crie o imóvel com matrícula atual
2. Crie a matrícula (pós-1976)
3. Adicione "Início de Matrícula" referenciando transcrição
4. Crie as transcrições históricas
5. Conecte transcrições formando a cadeia
6. Marque transcrição mais antiga como origem

**Resultado:** Árvore mostrando conversão de transcrição para matrícula e história completa.

---

### Caso 3: Fusão de Imóveis (Múltiplas Origens)

**Cenário:** Matrícula atual resulta da fusão de dois imóveis anteriores.

**Passos:**
1. Crie o imóvel com matrícula atual
2. Crie a matrícula atual
3. Adicione "Início de Matrícula" com múltiplas origens
4. Cadastre ambas as matrículas/transcrições originais
5. Complete cadeias de ambas as origens
6. Ao visualizar, selecione qual origem explorar

**Resultado:** Árvore mostrando bifurcação e origens múltiplas.

---

### Caso 4: Desmembramento (Uma Origem, Múltiplos Destinos)

**Cenário:** Um imóvel grande foi dividido em vários menores.

**Passos:**
1. Crie imóvel original com sua matrícula
2. Para cada imóvel resultante:
   - Crie novo imóvel
   - Crie matrícula com "Início de Matrícula"
   - Referencie matrícula original como origem
3. Todos os novos imóveis apontam para mesma origem

**Resultado:** Várias cadeias independentes partindo de mesma origem.

---

## 📞 Suporte e Recursos

### Documentação Adicional

- **[Documentação Técnica](README.md)** - Visão geral completa
- **[Guia de Instalação](INSTALLATION.md)** - Setup detalhado
- **[Guia de Desenvolvimento](DEVELOPMENT.md)** - Para desenvolvedores
- **[Deploy](deploy/README.md)** - Deployment em produção

### Recursos de Aprendizado

- **Interface Admin:** Experimente livremente em ambiente de teste
- **Dados de Exemplo:** Crie dados fictícios para praticar
- **Exportações:** Use para analisar estrutura dos dados

### Obtendo Ajuda

- **Issues:** [GitHub Issues](https://github.com/transistir/CadeiaDominial/issues)
- **Dúvidas:** Entre em contato com equipe de desenvolvimento
- **Bugs:** Reporte com detalhes para correção rápida

---

**[⬅️ Voltar ao README principal](../README.md)**
