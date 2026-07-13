# 📁 Organização do Projeto - Cadeia Dominial

## 🎯 Estrutura Organizada

### 📚 Documentação (`docs/`)
- **CHECKLIST_PRODUCAO.md** - Checklist completo para deploy em produção
- **README.md** - Índice organizado de toda a documentação
- **Cartórios** - Documentação sobre reformulação de cartórios
- **Refatoração** - Documentação das melhorias implementadas
- **Deploy** - Guias de deploy e configuração

### 🧪 Scripts de Teste (`tests_scripts/`)
- **test_*.py** - Scripts de teste de funcionalidades
- **analisar_estrutura_cartorios.py** - Análise da estrutura de cartórios

### 🔧 Código Principal
- **dominial/** - Aplicação Django principal
- **cadeia_dominial/** - Configurações do projeto
- **templates/** - Templates HTML
- **static/** - Arquivos estáticos (CSS, JS)
- **scripts/** - Scripts de automação

### 🐳 Docker e Deploy
- **docker-compose.yml** - Configuração Docker produção
- **docker-compose.dev.yml** - Configuração Docker desenvolvimento
- **Dockerfile** - Imagem Docker
- **nginx/** - Configuração Nginx

## 🚀 Como Navegar

### Para Deploy em Produção
1. **docs/CHECKLIST_PRODUCAO.md** - Checklist completo
2. **docs/README_DEPLOY_AUTOMATICO.md** - Guia de deploy automático
3. **docs/deploy_debian.md** - Deploy em Debian
4. **docs/deploy_railway.md** - Deploy no Railway

### Para Entender Cartórios
1. **docs/RESUMO_ANALISE_CARTORIOS.md** - Análise atual
2. **docs/PLANEJAMENTO_REFORMULACAO_CARTORIOS.md** - Planejamento
3. **docs/DETALHES_TECNICOS_CARTORIOS.md** - Implementação

### Para Testes
1. **tests_scripts/test_formulario_lancamento.py** - Teste do formulário
2. **tests_scripts/analisar_estrutura_cartorios.py** - Análise de cartórios
3. **tests_scripts/test_integracao_formulario.py** - Teste de integração

## ✅ Benefícios da Organização

### Antes
- ❌ Arquivos espalhados na raiz
- ❌ Difícil de encontrar documentação
- ❌ Scripts de teste misturados
- ❌ Confuso para novos desenvolvedores

### Depois
- ✅ Documentação centralizada em `docs/`
- ✅ Scripts de teste organizados em `tests_scripts/`
- ✅ Navegação clara e intuitiva
- ✅ Fácil manutenção e atualização

## 🔄 Próximos Passos

1. **Atualizar links** em documentação existente
2. **Criar documentação** para novos desenvolvedores
3. **Manter organização** conforme o projeto cresce
4. **Revisar periodicamente** a estrutura

---

**💡 Dica:** Use `Ctrl+F` para buscar rapidamente por termos específicos na documentação organizada. 