# PLANEJAMENTO DE DESENVOLVIMENTO - VERIFICAÇÃO DE DUPLICATAS

## **Objetivo**
Implementar uma funcionalidade que detecta quando uma origem/cartório já existe em outra cadeia dominial e oferece ao usuário a opção de importar automaticamente o trecho da cadeia correspondente, mantendo total retrocompatibilidade com dados existentes.

## **Validação Obrigatória - Prevenção de Duplicatas**

### **Regra Fundamental**
O sistema **DEVE IMPEDIR** a criação de lançamentos com origem/cartório duplicados. Não é uma opção - é uma validação obrigatória.

### **Comportamento Quando Duplicata é Detectada**
1. **Formulário bloqueado** - não permite continuar com dados duplicados
2. **Modal de opções** - usuário pode:
   - **Importar** a cadeia dominial existente
   - **Cancelar** e alterar os dados
3. **Se cancelar**:
   - **Campos origem/cartório** destacados em vermelho
   - **Mensagem de erro**: "Origem/cartório já existe. Altere a origem ou o cartório para continuar."
   - **Botão salvar** desabilitado até dados válidos
   - **Usuário obrigado** a modificar origem ou cartório
4. **Única saída**: Importar a cadeia ou usar dados diferentes

## **Retrocompatibilidade - Plano de Produção**

### **1. Análise de Impacto**
- **Dados existentes**: Sistema em produção com dados históricos
- **Risco**: Nenhum - todas as modificações são aditivas
- **Rollback**: Possível a qualquer momento sem perda de dados

### **2. Estratégia de Migração**
- **Fase 1**: Deploy das estruturas de dados (sem quebrar funcionalidades)
- **Fase 2**: Deploy das funcionalidades (com feature flag)
- **Fase 3**: Ativação gradual da funcionalidade
- **Fase 4**: Monitoramento e ajustes

### **3. Scripts de Migração**
```sql
-- Script 1: Criar tabela de documentos importados
CREATE TABLE IF NOT EXISTS dominial_documentoimportado (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES dominial_documento(id),
    imovel_origem_id INTEGER NOT NULL REFERENCES dominial_imovel(id),
    data_importacao TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    importado_por_id INTEGER REFERENCES auth_user(id),
    UNIQUE(documento_id, imovel_origem_id)
);

-- Script 2: Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_documentoimportado_documento ON dominial_documentoimportado(documento_id);
CREATE INDEX IF NOT EXISTS idx_documentoimportado_imovel_origem ON dominial_documentoimportado(imovel_origem_id);
```

### **4. Feature Flag**
```python
# settings.py
DUPLICATA_VERIFICACAO_ENABLED = os.getenv('DUPLICATA_VERIFICACAO_ENABLED', 'false').lower() == 'true'
```

## **Estratégia de Desenvolvimento em Fases Incrementais**

### **FASE 1: Estrutura Base e Testes (Sem Modificar Funcionalidades Existentes)**

#### **1.1 Criação do Service de Verificação de Duplicatas**
- **Arquivo**: `dominial/services/duplicata_verificacao_service.py`
- **Responsabilidade**: Verificar se origem/cartório já existe em outras cadeias dominiais
- **Métodos principais**:
  - `verificar_duplicata_origem(origem, cartorio)`
  - `obter_cadeia_dominial_origem(documento_origem)`
  - `calcular_documentos_importaveis(documento_origem)`

#### **1.2 Criação do Service de Importação**
- **Arquivo**: `dominial/services/importacao_cadeia_service.py`
- **Responsabilidade**: Importar documentos de outras cadeias dominiais
- **Métodos principais**:
  - `importar_cadeia_dominial(imovel_destino, documento_origem, documentos_importaveis)`
  - `marcar_documento_importado(documento, imovel_origem)`

#### **1.3 Modelo para Rastreamento de Documentos Importados**
- **Arquivo**: `dominial/models/documento_importado_models.py`
- **Campos**:
  - `documento` (ForeignKey para Documento)
  - `imovel_origem` (ForeignKey para Imovel)
  - `data_importacao` (DateTimeField)
  - `importado_por` (ForeignKey para User)

