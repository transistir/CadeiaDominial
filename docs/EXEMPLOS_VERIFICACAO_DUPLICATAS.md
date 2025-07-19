# 📝 EXEMPLOS PRÁTICOS - VERIFICAÇÃO DE DUPLICATAS

## 🎯 **Cenários de Uso**

### **Cenário 1: Usuário Descobre Duplicata Durante Lançamento**

#### **Situação**
- Usuário está criando um lançamento "Início de Matrícula"
- Preenche origem: "12345" e cartório: "Cartório Central"
- Sistema detecta que este documento já existe em outro imóvel

#### **Fluxo**
1. **Detecção**: Sistema verifica automaticamente
2. **Modal**: Aparece modal informando:
   ```
   📋 Duplicata Encontrada
   
   Origem encontrada: 12345
   Cartório: Cartório Central
   Imóvel de origem: Fazenda Santa Maria (MAT-001)
   Documentos que serão importados: 3
   
   Documentos da cadeia dominial:
   • Matrícula 12345 - Cartório Central
   • Transcrição 67890 - Cartório Central  
   • Transcrição 11111 - Cartório Central
   
   ⓘ Os documentos importados serão marcados com uma borda verde.
   ```

3. **Ação do Usuário**: Clica em "Importar Cadeia"
4. **Resultado**: 3 documentos são importados com borda verde

### **Cenário 2: Múltiplas Origens com Duplicatas**

#### **Situação**
- Usuário preenche múltiplas origens:
  - Origem 1: "12345" + Cartório A
  - Origem 2: "67890" + Cartório B
- Ambas existem em cadeias dominiais diferentes

#### **Fluxo**
1. **Verificação**: Sistema verifica cada origem individualmente
2. **Modal**: Mostra todas as duplicatas encontradas
3. **Importação**: Usuário pode importar uma ou ambas as cadeias
4. **Resultado**: Documentos importados mantêm suas relações originais

### **Cenário 3: Usuário Cancela Importação**

#### **Situação**
- Sistema detecta duplicata
- Usuário decide não importar

#### **Fluxo**
1. **Modal**: Aparece com opções
2. **Ação**: Usuário clica em "Cancelar"
3. **Resultado**: 
   - **Formulário é bloqueado** - não permite continuar com a origem/cartório duplicado
   - **Mensagem de erro** é exibida: "Origem/cartório já existe. Altere a origem ou o cartório para continuar."
   - **Campos origem e cartório** são destacados em vermelho
   - **Botão de salvar** fica desabilitado até que o usuário altere os dados
   - **Usuário deve** escolher uma origem diferente ou um cartório diferente
4. **Ação obrigatória**: Usuário precisa modificar origem ou cartório para prosseguir

## 🔧 **Exemplos de Código**

### **1. Verificação de Duplicata**

```python
# Exemplo de uso do service
from dominial.services.duplicata_verificacao_service import DuplicataVerificacaoService

# Verificar se origem/cartório já existe
resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
    origem="12345",
    cartorio=cartorio_objeto,
    imovel_atual=imovel_atual
)

if resultado['existe']:
    print(f"Duplicata encontrada no imóvel: {resultado['imovel_origem'].nome}")
    print(f"Documentos importáveis: {resultado['total_importaveis']}")
else:
    print("Nenhuma duplicata encontrada")
```

### **2. Importação de Cadeia**

```python
# Exemplo de importação
from dominial.services.importacao_cadeia_service import ImportacaoCadeiaService

# Importar cadeia dominial
documentos_importados = ImportacaoCadeiaService.importar_cadeia_dominial(
    imovel_destino=imovel_atual,
    documento_origem=documento_duplicado,
    documentos_importaveis=documentos_para_importar,
    usuario=request.user
)

print(f"Importados {len(documentos_importados)} documentos")
```

### **3. Verificação via JavaScript**

