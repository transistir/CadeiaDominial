# Tipos de Lançamento em Documentos de Imóveis

Este documento descreve **todos os tipos de lançamento** disponíveis no sistema, suas particularidades, campos obrigatórios e como são registrados via formulário. Esta documentação complementa o documento principal sobre a árvore da cadeia dominial.

> **Base Legal:** As regras para matrículas, transcrições e lançamentos em documentos de imóveis são reguladas principalmente pela **Lei nº 6.015/1973 (Lei de Registros Públicos)**, que estabelece o sistema registral imobiliário nos cartórios de Registro de Imóveis.

---

## ⚠️ IMPORTANTE: Tipos de Documento vs Tipos de Lançamento

Antes de entender os tipos de lançamento, é fundamental compreender a diferença entre **tipos de documento** e **tipos de lançamento**:

### Tipos de Documento (DocumentoTipo)

O sistema trabalha com **dois tipos de documentos**:

| Tipo | Período | Características | Identificação |
|------|---------|-----------------|---------------|
| **Matrícula** | Pós-1973 | Registro unitário e permanente do imóvel, concentrando todo o histórico em um só número | Prefixo `M` (ex: `M12345`) |
| **Transcrição** | Pré-1973 | Regime anterior que registrava cada transmissão em livros separados, gerando novos números sem individualização plena | Prefixo `T` (ex: `T123`) |

**Modelo:** `old/dominial/models/documento_models.py`

```python
class DocumentoTipo(models.Model):
    TIPO_CHOICES = [
        ('transcricao', 'Transcrição'),
        ('matricula', 'Matrícula')
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
```

### Tipos de Lançamento (LancamentoTipo)

Dentro de **qualquer documento** (matrícula ou transcrição), podem ser registrados **três tipos de lançamentos**:

1. **Averbação** - Atualiza fatos sem alterar direitos reais
2. **Registro** - Cria/transfere direitos reais
3. **Início de Matrícula** - Abertura inicial do registro (vincula transcrição a matrícula)

### ⚠️ Confusão: "Transação" vs "Transcrição"

**IMPORTANTE:** No código existe uma nomenclatura confusa:

- **"Transcrição"** = Tipo de documento (pré-1973)
- **"Transação"** = Campos de transmissão (livro_transacao, folha_transacao, data_transacao, cartorio_transmissao)

Os **campos de transação** (na verdade, **campos de transmissão**) aparecem quando o documento é do tipo **transcrição**, porque no regime antigo cada transmissão era registrada em livros separados. Esses campos NÃO são um tipo de lançamento, mas sim campos adicionais que aparecem para documentos do tipo transcrição.

**Arquivo:** `old/dominial/services/lancamento_campos_service.py`

```python
# Verifica se o documento é do tipo transcrição
is_transcricao = lancamento.documento.tipo.tipo == 'transcricao'

# Se for transcrição, processa campos de transmissão
if is_transcricao:
    LancamentoCamposService._processar_campos_transacao(request, lancamento)
    # ↑ Este método processa: livro_transacao, folha_transacao, 
    #   data_transacao, cartorio_transmissao
```

**Resumo:**
- **Transcrição** = Tipo de documento (histórico, pré-1973)
- **Transação** = Campos de transmissão (só aparecem para documentos do tipo transcrição)

---

## 📋 Tipo de Documento: Transcrição (Detalhado)

### Conceito Legal e Histórico

A **Transcrição** é um tipo de documento do **regime anterior à Lei 6.015/1973**. No sistema antigo, cada transmissão de propriedade era registrada em **livros separados**, gerando novos números sem individualização plena do imóvel. Isso criava dificuldades para rastrear o histórico completo de um imóvel.

### Características da Transcrição

| Aspecto | Descrição |
|---------|-----------|
| **Período** | Pré-1973 (regime anterior) |
| **Identificação** | Prefixo `T` seguido de número (ex: `T123`, `T456`) |
| **Registro** | Cada transmissão em livro separado |
| **Individualização** | Não havia individualização plena do imóvel |
| **Conversão** | Pode ser convertida em matrícula via requerimento no cartório |

### Diferenças entre Transcrição e Matrícula

| Característica | Transcrição (Pré-1973) | Matrícula (Pós-1973) |
|----------------|------------------------|----------------------|
| **Registro** | Cada transmissão em livro separado | Registro unitário e permanente |
| **Número** | Novos números a cada transmissão | Um único número para todo o histórico |
| **Individualização** | Parcial | Completa |
| **Histórico** | Fragmentado em múltiplos registros | Concentrado em um só documento |
| **Identificação** | Prefixo `T` | Prefixo `M` |

### Campos Especiais para Transcrições

Quando um documento é do tipo **transcrição**, o sistema exibe campos adicionais de **transmissão** para todos os tipos de lançamento:

