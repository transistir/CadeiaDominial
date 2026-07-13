# 🚀 Deploy e Produção

Documentação relacionada ao deploy, configuração de produção e infraestrutura do sistema Cadeia Dominial.

## 📋 **Arquivos Disponíveis**

### **Checklist e Guias**
- **[CHECKLIST_PRODUCAO.md](CHECKLIST_PRODUCAO.md)** - Checklist completo para deploy em produção
- **[README_DEPLOY_AUTOMATICO.md](README_DEPLOY_AUTOMATICO.md)** - Guia de deploy automático

### **Plataformas Específicas**
- **[deploy_debian.md](deploy_debian.md)** - Deploy em servidor Debian
- **[deploy_railway.md](deploy_railway.md)** - Deploy no Railway

### **Documentação na Raiz**
- **[README_DEPLOY.md](../../README_DEPLOY.md)** - Guia de deploy (na raiz)
- **[README_DOCKER.md](../../README_DOCKER.md)** - Configuração Docker (na raiz)

## 🎯 **Fluxo Recomendado para Deploy**

1. **Comece por:** [CHECKLIST_PRODUCAO.md](CHECKLIST_PRODUCAO.md)
2. **Escolha a plataforma:** Debian ou Railway
3. **Configure:** Docker se necessário
4. **Automatize:** Use o deploy automático

## 🔧 **Configurações de Produção**

- **Servidor:** Debian com PostgreSQL
- **Container:** Docker com Nginx
- **SSL:** Certbot para HTTPS
- **Backup:** Automático diário
- **Monitoramento:** Logs estruturados

---

**📚 [Voltar ao índice principal](../README.md)** 