```javascript
// Exemplo de verificação no frontend
async function verificarOrigemNoFormulario() {
    const origem = document.getElementById('origem_completa').value;
    const cartorioId = document.getElementById('cartorio_origem').value;
    
    if (origem && cartorioId) {
        const resultado = await DuplicataVerificacao.verificarOrigem(origem, cartorioId);
        
        if (resultado.existe) {
            DuplicataVerificacao.mostrarModal(resultado);
        }
    }
}

// Adicionar listener aos campos
document.getElementById('origem_completa').addEventListener('blur', verificarOrigemNoFormulario);
document.getElementById('cartorio_origem').addEventListener('change', verificarOrigemNoFormulario);
```

### **4. API de Verificação**

```bash
# Exemplo de requisição para a API
curl -X POST http://localhost:8000/api/verificar-duplicata/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: seu_token_aqui" \
  -d '{
    "origem": "12345",
    "cartorio_id": 1
  }'

# Resposta esperada
{
  "existe": true,
  "documento": {
    "id": 123,
    "numero": "12345",
    "tipo": "matricula",
    "cartorio": "Cartório Central"
  },
  "imovel_origem": {
    "id": 456,
    "nome": "Fazenda Santa Maria",
    "matricula": "MAT-001"
  },
  "documentos_importaveis": [
    {
      "id": 123,
      "numero": "12345",
      "tipo": "matricula",
      "cartorio": "Cartório Central"
    },
    {
      "id": 124,
      "numero": "67890", 
      "tipo": "transcricao",
      "cartorio": "Cartório Central"
    }
  ],
  "total_importaveis": 2
}
```

### **5. API de Importação**

```bash
# Exemplo de requisição para importar
curl -X POST http://localhost:8000/api/importar-cadeia/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: seu_token_aqui" \
  -d '{
    "documento_origem_id": 123,
    "documentos_importaveis_ids": [123, 124]
  }'

# Resposta esperada
{
  "sucesso": true,
  "documentos_importados": 2,
  "mensagem": "Cadeia dominial importada com sucesso"
}
```

## 🎨 **Exemplos de Interface**

### **1. Modal de Confirmação**

```html
<!-- Exemplo do modal -->
<div class="modal fade" id="modal-duplicata" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">📋 Duplicata Encontrada</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="duplicata-info">
          <p><strong>Origem encontrada:</strong> 12345</p>
          <p><strong>Cartório:</strong> Cartório Central</p>
          <p><strong>Imóvel de origem:</strong> Fazenda Santa Maria (MAT-001)</p>
          
          <div class="documentos-importaveis">
            <h6>Documentos da cadeia dominial:</h6>
            <ul>
              <li>Matrícula 12345 - Cartório Central</li>
              <li>Transcrição 67890 - Cartório Central</li>
            </ul>
          </div>
          
          <div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
            Os documentos importados serão marcados com uma borda verde.
          </div>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary btn-cancelar-importacao">
          <i class="fas fa-times"></i> Cancelar e Alterar Dados
        </button>
        <button type="button" class="btn btn-success btn-confirmar-importacao">
          <i class="fas fa-download"></i> Importar Cadeia
        </button>
      </div>
    </div>
  </div>
</div>
```

### **2. Documento com Borda Verde**

```css
/* Exemplo de CSS para documento importado */
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
```

### **3. Tooltip de Origem**

```html
<!-- Exemplo de tooltip -->
<div class="documento-card documento-importado" 
     data-origem="Importado de: Fazenda Santa Maria (MAT-001)">
  <h4>Matrícula 12345</h4>
  <p>Cartório Central</p>
  <!-- ... resto do conteúdo ... -->
</div>
```

## 📊 **Exemplos de Dados**

### **1. Estrutura de Resposta da API**

