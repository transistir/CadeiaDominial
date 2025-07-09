# Detalhes Técnicos - Reformulação dos Cartórios

## 1. Modificações no Modelo

### 1.1 Migração do Modelo Cartorios
```python
# dominial/models/imovel_models.py
class Cartorios(models.Model):
    TIPO_CHOICES = [
        ('cri', 'Cartório de Registro de Imóveis (CRI)'),
        ('notas', 'Cartório de Notas'),
    ]
    
    nome = models.CharField(max_length=200)
    cns = models.CharField(max_length=20, unique=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='cri')
    endereco = models.CharField(max_length=200, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        tipo_display = self.get_tipo_display()
        if self.cidade and self.estado:
            return f"{self.nome} ({tipo_display}) - {self.cidade}/{self.estado}"
        return f"{self.nome} ({tipo_display})"

    class Meta:
        verbose_name = 'Cartório'
        verbose_name_plural = 'Cartórios'
        ordering = ['tipo', 'estado', 'cidade', 'nome']
```

### 1.2 Arquivo de Migração
```python
# dominial/migrations/XXXX_add_tipo_to_cartorios.py
from django.db import migrations, models

def classificar_cartorios_existentes(apps, schema_editor):
    Cartorios = apps.get_model('dominial', 'Cartorios')
    
    # Palavras-chave para classificação
    cri_keywords = ['imovel', 'imoveis', 'imóveis', 'imobiliario', 'imobiliária', 'Registro de Imóveis']
    notas_keywords = ['nota', 'notas', 'tabelionato', 'tabelião', 'ofício']
    
    for cartorio in Cartorios.objects.all():
        nome_lower = cartorio.nome.lower()
        
        # Classificar como CRI se contém palavras-chave de imóveis
        if any(keyword in nome_lower for keyword in cri_keywords):
            cartorio.tipo = 'cri'
        # Classificar como notas se contém palavras-chave de notas
        elif any(keyword in nome_lower for keyword in notas_keywords):
            cartorio.tipo = 'notas'
        # Padrão: CRI
        else:
            cartorio.tipo = 'cri'
        
        cartorio.save()

class Migration(migrations.Migration):
    dependencies = [
        ('dominial', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartorios',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('cri', 'Cartório de Registro de Imóveis (CRI)'),
                    ('notas', 'Cartório de Notas'),
                ],
                default='cri',
                max_length=10,
                verbose_name='Tipo'
            ),
        ),
        migrations.RunPython(classificar_cartorios_existentes),
    ]
```

## 2. CartorioService Centralizado

