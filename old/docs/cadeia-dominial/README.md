# 🌳 Cadeia Dominial - Documentação

## 📋 **Visão Geral**

Esta pasta contém toda a documentação relacionada à **lógica e funcionamento da cadeia dominial**, incluindo tabelas, árvores e visualizações.

## 📚 **Documentação Disponível**

### **🏗️ Lógica e Funcionamento**
- **[LOGICA_CADEIA_DOMINIAL_TABELA.md](LOGICA_CADEIA_DOMINIAL_TABELA.md)** - **📋 LÓGICA** Explicação detalhada do funcionamento da cadeia dominial em formato de tabela

## 🎯 **Funcionalidades da Cadeia Dominial**

### **📊 Visualização em Tabela**
- **Expansão recursiva** de documentos
- **Ordenação hierárquica** por nível
- **Múltiplas origens** com escolha do usuário
- **Documentos importados** com destaque visual

### **🌳 Visualização em Árvore (D3.js)**
- **Estrutura hierárquica** visual
- **Expansão/contração** de nós
- **Destaque visual** para documentos especiais
- **Navegação intuitiva** pela cadeia

### **🔄 Integração com Origens Estruturadas**
- **Destaque de fim de cadeia** em documentos
- **Badges informativos** para tipo e classificação
- **Cores diferenciadas** para documentos especiais

## 🚀 **Como Usar Esta Documentação**

### **Para Entender a Lógica:**
1. **Leia:** **[LOGICA_CADEIA_DOMINIAL_TABELA.md](LOGICA_CADEIA_DOMINIAL_TABELA.md)**

### **Para Desenvolver Visualizações:**
1. **Entenda a lógica** primeiro
2. **Implemente tabela** seguindo a documentação
3. **Implemente árvore** com D3.js
4. **Adicione destaque** para origens estruturadas

## 🔧 **Componentes Técnicos**

### **Backend**
- `CadeiaDominialTabelaService` - Prepara dados para tabela
- `HierarquiaArvoreService` - Constrói estrutura da árvore
- `HierarquiaService` - Lógica base de hierarquia

### **Frontend**
- `cadeia_dominial_tabela.html` - Template da tabela
- `cadeia_dominial_d3.js` - Visualização em árvore
- `cadeia_dominial.css` - Estilos específicos

## 📊 **Fluxo de Dados**

```
Documento Ativo
       ↓
Buscar Lançamentos
       ↓
Expandir Origens
       ↓
Buscar Documentos Anteriores
       ↓
Ordenar Hierarquicamente
       ↓
Preparar para Visualização
       ↓
Renderizar (Tabela/Árvore)
```

## 🎨 **Destaques Visuais**

### **Tabela**
- **Bordas coloridas** para documentos especiais
- **Badges informativos** para tipo e status
- **Indentação** para mostrar hierarquia

### **Árvore D3**
- **Cores diferenciadas** por tipo de documento
- **Badges informativos** sobre status
- **Animações** para expansão/contração

---

**📚 Para voltar à documentação principal:** [../README.md](../README.md) 