```json
{
  "existe": true,
  "documento": {
    "id": 123,
    "numero": "12345",
    "tipo": "matricula",
    "tipo_display": "Matrícula",
    "data": "01/01/2020",
    "cartorio": "Cartório Central",
    "livro": "1",
    "folha": "1"
  },
  "imovel_origem": {
    "id": 456,
    "nome": "Fazenda Santa Maria",
    "matricula": "MAT-001",
    "proprietario": "João Silva"
  },
  "documentos_importaveis": [
    {
      "id": 123,
      "numero": "12345",
      "tipo": "matricula",
      "tipo_display": "Matrícula",
      "cartorio": "Cartório Central",
      "data": "01/01/2020"
    },
    {
      "id": 124,
      "numero": "67890",
      "tipo": "transcricao", 
      "tipo_display": "Transcrição",
      "cartorio": "Cartório Central",
      "data": "15/03/2020"
    }
  ],
  "total_importaveis": 2
}
```

### **2. Log de Importação**

```python
# Exemplo de log gerado
{
  "timestamp": "2024-01-15T10:30:00Z",
  "usuario": "joao.silva",
  "acao": "importar_cadeia_dominial",
  "imovel_destino": "Fazenda Nova (MAT-002)",
  "imovel_origem": "Fazenda Santa Maria (MAT-001)",
  "documentos_importados": [
    {"id": 789, "numero": "12345", "tipo": "matricula"},
    {"id": 790, "numero": "67890", "tipo": "transcricao"}
  ],
  "total_importados": 2
}
```

## 🧪 **Exemplos de Testes**

### **1. Teste de Verificação**

```python
def test_verificar_duplicata_existente(self):
    """Testa verificação de duplicata existente"""
    # Criar documento em outro imóvel
    documento_outro = Documento.objects.create(
        imovel=self.imovel2,
        tipo=self.tipo_doc,
        numero='DOC001',
        cartorio=self.cartorio
    )
    
    # Verificar duplicata
    resultado = DuplicataVerificacaoService.verificar_duplicata_origem(
        'DOC001', self.cartorio, self.imovel1
    )
    
    self.assertTrue(resultado['existe'])
    self.assertEqual(resultado['documento'], documento_outro)
    self.assertEqual(resultado['imovel_origem'], self.imovel2)
```

### **2. Teste de Importação**

```python
def test_importar_cadeia_dominial(self):
    """Testa importação de cadeia dominial"""
    # Criar documentos na origem
    doc1 = Documento.objects.create(
        imovel=self.imovel1,
        numero='DOC001',
        cartorio=self.cartorio
    )
    
    doc2 = Documento.objects.create(
        imovel=self.imovel1,
        numero='DOC002',
        cartorio=self.cartorio
    )
    
    # Importar cadeia
    documentos_importados = ImportacaoCadeiaService.importar_cadeia_dominial(
        self.imovel2, doc1, [doc1, doc2], self.user
    )
    
    self.assertEqual(len(documentos_importados), 2)
    self.assertTrue(all(doc.imovel == self.imovel2 for doc in documentos_importados))
```

## 🎯 **Casos de Borda**

### **1. Documento Já Importado**

```python
# Verificar se documento já foi importado
def verificar_ja_importado(documento, imovel_destino):
    return DocumentoImportado.objects.filter(
        documento=documento,
        imovel_origem=documento.imovel
    ).exists()
```

### **2. Múltiplas Importações**

```python
# Permitir múltiplas importações do mesmo documento
def importar_multiplas_vezes(documento, imoveis_destino):
    for imovel_destino in imoveis_destino:
        ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino, documento, [documento], usuario
        )
```

### **3. Rollback de Importação**

```python
# Desfazer importação
def desfazer_importacao(documento_importado, usuario):
    # Remover documento importado
    documento_importado.delete()
    
    # Remover registro de importação
    DocumentoImportado.objects.filter(
        documento=documento_importado
    ).delete()
    
    # Log da ação
    logger.info(f"Importação desfeita por {usuario}")
```

Estes exemplos fornecem uma visão prática de como a funcionalidade funcionará em diferentes cenários, facilitando o desenvolvimento e testes. 