- `livro_transacao` - Livro onde foi registrada a transmissão
- `folha_transacao` - Folha onde foi registrada a transmissão
- `data_transacao` - Data da transmissão
- `cartorio_transmissao` - Cartório onde foi registrada a transmissão

**Por que esses campos existem?**

No regime de transcrições, cada transmissão era registrada em livros separados. Por isso, é necessário registrar em qual livro, folha e cartório cada transmissão ocorreu, diferente do regime de matrícula onde tudo fica concentrado em um único documento.

### Conversão de Transcrição em Matrícula

Uma transcrição pode ser convertida em matrícula através de requerimento no cartório da circunscrição, exigindo:

- Certidão atualizada de ônus (prazo máximo de 20-30 dias)
- Requerimento com firma reconhecida
- Certidão municipal

Após a conversão, o documento passa a ser do tipo **matrícula** e os campos de transmissão não são mais necessários.

### Implementação no Código

**Modelo:** `old/dominial/models/documento_models.py`

```python
class DocumentoTipo(models.Model):
    TIPO_CHOICES = [
        ('transcricao', 'Transcrição'),  # Regime pré-1973
        ('matricula', 'Matrícula')       # Regime pós-1973
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)

class Documento(models.Model):
    tipo = models.ForeignKey(DocumentoTipo, on_delete=models.PROTECT)
    # Se tipo.tipo == 'transcricao', o documento é uma transcrição
```

**Service:** `old/dominial/services/lancamento_campos_service.py`

```python
# Verifica se o documento é do tipo transcrição
is_transcricao = lancamento.documento.tipo.tipo == 'transcricao'

# Se for transcrição, processa campos de transmissão
if is_transcricao:
    LancamentoCamposService._processar_campos_transacao(request, lancamento)
```

**Frontend:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
// Verificar se o documento é do tipo transcrição
const isTranscricao = window.isTranscricao === true || 
                      documentoNumero.value.startsWith('T') ||
                      document.body.classList.contains('documento-transcricao');

// Se for transcrição, mostrar campos de transmissão
if (isTranscricao) {
    transacaoFields.classList.remove('hidden');
}
```

### Base Legal

- **Lei 6.015/1973:** Estabeleceu o sistema de matrícula, substituindo o regime de transcrições
- **Arts. 195-197:** Regulamentam a conversão de transcrições em matrículas
- **Art. 230:** Estabelece que ônus existentes devem ser averbados imediatamente na abertura da matrícula

---

## Visão Geral dos Tipos de Lançamento

O sistema suporta três tipos principais de lançamentos para documentos de imóveis (matrículas e transcrições):

| Tipo | Sigla | Finalidade | Base Legal |
|------|-------|------------|------------|
| **Averbação** | `AV{número} {matrícula}` | Atualiza/modifica fatos sem alterar direitos reais | Art. 167, II - Lei 6.015/73 |
| **Registro** | `R{número} {matrícula}` | Cria/transfere direitos reais | Art. 167, I - Lei 6.015/73 |
| **Início de Matrícula** | `{matrícula}` | Abertura inicial do registro | Arts. 176, 195-197 - Lei 6.015/73 |

---

## 1. Averbação

### Conceito Legal

A **Averbação** é um lançamento que atualiza fatos modificadores **sem alterar direitos reais**. É registrado à margem da matrícula e serve para documentar eventos que afetam o imóvel, mas não transferem propriedade ou criam direitos reais.

### Características

- **Sigla do lançamento:** `AV{número} {matrícula}`
  - Exemplo: `AV5 M12345` (Averbação número 5 da matrícula M12345)
- **Número do lançamento:** Obrigatório (campo numérico simples, ex: `5`)
- **Formato completo:** O sistema gera automaticamente `AV{número} {sigla_matrícula}`

### Campos Obrigatórios

| Campo | Tipo | Descrição | Validação |
|-------|------|-----------|-----------|
| `tipo` | Select | Tipo de lançamento (deve ser "Averbação") | Obrigatório |
| `data` | Date | Data do lançamento | Obrigatório |
| `descricao` | Text | Descrição detalhada do fato averbado | Obrigatório (mínimo de caracteres) |
| `numero_lancamento_simples` | Number | Número sequencial do lançamento (ex: 1, 5, 10) | Obrigatório |

### Campos Opcionais

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `transmitente` | Autocomplete (Pessoas) | Pessoa que transmite (se aplicável) |
| `adquirente` | Autocomplete (Pessoas) | Pessoa que adquire (se aplicável) |
| `observacoes` | Text | Observações adicionais |
| `forma` | Text | Forma do ato (ex: "Averbação de construção") |
| `area` | Decimal | Área relacionada ao fato averbado (em hectares, 4 casas decimais) |
| `origem` | Text | Referência a documento origem (se aplicável) |
| `cartorio_origem` | Select (Cartorios) | Cartório de origem (se aplicável) |

### Exemplos de Uso

**Averbações comuns:**

- 📋 **Construção/Demolição:** Averbação de edificação ou demolição no imóvel
- 📋 **Mudança de Nome:** Correção de nome do proprietário
- 📋 **Desmembramento:** Divisão do imóvel em lotes
- 📋 **Óbito:** Registro de falecimento do proprietário
- 📋 **Cancelamento de Ônus:** Cancelamento de hipoteca, penhora, etc.
- 📋 **Restrições:** Limitações de uso, servidões, etc.

### Implementação no Código

> **Nota (schema v2):** o CRI de origem passa a ficar em `origem.cri_id` e fim de cadeia em `origem_fim_cadeia`; `cartorio_origem_id` foi removido do lancamento.

**Modelo:** `old/dominial/models/lancamento_models.py`

```python
# Validação específica para averbação
if self.tipo.tipo == 'averbacao':
    if not self.tipo.requer_descricao:
        raise ValidationError("Averbações devem requerer descrição")
