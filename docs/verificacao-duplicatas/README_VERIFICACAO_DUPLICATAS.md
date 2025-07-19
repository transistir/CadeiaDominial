# 📚 DOCUMENTAÇÃO - VERIFICAÇÃO DE DUPLICATAS

## 🎯 **Visão Geral**
Esta documentação cobre a implementação da funcionalidade de verificação de duplicatas no sistema Cadeia Dominial. A funcionalidade detecta automaticamente quando uma origem/cartório já existe em outra cadeia dominial e oferece importação automática do trecho correspondente.

## 📋 **Índice da Documentação**

### **1. Planejamento Principal**
- **[PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md](PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md)**
  - Documentação completa e detalhada
  - Estratégia de desenvolvimento em 6 fases
  - Implementação técnica detalhada
  - Plano de deploy em produção
  - Estratégia de retrocompatibilidade

### **2. Resumo Executivo**
- **[RESUMO_VERIFICACAO_DUPLICATAS.md](RESUMO_VERIFICACAO_DUPLICATAS.md)**
  - Visão geral rápida da funcionalidade
  - Pontos principais de retrocompatibilidade
  - Fases de desenvolvimento resumidas
  - Comandos úteis para deploy

### **3. Checklist de Implementação**
- **[CHECKLIST_VERIFICACAO_DUPLICATAS.md](CHECKLIST_VERIFICACAO_DUPLICATAS.md)**
  - Checklist detalhado por fase
  - Tarefas específicas para cada etapa
  - Critérios de conclusão
  - Acompanhamento de progresso

### **4. Exemplos Práticos**
- **[EXEMPLOS_VERIFICACAO_DUPLICATAS.md](EXEMPLOS_VERIFICACAO_DUPLICATAS.md)**
  - Cenários de uso reais
  - Exemplos de código
  - Exemplos de interface
  - Casos de borda

## 🚀 **Início Rápido**

### **Para Desenvolvedores**
1. Leia o **[RESUMO_VERIFICACAO_DUPLICATAS.md](RESUMO_VERIFICACAO_DUPLICATAS.md)** para entender o conceito
2. Use o **[CHECKLIST_VERIFICACAO_DUPLICATAS.md](CHECKLIST_VERIFICACAO_DUPLICATAS.md)** para acompanhar o progresso
3. Consulte **[EXEMPLOS_VERIFICACAO_DUPLICATAS.md](EXEMPLOS_VERIFICACAO_DUPLICATAS.md)** para exemplos práticos
4. Implemente seguindo **[PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md](PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md)**

### **Para Gerentes/Stakeholders**
1. Leia o **[RESUMO_VERIFICACAO_DUPLICATAS.md](RESUMO_VERIFICACAO_DUPLICATAS.md)** para visão geral
2. Consulte **[PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md](PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md)** para cronograma
3. Use **[CHECKLIST_VERIFICACAO_DUPLICATAS.md](CHECKLIST_VERIFICACAO_DUPLICATAS.md)** para acompanhar progresso

### **Para Deploy em Produção**
1. Siga o plano de deploy em **[PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md](PLANEJAMENTO_VERIFICACAO_DUPLICATAS.md)**
2. Use os comandos em **[RESUMO_VERIFICACAO_DUPLICATAS.md](RESUMO_VERIFICACAO_DUPLICATAS.md)**
3. Monitore usando o checklist de deploy

## 🔑 **Pontos-Chave**

### **Retrocompatibilidade**
- ✅ **100% segura** - Todas as modificações são aditivas
- ✅ **Feature flag** - Pode ser desabilitada a qualquer momento
- ✅ **Rollback** - Possível sem perda de dados
- ✅ **Dados existentes** - Não são afetados

### **Indicação Visual**
- **Borda verde** nos cards de documentos importados (não cor de fundo)
- **Preserva cores originais** de transcrições e matrículas
- **Tooltip** indicando origem do documento
- **Badge** "📋 Importado" no canto superior direito