#### **1.4 Testes Unitários**
- **Arquivo**: `dominial/tests/test_duplicata_verificacao.py`
- **Cenários de teste**:
  - Verificar duplicata existente
  - Verificar duplicata inexistente
  - Calcular documentos importáveis
  - Importar cadeia dominial
  - Validar integridade dos dados

### **FASE 2: API e Endpoints**

#### **2.1 API de Verificação**
- **Arquivo**: `dominial/views/api_duplicata_views.py`
- **Endpoints**:
  - `POST /api/verificar-duplicata/` - Verifica se origem/cartório existe
  - `POST /api/importar-cadeia/` - Importa cadeia dominial

#### **2.2 Validação e Segurança**
- **Validação**: Verificar permissões do usuário
- **Segurança**: CSRF protection, validação de dados
- **Logs**: Registrar todas as operações de importação

### **FASE 3: Interface do Usuário**

#### **3.1 Modal de Confirmação**
- **Arquivo**: `templates/dominial/components/_modal_duplicata.html`
- **Funcionalidades**:
  - Mostrar informações da duplicata encontrada
  - Listar documentos que serão importados
  - Botões de confirmação/cancelamento

#### **3.2 JavaScript para Interação**
- **Arquivo**: `static/dominial/js/duplicata_verificacao.js`
- **Funcionalidades**:
  - Detectar mudanças nos campos origem/cartório
  - Fazer requisição AJAX para verificar duplicata
  - Exibir modal com resultados
  - Processar confirmação de importação

#### **3.3 CSS para Estilização**
- **Arquivo**: `static/dominial/css/duplicata_verificacao.css`
- **Estilos**:
  - Modal responsivo
  - **Borda verde para documentos importados** (não cor de fundo)
  - Indicadores visuais sutis

### **FASE 4: Integração com Formulário Existente**

#### **4.1 Modificação do Formulário de Lançamento**
- **Arquivo**: `templates/dominial/lancamento_form.html`
- **Modificações mínimas**:
  - Adicionar IDs únicos aos campos origem/cartório
  - Incluir modal de duplicata
  - Incluir JavaScript de verificação

#### **4.2 Integração com Service de Criação**
- **Arquivo**: `dominial/services/lancamento_criacao_service.py`
- **Modificações**:
  - Adicionar verificação de duplicata antes da criação
  - Integrar com service de importação se necessário

### **FASE 5: Visualização e Indicadores**

#### **5.1 Modificação da Árvore da Cadeia Dominial**
- **Arquivo**: `static/dominial/js/cadeia_dominial_d3.js`
- **Modificações**:
  - **Adicionar borda verde para documentos importados** (preservar cores originais)
  - Tooltip indicando origem do documento

#### **5.2 Modificação da Tabela da Cadeia Dominial**
- **Arquivo**: `templates/dominial/cadeia_dominial_tabela.html`
- **Modificações**:
  - **Borda verde para documentos importados**
  - Coluna adicional com informação de origem

### **FASE 6: Otimizações e Melhorias**

#### **6.1 Performance**
- **Cache**: Implementar cache para verificações frequentes
- **Índices**: Adicionar índices no banco para consultas rápidas
- **Lazy loading**: Carregar dados de importação sob demanda

#### **6.2 Usabilidade**
- **Feedback visual**: Indicadores de progresso durante importação
- **Undo**: Possibilidade de desfazer importação
- **Histórico**: Log de todas as importações realizadas

## **Implementação Técnica Detalhada**

### **1. Estrutura de Dados**

```python
# dominial/models/documento_importado_models.py
class DocumentoImportado(models.Model):
    documento = models.ForeignKey('Documento', on_delete=models.CASCADE)
    imovel_origem = models.ForeignKey('Imovel', on_delete=models.CASCADE)
    data_importacao = models.DateTimeField(auto_now_add=True)
    importado_por = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    
    class Meta:
        verbose_name = "Documento Importado"
        verbose_name_plural = "Documentos Importados"
        unique_together = ('documento', 'imovel_origem')
        db_table = 'dominial_documentoimportado'

    def __str__(self):
        return f"Documento {self.documento.numero} importado de {self.imovel_origem.matricula}"
```