```

**Service:** `old/dominial/services/lancamento_campos_service.py`

```python
@staticmethod
def _processar_campos_averbacao(request, lancamento):
    # Processa forma, descrição, área, origem, cartório de origem
    lancamento.descricao = request.POST.get('descricao', '').strip()
    # ...
```

**Frontend:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
// Geração automática da sigla
if (selectedTipo === 'averbacao') {
    sigla = `AV${numero} ${siglaMatricula}`;
}
```

---

## 2. Registro

### Conceito Legal

O **Registro** é um lançamento que **cria, transmite ou extingue direitos reais** sobre o imóvel. É a inscrição principal no Livro nº 2 (Registro Geral) e exige título hábil (como escritura pública) para sua realização.

### Características

- **Sigla do lançamento:** `R{número} {matrícula}`
  - Exemplo: `R1 M12345` (Registro número 1 da matrícula M12345)
- **Número do lançamento:** Obrigatório (campo numérico simples, ex: `1`)
- **Formato completo:** O sistema gera automaticamente `R{número} {sigla_matrícula}`

### Campos Obrigatórios

| Campo | Tipo | Descrição | Validação |
|-------|------|-----------|-----------|
| `tipo` | Select | Tipo de lançamento (deve ser "Registro") | Obrigatório |
| `data` | Date | Data do registro | Obrigatório |
| `titulo` | Text | Tipo de título/documento (ex: "Compra e Venda", "Doação") | Obrigatório |
| `transmitente` | Autocomplete (Pessoas) | Pessoa(s) que transmite(m) o direito | Obrigatório (pelo menos 1) |
| `adquirente` | Autocomplete (Pessoas) | Pessoa(s) que adquire(m) o direito | Obrigatório (pelo menos 1) |
| `cartorio_transmissao` | Select (Cartorios) | Cartório onde foi registrada a transmissão | Obrigatório |
| `numero_lancamento_simples` | Number | Número sequencial do lançamento (ex: 1, 2, 3) | Obrigatório |

### Campos Opcionais

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valor_transacao` | Decimal | Valor da transação (10 dígitos, 2 decimais) |
| `area` | Decimal | Área do imóvel na transação (em hectares, 4 casas decimais) |
| `observacoes` | Text | Observações adicionais |
| `livro_transacao` | Text | Livro da transmissão (apenas para documentos do tipo transcrição) |
| `folha_transacao` | Text | Folha da transmissão (apenas para documentos do tipo transcrição) |
| `data_transacao` | Date | Data da transmissão (pode diferir da data do registro; apenas para transcrições) |
| `origem` | Text | Referência a documento origem (se aplicável) |
| `cartorio_origem` | Select (Cartorios) | Cartório de origem (se aplicável) |

### Exemplos de Uso

**Registros comuns:**

- 📋 **Compra e Venda:** Transferência de propriedade por compra
- 📋 **Doação:** Transferência gratuita de propriedade
- 📋 **Hipoteca:** Criação de direito real de garantia
- 📋 **Usucapião:** Aquisição de propriedade por posse prolongada
- 📋 **Servidão:** Criação de direito real sobre imóvel alheio
- 📋 **Herança:** Transferência por sucessão hereditária

### Implementação no Código

**Modelo:** `old/dominial/models/lancamento_models.py`

```python
# Validação específica para registro
if self.tipo == 'registro':
    if not self.tipo.requer_cartorio_origem:
        raise ValidationError("Registros devem requerer cartório de origem")
    if not self.tipo.requer_titulo:
        raise ValidationError("Registros devem requerer título")
