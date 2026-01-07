# 🚀 Guia de Deploy - Railway

## Pré-requisitos
- Conta no [Railway](https://railway.app)
- Repositório no GitHub

## Passos para Deploy

### 1. Preparar o Projeto
```bash
# Verificar se todos os arquivos estão commitados
git status
git add .
git commit -m "feat: preparar projeto para deploy"
git push origin develop
```

### 2. Configurar Railway
1. Acesse [railway.app](https://railway.app)
2. Faça login com sua conta GitHub
3. Clique em "New Project"
4. Selecione "Deploy from GitHub repo"
5. Escolha o repositório `CadeiaDominial`
6. Selecione a branch `develop`

### 3. Configurar Banco de Dados
1. No projeto Railway, clique em "New"
2. Selecione "Database" → "PostgreSQL"
3. Aguarde a criação do banco
4. Copie a URL do banco (será usada nas variáveis de ambiente)

### 4. Configurar Variáveis de Ambiente
No projeto Railway, vá em "Variables" e adicione:

```env
# Django
SECRET_KEY=sua_chave_secreta_muito_segura_aqui
DEBUG=False
ALLOWED_HOSTS=seu-app.railway.app

# Banco de Dados (copie da URL do PostgreSQL)
DATABASE_URL=postgresql://usuario:senha@host:porta/nome_do_banco

# CSRF
CSRF_TRUSTED_ORIGINS=https://seu-app.railway.app

# Email (opcional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu_email@gmail.com
EMAIL_HOST_PASSWORD=sua_senha_de_app
```

### 5. Configurar Build
No Railway, vá em "Settings" → "Build Command":
```bash
python manage.py collectstatic --noinput
```

### 6. Configurar Start Command
No Railway, vá em "Settings" → "Start Command":
```bash
gunicorn cadeia_dominial.wsgi
```

### 7. Deploy
1. Railway fará deploy automático
2. Aguarde a conclusão do build
3. Acesse a URL fornecida

### 8. Configurar Banco
```bash
# No terminal do Railway ou via SSH
python manage.py migrate
python manage.py createsuperuser
```

## URLs de Acesso
- **Aplicação**: https://seu-app.railway.app
- **Admin**: https://seu-app.railway.app/admin

## Monitoramento
- Railway fornece logs em tempo real
- Monitore o uso de recursos no dashboard
- Configure alertas se necessário

## Backup
- Railway faz backup automático do PostgreSQL
- Configure backup manual se necessário

## Custos
- **Gratuito**: 500 horas/mês
- **Pago**: $5-20/mês dependendo do uso 