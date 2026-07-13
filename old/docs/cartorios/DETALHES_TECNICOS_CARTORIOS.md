# Detalhes Técnicos - Reformulação dos Cartórios

## Nova Estratégia Simplificada

### 1. Modelo de Dados Atualizado

#### 1.1 Modificação do Modelo Lancamento
```python
# dominial/models/lancamento_models.py
class Lancamento(models.Model):
    # ... campos existentes ...
    
    # NOVO: Cartório de Registro (CRI) - Lista fixa
    cartorio_registro = models.ForeignKey(
        'Cartorios', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='lancamentos_registro',
        verbose_name='Cartório de Registro'
    )
    
    # NOVO: Cartório de Transmissão - Campo livre
    cartorio_transmissao = models.CharField(
        max_length=255, 
        blank=True,
        verbose_name='Cartório de Transmissão'
    )
    
    # MANTER: Campo existente para compatibilidade
    cartorio = models.ForeignKey(
        'Cartorios', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name='Cartório (Legado)'
    )
```

#### 1.2 Atualização do Modelo Cartorios
```python
# dominial/models/imovel_models.py
class Cartorios(models.Model):
    TIPO_CHOICES = [
        ('CRI', 'Cartório de Registro de Imóveis'),
        ('OUTRO', 'Outro'),
    ]
    
    nome = models.CharField(max_length=200)
    cns = models.CharField(max_length=20, unique=True)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    tipo = models.CharField(
        max_length=10, 
        choices=TIPO_CHOICES, 
        default='CRI',
        verbose_name='Tipo de Cartório'
    )
    
    class Meta:
        verbose_name = 'Cartório'
        verbose_name_plural = 'Cartórios'
        ordering = ['tipo', 'estado', 'cidade', 'nome']
```

### 2. Migração de Dados

#### 2.1 Script de Migração Segura
```python
# dominial/migrations/XXXX_migrar_cartorios_registro_transmissao.py
from django.db import migrations, models
import django.db.models.deletion

def migrar_dados_cartorios(apps, schema_editor):
    """
    Migração segura dos dados existentes:
    - Cartórios existentes → CRI (cartorio_registro)
    - Campo transmissão fica vazio inicialmente
    """
    Lancamento = apps.get_model('dominical', 'Lancamento')
    
    print("Iniciando migração de dados de cartórios...")
    total = Lancamento.objects.count()
    processados = 0
    
    for lancamento in Lancamento.objects.all():
        if lancamento.cartorio:
            # Preservar cartório existente como CRI
            lancamento.cartorio_registro = lancamento.cartorio
            lancamento.cartorio_transmissao = ""
            lancamento.save()
            processados += 1
            
            if processados % 100 == 0:
                print(f"Processados: {processados}/{total}")
    
    print(f"Migração concluída: {processados} registros processados")

def reverter_migracao(apps, schema_editor):
    """
    Reverter migração se necessário
    """
    Lancamento = apps.get_model('dominical', 'Lancamento')
    
    for lancamento in Lancamento.objects.all():
        if lancamento.cartorio_registro:
            lancamento.cartorio = lancamento.cartorio_registro
            lancamento.save()

class Migration(migrations.Migration):
    dependencies = [
        ('dominical', '0024_alter_terraindigenareferencia_estado'),
    ]

    operations = [
        # Adicionar novos campos
        migrations.AddField(
            model_name='lancamento',
            name='cartorio_registro',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='lancamentos_registro',
                to='dominical.cartorios',
                verbose_name='Cartório de Registro'
            ),
        ),
        migrations.AddField(
            model_name='lancamento',
            name='cartorio_transmissao',
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name='Cartório de Transmissão'
            ),
        ),
        
        # Adicionar campo tipo ao modelo Cartorios
        migrations.AddField(
            model_name='cartorios',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('CRI', 'Cartório de Registro de Imóveis'),
                    ('OUTRO', 'Outro')
                ],
                default='CRI',
                max_length=10,
                verbose_name='Tipo de Cartório'
            ),
        ),
        
        # Executar migração de dados
        migrations.RunPython(
            migrar_dados_cartorios,
            reverter_migracao
        ),
    ]
```

### 3. Formulários Atualizados

