# Fim de Cadeia Dominial

Este documento descreve o conceito de **"Fim de Cadeia"** no sistema de cadeia dominial, suas classificações, tipos e como é implementado no código.

> **Contexto:** Na cadeia dominial, quando rastreamos a origem de um imóvel, eventualmente chegamos a um ponto onde não há mais documentos anteriores ou onde a origem não pode ser rastreada. Esse ponto é chamado de "fim de cadeia".

---

## Conceito de Fim de Cadeia

### Definição

**Fim de Cadeia** é o ponto na cadeia dominial onde não há mais documentos anteriores para rastrear, ou onde a origem do imóvel não pode ser determinada através de documentos registrais tradicionais.

### Quando a Cadeia Termina?

A cadeia dominial termina quando a origem do lançamento é uma das seguintes opções:

1. **Outra** - Situações especiais (sentença judicial, processo, etc.)
2. **Destacamento do Patrimônio Público** - Origem em órgão público (INCRA, Estado, União, etc.)
3. **Registro** - Origem em registro que não é CRI (cartório de notas)
4. **Sem Origem** - Não há origem documentada

> **Nota:** Se a origem for **Matrícula** ou **Transcrição**, a cadeia **continua** e o sistema deve buscar/criar o documento de origem para expandir a árvore.

---

## Modelos de Dados

> **Nota (schema v2):** fim de cadeia e indicado por `origem.tipo = 'fim_cadeia'` e os detalhes ficam em `origem_fim_cadeia`.

### 1. OrigemFimCadeia (schema consolidado v2)

Armazena informações de fim de cadeia **por origem individual** quando um lançamento possui múltiplas origens.

**Campos:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `origem` | FK (Origem) | Origem a que estes dados pertencem |
| `tipo_fim_cadeia` | Text | Tipo do fim de cadeia (ver tipos abaixo) |
| `especificacao_fim_cadeia` | Text | Especificação quando tipo = "outra" |
| `classificacao_fim_cadeia` | Text | Classificação do imóvel (ver classificações abaixo) |
| `sigla_patrimonio_publico` | Text | Sigla do órgão quando tipo = "destacamento_publico" |

**Constraints:**
- `origem_id` único (1:1 com `origem`)

**Validações:**
- Se `origem.tipo = 'fim_cadeia'`, então `origem_fim_cadeia` é obrigatório
- Se `tipo_fim_cadeia = 'outra'`, então `especificacao_fim_cadeia` é obrigatório
- Se `tipo_fim_cadeia = 'destacamento_publico'`, então `sigla_patrimonio_publico` é obrigatório

### 2. FimCadeia (legado)

**Arquivo:** `old/dominial/models/lancamento_models.py:204`

Tabela de catalogo **legada** (removida no schema consolidado v2). Os dados relevantes agora vivem em `origem_fim_cadeia`.

**Campos:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `nome` | CharField | Nome do fim de cadeia (ex: "Estado da Bahia", "INCRA") |
| `tipo` | CharField | Tipo: `destacamento_publico`, `outra`, `sem_origem` |
| `classificacao` | CharField | Classificação: `origem_lidima`, `sem_origem`, `inconclusa` |
| `sigla` | CharField | Sigla do órgão (ex: "INCRA", "SPU") |
| `descricao` | TextField | Descrição detalhada |
| `ativo` | Boolean | Se está ativo |

**Métodos:**
- `get_cor_css()` - Retorna cor CSS baseada na classificação
- `get_cor_borda_css()` - Retorna cor da borda CSS

---

## Tipos de Fim de Cadeia

### 1. Destacamento do Patrimônio Público

**Valor:** `destacamento_publico`

**Descrição:** A origem do imóvel é um órgão público que gerencia terras públicas.

**Exemplos:**
- INCRA (Instituto Nacional de Colonização e Reforma Agrária)
- Estados (governos estaduais)
- União (SPU - Secretaria do Patrimônio da União)
- Municípios

**Campos adicionais obrigatórios:**
- `sigla_patrimonio_publico` - Sigla do órgão (ex: "INCRA", "Estado", "SPU")

**Formato de armazenamento:**
```
Destacamento Público:Sigla:Classificação
Exemplo: Destacamento Público:INCRA:origem_lidima
```