### 2.1 Implementação do Service
```python
# dominial/services/cartorio_service.py
from django.core.exceptions import ValidationError
from django.db import transaction
from ..models import Cartorios
import uuid

class CartorioService:
    """
    Service centralizado para operações com cartórios
    """
    
    @staticmethod
    def obter_cartorios_por_tipo(tipo):
        """
        Obtém cartórios por tipo (cri ou notas)
        
        Args:
            tipo (str): 'cri' ou 'notas'
            
        Returns:
            QuerySet: Cartórios do tipo especificado
        """
        if tipo not in ['cri', 'notas']:
            raise ValueError("Tipo deve ser 'cri' ou 'notas'")
        
        return Cartorios.objects.filter(tipo=tipo).order_by('estado', 'cidade', 'nome')
    
    @staticmethod
    def obter_cartorio_por_id(id, tipo=None):
        """
        Obtém cartório por ID com validação opcional de tipo
        
        Args:
            id (int): ID do cartório
            tipo (str, optional): Tipo esperado ('cri' ou 'notas')
            
        Returns:
            Cartorios: Instância do cartório
            
        Raises:
            Cartorios.DoesNotExist: Se cartório não encontrado
            ValidationError: Se tipo não corresponde ao esperado
        """
        try:
            cartorio = Cartorios.objects.get(id=id)
            
            if tipo and cartorio.tipo != tipo:
                raise ValidationError(f"Cartório deve ser do tipo {tipo}")
            
            return cartorio
        except Cartorios.DoesNotExist:
            raise ValidationError("Cartório não encontrado")
    
    @staticmethod
    @transaction.atomic
    def criar_cartorio_via_modal(dados):
        """
        Cria cartório via modal com validações
        
        Args:
            dados (dict): Dados do formulário
                - nome (str): Nome do cartório
                - tipo (str): 'cri' ou 'notas'
                - cidade (str, optional): Cidade
                - estado (str, optional): Estado
                - endereco (str, optional): Endereço
                - telefone (str, optional): Telefone
                - email (str, optional): Email
                
        Returns:
            Cartorios: Cartório criado
            
        Raises:
            ValidationError: Se dados inválidos
        """
        # Validações
        if not dados.get('nome'):
            raise ValidationError("Nome do cartório é obrigatório")
        
        if dados.get('tipo') not in ['cri', 'notas']:
            raise ValidationError("Tipo deve ser 'cri' ou 'notas'")
        
        # Verificar se já existe cartório com mesmo nome e tipo
        if Cartorios.objects.filter(nome__iexact=dados['nome'], tipo=dados['tipo']).exists():
            raise ValidationError(f"Já existe um cartório com o nome '{dados['nome']}' do tipo {dados['tipo']}")
        
        # Gerar CNS único
        cns_unico = f"CNS{str(uuid.uuid4().int)[:10]}"
        
        # Criar cartório
        cartorio = Cartorios.objects.create(
            nome=dados['nome'],
            tipo=dados['tipo'],
            cns=cns_unico,
            cidade=dados.get('cidade'),
            estado=dados.get('estado'),
            endereco=dados.get('endereco'),
            telefone=dados.get('telefone'),
            email=dados.get('email')
        )
        
        return cartorio
    
    @staticmethod
    def validar_cartorio_existente(nome, tipo):
        """
        Valida se cartório existe no tipo especificado
        
        Args:
            nome (str): Nome do cartório
            tipo (str): Tipo esperado
            
        Returns:
            bool: True se existe, False caso contrário
        """
        return Cartorios.objects.filter(nome__iexact=nome, tipo=tipo).exists()
    
    @staticmethod
    def processar_cartorio_request(request, campo_nome, tipo_cartorio):
        """
        Processa cartório a partir de dados do request
        
        Args:
            request: HttpRequest
            campo_nome (str): Nome do campo no POST
            tipo_cartorio (str): Tipo esperado do cartório
            
        Returns:
            Cartorios: Instância do cartório
            
        Raises:
            ValidationError: Se cartório inválido ou não fornecido
        """
        cartorio_id = request.POST.get(campo_nome)
        
        if not cartorio_id:
            raise ValidationError(f"Campo {campo_nome} é obrigatório")
        
        try:
            return CartorioService.obter_cartorio_por_id(cartorio_id, tipo_cartorio)
        except (Cartorios.DoesNotExist, ValidationError) as e:
            raise ValidationError(f"Cartório inválido: {str(e)}")
```

## 3. Views de Autocomplete Atualizadas