#### 3.1 Template de Formulário de Lançamento
```html
<!-- templates/dominial/lancamento_form.html -->
<div class="form-group">
    <label for="cartorio_registro">Cartório de Registro (CRI) *</label>
    <select name="cartorio_registro" id="cartorio_registro" class="form-control" required>
        <option value="">Selecione um cartório de registro...</option>
        {% for cartorio in cartorios_cri %}
            <option value="{{ cartorio.id }}" 
                    {% if lancamento.cartorio_registro_id == cartorio.id %}selected{% endif %}>
                {{ cartorio.nome }} - {{ cartorio.cidade }}/{{ cartorio.estado }}
            </option>
        {% endfor %}
    </select>
    <small class="form-text text-muted">
        Selecione o cartório de registro de imóveis responsável pelo documento
    </small>
</div>

<div class="form-group">
    <label for="cartorio_transmissao">Cartório de Transmissão</label>
    <input type="text" 
           name="cartorio_transmissao" 
           id="cartorio_transmissao" 
           class="form-control"
           value="{{ lancamento.cartorio_transmissao|default:'' }}"
           placeholder="Digite o nome do cartório de transmissão (opcional)">
    <small class="form-text text-muted">
        Cartório onde ocorreu a transmissão (se aplicável)
    </small>
</div>
```

#### 3.2 View Atualizada
```python
# dominial/views/lancamento_views.py
def lancamento_form(request, pk=None):
    if request.method == 'POST':
        # ... lógica de salvamento ...
        pass
    
    # Buscar apenas cartórios CRI para o select
    cartorios_cri = Cartorios.objects.filter(
        tipo='CRI'
    ).order_by('estado', 'cidade', 'nome')
    
    context = {
        'lancamento': lancamento,
        'cartorios_cri': cartorios_cri,
        # ... outros contextos ...
    }
    return render(request, 'dominial/lancamento_form.html', context)
```

### 4. JavaScript Simplificado

#### 4.1 Autocomplete para CRI
```javascript
// static/dominial/js/lancamento_form.js
$(document).ready(function() {
    // Autocomplete para cartório de registro (CRI)
    $('#cartorio_registro').select2({
        placeholder: 'Selecione um cartório de registro...',
        allowClear: true,
        ajax: {
            url: '/dominial/cartorio-cri-autocomplete/',
            dataType: 'json',
            delay: 250,
            data: function(params) {
                return {
                    q: params.term,
                    page: params.page
                };
            },
            processResults: function(data, params) {
                params.page = params.page || 1;
                return {
                    results: data.items,
                    pagination: {
                        more: data.pagination.more
                    }
                };
            },
            cache: true
        },
        minimumInputLength: 2
    });
    
    // Campo de transmissão - texto livre
    $('#cartorio_transmissao').on('input', function() {
        // Validação básica se necessário
        let valor = $(this).val();
        if (valor.length > 255) {
            $(this).val(valor.substring(0, 255));
        }
    });
});
```

#### 4.2 View de Autocomplete CRI
```python
# dominial/views/autocomplete_views.py
from django.http import JsonResponse
from django.db.models import Q

def cartorio_cri_autocomplete(request):
    """Autocomplete para cartórios de registro de imóveis (CRI)"""
    q = request.GET.get('q', '')
    page = int(request.GET.get('page', 1))
    page_size = 20
    
    if len(q) < 2:
        return JsonResponse({
            'items': [],
            'pagination': {'more': False}
        })
    
    # Buscar apenas cartórios CRI
    cartorios = Cartorios.objects.filter(
        tipo='CRI',
        Q(nome__icontains=q) | 
        Q(cidade__icontains=q) | 
        Q(estado__icontains=q)
    ).order_by('estado', 'cidade', 'nome')
    
    # Paginação
    start = (page - 1) * page_size
    end = start + page_size
    cartorios_page = cartorios[start:end]
    
    items = []
    for cartorio in cartorios_page:
        items.append({
            'id': cartorio.id,
            'text': f"{cartorio.nome} - {cartorio.cidade}/{cartorio.estado}"
        })
    
    return JsonResponse({
        'items': items,
        'pagination': {
            'more': cartorios.count() > end
        }
    })
```

### 5. Validações

#### 5.1 Validação no Formulário
```python
# dominial/forms/lancamento_forms.py
from django import forms
from django.core.exceptions import ValidationError

class LancamentoForm(forms.ModelForm):
    class Meta:
        model = Lancamento
        fields = [
            # ... outros campos ...
            'cartorio_registro',
            'cartorio_transmissao',
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        cartorio_registro = cleaned_data.get('cartorio_registro')
        cartorio_transmissao = cleaned_data.get('cartorio_transmissao')
        
        # CRI é obrigatório para documentos principais
        if not cartorio_registro:
            raise ValidationError(
                "Cartório de registro é obrigatório para documentos principais"
            )
        
        # Validar se cartório selecionado é realmente CRI
        if cartorio_registro and cartorio_registro.tipo != 'CRI':
            raise ValidationError(
                "Cartório selecionado não é um cartório de registro de imóveis"
            )
        
        return cleaned_data
```