### **2. Service de Verificação**

```python
# dominial/services/duplicata_verificacao_service.py
from django.conf import settings
from ..models import Documento, DocumentoImportado

class DuplicataVerificacaoService:
    @staticmethod
    def verificar_duplicata_origem(origem, cartorio, imovel_atual):
        """
        Verifica se uma origem/cartório já existe em outras cadeias dominiais
        """
        if not settings.DUPLICATA_VERIFICACAO_ENABLED:
            return {'existe': False}
        
        # Buscar documento com mesmo número e cartório
        documento_existente = Documento.objects.filter(
            numero=origem,
            cartorio=cartorio
        ).exclude(imovel=imovel_atual).first()
        
        if documento_existente:
            documentos_importaveis = DuplicataVerificacaoService._calcular_documentos_importaveis(documento_existente)
            
            return {
                'existe': True,
                'documento': documento_existente,
                'imovel_origem': documento_existente.imovel,
                'documentos_importaveis': documentos_importaveis,
                'total_importaveis': len(documentos_importaveis)
            }
        
        return {'existe': False}
    
    @staticmethod
    def _calcular_documentos_importaveis(documento_origem):
        """
        Calcula quais documentos podem ser importados a partir de um documento de origem
        """
        # Implementar lógica para encontrar documentos na cadeia dominial
        # que se originam do documento_origem (para trás no tempo)
        pass
```

### **3. Service de Importação**

```python
# dominial/services/importacao_cadeia_service.py
from django.contrib.auth.models import User
from ..models import Documento, DocumentoImportado

class ImportacaoCadeiaService:
    @staticmethod
    def importar_cadeia_dominial(imovel_destino, documento_origem, documentos_importaveis, usuario):
        """
        Importa uma cadeia dominial para o imóvel de destino
        """
        documentos_importados = []
        
        for doc_importavel in documentos_importaveis:
            # Criar cópia do documento no imóvel de destino
            documento_importado = Documento.objects.create(
                imovel=imovel_destino,
                tipo=doc_importavel.tipo,
                numero=doc_importavel.numero,
                data=doc_importavel.data,
                cartorio=doc_importavel.cartorio,
                livro=doc_importavel.livro,
                folha=doc_importavel.folha,
                origem=doc_importavel.origem,
                observacoes=f"Importado de {doc_importavel.imovel.matricula} - {doc_importavel.imovel.nome}",
                cri_atual=doc_importavel.cri_atual,
                cri_origem=doc_importavel.cri_origem
            )
            
            # Marcar como importado
            DocumentoImportado.objects.create(
                documento=documento_importado,
                imovel_origem=doc_importavel.imovel,
                importado_por=usuario
            )
            
            documentos_importados.append(documento_importado)
        
        return documentos_importados
```

### **4. Interface JavaScript**