### 3.1 Novas Views
```python
# dominial/views/autocomplete_views.py
from django.http import JsonResponse
from ..models import Cartorios
from ..services.cartorio_service import CartorioService

def cartorio_cri_autocomplete(request):
    """View para autocomplete de cartórios de registro de imóveis (CRI)"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    cartorios = CartorioService.obter_cartorios_por_tipo('cri')\
        .filter(nome__icontains=query)\
        .values('id', 'nome', 'cidade', 'estado')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio['id'],
            'nome': cartorio['nome'],
            'cidade': cartorio['cidade'],
            'estado': cartorio['estado'],
            'tipo': 'cri'
        })
    
    return JsonResponse({'results': results})

def cartorio_notas_autocomplete(request):
    """View para autocomplete de cartórios de notas"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    cartorios = CartorioService.obter_cartorios_por_tipo('notas')\
        .filter(nome__icontains=query)\
        .values('id', 'nome', 'cidade', 'estado')[:10]
    
    results = []
    for cartorio in cartorios:
        results.append({
            'id': cartorio['id'],
            'nome': cartorio['nome'],
            'cidade': cartorio['cidade'],
            'estado': cartorio['estado'],
            'tipo': 'notas'
        })
    
    return JsonResponse({'results': results})

def cartorio_modal_cri(request):
    """View para criar novo cartório CRI via modal"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.POST.get('nome'),
                'tipo': 'cri',
                'cidade': request.POST.get('cidade'),
                'estado': request.POST.get('estado'),
                'endereco': request.POST.get('endereco'),
                'telefone': request.POST.get('telefone'),
                'email': request.POST.get('email')
            }
            
            cartorio = CartorioService.criar_cartorio_via_modal(dados)
            
            return JsonResponse({
                'success': True,
                'cartorio': {
                    'id': cartorio.id,
                    'nome': cartorio.nome,
                    'cidade': cartorio.cidade,
                    'estado': cartorio.estado,
                    'tipo': cartorio.tipo
                }
            })
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

def cartorio_modal_notas(request):
    """View para criar novo cartório de notas via modal"""
    if request.method == 'POST':
        try:
            dados = {
                'nome': request.POST.get('nome'),
                'tipo': 'notas',
                'cidade': request.POST.get('cidade'),
                'estado': request.POST.get('estado'),
                'endereco': request.POST.get('endereco'),
                'telefone': request.POST.get('telefone'),
                'email': request.POST.get('email')
            }
            
            cartorio = CartorioService.criar_cartorio_via_modal(dados)
            
            return JsonResponse({
                'success': True,
                'cartorio': {
                    'id': cartorio.id,
                    'nome': cartorio.nome,
                    'cidade': cartorio.cidade,
                    'estado': cartorio.estado,
                    'tipo': cartorio.tipo
                }
            })
        except ValidationError as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})
```

## 4. URLs Atualizadas

### 4.1 Novas URLs
```python
# dominial/urls.py
from .views.autocomplete_views import (
    cartorio_cri_autocomplete, 
    cartorio_notas_autocomplete,
    cartorio_modal_cri,
    cartorio_modal_notas
)

urlpatterns = [
    # ... outras URLs ...
    
    # Autocomplete de cartórios
    path('cartorio-cri-autocomplete/', cartorio_cri_autocomplete, name='cartorio-cri-autocomplete'),
    path('cartorio-notas-autocomplete/', cartorio_notas_autocomplete, name='cartorio-notas-autocomplete'),
    
    # Modais de criação
    path('cartorio-modal-cri/', cartorio_modal_cri, name='cartorio-modal-cri'),
    path('cartorio-modal-notas/', cartorio_modal_notas, name='cartorio-modal-notas'),
]
```

## 5. JavaScript Unificado

