# ✅ CHECKLIST - VERIFICAÇÃO DE DUPLICATAS

## 📋 **FASE 1: Estrutura Base e Testes**

### **1.1 Modelo de Dados**
- [ ] Criar `dominial/models/documento_importado_models.py`
- [ ] Definir modelo `DocumentoImportado`
- [ ] Configurar Meta e relacionamentos
- [ ] Criar migração inicial
- [ ] Testar migração em ambiente de desenvolvimento

### **1.2 Service de Verificação**
- [ ] Criar `dominial/services/duplicata_verificacao_service.py`
- [ ] Implementar `verificar_duplicata_origem()`
- [ ] Implementar `obter_cadeia_dominial_origem()`
- [ ] Implementar `calcular_documentos_importaveis()`
- [ ] Adicionar feature flag check
- [ ] Testar service com dados de exemplo

### **1.3 Service de Importação**
- [ ] Criar `dominial/services/importacao_cadeia_service.py`
- [ ] Implementar `importar_cadeia_dominial()`
- [ ] Implementar `marcar_documento_importado()`
- [ ] Adicionar validações de integridade
- [ ] Testar importação com dados de exemplo

### **1.4 Testes Unitários**
- [ ] Criar `dominial/tests/test_duplicata_verificacao.py`
- [ ] Teste: verificar duplicata existente
- [ ] Teste: verificar duplicata inexistente
- [ ] Teste: calcular documentos importáveis
- [ ] Teste: importar cadeia dominial
- [ ] Teste: validar integridade dos dados
- [ ] Executar todos os testes: `python manage.py test dominial.tests.test_duplicata_verificacao`

### **1.5 Feature Flag**
- [ ] Adicionar `DUPLICATA_VERIFICACAO_ENABLED` no settings
- [ ] Configurar variável de ambiente
- [ ] Testar feature flag desabilitado
- [ ] Testar feature flag habilitado

## 📋 **FASE 2: API e Endpoints**

### **2.1 Views da API**
- [ ] Criar `dominial/views/api_duplicata_views.py`
- [ ] Implementar `verificar_duplicata_api()`
- [ ] Implementar `importar_cadeia_api()`
- [ ] Adicionar decoradores de autenticação
- [ ] Adicionar validação CSRF

### **2.2 URLs**
- [ ] Adicionar URLs no `dominial/urls.py`
- [ ] Configurar rota `/api/verificar-duplicata/`
- [ ] Configurar rota `/api/importar-cadeia/`
- [ ] Testar endpoints com Postman/curl

### **2.3 Validação e Segurança**
- [ ] Validar permissões do usuário
- [ ] Implementar rate limiting
- [ ] Adicionar logs de auditoria
- [ ] Validar dados de entrada
- [ ] Testar cenários de erro

### **2.4 Testes de API**
- [ ] Teste: verificar duplicata via API
- [ ] Teste: importar cadeia via API
- [ ] Teste: cenários de erro
- [ ] Teste: autenticação e permissões

## 📋 **FASE 3: Interface do Usuário**

### **3.1 Modal de Confirmação**
- [ ] Criar `templates/dominial/components/_modal_duplicata.html`
- [ ] Estruturar HTML do modal
- [ ] Adicionar informações da duplicata
- [ ] Listar documentos importáveis
- [ ] Botão "Importar Cadeia" (verde)
- [ ] Botão "Cancelar e Alterar Dados" (cinza)
- [ ] Testar responsividade

### **3.2 JavaScript**
- [ ] Criar `static/dominial/js/duplicata_verificacao.js`
- [ ] Implementar `DuplicataVerificacao` class
- [ ] Método `verificarOrigem()`
- [ ] Método `mostrarModal()`
- [ ] Método `confirmarImportacao()`
- [ ] Método `cancelarImportacao()` - **BLOQUEIA formulário**
- [ ] Método `bloquearFormularioDuplicata()` - destaca campos em vermelho
- [ ] Método `adicionarMensagemErro()` - mostra mensagem de erro
- [ ] Tratamento de erros
- [ ] Testar interações

### **3.3 CSS**
- [ ] Criar `static/dominial/css/duplicata_verificacao.css`
- [ ] Estilos do modal
- [ ] **Borda verde para documentos importados**
- [ ] Badge "📋 Importado"
- [ ] Tooltip de origem
- [ ] **Estilos para campos inválidos** (vermelho)
- [ ] **Estilos para mensagens de erro**
- [ ] Animações e transições
- [ ] Responsividade

### **3.4 Testes de Interface**
- [ ] Teste: exibição do modal
- [ ] Teste: interação com JavaScript
- [ ] Teste: estilos CSS
- [ ] Teste: responsividade mobile

## 📋 **FASE 4: Integração com Formulário Existente**