### **Fases de Desenvolvimento**
1. **Fase 1**: Estrutura base e testes
2. **Fase 2**: API e endpoints
3. **Fase 3**: Interface do usuário
4. **Fase 4**: Integração com formulário existente
5. **Fase 5**: Visualização e indicadores
6. **Fase 6**: Otimizações e melhorias

## 📁 **Arquivos do Projeto**

### **Backend**
```
dominial/
├── models/
│   └── documento_importado_models.py          # Novo modelo
├── services/
│   ├── duplicata_verificacao_service.py      # Novo service
│   └── importacao_cadeia_service.py          # Novo service
├── views/
│   └── api_duplicata_views.py                # Novas APIs
└── tests/
    └── test_duplicata_verificacao.py         # Novos testes
```

### **Frontend**
```
templates/dominial/components/
└── _modal_duplicata.html                     # Novo modal

static/dominial/
├── js/
│   └── duplicata_verificacao.js              # Novo JavaScript
└── css/
    └── duplicata_verificacao.css             # Novo CSS
```

### **Configuração**
```
settings.py
├── DUPLICATA_VERIFICACAO_ENABLED             # Feature flag
└── URLs para APIs                            # Novos endpoints
```

## 🧪 **Testes**

### **Comandos de Teste**
```bash
# Executar todos os testes da funcionalidade
python manage.py test dominial.tests.test_duplicata_verificacao

# Executar testes específicos
python manage.py test dominial.tests.test_duplicata_verificacao.DuplicataVerificacaoTestCase.test_verificar_duplicata_existente

# Executar testes de regressão
python manage.py test dominial.tests
```

### **Testes de Performance**
```bash
# Verificar performance da verificação
python manage.py shell -c "
from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService
import time
start = time.time()
resultado = DuplicataVerificacaoService.verificar_duplicata_origem('12345', cartorio, imovel)
end = time.time()
print(f'Tempo de verificação: {end - start:.2f} segundos')
"
```

## 🚀 **Deploy**

### **Comandos de Deploy**
```bash
# Fase 1 - Estruturas (sem risco)
pg_dump cadeia_dominial > backup_pre_duplicata.sql
python manage.py migrate
python manage.py check

# Fase 2 - Funcionalidades (feature flag desabilitado)
git pull origin main
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn

# Fase 3 - Ativação gradual
export DUPLICATA_VERIFICACAO_ENABLED=true
sudo systemctl restart gunicorn
```

### **Verificação de Status**
```bash
# Verificar feature flag
python manage.py shell -c "from django.conf import settings; print(settings.DUPLICATA_VERIFICACAO_ENABLED)"

# Verificar documentos importados
python manage.py shell -c "from dominial.models import DocumentoImportado; print(DocumentoImportado.objects.count())"
```

## 📊 **Monitoramento**

### **Logs Importantes**
- Verificação de duplicatas
- Importações realizadas
- Erros de importação
- Performance das consultas

### **Métricas**
- Tempo de verificação (< 2 segundos)
- Taxa de uso da funcionalidade
- Taxa de sucesso na importação
- Uso de memória e CPU

## 🆘 **Suporte**

### **Problemas Comuns**
1. **Feature flag não funciona**: Verificar variável de ambiente
2. **Verificação lenta**: Verificar índices no banco
3. **Modal não aparece**: Verificar JavaScript e CSS
4. **Importação falha**: Verificar logs de erro

### **Rollback**
```bash
# Desabilitar funcionalidade
export DUPLICATA_VERIFICACAO_ENABLED=false
sudo systemctl restart gunicorn

# Verificar se foi desabilitado
python manage.py shell -c "from django.conf import settings; print(settings.DUPLICATA_VERIFICACAO_ENABLED)"
```

## 📝 **Atualizações da Documentação**

### **Versão da Documentação**
- **Versão**: 1.0
- **Data**: Janeiro 2024
- **Última atualização**: [Data]

### **Histórico de Mudanças**
- **v1.0**: Documentação inicial completa
  - Planejamento detalhado
  - Exemplos práticos
  - Checklist de implementação
  - Estratégia de retrocompatibilidade

---

**📞 Para dúvidas ou sugestões sobre esta documentação, consulte a equipe de desenvolvimento.** 