### 5.1 Service JavaScript
```javascript
// static/dominial/js/cartorio_service.js
class CartorioService {
    static async carregarCartorios(tipo, selectElement) {
        try {
            const response = await fetch(`/dominial/cartorio-${tipo}-autocomplete/?q=`);
            const data = await response.json();
            
            // Limpar opções existentes
            selectElement.innerHTML = '<option value="">Selecione um cartório...</option>';
            
            // Adicionar novas opções
            data.results.forEach(cartorio => {
                const option = document.createElement('option');
                option.value = cartorio.id;
                option.textContent = `${cartorio.nome}${cartorio.cidade ? ` - ${cartorio.cidade}/${cartorio.estado}` : ''}`;
                selectElement.appendChild(option);
            });
        } catch (error) {
            console.error('Erro ao carregar cartórios:', error);
        }
    }
    
    static abrirModalCartorio(tipo) {
        // Definir tipo no modal
        document.getElementById('tipo_cartorio').value = tipo;
        
        // Limpar formulário
        document.getElementById('cartorioForm').reset();
        
        // Abrir modal
        const modal = new bootstrap.Modal(document.getElementById('cartorioModal'));
        modal.show();
    }
    
    static async salvarCartorio() {
        const form = document.getElementById('cartorioForm');
        const formData = new FormData(form);
        
        try {
            const tipo = formData.get('tipo');
            const url = tipo === 'cri' ? '/dominial/cartorio-modal-cri/' : '/dominial/cartorio-modal-notas/';
            
            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Fechar modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('cartorioModal'));
                modal.hide();
                
                // Atualizar select correspondente
                const selectId = `cartorio_${tipo}`;
                const selectElement = document.getElementById(selectId);
                if (selectElement) {
                    await this.carregarCartorios(tipo, selectElement);
                    
                    // Selecionar o cartório criado
                    selectElement.value = data.cartorio.id;
                }
                
                // Mostrar mensagem de sucesso
                this.mostrarNotificacao('Cartório criado com sucesso!', 'success');
            } else {
                this.mostrarNotificacao(data.error, 'error');
            }
        } catch (error) {
            console.error('Erro ao salvar cartório:', error);
            this.mostrarNotificacao('Erro ao salvar cartório', 'error');
        }
    }
    
    static mostrarNotificacao(mensagem, tipo) {
        // Implementar notificação (pode usar toast ou alert)
        if (tipo === 'success') {
            alert(mensagem);
        } else {
            alert('Erro: ' + mensagem);
        }
    }
    
    static inicializarCamposCartorio() {
        // Inicializar todos os campos de cartório na página
        const cartorioFields = document.querySelectorAll('[data-cartorio-tipo]');
        
        cartorioFields.forEach(field => {
            const tipo = field.dataset.cartorioTipo;
            const selectId = field.id;
            
            // Carregar cartórios do tipo especificado
            this.carregarCartorios(tipo, field);
        });
    }
}

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    CartorioService.inicializarCamposCartorio();
});
```

## 6. Template do Modal

### 6.1 Modal Unificado
```html
<!-- templates/dominial/components/_cartorio_modal.html -->
<div class="modal fade" id="cartorioModal" tabindex="-1" aria-labelledby="cartorioModalLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="cartorioModalLabel">Novo Cartório</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
                <form id="cartorioForm">
                    {% csrf_token %}
                    <div class="form-group mb-3">
                        <label for="tipo_cartorio" class="form-label">Tipo *</label>
                        <select name="tipo" id="tipo_cartorio" class="form-select" required>
                            <option value="cri">Cartório de Registro de Imóveis (CRI)</option>
                            <option value="notas">Cartório de Notas</option>
                        </select>
                    </div>
                    <div class="form-group mb-3">
                        <label for="nome_cartorio" class="form-label">Nome *</label>
                        <input type="text" name="nome" id="nome_cartorio" class="form-control" required>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="form-group mb-3">
                                <label for="cidade_cartorio" class="form-label">Cidade</label>
                                <input type="text" name="cidade" id="cidade_cartorio" class="form-control">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="form-group mb-3">
                                <label for="estado_cartorio" class="form-label">Estado</label>
                                <input type="text" name="estado" id="estado_cartorio" class="form-control" maxlength="2">
                            </div>
                        </div>
                    </div>
                    <div class="form-group mb-3">
                        <label for="endereco_cartorio" class="form-label">Endereço</label>
                        <input type="text" name="endereco" id="endereco_cartorio" class="form-control">
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <div class="form-group mb-3">
                                <label for="telefone_cartorio" class="form-label">Telefone</label>
                                <input type="text" name="telefone" id="telefone_cartorio" class="form-control">
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="form-group mb-3">
                                <label for="email_cartorio" class="form-label">Email</label>
                                <input type="email" name="email" id="email_cartorio" class="form-control">
                            </div>
                        </div>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                <button type="button" class="btn btn-primary" onclick="CartorioService.salvarCartorio()">Salvar</button>
            </div>
        </div>
    </div>
</div>
```

## 7. Padrão de Campo de Cartório