### **4.1 Formulário de Lançamento**
- [ ] Modificar `templates/dominial/lancamento_form.html`
- [ ] Adicionar IDs únicos aos campos origem/cartório
- [ ] Incluir modal de duplicata
- [ ] Incluir JavaScript de verificação
- [ ] Incluir CSS de estilos
- [ ] Testar formulário existente (não quebrar)

### **4.2 Service de Criação**
- [ ] Modificar `dominial/services/lancamento_criacao_service.py`
- [ ] Adicionar verificação de duplicata antes da criação
- [ ] Integrar com service de importação
- [ ] Manter funcionalidade existente intacta
- [ ] Testar criação de lançamentos

### **4.3 Testes de Integração**
- [ ] Teste: fluxo completo do formulário
- [ ] Teste: verificação durante criação
- [ ] Teste: importação durante criação
- [ ] Teste: funcionalidades existentes não quebradas

## 📋 **FASE 5: Visualização e Indicadores** ✅

### **5.1 Árvore da Cadeia Dominial** ✅
- [x] Modificar `static/dominial/js/cadeia_dominial_d3.js`
- [x] **Adicionar borda verde para documentos importados**
- [x] Preservar cores originais de transcrições/matrículas
- [x] Tooltip indicando origem do documento
- [x] Testar visualização

### **5.2 Tabela da Cadeia Dominial** ✅
- [x] Modificar `templates/dominial/cadeia_dominial_tabela.html`
- [x] **Borda verde para documentos importados**
- [x] Coluna adicional com informação de origem
- [x] Testar tabela

### **5.3 Service de Tabela** ✅
- [x] Modificar `dominial/services/cadeia_dominial_tabela_service.py`
- [x] Adicionar informação de documentos importados
- [x] Testar service

### **5.4 Testes de Visualização** ✅
- [x] Teste: árvore com documentos importados
- [x] Teste: tabela com documentos importados
- [x] Teste: indicadores visuais corretos

## 📋 **FASE 6: Otimizações e Melhorias**

### **6.1 Performance**
- [ ] Implementar cache para verificações
- [ ] Adicionar índices no banco de dados
- [ ] Otimizar queries
- [ ] Implementar lazy loading
- [ ] Testar performance

### **6.2 Usabilidade**
- [ ] Feedback visual durante importação
- [ ] Possibilidade de desfazer importação
- [ ] Histórico de importações
- [ ] Melhorias de UX

### **6.3 Monitoramento**
- [ ] Logs de auditoria
- [ ] Métricas de uso
- [ ] Monitoramento de erros
- [ ] Alertas de performance

## 🚀 **DEPLOY EM PRODUÇÃO**

### **Deploy Fase 1 - Estruturas**
- [ ] Backup do banco de dados
- [ ] Deploy das migrações
- [ ] Verificar integridade
- [ ] Testar funcionalidades existentes

### **Deploy Fase 2 - Funcionalidades**
- [ ] Deploy do código (feature flag desabilitado)
- [ ] Coletar arquivos estáticos
- [ ] Reiniciar serviços
- [ ] Verificar logs

### **Deploy Fase 3 - Ativação**
- [ ] Ativar para usuários de teste
- [ ] Monitorar logs e performance
- [ ] Ativar para todos os usuários
- [ ] Monitoramento contínuo

## 🧪 **TESTES FINAIS**

### **Testes de Regressão**
- [ ] Todos os testes existentes passam
- [ ] Funcionalidades existentes não quebradas
- [ ] Performance não degradada
- [ ] Interface responsiva

### **Testes de Aceitação**
- [ ] Usuário consegue verificar duplicata
- [ ] Usuário consegue importar cadeia
- [ ] Indicadores visuais funcionam
- [ ] Modal funciona corretamente

### **Testes de Performance**
- [ ] Verificação < 2 segundos
- [ ] Importação não trava o sistema
- [ ] Cache funcionando
- [ ] Queries otimizadas

## 📊 **DOCUMENTAÇÃO**

### **Documentação Técnica**
- [ ] Atualizar `PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md`
- [ ] Atualizar `RESUMO_VERIFICACAO_DUPLICATAS.md`
- [ ] Documentar APIs
- [ ] Documentar configurações

### **Documentação de Usuário**
- [ ] Manual de uso da funcionalidade
- [ ] Screenshots da interface
- [ ] FAQ
- [ ] Vídeo tutorial

## 🎯 **CRITÉRIOS DE CONCLUSÃO**

- [ ] Todas as fases implementadas
- [ ] Todos os testes passando
- [ ] Deploy em produção bem-sucedido
- [ ] Funcionalidade ativa e funcionando
- [ ] Usuários treinados
- [ ] Monitoramento configurado
- [ ] Documentação completa

---

**Status Geral**: ✅ Fases 1-5 COMPLETAS  
**Última atualização**: 20/07/2025  
**Próxima revisão**: FASE 6 - Otimizações 