```

**Service:** `old/dominial/services/lancamento_campos_service.py`

```python
@staticmethod
def _processar_campos_registro(request, lancamento):
    # Processa área, origem, cartório de origem
    # Transmitentes e adquirentes são processados separadamente via LancamentoPessoaService
    lancamento.area = float(area_value) if area_value else None
    # ...
```

**Frontend:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
// Geração automática da sigla
if (selectedTipo === 'registro') {
    sigla = `R${numero} ${siglaMatricula}`;
}
```

---

## 3. Início de Matrícula

### Conceito Legal

O **Início de Matrícula** é o lançamento que **abre o registro inicial** de um imóvel no sistema de matrícula (pós-1973). Este lançamento estabelece a origem do imóvel, vinculando-o a documentos anteriores (transcrições ou outras matrículas) e criando a base da cadeia dominial.

### Características

- **Sigla do lançamento:** `{matrícula}` (usa a sigla da matrícula diretamente, sem prefixo)
  - Exemplo: `M12345` (Início de matrícula da matrícula M12345)
- **Número do lançamento:** Não se aplica (o sistema usa a sigla da matrícula)
- **Múltiplas origens:** Permite informar várias origens separadas por ponto e vírgula (`;`)

### Campos Obrigatórios

| Campo | Tipo | Descrição | Validação |
|-------|------|-----------|-----------|
| `tipo` | Select | Tipo de lançamento (deve ser "Início de Matrícula") | Obrigatório |
| `data` | Date | Data do início de matrícula | Obrigatório |
| `cartorio_origem` | Select (Cartorios) | Cartório de origem do documento anterior | Obrigatório |
| `livro_origem` | Text | Livro de origem do documento anterior | Obrigatório |
| `folha_origem` | Text | Folha de origem do documento anterior | Obrigatório |
| `data_origem` | Date | Data do documento de origem | Obrigatório |
| `origem_completa[]` | Text (Array) | Uma ou mais origens (ex: "M50", "T20", "M30") | Obrigatório (pelo menos 1) |

### Campos Opcionais

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `transmitente` | Autocomplete (Pessoas) | Pessoa que transmite (se aplicável) |
| `adquirente` | Autocomplete (Pessoas) | Pessoa que adquire (se aplicável) |
| `forma` | Text | Forma do ato (ex: "Transcrição em Matrícula") |
| `titulo` | Text | Tipo de título/documento |
| `area` | Decimal | Área do imóvel (em hectares, 4 casas decimais) |
| `observacoes` | Text | Observações adicionais |
| `livro_transacao` | Text | Livro da transmissão (apenas para documentos do tipo transcrição) |
| `folha_transacao` | Text | Folha da transmissão (apenas para documentos do tipo transcrição) |
| `data_transacao` | Date | Data da transmissão (apenas para documentos do tipo transcrição) |

### Particularidades: Múltiplas Origens

O lançamento de "Início de Matrícula" permite informar **múltiplas origens**, cada uma com seu próprio cartório, livro e folha:

**Formato de entrada:**
```
Origem 1: M50 (Cartório: 1º CRI Salvador, Livro: 3, Folha: 45)
Origem 2: T20 (Cartório: 2º CRI Salvador, Livro: 5, Folha: 12)
Origem 3: M30 (Cartório: 1º CRI Salvador, Livro: 2, Folha: 30)
```

**Armazenamento:**
- As origens são concatenadas com ponto e vírgula: `M50; T20; M30`
- O sistema armazena o mapeamento de cartórios por origem em cache temporário
- Cada origem pode ter informações de "fim de cadeia" associadas

### Particularidades: Opções de Origem

O sistema deve exigir que o usuário escolha uma das opções de origem ao cadastrar um lançamento do tipo "Início de Matrícula":

#### Opções de Origem Disponíveis

| Opção | Descrição | Campos Obrigatórios | Continua a Cadeia? |
|-------|-----------|---------------------|-------------------|
| **a. Matrícula** | Origem é uma matrícula anterior | Número da matrícula + CRI | ✓ Sim - a cadeia continua |
| **b. Transcrição** | Origem é uma transcrição anterior | Número da transcrição + CRI | ✓ Sim - a cadeia continua |
| **c. Outra** | Outra situação (comumente sentença judicial) | Especificação detalhada (número de processo, Vara, data, etc.) | ✗ Não - fim de cadeia |
| **d. Destacamento do Patrimônio Público** | Origem é órgão público (INCRA, governo estadual, etc.) | Sigla do órgão (INCRA, Estado, etc.) | ✗ Não - fim de cadeia |
| **e. Registro** | Origem é um registro (não sempre CRI) | Número + Livro + Cartório | ✗ Não - fim de cadeia |
| **f. Sem Origem** | Não há origem documentada | Reprodução de fala da transcrição (opcional) | ✗ Não - fim de cadeia |

#### Regras de Continuidade da Cadeia

