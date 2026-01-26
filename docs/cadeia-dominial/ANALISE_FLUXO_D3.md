# Análise do Fluxo D3 - Comparação Documentação vs Código Real

## Resumo Executivo

Este documento compara a documentação em `D3_CHAIN_VISUALIZATION_FLOW.md` com o código real do sistema para identificar discrepâncias e confirmar a origem dos dados.

## ✅ Fluxo Confirmado

### 1. URL Routing
**Documentação:** `dominial/urls.py:42`
**Código Real:** ✅ **CONFIRMADO**
```42:42:dominial/urls.py
    path('cadeia-dominial/<int:tis_id>/<int:imovel_id>/arvore/', cadeia_dominial_arvore, name='cadeia_dominial_arvore'),
```

### 2. Backend View
**Documentação:** `dominial/views/cadeia_dominial_views.py:58`
**Código Real:** ✅ **CONFIRMADO**
```58:75:dominial/views/cadeia_dominial_views.py
def cadeia_dominial_arvore(request, tis_id, imovel_id):
    """Retorna os dados da cadeia dominial em formato de árvore para o diagrama"""
    try:
        tis = get_object_or_404(TIs, id=tis_id)
        imovel = get_object_or_404(Imovel, id=imovel_id, terra_indigena_id=tis)
        # Delegar a construção da árvore para um service/utilitário
        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel, criar_documentos_automaticos=True)
        
        # Adicionar headers para evitar cache
        response = JsonResponse(arvore, safe=False)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
```

### 3. Service de Construção da Árvore
**Documentação:** `dominial/services/hierarquia_arvore_service.py`
**Código Real:** ✅ **CONFIRMADO**

O serviço `HierarquiaArvoreService.construir_arvore_cadeia_dominial()` retorna um dicionário Python que é convertido em JSON pela view.

### 4. Frontend JavaScript - Origem dos Dados

**Arquivo:** `static/dominial/js/cadeia_dominial_d3.js` (arquivo ativo usado pelo sistema)

#### 4.1. Fetch dos Dados
**Linha 111:** O JavaScript faz um fetch para a API:
```111:111:old/static/dominial/js/cadeia_dominial_d3.js
    fetch(`/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`)
```

**⚠️ DISCREPÂNCIA ENCONTRADA:**
- **Documentação diz:** `/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/`
- **Código real:** `/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/?t=${timestamp}`
  - O código adiciona um parâmetro `t` (timestamp) para evitar cache, mas isso não está documentado.

#### 4.2. Processamento dos Dados
**Linha 112-113:** A resposta JSON é processada:
```112:113:old/static/dominial/js/cadeia_dominial_d3.js
        .then(response => response.json())
        .then(data => {
```

**Linha 180:** O objeto `data` contém `data.documentos`:
```180:180:old/static/dominial/js/cadeia_dominial_d3.js
    console.log(`DEBUG: Iniciando conversão - Backend enviou ${data.documentos.length} documentos únicos`);
```

**Linha 184:** `data.documentos` é usado diretamente:
```184:187:old/static/dominial/js/cadeia_dominial_d3.js
    data.documentos.forEach(doc => {
        doc.children = [];
        docMap[doc.numero] = doc;
    });
```

**Linha 213:** `data.conexoes` também é usado:
```213:216:old/static/dominial/js/cadeia_dominial_d3.js
        const filhos = data.conexoes
            .filter(con => con.from === node.numero)
            .map(con => docMap[con.to])
            .filter(doc => doc);
```

## 📍 Origem dos Dados - Resposta Completa

### Estrutura JSON Retornada pela API

A view `cadeia_dominial_arvore` retorna um JSON com a seguinte estrutura:

```json
{
  "imovel": {
    "id": 1,
    "matricula": "6700",
    "nome": "Imóvel X",
    "proprietario": "Nome do Proprietário"
  },
  "documentos": [
    {
      "id": 1,
      "numero": "M6700",
      "tipo": "matricula",
      "tipo_display": "Matrícula",
      "tipo_documento": "matricula",
      "data": "15/03/2000",
      "cartorio": "Cartório de Registro X",
      "livro": "123",
      "folha": "45",
      "origem": "",
      "total_lancamentos": 3,
      "nivel": 0,
      "nivel_manual": null,
      "is_importado": false,
      "is_compartilhado": false,
      "is_fim_cadeia": false,
      "classificacao_fim_cadeia": null,
      "x": 0,
      "y": 0
    }
  ],
  "conexoes": [
    {
      "from": "M6700",
      "to": "M6500",
      "tipo": "origem_lancamento"
    }
  ],
  "origens_identificadas": []
}
```