### 2. Outra

**Valor:** `outra`

**Descrição:** Situações especiais que não se enquadram nas outras categorias. Comumente usado para sentenças judiciais.

**Exemplos:**
- Sentença judicial (com número de processo, Vara, data, etc.)
- Decisões administrativas
- Outras situações não previstas

**Campos adicionais obrigatórios:**
- `especificacao_fim_cadeia` - Descrição detalhada da situação

**Formato de armazenamento:**
```
Outra:Especificação:Classificação
Exemplo: Outra:Processo 1234567-89.2023.8.05.0001, Vara Cível, 15/03/2023:inconclusa
```

### 3. Sem Origem

**Valor:** `sem_origem`

**Descrição:** Não há origem documentada para o imóvel. Pode incluir reprodução de fala da transcrição.

**Campos opcionais:**
- `especificacao_fim_cadeia` - Reprodução de fala da transcrição (opcional)

**Formato de armazenamento:**
```
Sem Origem::Classificação
Exemplo: Sem Origem::sem_origem
```

### 4. Registro (Cartório de Notas)

**Valor:** `registro` (implícito quando origem é do tipo "Registro")

**Descrição:** A origem é um registro em cartório de notas (não CRI - Cartório de Registro de Imóveis).

**Campos obrigatórios:**
- Número do registro
- Livro
- Cartório (de notas, não CRI)

**Observação:** Cartórios de notas não devem aparecer na lista de cartórios de registro de imóveis. Devem ser separados no sistema.

---

## Classificações de Fim de Cadeia

Quando a cadeia chega ao fim, o sistema **deve exigir** que o usuário classifique o imóvel em uma das seguintes categorias:

### 1. Imóvel com Origem Lídima

**Valor:** `origem_lidima`

**Descrição:** O imóvel possui origem documentada e legítima. A cadeia dominial foi rastreada até um ponto válido e confiável.