- **Opções a e b (Matrícula/Transcrição):** A cadeia **continua**. O sistema deve buscar/criar o documento de origem e permitir que a cadeia seja expandida recursivamente.
- **Opções c, d, e e f:** A cadeia **termina**. O sistema deve marcar como "fim de cadeia" e solicitar classificação.

#### Marcação Visual na Árvore

Quando a cadeia chega ao fim (opções c, d, e ou f), o sistema deve:
- Exibir uma **moldura ou marcação bem nítida** na árvore indicando que chegamos na origem (ou na falta dela)
- A marcação deve ser visualmente distinta para facilitar identificação

### Particularidades: Fim de Cadeia

Cada origem pode ser marcada como **"Fim de Cadeia"**, indicando que a cadeia dominial termina naquela origem. Quando marcado, são obrigatórios:

- `tipo_fim_cadeia`: Tipo do fim de cadeia
  - `destacamento_publico`: Destacamento do Patrimônio Público
  - `outra`: Outra situação
  - `sem_origem`: Sem Origem
- `classificacao_fim_cadeia`: Classificação do imóvel
  - `origem_lidima`: Imóvel com Origem Lídima
  - `sem_origem`: Imóvel sem Origem
  - `inconclusa`: Situação Inconclusa
- `especificacao_fim_cadeia`: Especificação (obrigatório se tipo = "outra")
- `sigla_patrimonio_publico`: Sigla do órgão (ex: "INCRA", "Estado")

#### Classificação Obrigatória no Fim de Cadeia

Quando a cadeia chega ao fim, o sistema **deve pedir** para marcar uma das opções de classificação:

- **Imóvel com origem lídima** (`origem_lidima`)
- **Imóvel sem origem** (`sem_origem`)
- **Situação inconclusa** (`inconclusa`)

**Visualização:**
- Se der para marcar isso na árvore, ótimo
- Se ficar ilegível, não tem problema, mas essa informação sobre a origem (lídima, sem origem ou inconclusa) será o principal
- Em algum lugar, precisa aparecer uma **lista de imóveis com essa condição**

> **📋 Documentação Complementar:** Para informações detalhadas sobre fim de cadeia, tipos, classificações e implementação, consulte o documento: [`fim-de-cadeia.md`](./fim-de-cadeia.md).

### Exemplos de Uso

**Início de Matrícula comum:**

- 🚀 **Primeiro registro pós-1973:** Abertura de matrícula para imóvel que estava em transcrição
- 🚀 **Conversão de transcrição:** Transformação de transcrição em matrícula
- 🚀 **Abertura com múltiplas origens:** Matrícula que deriva de várias matrículas/transcrições anteriores

### Implementação no Código

**Modelo:** `old/dominial/models/lancamento_models.py`

```python
# Validação específica para início de matrícula
if self.tipo and self.tipo.tipo == 'inicio_matricula':
    if not self.cartorio_origem:
        raise ValidationError("Cartório de origem é obrigatório para início de matrícula")
```

**Service:** `old/dominial/services/lancamento_campos_service.py`

```python
@staticmethod
def _processar_campos_inicio_matricula(request, lancamento):
    # Processa múltiplas origens
    origens_completas = request.POST.getlist('origem_completa[]')
    # Concatena com ponto e vírgula
    lancamento.origem = '; '.join(origens_validas)
    # Processa informações de fim de cadeia por origem
    # ...
```

**Frontend:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
// Para início de matrícula, usa a sigla da matrícula diretamente
if (selectedTipo === 'inicio_matricula') {
    numeroCompletoInput.value = siglaMatricula;
}
```

---

## Fluxo de Preenchimento do Formulário

### 1. Seleção do Tipo de Lançamento

O usuário seleciona o tipo de lançamento no campo `tipo_lancamento`. O formulário **mostra/oculta campos dinamicamente** baseado na seleção:

**Arquivo:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
function toggleFields() {
    const selectedTipo = tipoSelect.options[tipoSelect.selectedIndex].getAttribute('data-tipo');
    
    // Esconder todos os campos primeiro
    averbacaoFields.classList.add('hidden');
    registroFields.classList.add('hidden');
    inicioMatriculaFields.classList.add('hidden');
    
    // Mostrar campos específicos do tipo selecionado
    if (selectedTipo === 'averbacao') {
        averbacaoFields.classList.remove('hidden');
    } else if (selectedTipo === 'registro') {
        registroFields.classList.remove('hidden');
    } else if (selectedTipo === 'inicio_matricula') {
        inicioMatriculaFields.classList.remove('hidden');
    }
}
```

### 2. Geração Automática da Sigla

Para **Averbação** e **Registro**, o sistema gera automaticamente a sigla completa quando o usuário preenche o número:

