"""
Script para criar ou atualizar o usuário admin no modo desenvolvimento.
Este script é executado via: python manage.py shell < create_admin_user.py
"""
import os
from django.contrib.auth.models import User

# Obter credenciais das variáveis de ambiente
username = os.environ.get('ADMIN_USERNAME', 'admin')
email = os.environ.get('ADMIN_EMAIL', 'admin@cadeiadominial.com.br')
password = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Criar ou atualizar o usuário admin
user, created = User.objects.get_or_create(
    username=username,
    defaults={
        'email': email,
        'is_superuser': True,
        'is_staff': True,
    }
)

# Sempre atualizar a senha para garantir que está correta
user.set_password(password)
user.email = email
user.is_superuser = True
user.is_staff = True
user.save()

if created:
    print(f'✅ Usuário admin criado com sucesso!')
    print(f'   Usuário: {username}')
    print(f'   Email: {email}')
    print(f'   Senha: {password}')
else:
    print(f'✅ Usuário admin já existe e foi atualizado!')
    print(f'   Usuário: {username}')
    print(f'   Senha resetada para: {password}')

