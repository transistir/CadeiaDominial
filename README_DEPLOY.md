# 🚀 Deploy da Cadeia Dominial

Este guia explica como fazer deploy da aplicação Cadeia Dominial em diferentes plataformas.

## 📋 Pré-requisitos

- Conta no GitHub
- Conta na plataforma escolhida (Railway, Render, etc.)
- Python 3.11+
- Git

## 🎯 Plataformas Recomendadas

### 1. Railway (Recomendado)
- **Custo**: Gratuito para começar
- **Facilidade**: ⭐⭐⭐⭐⭐
- **Recursos**: PostgreSQL incluído, SSL gratuito
- **Guia**: [deploy_railway.md](deploy_railway.md)

### 2. Render
- **Custo**: Gratuito para começar
- **Facilidade**: ⭐⭐⭐⭐
- **Recursos**: PostgreSQL gratuito, SSL gratuito
- **URL**: [render.com](https://render.com)

### 3. Heroku
- **Custo**: $5-25/mês
- **Facilidade**: ⭐⭐⭐⭐
- **Recursos**: Muito estável, add-ons abundantes
- **URL**: [heroku.com](https://heroku.com)

## 🛠️ Preparação do Projeto

### 1. Verificar Arquivos
Certifique-se de que os seguintes arquivos estão presentes:
- ✅ `requirements.txt` - Dependências Python
- ✅ `Procfile` - Configuração do servidor
- ✅ `runtime.txt` - Versão do Python
- ✅ `cadeia_dominial/settings_prod.py` - Configurações de produção

### 2. Executar Script de Deploy
```bash
# Tornar executável (se necessário)
chmod +x deploy.sh

# Executar deploy
./deploy.sh
```

### 3. Deploy Manual
```bash
# Atualizar dependências
pip install -r requirements.txt

# Coletar arquivos estáticos
python manage.py collectstatic --noinput

# Commit e push
git add .
git commit -m "feat: preparar para deploy"
git push origin develop
```

## 🔧 Configurações de Produção

### Variáveis de Ambiente Necessárias
```env
# Django
SECRET_KEY=sua_chave_secreta_muito_segura
DEBUG=False
ALLOWED_HOSTS=seu-dominio.com

# Banco de Dados
DATABASE_URL=postgresql://usuario:senha@host:porta/nome_do_banco

# CSRF
CSRF_TRUSTED_ORIGINS=https://seu-dominio.com

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_de_app
```

### Comandos de Build
```bash
# Build Command
python manage.py collectstatic --noinput

# Start Command
gunicorn cadeia_dominial.wsgi
```

## 🗄️ Configuração do Banco

Após o deploy, execute:
```bash
# Migrar banco
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Carregar dados iniciais (se necessário)
python manage.py loaddata dados_iniciais.json
```

## 📊 Monitoramento

### Logs
- Railway: Dashboard → Logs
- Render: Dashboard → Logs
- Heroku: `heroku logs --tail`

### Métricas
- Uso de CPU e memória
- Requisições por minuto
- Tempo de resposta
- Erros 4xx/5xx

## 🔒 Segurança

### Checklist
- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` segura
- [ ] `ALLOWED_HOSTS` configurado
- [ ] `CSRF_TRUSTED_ORIGINS` configurado
- [ ] SSL/HTTPS ativo
- [ ] Senhas fortes
- [ ] Backup configurado

### Backup
```bash
# Backup do banco
python manage.py dumpdata > backup.json

# Restore
python manage.py loaddata backup.json
```

## 🚨 Troubleshooting

### Problemas Comuns

1. **Erro de arquivos estáticos**
   ```bash
   python manage.py collectstatic --noinput
   ```

2. **Erro de migração**
   ```bash
   python manage.py migrate --run-syncdb
   ```

3. **Erro de permissão**
   ```bash
   chmod +x deploy.sh
   ```

4. **Timeout no deploy**
   - Verificar logs
   - Aumentar timeout na plataforma
   - Otimizar build

### Logs Úteis
```bash
# Ver logs em tempo real
tail -f logs/app.log

# Ver erros
grep ERROR logs/app.log

# Ver performance
grep "Request took" logs/app.log
```

## 📞 Suporte

- **Railway**: [docs.railway.app](https://docs.railway.app)
- **Render**: [render.com/docs](https://render.com/docs)
- **Heroku**: [devcenter.heroku.com](https://devcenter.heroku.com)

## 💰 Custos Estimados

| Plataforma | Plano Gratuito | Plano Pago |
|------------|----------------|------------|
| Railway    | 500h/mês       | $5-20/mês  |
| Render     | 750h/mês       | $7-25/mês  |
| Heroku     | Não disponível | $5-25/mês  |

## 🎉 Próximos Passos

1. ✅ Fazer deploy
2. ✅ Configurar domínio personalizado
3. ✅ Configurar SSL
4. ✅ Configurar backup automático
5. ✅ Configurar monitoramento
6. ✅ Configurar CI/CD
7. ✅ Testar em produção 