```javascript
// static/dominial/js/duplicata_verificacao.js
class DuplicataVerificacao {
    static async verificarOrigem(origem, cartorioId) {
        try {
            const response = await fetch('/api/verificar-duplicata/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ 
                    origem: origem, 
                    cartorio_id: cartorioId 
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('Erro ao verificar duplicata:', error);
            return { existe: false, erro: error.message };
        }
    }
    
    static mostrarModal(duplicata) {
        const modal = document.getElementById('modal-duplicata');
        const titulo = modal.querySelector('.modal-title');
        const corpo = modal.querySelector('.modal-body');
        const btnConfirmar = modal.querySelector('.btn-confirmar-importacao');
        
        titulo.textContent = `Duplicata Encontrada`;
        corpo.innerHTML = this.criarConteudoModal(duplicata);
        
        btnConfirmar.onclick = () => this.confirmarImportacao(duplicata);
        
        // Configurar botão cancelar
        const btnCancelar = modal.querySelector('.btn-cancelar-importacao');
        btnCancelar.onclick = () => this.cancelarImportacao();
        
        // Mostrar modal
        const bootstrapModal = new bootstrap.Modal(modal);
        bootstrapModal.show();
    }
    
    static criarConteudoModal(duplicata) {
        return `
            <div class="duplicata-info">
                <p><strong>Origem encontrada:</strong> ${duplicata.documento.numero}</p>
                <p><strong>Cartório:</strong> ${duplicata.documento.cartorio.nome}</p>
                <p><strong>Imóvel de origem:</strong> ${duplicata.imovel_origem.nome} (${duplicata.imovel_origem.matricula})</p>
                <p><strong>Documentos que serão importados:</strong> ${duplicata.total_importaveis}</p>
                
                <div class="documentos-importaveis">
                    <h6>Documentos da cadeia dominial:</h6>
                    <ul>
                        ${duplicata.documentos_importaveis.map(doc => 
                            `<li>${doc.tipo_display} ${doc.numero} - ${doc.cartorio}</li>`
                        ).join('')}
                    </ul>
                </div>
                
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    Os documentos importados serão marcados com uma borda verde para indicar que foram importados de outra cadeia dominial.
                </div>
            </div>
        `;
    }
    
    static async confirmarImportacao(duplicata) {
        try {
            const response = await fetch('/api/importar-cadeia/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    documento_origem_id: duplicata.documento.id,
                    documentos_importaveis_ids: duplicata.documentos_importaveis.map(d => d.id)
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const resultado = await response.json();
            
            if (resultado.sucesso) {
                // Fechar modal e recarregar página
                const modal = bootstrap.Modal.getInstance(document.getElementById('modal-duplicata'));
                modal.hide();
                
                // Mostrar mensagem de sucesso
                this.mostrarMensagemSucesso(`Importação realizada com sucesso! ${resultado.documentos_importados} documentos importados.`);
                
                // Recarregar página após 2 segundos
                setTimeout(() => window.location.reload(), 2000);
            } else {
                throw new Error(resultado.erro || 'Erro desconhecido na importação');
            }
        } catch (error) {
            console.error('Erro ao importar cadeia:', error);
            this.mostrarMensagemErro(`Erro na importação: ${error.message}`);
        }
    }
    
    static cancelarImportacao() {
        // Fechar modal
        const modal = bootstrap.Modal.getInstance(document.getElementById('modal-duplicata'));
        modal.hide();
        
        // Bloquear formulário
        this.bloquearFormularioDuplicata();
        
        // Mostrar mensagem de erro
        this.mostrarMensagemErro('Origem/cartório já existe. Altere a origem ou o cartório para continuar.');
    }
    
    static bloquearFormularioDuplicata() {
        // Destacar campos em vermelho
        const origemField = document.getElementById('origem_completa');
        const cartorioField = document.getElementById('cartorio_origem');
        const submitButton = document.querySelector('button[type="submit"]');
        
        if (origemField) {
            origemField.classList.add('is-invalid');
            origemField.style.borderColor = '#dc3545';
        }
        
        if (cartorioField) {
            cartorioField.classList.add('is-invalid');
            cartorioField.style.borderColor = '#dc3545';
        }
        
        // Desabilitar botão de salvar
        if (submitButton) {
            submitButton.disabled = true;
            submitButton.classList.add('btn-secondary');
            submitButton.classList.remove('btn-primary', 'btn-success');
        }
        
        // Adicionar mensagem de erro
        this.adicionarMensagemErro('Origem/cartório já existe. Altere a origem ou o cartório para continuar.');
    }
    
    static adicionarMensagemErro(mensagem) {
        // Remover mensagens de erro existentes
        const mensagensExistentes = document.querySelectorAll('.duplicata-error-message');
        mensagensExistentes.forEach(msg => msg.remove());
        
        // Criar nova mensagem de erro
        const errorDiv = document.createElement('div');
        errorDiv.className = 'alert alert-danger duplicata-error-message';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <strong>Erro:</strong> ${mensagem}
        `;
        
        // Inserir no início do formulário
        const form = document.querySelector('form');
        if (form) {
            form.insertBefore(errorDiv, form.firstChild);
        }
    }
    
    static getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    
    static mostrarMensagemSucesso(mensagem) {
        // Implementar toast ou alert de sucesso
    }
    
    static mostrarMensagemErro(mensagem) {
        // Implementar toast ou alert de erro
    }
}
```

### **5. CSS para Indicadores Visuais**

```css
/* static/dominial/css/duplicata_verificacao.css */