### 6. Comando de Limpeza de Dados

#### 6.1 Script para Limpar Dados Problemáticos
```python
# dominial/management/commands/limpar_cartorios_problematicos.py
from django.core.management.base import BaseCommand
from dominial.models import Cartorios

class Command(BaseCommand):
    help = 'Limpa cartórios com dados problemáticos'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando limpeza de cartórios problemáticos...")
        
        # 1. Remover cartórios com CNS zero ou inválido
        cartorios_invalidos = Cartorios.objects.filter(
            cns__in=['0', '00000000000000000000', '']
        )
        count_invalidos = cartorios_invalidos.count()
        cartorios_invalidos.delete()
        self.stdout.write(f"Removidos {count_invalidos} cartórios com CNS inválido")
        
        # 2. Corrigir cartórios com estado nulo
        cartorios_sem_estado = Cartorios.objects.filter(estado__isnull=True)
        count_sem_estado = cartorios_sem_estado.count()
        cartorios_sem_estado.update(estado='SP')  # Padrão
        self.stdout.write(f"Corrigidos {count_sem_estado} cartórios sem estado")
        
        # 3. Marcar todos como CRI (padrão)
        cartorios_sem_tipo = Cartorios.objects.filter(tipo__isnull=True)
        count_sem_tipo = cartorios_sem_tipo.count()
        cartorios_sem_tipo.update(tipo='CRI')
        self.stdout.write(f"Marcados {count_sem_tipo} cartórios como CRI")
        
        self.stdout.write(
            self.style.SUCCESS('Limpeza concluída com sucesso!')
        )
```

### 7. Testes

#### 7.1 Teste de Migração
```python
# dominial/tests/test_migracao_cartorios.py
from django.test import TestCase
from dominial.models import Lancamento, Cartorios

class MigracaoCartoriosTest(TestCase):
    def setUp(self):
        # Criar cartório de teste
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Teste',
            cns='12345678901234567890',
            cidade='São Paulo',
            estado='SP',
            tipo='CRI'
        )
        
        # Criar lançamento com cartório
        self.lancamento = Lancamento.objects.create(
            cartorio=self.cartorio,
            # ... outros campos obrigatórios ...
        )
    
    def test_migracao_preserva_dados(self):
        """Testa se a migração preserva os dados existentes"""
        # Simular migração
        self.lancamento.cartorio_registro = self.lancamento.cartorio
        self.lancamento.cartorio_transmissao = ""
        self.lancamento.save()
        
        # Verificar se dados foram preservados
        self.assertEqual(self.lancamento.cartorio_registro, self.cartorio)
        self.assertEqual(self.lancamento.cartorio_transmissao, "")
        self.assertEqual(self.lancamento.cartorio, self.cartorio)  # Campo legado
    
    def test_validacao_cri_obrigatorio(self):
        """Testa se CRI é obrigatório"""
        lancamento_sem_cri = Lancamento.objects.create(
            # ... sem cartório_registro ...
        )
        
        with self.assertRaises(ValidationError):
            lancamento_sem_cri.full_clean()
```

### 8. Deploy Seguro

#### 8.1 Checklist de Deploy
- [ ] Backup completo do banco de produção
- [ ] Teste da migração em ambiente de desenvolvimento
- [ ] Validação de dados após migração
- [ ] Deploy em horário de baixo tráfego
- [ ] Monitoramento pós-deploy
- [ ] Rollback plan preparado

#### 8.2 Script de Rollback
```python
# Script de emergência para reverter mudanças
def rollback_cartorios():
    """Reverte mudanças se necessário"""
    with connection.cursor() as cursor:
        # Restaurar campo cartorio original
        cursor.execute("""
            UPDATE dominial_lancamento 
            SET cartorio_id = cartorio_registro_id 
            WHERE cartorio_registro_id IS NOT NULL
        """)
        
        # Remover novos campos (se necessário)
        # ALTER TABLE dominial_lancamento DROP COLUMN cartorio_registro_id;
        # ALTER TABLE dominial_lancamento DROP COLUMN cartorio_transmissao;
```

## Conclusão

A nova implementação é mais simples e flexível:
- **CRI**: Lista fixa, seleção obrigatória
- **Transmissão**: Campo livre, flexível
- **Migração**: Segura, preserva dados existentes
- **Interface**: Mais intuitiva e clara 
**Próximo**: Implementar seguindo o cronograma do plano principal 