### ❌ NÃO Existe Arquivo JSON Estático

**Conclusão:** Não há arquivo JSON estático. Todos os dados vêm dinamicamente da API Django através do endpoint `/dominial/cadeia-dominial/{tis_id}/{imovel_id}/arvore/`.

## 🔍 Discrepâncias Encontradas

### 1. Parâmetro de Cache no Fetch
- **Documentação:** Não menciona o parâmetro `?t=${timestamp}`
- **Código Real:** Usa timestamp para evitar cache
- **Impacto:** Baixo - funcionalidade adicional não documentada

### 2. Variáveis Globais no Template
**Documentação menciona:** `window.tisId` e `window.imovelId`
**Código Real:** ✅ **CONFIRMADO** em `templates/dominial/cadeia_dominial_d3.html:106-107`
```106:107:templates/dominial/cadeia_dominial_d3.html
    window.tisId = {{ tis.id|safe }};
    window.imovelId = {{ imovel.id|safe }};
```

### 3. Caminho do Arquivo JavaScript
**Documentação diz:** `static/dominial/js/cadeia_dominial_d3.js`
**Código Real:** ✅ **CONFIRMADO**
- **Arquivo ativo:** `static/dominial/js/cadeia_dominial_d3.js` (usado pelo template)
- **Arquivo antigo/backup:** `old/static/dominial/js/cadeia_dominial_d3.js` (versão antiga)
- **Template usa:** `{% static 'dominial/js/cadeia_dominial_d3.js' %}` → resolve para `static/dominial/js/cadeia_dominial_d3.js`

## 📋 Fluxo Completo Confirmado

```
1. Usuário acessa: /tis/{tis_id}/imovel/{imovel_id}/cadeia-dominial/
   ↓
2. Django renderiza template: templates/dominial/cadeia_dominial_d3.html
   ↓
3. Template define: window.tisId e window.imovelId
   ↓
4. JavaScript carrega: static/dominial/js/cadeia_dominial_d3.js
   ↓
5. DOMContentLoaded dispara fetch:
   GET /dominial/cadeia-dominial/{tis_id}/{imovel_id}/arvore/?t={timestamp}
   ↓
6. Django View: cadeia_dominial_arvore()
   ↓
7. Service: HierarquiaArvoreService.construir_arvore_cadeia_dominial()
   ↓
8. Retorna JSON: { documentos: [...], conexoes: [...], imovel: {...} }
   ↓
9. JavaScript: converterParaArvoreD3(data)
   - Processa data.documentos
   - Processa data.conexoes
   - Constrói árvore hierárquica
   ↓
10. JavaScript: renderArvoreD3(arvore, ...)
    - Usa D3.js para renderizar SVG
    - Aplica layout, cores, interações
```

## ✅ Validações

### Onde vem `data.documentos`?
**Resposta:** Vem da resposta JSON da API Django endpoint `/dominial/cadeia-dominial/{tis_id}/{imovel_id}/arvore/`, que é gerada pelo `HierarquiaArvoreService.construir_arvore_cadeia_dominial()`.

### Existe arquivo JSON estático?
**Resposta:** ❌ **NÃO**. Todos os dados são gerados dinamicamente pelo backend Django.

### A documentação está correta?
**Resposta:** ✅ **MAIORIA CORRETA**, com pequenas omissões:
- Não menciona o parâmetro `?t={timestamp}` no fetch para evitar cache
- O caminho do arquivo JS na documentação está correto (`static/dominial/js/cadeia_dominial_d3.js`)

## 🔧 Recomendações

1. **Atualizar documentação** para incluir o parâmetro `?t={timestamp}` no fetch para evitar cache
2. **Adicionar** na documentação a estrutura completa do JSON retornado pela API
3. **Documentar** o uso do timestamp para evitar cache no frontend
4. **Considerar** remover ou documentar o arquivo em `old/static/` como backup/versão antiga