**Arquivo:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
window.gerarNumeroLancamento = function() {
    const numero = numeroSimplesInput.value.trim();
    const selectedTipo = tipoSelect.options[tipoSelect.selectedIndex].getAttribute('data-tipo');
    const siglaMatricula = document.querySelector('input[name="sigla_matricula"]').value;
    
    if (selectedTipo === 'averbacao') {
        sigla = `AV${numero} ${siglaMatricula}`;
    } else if (selectedTipo === 'registro') {
        sigla = `R${numero} ${siglaMatricula}`;
    }
    
    numeroCompletoInput.value = sigla;
};
```

### 3. Validação de Campos Obrigatórios

O formulário valida campos obrigatórios antes do submit:

**Arquivo:** `staticfiles/dominial/js/lancamento_form.js`

```javascript
form.addEventListener('submit', function(e) {
    // Validar número simples para registro e averbação
    if ((selectedTipo === 'registro' || selectedTipo === 'averbacao') && !numeroSimplesValue) {
        alert('Para lançamentos do tipo "Registro" e "Averbação", é obrigatório preencher o campo "Número"');
        e.preventDefault();
        return false;
    }
    
    // Validar campos obrigatórios marcados com [required]
    const requiredFields = form.querySelectorAll('[required]');
    // ...
});
```

### 4. Processamento no Backend

Após o submit, o backend processa os campos específicos por tipo:

**Arquivo:** `old/dominial/services/lancamento_campos_service.py`

```python
@staticmethod
def processar_campos_por_tipo(request, lancamento):
    if lancamento.tipo.tipo == 'averbacao':
        LancamentoCamposService._processar_campos_averbacao(request, lancamento)
    elif lancamento.tipo.tipo == 'registro':
        LancamentoCamposService._processar_campos_registro(request, lancamento)
    elif lancamento.tipo.tipo == 'inicio_matricula':
        LancamentoCamposService._processar_campos_inicio_matricula(request, lancamento)
```

---

## Tabela Comparativa de Campos

> **⚠️ Nota:** Os campos `livro_transacao`, `folha_transacao` e `data_transacao` aparecem apenas quando o documento é do tipo **transcrição** (não quando é matrícula). Eles são campos de **transmissão** que existem por causa do regime antigo de transcrições.

| Campo | Averbação | Registro | Início de Matrícula |
|-------|-----------|---------|---------------------|
| **Obrigatórios** |
| `tipo` | ✓ | ✓ | ✓ |
| `data` | ✓ | ✓ | ✓ |
| `numero_lancamento_simples` | ✓ | ✓ | ✗ |
| `descricao` | ✓ | ✗ | ✗ |
| `titulo` | ✗ | ✓ | ✗ |
| `transmitente` | ✗ | ✓ | ✗ |
| `adquirente` | ✗ | ✓ | ✗ |
| `cartorio_transmissao` | ✗ | ✓ | ✗ |
| `cartorio_origem` | ✗ | ✗ | ✓ |
| `livro_origem` | ✗ | ✗ | ✓ |
| `folha_origem` | ✗ | ✗ | ✓ |
| `data_origem` | ✗ | ✗ | ✓ |
| `origem_completa[]` | ✗ | ✗ | ✓ |
| **Opcionais** |
| `transmitente` | ✓ | - | ✓ |
| `adquirente` | ✓ | - | ✓ |
| `observacoes` | ✓ | ✓ | ✓ |
| `area` | ✓ | ✓ | ✓ |
| `valor_transacao` | ✗ | ✓ | ✗ |
| `forma` | ✓ | ✗ | ✓ |
| `origem` | ✓ | ✓ | - |
| `livro_transacao` | ✗ | ✓* | ✓* |
| `folha_transacao` | ✗ | ✓* | ✓* |
| `data_transacao` | ✗ | ✓* | ✓* |

\* *Estes campos aparecem apenas quando o documento é do tipo **transcrição** (não para matrículas). São campos de transmissão do regime antigo.*

---

## Regras de Negócio Importantes

### 1. Numeração de Lançamentos

- **Averbação e Registro:** O número do lançamento é sequencial dentro do documento
  - Exemplo: Primeiro registro = `R1`, segundo registro = `R2`, primeira averbação = `AV1`
- **Início de Matrícula:** Não possui número próprio, usa a sigla da matrícula

### 2. Herança de Livro e Folha

Para **Início de Matrícula**, o sistema tenta **herdar livro e folha** do primeiro lançamento do documento de origem:

**Arquivo:** `old/dominial/services/lancamento_campos_service.py`

```python
# Primeiro, tentar herdar do primeiro lançamento do documento da origem
if cartorio_origem_encontrado and origens_validas:
    documento_origem = Documento.objects.filter(
        numero=numero_origem,
        cartorio=cartorio_origem_encontrado
    ).first()
    
    if documento_origem:
        primeiro_lancamento = documento_origem.lancamentos.order_by('id').first()
        if primeiro_lancamento:
            livro_origem_encontrado = primeiro_lancamento.livro_origem
            folha_origem_encontrada = primeiro_lancamento.folha_origem