**Cor na visualização:** Verde (#28a745)

**Exemplos:**
- Origem em INCRA com documentação adequada
- Origem em matrícula/transcrição anterior válida
- Sentença judicial com fundamentação adequada

### 2. Imóvel sem Origem

**Valor:** `sem_origem`

**Descrição:** O imóvel não possui origem documentada ou a origem não pode ser determinada.

**Cor na visualização:** Vermelho (#dc3545)

**Exemplos:**
- Não há documentos anteriores
- Origem desconhecida
- Documentação perdida ou destruída

### 3. Situação Inconclusa

**Valor:** `inconclusa`

**Descrição:** A situação da origem do imóvel não pode ser determinada com certeza. Requer investigação adicional ou há dúvidas sobre a legitimidade.

**Cor na visualização:** Amarelo (#ffc107)

**Exemplos:**
- Processo judicial em andamento
- Documentação incompleta ou questionável
- Conflito entre documentos
- Necessidade de análise mais profunda

---

## Fluxo de Preenchimento

### 1. Usuário Seleciona Origem

No lançamento do tipo "Início de Matrícula", o usuário escolhe uma das opções de origem:

- **Matrícula** → Cadeia continua
- **Transcrição** → Cadeia continua
- **Outra** → Fim de cadeia
- **Destacamento do Patrimônio Público** → Fim de cadeia
- **Registro** → Fim de cadeia
- **Sem Origem** → Fim de cadeia

### 2. Se Fim de Cadeia, Preencher Informações

Se a origem escolhida indica fim de cadeia, o sistema exibe campos adicionais:

1. **Tipo do Fim de Cadeia** (obrigatório)
   - Destacamento do Patrimônio Público
   - Outra
   - Sem Origem

2. **Classificação** (obrigatório)
   - Imóvel com Origem Lídima
   - Imóvel sem Origem
   - Situação Inconclusa

3. **Campos específicos por tipo:**
   - Se "Destacamento Público": Sigla do órgão (obrigatório)
   - Se "Outra": Especificação (obrigatório)
   - Se "Sem Origem": Especificação (opcional)

### 3. Validação

O sistema valida:
- Tipo e classificação são obrigatórios quando fim de cadeia está marcado
- Especificação é obrigatória quando tipo = "outra"
- Sigla é obrigatória quando tipo = "destacamento_publico"

---

## Visualização na Árvore D3

### Marcação Visual

Quando a cadeia chega ao fim, o sistema deve exibir uma **moldura ou marcação bem nítida** na árvore indicando que chegamos na origem (ou na falta dela).

**Implementação atual:**

**Arquivo:** `old/static/dominial/js/cadeia_dominial_d3.js`

```javascript
// Cores baseadas na classificação
const cores = {
    'origem_lidima': '#28a745',  // Verde
    'sem_origem': '#dc3545',      // Vermelho
    'inconclusa': '#ffc107'       // Amarelo
};
```

### Formato de Exibição

Os nós de fim de cadeia são exibidos com:
- Cor de fundo baseada na classificação
- Borda destacada
- Texto indicando o tipo de fim de cadeia
- Sigla ou especificação (quando aplicável)

---

## Lista de Imóveis por Classificação

**Requisito:** Em algum lugar do sistema, precisa aparecer uma **lista de imóveis com cada condição** (origem lídima, sem origem, inconclusa).

### Implementação Sugerida

1. **Relatório/Filtro na tela de imóveis:**
   - Filtro por classificação de fim de cadeia
   - Lista de imóveis agrupados por classificação

2. **Dashboard/Estatísticas:**
   - Contador de imóveis por classificação
   - Gráficos de distribuição

3. **Exportação:**
   - Exportar lista de imóveis por classificação
   - Relatório em PDF/Excel

---

## Implementação no Código

### Frontend

**Arquivo:** `staticfiles/dominial/js/origem_simples.js`

```javascript
function criarContainerFimCadeia(index) {
    // Cria container com campos de fim de cadeia
    // - Tipo do fim de cadeia (select)
    // - Classificação (select)
    // - Sigla do patrimônio público (input, aparece se tipo = destacamento_publico)
    // - Especificação (textarea, aparece se tipo = outra)
}
```

### Backend

**Arquivo:** `old/dominial/services/lancamento_campos_service.py`

```python
@staticmethod
def _processar_campos_inicio_matricula(request, lancamento):
    # Processa múltiplas origens
    origens_completas = request.POST.getlist('origem_completa[]')
    
    # Para cada origem, verifica se é fim de cadeia
    for index, origem in enumerate(origens_completas):
        fim_cadeia = request.POST.getlist('fim_cadeia[]')[index] == 'on'
        
        if fim_cadeia:
            # Criar/atualizar OrigemFimCadeia
            tipo_fim_cadeia = request.POST.getlist('tipo_fim_cadeia[]')[index]
            classificacao = request.POST.getlist('classificacao_fim_cadeia[]')[index]
            # ...
```

### Modelo

**Arquivo:** `old/dominial/models/lancamento_models.py`

```python
class OrigemFimCadeia(models.Model):
    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE)
    indice_origem = models.IntegerField()
    fim_cadeia = models.BooleanField(default=False)
    tipo_fim_cadeia = models.CharField(max_length=50, choices=[...])
    classificacao_fim_cadeia = models.CharField(max_length=50, choices=[...])
    especificacao_fim_cadeia = models.TextField(null=True, blank=True)
    
    def clean(self):
        if self.fim_cadeia:
            if not self.tipo_fim_cadeia:
                raise ValidationError("Tipo obrigatório")
            if not self.classificacao_fim_cadeia:
                raise ValidationError("Classificação obrigatória")
```

---

## Formato de Armazenamento

### No Campo `origem` do Lançamento

Quando uma origem é marcada como fim de cadeia, o formato armazenado no campo `origem` do lançamento é:

**Formato geral:**
```
Tipo:Valor:Classificação
```

**Exemplos:**
```
Destacamento Público:INCRA:origem_lidima
Outra:Processo 1234567, Vara Cível:inconclusa
Sem Origem::sem_origem
```

### No Modelo OrigemFimCadeia

As informações detalhadas são armazenadas no modelo `OrigemFimCadeia`, vinculado ao lançamento e ao índice da origem.

---

## Regras de Negócio Importantes

### 1. Múltiplas Origens com Fim de Cadeia

Um lançamento pode ter múltiplas origens, e cada uma pode ser marcada independentemente como fim de cadeia:

```
M100 tem origens:
  - M50 (continua a cadeia)
  - Destacamento Público:INCRA (fim de cadeia, origem_lidima)
  - T20 (continua a cadeia)
  - Sem Origem (fim de cadeia, sem_origem)
```

### 2. Classificação Obrigatória

**Sempre** que a cadeia chega ao fim, a classificação é obrigatória. Não é possível salvar um fim de cadeia sem classificação.

### 3. Separação de Cartórios

Cartórios de **Registro de Imóveis** (CRI) e cartórios de **Notas** (Tabelionato) devem ser separados:
- CRI: usados em "Informações Básicas da Matrícula/Transcrição"
- Notas: usados em "Transmissão" quando origem é "Registro"
- Cartórios de notas não aparecem na lista de CRI

### 4. Visualização na Árvore

- Se der para marcar a classificação na árvore, ótimo
- Se ficar ilegível, não tem problema, mas a informação sobre a origem (lídima, sem origem ou inconclusa) será o principal
- A marcação visual deve ser clara e distinta

---

## Referências Legais

### Lei nº 6.015/1973 (Lei de Registros Públicos)

- **Art. 167:** Define os tipos de lançamentos (Registro e Averbação)
- **Arts. 176, 195-197:** Define Início de Matrícula e conversão de transcrições

### Contexto de Terras Indígenas

No contexto de terras indígenas, o rastreamento da cadeia dominial é fundamental para:
- Identificar origens legítimas de propriedade
- Detectar possíveis irregularidades ou fraudes
- Documentar a história da propriedade do imóvel
- Suportar processos de regularização fundiária

---

## Arquivos Relacionados

### Modelos
- `old/dominial/models/lancamento_models.py` - Modelos `OrigemFimCadeia` e `FimCadeia`

### Services
- `old/dominial/services/lancamento_campos_service.py` - Processamento de campos de fim de cadeia
- `old/dominial/services/lancamento_origem_service.py` - Processamento de origens

### Frontend
- `staticfiles/dominial/js/origem_simples.js` - Interface de fim de cadeia
- `old/static/dominial/js/cadeia_dominial_d3.js` - Visualização D3 com cores de classificação

### Documentação Relacionada
- `docs/cadeia-dominial/TIPOS_LANCAMENTO.md` - Tipos de lançamento e origens
- `docs/cadeia-dominial/DESENHO_ARVORE_CADEIA_DOMINIAL.md` - Desenho da árvore da cadeia dominial

---

## Exemplos Práticos

### Exemplo 1: Origem em INCRA

```
Lançamento: Início de Matrícula M100
Origem: Destacamento do Patrimônio Público
  - Tipo: Destacamento do Patrimônio Público
  - Sigla: INCRA
  - Classificação: Imóvel com Origem Lídima

Resultado na árvore:
M100 → [FIM CADEIA: INCRA - Verde (origem lídima)]
```

### Exemplo 2: Sentença Judicial

```
Lançamento: Início de Matrícula M200
Origem: Outra
  - Tipo: Outra
  - Especificação: Processo 1234567-89.2023.8.05.0001, Vara Cível de Salvador, 15/03/2023
  - Classificação: Situação Inconclusa

Resultado na árvore:
M200 → [FIM CADEIA: Outra - Amarelo (inconclusa)]
```

### Exemplo 3: Sem Origem

```
Lançamento: Início de Matrícula M300
Origem: Sem Origem
  - Tipo: Sem Origem
  - Especificação: (vazio ou reprodução de fala da transcrição)
  - Classificação: Imóvel sem Origem

Resultado na árvore:
M300 → [FIM CADEIA: Sem Origem - Vermelho (sem origem)]
```

---

## Checklist de Implementação

- [ ] Interface de seleção de tipo de origem (Matrícula, Transcrição, Outra, etc.)
- [ ] Campos de fim de cadeia aparecem quando origem indica fim
- [ ] Validação de campos obrigatórios por tipo
- [ ] Armazenamento no modelo `OrigemFimCadeia`
- [ ] Visualização na árvore D3 com cores e marcações
- [ ] Lista de imóveis por classificação
- [ ] Separação de cartórios (CRI vs Notas)
- [ ] Relatórios e exportação por classificação
