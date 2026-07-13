# Generated manually to fix matricula unique constraint
# A matrícula deve ser única por cartório, não globalmente
#
# IMPORTANTE: Execute o comando de verificação antes de aplicar esta migração:
# python manage.py verificar_matricula_constraint
#
# Esta migração pode falhar se houver matrículas duplicadas no mesmo cartório.
# Nesse caso, resolva as duplicatas antes de aplicar a migração.

from django.db import migrations, models


def verificar_duplicatas(apps, schema_editor):
    """
    Função para verificar se há duplicatas antes de aplicar a constraint.
    Se houver, a migração será interrompida com uma mensagem clara.
    """
    Imovel = apps.get_model('dominial', 'Imovel')
    
    # Verificar duplicatas no mesmo cartório
    from django.db.models import Count
    duplicatas = Imovel.objects.values('matricula', 'cartorio').annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    if duplicatas.exists():
        problemas = []
        for dup in duplicatas:
            matricula = dup['matricula']
            cartorio_id = dup['cartorio']
            count = dup['count']
            cartorio_nome = "Sem cartório"
            if cartorio_id:
                try:
                    Cartorio = apps.get_model('dominial', 'Cartorios')
                    cartorio = Cartorio.objects.filter(id=cartorio_id).first()
                    if cartorio:
                        cartorio_nome = cartorio.nome
                except:
                    pass
            problemas.append(f"Matrícula '{matricula}' no cartório '{cartorio_nome}' ({cartorio_id}): {count} ocorrências")
        
        raise ValueError(
            f"❌ ERRO: Encontradas {duplicatas.count()} matrículas duplicadas no mesmo cartório!\n\n"
            f"Problemas encontrados:\n" + "\n".join(f"  - {p}" for p in problemas) + "\n\n"
            f"Por favor, resolva essas duplicatas antes de aplicar a migração.\n"
            f"Execute: python manage.py verificar_matricula_constraint para mais detalhes."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('dominial', '0041_fimcadeia'),
    ]

    operations = [
        # Passo 0: Verificar duplicatas antes de prosseguir
        migrations.RunPython(verificar_duplicatas, migrations.RunPython.noop),
        
        # Passo 1: Remover a constraint unique do campo matricula
        migrations.AlterField(
            model_name='imovel',
            name='matricula',
            field=models.CharField(
                help_text='Número da matrícula. Deve ser único por cartório.',
                max_length=50
            ),
        ),
        # Passo 2: Adicionar constraint única composta (matricula, cartorio)
        migrations.AddConstraint(
            model_name='imovel',
            constraint=models.UniqueConstraint(
                fields=['matricula', 'cartorio'],
                name='unique_matricula_por_cartorio'
            ),
        ),
        # Passo 3: Adicionar índice para melhorar performance de buscas
        migrations.AddIndex(
            model_name='imovel',
            index=models.Index(fields=['matricula', 'cartorio'], name='dom_imovel_mat_cart_idx'),
        ),
    ]