```

### 3. Múltiplas Pessoas

Para **Registro**, o sistema permite múltiplas pessoas como transmitentes e adquirentes através do modelo `LancamentoPessoa`:

**Arquivo:** `old/dominial/models/lancamento_models.py`

```python
class LancamentoPessoa(models.Model):
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE)
    pessoa = models.ForeignKey('Pessoas', on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=[('transmitente', 'Transmitente'), ('adquirente', 'Adquirente')])
```

### 4. Campos de Transmissão (para Documentos do Tipo Transcrição)

> **⚠️ ATENÇÃO:** Esta seção trata de **campos de transmissão** que aparecem quando o documento é do tipo **transcrição** (não confundir com tipo de lançamento).

Para documentos do tipo **transcrição** (regime pré-1973), o sistema exibe campos adicionais de **transmissão** (`livro_transacao`, `folha_transacao`, `data_transacao`, `cartorio_transmissao`) para **todos os tipos de lançamento**. Isso ocorre porque no regime antigo de transcrições, cada transmissão era registrada em livros separados.

**Arquivo:** `old/dominial/services/lancamento_campos_service.py`

```python
# Verifica se o documento é do tipo transcrição
is_transcricao = lancamento.documento.tipo.tipo == 'transcricao'

if lancamento.tipo.tipo == 'averbacao':
    LancamentoCamposService._processar_campos_averbacao(request, lancamento)
    # Se for transcrição, também processa campos de transmissão
    if is_transcricao:
        LancamentoCamposService._processar_campos_transacao(request, lancamento)
        # ↑ Processa: livro_transacao, folha_transacao, data_transacao, 
        #   cartorio_transmissao
```

**Campos de Transmissão disponíveis para transcrições:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `livro_transacao` | Text | Livro onde foi registrada a transmissão |
| `folha_transacao` | Text | Folha onde foi registrada a transmissão |
| `data_transacao` | Date | Data da transmissão (pode diferir da data do lançamento) |
| `cartorio_transmissao` | Select (Cartorios) | Cartório onde foi registrada a transmissão |

**Nota:** A nomenclatura "transação" no código é tecnicamente incorreta - deveria ser "transmissão", mas foi mantida por questões de compatibilidade com código legado.

---

## Melhorias na Tela "Novo Lançamento"

Esta seção documenta as melhorias de interface e usabilidade solicitadas para a tela de criação de novos lançamentos.

### 1. Destaque da Matrícula

**Requisito:** A matrícula cujos lançamentos serão feitos deve estar em maior evidência na tela.

**Implementação sugerida:**
- Exibir a matrícula atual em um card destacado no topo do formulário
- Usar tipografia maior e cor de destaque
- Incluir informações básicas: número da matrícula, CRI, proprietário atual

### 2. Abolição de Livro e Folha em Lançamentos Repetidos

**Requisito:** Todos os lançamentos em uma matrícula terão o mesmo número de livro e página. O sistema deve herdar automaticamente esses valores do primeiro lançamento, poupando tempo do usuário.

**Regra de negócio:**
- Ao criar o primeiro lançamento de uma matrícula, o usuário preenche livro e folha
- Para lançamentos subsequentes, o sistema deve:
  - Herdar automaticamente livro e folha do primeiro lançamento da matrícula
  - Ocultar ou desabilitar os campos de livro e folha (ou torná-los opcionais apenas para correções)
  - Permitir edição apenas se necessário (casos excepcionais)

**Implementação sugerida:**
```python
# No service de lançamento
def obter_livro_folha_da_matricula(documento):
    primeiro_lancamento = documento.lancamentos.order_by('id').first()
    if primeiro_lancamento:
        return {
            'livro': primeiro_lancamento.livro,
            'folha': primeiro_lancamento.folha
        }
    return None
