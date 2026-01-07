# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.0.0-beta] - 2024-12-19

### Adicionado
- Sistema completo de gestão de cadeia dominial
- Modelos de dados para TIs, Imóveis, Documentos e Lançamentos
- Interface administrativa personalizada
- Visualização em árvore interativa com zoom e pan
- Sistema de autenticação e autorização
- Base de dados de cartórios brasileiros
- Comandos de gerenciamento para inicialização do sistema
- Templates responsivos e modernos
- Sistema de tipos de documento e lançamento
- Relacionamentos entre documentos e lançamentos
- Detecção automática de documentos de origem
- Cards dinâmicos com tamanho ajustável
- Conexões visuais entre documentos relacionados
- Controles de zoom seletivo na área da árvore
- Efeitos visuais e transições suaves
- Sistema de pessoas e proprietários
- Validação de dados e integridade
- URLs de autenticação padrão do Django

### Melhorado
- Design da interface com tema consistente
- Navegação intuitiva entre seções
- Feedback visual em interações
- Espaçamento e legibilidade dos elementos
- Tamanho dos números de documento nos cards
- Zoom aplicado apenas na área da árvore
- Espaçamento entre cards de documentos
- Remoção de elementos visuais desnecessários

### Corrigido
- Erro de referência à variável `container` no JavaScript
- URLs de autenticação faltantes (404 em navegadores diferentes)
- Problemas de posicionamento dos cards
- Linhas de conexão desnecessárias

### Removido
- Ícones dos cards para dar mais espaço aos números
- Palavra "Matrícula" dos cards (mantendo apenas "Transcrição")
- Linha horizontal verde conectando cards de origem

## [0.1.0] - 2024-12-01

### Adicionado
- Estrutura inicial do projeto Django
- Modelos básicos de dados
- Migrações iniciais
- Configuração básica do projeto

---

## Tipos de Mudanças

- **Adicionado** para novas funcionalidades
- **Alterado** para mudanças em funcionalidades existentes
- **Descontinuado** para funcionalidades que serão removidas em breve
- **Removido** para funcionalidades removidas
- **Corrigido** para correções de bugs
- **Segurança** para vulnerabilidades corrigidas 