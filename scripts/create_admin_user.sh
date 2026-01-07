#!/bin/bash
# Script para criar ou atualizar o usuário admin no modo desenvolvimento

# Executar código Python via manage.py shell usando heredoc
python manage.py shell << 'PYTHON_SCRIPT'
import os
from django.contrib.auth.models import User

username = os.environ.get('ADMIN_USERNAME', 'admin')
email = os.environ.get('ADMIN_EMAIL', 'admin@cadeiadominial.com.br')
password = os.environ.get('ADMIN_PASSWORD', 'admin123')

user, created = User.objects.get_or_create(
    username=username,
    defaults={'email': email, 'is_superuser': True, 'is_staff': True}
)

user.set_password(password)
user.email = email
user.is_superuser = True
user.is_staff = True
user.save()

if created:
    print('✅ Usuário admin criado com sucesso!')
    print('   Usuário:', username)
    print('   Email:', email)
    print('   Senha:', password)
else:
    print('✅ Usuário admin já existe e foi atualizado!')
    print('   Usuário:', username)
    print('   Senha resetada para:', password)
PYTHON_SCRIPT