/* Modal de duplicata */
.modal-duplicata .modal-header {
    background: linear-gradient(135deg, #28a745, #20c997);
    color: white;
}

.modal-duplicata .modal-title {
    font-weight: 600;
}

.duplicata-info {
    padding: 15px 0;
}

.documentos-importaveis {
    margin-top: 15px;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 6px;
    border-left: 4px solid #28a745;
}

.documentos-importaveis ul {
    margin: 0;
    padding-left: 20px;
}

.documentos-importaveis li {
    margin: 5px 0;
    color: #495057;
}

/* Borda verde para documentos importados */
.documento-importado {
    border: 3px solid #28a745 !important;
    border-radius: 8px;
    position: relative;
}

.documento-importado::before {
    content: "📋 Importado";
    position: absolute;
    top: -10px;
    right: 10px;
    background: #28a745;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    z-index: 10;
}

/* Tooltip para documentos importados */
.documento-importado:hover::after {
    content: attr(data-origem);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 12px;
    white-space: nowrap;
    z-index: 1000;
}

/* Animação para documentos recém-importados */
.documento-importado-recem {
    animation: pulse-verde 2s ease-in-out;
}

@keyframes pulse-verde {
    0% { border-color: #28a745; }
    50% { border-color: #20c997; }
    100% { border-color: #28a745; }
}
```

## 🧪 **Estratégia de Testes**

### **1. Testes Unitários**
```python
# dominial/tests/test_duplicata_verificacao.py
from django.test import TestCase
from django.contrib.auth.models import User
from ..models import Imovel, Documento, Cartorios, DocumentoTipo
from ..services.duplicata_verificacao_service import DuplicataVerificacaoService
from ..services.importacao_cadeia_service import ImportacaoCadeiaService

class DuplicataVerificacaoTestCase(TestCase):
    def setUp(self):
        # Criar dados de teste
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.cartorio = Cartorios.objects.create(nome='Cartório Teste', cns='123456')
        self.tipo_doc = DocumentoTipo.objects.create(tipo='matricula')
        
        # Criar imóveis de teste
        self.imovel1 = Imovel.objects.create(
            matricula='123',
            nome='Imóvel 1',
            cartorio=self.cartorio
        )
        
        self.imovel2 = Imovel.objects.create(
            matricula='456',
            nome='Imóvel 2',
            cartorio=self.cartorio
        )
        
        # Criar documento no imóvel 1
        self.documento1 = Documento.objects.create(
            imovel=self.imovel1,
            tipo=self.tipo_doc,
            numero='DOC001',
            data='2024-01-01',
            cartorio=self.cartorio,
            livro='1',
            folha='1'
        )
    
    def test_verificar_duplicata_existente(self):
        """Testa verificação de duplicata existente"""
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            'DOC001', self.cartorio, self.imovel2
        )
        
        self.assertTrue(resultado['existe'])
        self.assertEqual(resultado['documento'], self.documento1)
        self.assertEqual(resultado['imovel_origem'], self.imovel1)
    
    def test_verificar_duplicata_inexistente(self):
        """Testa verificação de duplicata inexistente"""
        resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
            'DOC999', self.cartorio, self.imovel2
        )
        
        self.assertFalse(resultado['existe'])
    
    def test_importar_cadeia_dominial(self):
        """Testa importação de cadeia dominial"""
        documentos_importaveis = [self.documento1]
        
        documentos_importados = ImportacaoCadeiaService.importar_cadeia_dominial(
            self.imovel2, self.documento1, documentos_importaveis, self.user
        )
        
        self.assertEqual(len(documentos_importados), 1)
        self.assertEqual(documentos_importados[0].numero, 'DOC001')
        self.assertEqual(documentos_importados[0].imovel, self.imovel2)
```

### **2. Testes de Integração**
- Fluxo completo do formulário
- Interação com modal
- Importação e visualização

### **3. Testes de Performance**
- Verificação com grande volume de dados
- Cache de consultas
- Otimização de queries

## **Cronograma de Desenvolvimento**

### **Fase 1**
- Criar estrutura base
- Implementar services
- Criar testes unitários
- **Deploy**: Estruturas de dados (sem ativar funcionalidade)

### **Fase 2**
- Implementar APIs
- Criar endpoints
- Testar integração
- **Deploy**: APIs (com feature flag desabilitado)

### **Fase 3**
- Desenvolver interface
- Implementar modal
- Criar JavaScript
- **Deploy**: Interface (com feature flag desabilitado)

### **Fase 4**
- Integrar com formulário
- Testar fluxo completo
- Ajustes e correções
- **Deploy**: Integração completa (com feature flag desabilitado)

### **Fase 5**
- Modificar visualizações
- Implementar indicadores
- Testar interface
- **Deploy**: Visualizações (com feature flag desabilitado)

### **Fase 6**
- Otimizações
- Melhorias de UX
- Documentação
- **Deploy**: Ativação gradual da funcionalidade

## **Critérios de Sucesso**

1. **Funcionalidade**: Sistema detecta duplicatas corretamente
2. **Performance**: Verificação rápida (< 2 segundos)
3. **Usabilidade**: Interface intuitiva e responsiva
4. **Integridade**: Dados importados mantêm relações corretas
5. **Segurança**: Validações adequadas e logs de auditoria
6. **Compatibilidade**: Não interfere com funcionalidades existentes
7. **Retrocompatibilidade**: Funciona com dados existentes sem quebrar

## **Fluxo de Desenvolvimento Git**

1. **Branch principal**: `main` (sempre estável)
2. **Branch de desenvolvimento**: `develop`
3. **Branches de feature**: `feature/duplicata-verificacao-fase-1`
4. **Commits**: Seguir convenção de commits do projeto
5. **Pull Requests**: Revisão obrigatória antes do merge
6. **Testes**: Todos os testes devem passar antes do merge

## **Plano de Deploy em Produção**

### **Deploy Fase 1 (Estruturas)**
```bash
# 1. Backup do banco
pg_dump cadeia_dominial > backup_pre_duplicata_$(date +%Y%m%d_%H%M%S).sql

# 2. Deploy das migrações
python manage.py migrate

# 3. Verificar integridade
python manage.py check

# 4. Testar funcionalidades existentes
python manage.py test dominial.tests.test_lancamento
```

### **Deploy Fase 2 (Funcionalidades)**
```bash
# 1. Deploy do código
git pull origin main

# 2. Coletar arquivos estáticos
python manage.py collectstatic --noinput

# 3. Reiniciar serviços
sudo systemctl restart gunicorn
sudo systemctl restart nginx

# 4. Verificar logs
tail -f /var/log/gunicorn/error.log
```

### **Ativação Gradual**
```bash
# 1. Ativar para usuários de teste
export DUPLICATA_VERIFICACAO_ENABLED=true

# 2. Monitorar logs e performance
tail -f /var/log/duplicata_verificacao.log

# 3. Ativar para todos os usuários
# (após validação dos testes)
```

## **Métricas de Monitoramento**

### **Performance**
- Tempo de resposta da verificação de duplicatas
- Uso de memória e CPU
- Queries de banco de dados

### **Usabilidade**
- Taxa de uso da funcionalidade
- Taxa de sucesso na importação
- Feedback dos usuários

### **Integridade**
- Logs de auditoria
- Verificação de dados importados
- Backup automático antes de importações

## 🔧 **Comandos de Manutenção**

### **Verificar Status**
```bash
# Verificar se feature flag está ativo
python manage.py shell -c "from django.conf import settings; print(settings.DUPLICATA_VERIFICACAO_ENABLED)"

# Verificar documentos importados
python manage.py shell -c "from dominial.models import DocumentoImportado; print(DocumentoImportado.objects.count())"
```

### **Rollback**
```bash
# Desabilitar funcionalidade
export DUPLICATA_VERIFICACAO_ENABLED=false

# Reiniciar serviços
sudo systemctl restart gunicorn
```

Este planejamento garante uma implementação incremental, segura e bem testada, com total retrocompatibilidade e indicação visual adequada através de bordas verdes. 