### 7.1 Template Reutilizável
```html
<!-- templates/dominial/components/_cartorio_field.html -->
{% load static %}

<div class="form-group">
    <label for="{{ field_id }}">{{ label }}</label>
    <div class="cartorio-select-container">
        <select name="{{ field_name }}" id="{{ field_id }}" 
                class="form-select" 
                data-cartorio-tipo="{{ tipo_cartorio }}"
                {% if required %}required{% endif %}>
            <option value="">Selecione um cartório...</option>
        </select>
        <button type="button" class="btn btn-sm btn-outline-primary ms-2" 
                onclick="CartorioService.abrirModalCartorio('{{ tipo_cartorio }}')">
            + Novo
        </button>
    </div>
    {% if help_text %}
        <small class="form-text text-muted">{{ help_text }}</small>
    {% endif %}
</div>

<!-- Incluir modal se não estiver incluído -->
{% if not modal_included %}
    {% include "dominial/components/_cartorio_modal.html" %}
{% endif %}
```

## 8. Comandos de Importação Separados

### 8.1 Importação de CRI
```python
# dominial/management/commands/importar_cartorios_cri.py
from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import requests
import html

class Command(BaseCommand):
    help = 'Importa cartórios de registro de imóveis (CRI)'

    def add_arguments(self, parser):
        parser.add_argument('estado', type=str, help='Sigla do estado (ex: SP)')

    def handle(self, *args, **options):
        estado = options['estado'].upper()
        
        # URL da API do CNJ para cartórios de registro de imóveis
        url = f"https://www.cnj.jus.br/corregedoria/justica-estadual/{estado.lower()}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Processar dados e filtrar apenas CRI
            cartorios_cri = self.filtrar_cartorios_cri(response.json())
            
            for cartorio_data in cartorios_cri:
                self.criar_cartorio_cri(cartorio_data)
                
            self.stdout.write(
                self.style.SUCCESS(f'Importação concluída: {len(cartorios_cri)} CRI importados')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro na importação: {str(e)}')
            )
    
    def filtrar_cartorios_cri(self, dados):
        """Filtra apenas cartórios de registro de imóveis"""
        cri_keywords = ['imovel', 'imoveis', 'imóveis', 'imobiliario', 'imobiliária', 'Registro de Imóveis']
        
        cartorios_cri = []
        for cartorio in dados:
            nome = cartorio.get('nome_serventia', '').lower()
            if any(keyword in nome for keyword in cri_keywords):
                cartorios_cri.append(cartorio)
        
        return cartorios_cri
    
    def criar_cartorio_cri(self, dados):
        """Cria cartório CRI no banco"""
        nome = html.unescape(dados.get('nome_serventia', ''))
        
        if not nome:
            return
        
        # Verificar se já existe
        if Cartorios.objects.filter(nome__iexact=nome, tipo='cri').exists():
            return
        
        # Criar novo CRI
        Cartorios.objects.create(
            nome=nome,
            tipo='cri',
            cns=dados.get('cns', ''),
            cidade=dados.get('cidade', ''),
            estado=dados.get('estado', ''),
            endereco=dados.get('endereco', ''),
            telefone=dados.get('telefone', ''),
            email=dados.get('email', '')
        )
```