```

### 3. Campo de Área

**Requisito:** Inserir campo de área em todos os tipos de lançamento.

**Especificações:**
- Campo: `area` (Decimal)
- Formato: 4 casas decimais
- Unidade: Hectares
- Obrigatório: Não (opcional)

**Observação:** O campo de área já existe no modelo `Lancamento` e aparece como opcional em Averbação, Registro e Início de Matrícula. A validação de 4 casas decimais deve ser implementada no frontend e backend.

### 4. Visualização de Lançamentos Anteriores (Planilha)

**Requisito:** Visualizar as linhas de cima (lançamentos já feitos) na tela de novo lançamento, pois é na comparação que se percebem fraudes.

**Implementação sugerida:**
- Adicionar uma seção de "Lançamentos Anteriores" acima ou ao lado do formulário
- Exibir em formato de tabela/planilha:
  - Número do lançamento
  - Tipo (Averbação/Registro/Início de Matrícula)
  - Data
  - Descrição/Título
  - Transmitentes/Adquirentes
  - Área
  - Livro/Folha
- Permitir ordenação e filtros
- Destacar o último lançamento para referência

### 5. Troca de Nomenclatura: Cartório → Registro Imobiliário

**Requisito:** No campo "Informações Básicas da Matrícula/Transcrição", trocar "Cartório" por "Registro Imobiliário".

**Implementação:**
- Atualizar labels e textos de interface
- Manter a nomenclatura técnica no código (`cartorio`) para compatibilidade
- Atualizar documentação e mensagens de erro

### 6. Validação de Cartório (Registro Imobiliário) - Seleção Obrigatória

**Requisito:** No campo "Registro Imobiliário" (anteriormente "Cartório") no quadro "Informações Básicas da Matrícula/Transcrição", impedir que alguém digite algo e crie um cartório novo. O usuário deve obrigatoriamente selecionar um existente.

**Regra de negócio:**
- O campo deve ser um **select/autocomplete** que só permite seleção de cartórios existentes
- Não deve permitir criação de novos cartórios neste contexto
- A criação de novos cartórios deve ser feita em outra tela/fluxo administrativo

**Observação:** Em um momento futuro, pode-se pensar em um modo de adicionar cartório, pois sempre se criam novos.

### 7. Cartórios de Notas vs Cartórios de Registro de Imóveis

**Requisito:** No quadro "Transmissão", na opção de lançar registro, o usuário será obrigado a criar novos cartórios, mas esses cartórios (que são de notas) não podem entrar na lista dos cartórios de registro de imóveis.

**Regra de negócio:**
- Cartórios de **Registro de Imóveis** (CRI): usados em "Informações Básicas da Matrícula/Transcrição"
- Cartórios de **Notas** (Tabelionato): usados em "Transmissão" quando o lançamento é do tipo Registro
- Os dois tipos devem ser separados no sistema
- Cartórios de notas não devem aparecer na lista de seleção de cartórios de registro de imóveis

**Implementação sugerida:**
- Adicionar campo `tipo` ao modelo `Cartorio`:
  - `registro_imoveis` - Cartório de Registro de Imóveis (CRI)
  - `tabelionato` - Cartório de Notas
- Filtrar cartórios por tipo em cada contexto
- Permitir criação de cartórios de notas apenas no contexto de transmissão

### 8. Campos Opcionais de Transmitentes e Adquirentes em Averbação

**Requisito:** Quando o lançamento for Averbação, precisa ter opcionalmente os campos transmitentes e adquirentes.

**Status atual:** Os campos `transmitente` e `adquirente` já aparecem como opcionais para Averbação na tabela comparativa (linha 565-566). A implementação já permite isso através do modelo `LancamentoPessoa`.

**Validação necessária:** Garantir que o formulário de Averbação exiba esses campos como opcionais.

---

## Referências Legais

### Lei nº 6.015/1973 (Lei de Registros Públicos)

- **Art. 167, I:** Define **Registro** - cria, transmite ou extingue direitos reais
- **Art. 167, II:** Define **Averbação** - atualiza fatos modificadores sem alterar direitos reais
- **Arts. 176, 195-197:** Define **Início de Matrícula** - abertura inicial do registro

### Fontes Consultadas

- [Lei 6.015/73 - Planalto](https://www.planalto.gov.br/ccivil_03/leis/L6216.htm)
- [ANOREG-PR - Abertura de Matrícula](https://www.anoregpr.org.br/claves-notariais-registrais/abertura-de-matricula/)
- [Modelo Inicial - Direito Imobiliário](https://modeloinicial.com.br/materia/direito-imobiliario-averbacao)

---

## Arquivos Relacionados

### Modelos
- `old/dominial/models/lancamento_models.py` - Modelos `Lancamento`, `LancamentoTipo`, `LancamentoPessoa`

### Services
- `old/dominial/services/lancamento_campos_service.py` - Processamento de campos por tipo
- `old/dominial/services/lancamento_origem_service.py` - Processamento de origens
- `old/dominial/services/lancamento_validacao_service.py` - Validação de campos

### Frontend
- `staticfiles/dominial/js/lancamento_form.js` - Formulário dinâmico e validações
- `staticfiles/dominial/js/origem_simples.js` - Gerenciamento de múltiplas origens

### Documentação Relacionada
- `docs/cadeia-dominial/DESENHO_ARVORE_CADEIA_DOMINIAL.md` - Documentação sobre a árvore da cadeia dominial
- `docs/legacy-django/07-core-features-workflows.md` - Fluxos de trabalho do sistema