### 8.2 Importação de Cartórios de Notas
```python
# dominial/management/commands/importar_cartorios_notas.py
from django.core.management.base import BaseCommand
from dominial.models import Cartorios
import requests
import html

class Command(BaseCommand):
    help = 'Importa cartórios de notas'

    def add_arguments(self, parser):
        parser.add_argument('estado', type=str, help='Sigla do estado (ex: SP)')

    def handle(self, *args, **options):
        estado = options['estado'].upper()
        
        # URL da API do CNJ para cartórios de notas
        url = f"https://www.cnj.jus.br/corregedoria/justica-estadual/{estado.lower()}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            # Processar dados e filtrar apenas cartórios de notas
            cartorios_notas = self.filtrar_cartorios_notas(response.json())
            
            for cartorio_data in cartorios_notas:
                self.criar_cartorio_notas(cartorio_data)
                
            self.stdout.write(
                self.style.SUCCESS(f'Importação concluída: {len(cartorios_notas)} cartórios de notas importados')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro na importação: {str(e)}')
            )
    
    def filtrar_cartorios_notas(self, dados):
        """Filtra apenas cartórios de notas"""
        notas_keywords = ['nota', 'notas', 'tabelionato', 'tabelião', 'ofício']
        
        cartorios_notas = []
        for cartorio in dados:
            nome = cartorio.get('nome_serventia', '').lower()
            if any(keyword in nome for keyword in notas_keywords):
                cartorios_notas.append(cartorio)
        
        return cartorios_notas
    
    def criar_cartorio_notas(self, dados):
        """Cria cartório de notas no banco"""
        nome = html.unescape(dados.get('nome_serventia', ''))
        
        if not nome:
            return
        
        # Verificar se já existe
        if Cartorios.objects.filter(nome__iexact=nome, tipo='notas').exists():
            return
        
        # Criar novo cartório de notas
        Cartorios.objects.create(
            nome=nome,
            tipo='notas',
            cns=dados.get('cns', ''),
            cidade=dados.get('cidade', ''),
            estado=dados.get('estado', ''),
            endereco=dados.get('endereco', ''),
            telefone=dados.get('telefone', ''),
            email=dados.get('email', '')
        )
```

## 9. Testes

### 9.1 Testes Unitários
```python
# dominial/tests/test_cartorio_service.py
from django.test import TestCase
from django.core.exceptions import ValidationError
from ..models import Cartorios
from ..services.cartorio_service import CartorioService

class CartorioServiceTest(TestCase):
    def setUp(self):
        self.cartorio_cri = Cartorios.objects.create(
            nome='Cartório de Registro de Imóveis Teste',
            tipo='cri',
            cns='CNS123456',
            cidade='São Paulo',
            estado='SP'
        )
        
        self.cartorio_notas = Cartorios.objects.create(
            nome='Cartório de Notas Teste',
            tipo='notas',
            cns='CNS789012',
            cidade='São Paulo',
            estado='SP'
        )
    
    def test_obter_cartorios_por_tipo(self):
        cartorios_cri = CartorioService.obter_cartorios_por_tipo('cri')
        self.assertEqual(cartorios_cri.count(), 1)
        self.assertEqual(cartorios_cri.first(), self.cartorio_cri)
        
        cartorios_notas = CartorioService.obter_cartorios_por_tipo('notas')
        self.assertEqual(cartorios_notas.count(), 1)
        self.assertEqual(cartorios_notas.first(), self.cartorio_notas)
    
    def test_criar_cartorio_via_modal(self):
        dados = {
            'nome': 'Novo Cartório CRI',
            'tipo': 'cri',
            'cidade': 'Rio de Janeiro',
            'estado': 'RJ'
        }
        
        cartorio = CartorioService.criar_cartorio_via_modal(dados)
        self.assertEqual(cartorio.nome, 'Novo Cartório CRI')
        self.assertEqual(cartorio.tipo, 'cri')
        self.assertEqual(cartorio.cidade, 'Rio de Janeiro')
    
    def test_validar_cartorio_existente(self):
        self.assertTrue(
            CartorioService.validar_cartorio_existente('Cartório de Registro de Imóveis Teste', 'cri')
        )
        self.assertFalse(
            CartorioService.validar_cartorio_existente('Cartório Inexistente', 'cri')
        )
    
    def test_obter_cartorio_por_id(self):
        cartorio = CartorioService.obter_cartorio_por_id(self.cartorio_cri.id, 'cri')
        self.assertEqual(cartorio, self.cartorio_cri)
        
        with self.assertRaises(ValidationError):
            CartorioService.obter_cartorio_por_id(self.cartorio_cri.id, 'notas')
```

---

**Status**: Detalhes técnicos criados
**Próximo**: Implementar seguindo o cronograma do plano principal 