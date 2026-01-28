> **LEGACY / REFERENCIA**: este documento foi consolidado. Fonte de verdade: `docs/db/SCHEMA_CONSOLIDATED.md` e ERD em `docs/db/SCHEMA_CONSOLIDATED_ERD.*`.
>
> Este arquivo e mantido apenas para contexto historico e pode conter regras desatualizadas.

# Proposta: Tipo de Origem Unificado para Lançamentos

**Versão:** 1.0
**Data:** 2026-01-28
**Objetivo:** Substituir o checkbox "Fim de Cadeia" por um select com 3 opções (Matrícula, Transcrição, Fim de Cadeia), simplificando a UX e normalizando o modelo de dados.

---

## Sumário

1. [Contexto e Problema](#contexto-e-problema)
2. [Solução Proposta](#solução-proposta)
3. [Modelo de Dados](#modelo-de-dados)
4. [Frontend - Fluxo de Interface](#frontend---fluxo-de-interface)
5. [Backend - Processamento](#backend---processamento)
6. [Visualização na Árvore](#visualização-na-árvore-react-flow)
7. [Migration de Dados](#migration-de-dados)
8. [Deprecação de Campos Legados](#deprecação-de-campos-legados)
9. [Avaliação de Viabilidade](#avaliação-de-viabilidade)

---

## 1. Contexto e Problema

### Situação Atual

O sistema atual usa um padrão confuso para identificar fins de cadeia:

```
┌─────────────────────────────────────────────────────────────────┐
│  Tipo de Origem: [Matrícula ▼]                                  │
│  Número: [M50                  ]                                │
│  Cartório: [1º CRI Salvador ▼]                                  │
│  Livro: [3           ]                                          │
│  Folgo: [45          ]                                          │
│                                                                 │
│  ☑️ Esta origem é um Fim de Cadeia                              │  ← Checkbox separado
│  Tipo: [Destacamento Público ▼]                                 │
│  Classificação: [Origem Lídima ▼]                               │
└─────────────────────────────────────────────────────────────────┘
```

### Problemas Identificados

| Problema                            | Impacto                                                 |
| ----------------------------------- | ------------------------------------------------------- |
| **Checkbox separado**               | Usuário pode esquecer de marcar, deixando campos órfãos |
| **Campos visíveis simultaneamente** | Confusão sobre quais campos são relevantes              |
| **UX não linear**                   | Usuário precisa entender lógica condicional             |
| **Checkbox escondido**              | Fim de cadeia é secundário, não primário                |
| **Validação complexa**              | Código precisa verificar checkbox + campos preenchidos  |

### Análise do Fluxo Atual

```
Selecionar Origem → Preencher Dados → [Opção esquecida: Checkbox Fim de Cadeia]
```

O usuário foca em "origem" primeiro, e "fim de cadeia" é uma consideração secundária que facilmente escapa.

---

## 2. Solução Proposta

### Conceito: Tipo de Origem como Primeira Classificação

Em vez de perguntar "qual é a origem?" e depois "é fim de cadeia?", perguntamos:

**"Qual é o tipo desta origem?"**

```
┌─────────────────────────────────────────────────────────────────┐
│  Tipo de Origem: [Matrícula        ▼]  ← Campo principal        │
│                           ├── Matrícula                          │
│                           ├── Transcrição                        │
│                           └── Fim de Cadeia                      │
│                                                                 │
│  [Campos de REGISTRO aparecem aqui]  ← Se Matrícula/Transcrição │
│  [Campos de FIM DE CADEIA aparecem aqui] ← Se Fim de Cadeia     │
└─────────────────────────────────────────────────────────────────┘
```

### Comparativo de UX

| Aspecto              | Atual (Checkbox)               | Proposto (Select)              |
| -------------------- | ------------------------------ | ------------------------------ |
| **Primeira decisão** | Escolher tipo (M/T)            | Escolher tipo (M/T/Fim)        |
| **Campos visíveis**  | Todos juntos                   | Apenas os relevantes           |
| **Fim de Cadeia**    | Secundário (checkbox)          | Primário (opção no select)     |
| **Validação**        | Checkbox + campos condicionais | Tipo determina obrigatoriedade |
| **Erros comuns**     | Esquecer checkbox              | Selecionar tipo errado         |

### Tipos de Origem Definidos

| Tipo              | Descrição                         | Campos Exigidos                | Continua Cadeia? |
| ----------------- | --------------------------------- | ------------------------------ | ---------------- |
| **Matrícula**     | Origem é uma matrícula anterior   | cartório, livro, folha, número | ✅ Sim           |
| **Transcrição**   | Origem é uma transcrição anterior | cartório, livro, folha, número | ✅ Sim           |
| **Fim de Cadeia** | Origem sem documento rastreável   | tipo_fim, classificação        | ❌ Não           |

---

## 3. Modelo de Dados

### 3.1 Tabela `lancamento_origem` (Nova)

```sql
CREATE TABLE lancamento_origem (
    -- Identificação
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lancamento_id INTEGER NOT NULL REFERENCES lancamento(id),
    indice_origem INTEGER NOT NULL,

    -- Tipo de origem (campo principal)
    tipo_origem TEXT NOT NULL
        CHECK(tipo_origem IN ('matricula', 'transcricao', 'fim_cadeia')),

    -- ───────────────────────────────────────────────────────────────
    -- Campos visíveis APENAS quando tipo_origem IN ('matricula', 'transcricao')
    -- ───────────────────────────────────────────────────────────────
    documento_numero VARCHAR(50),  -- "M50", "T20", etc.
    cartorio_id INTEGER REFERENCES cartorios(id),
    livro VARCHAR(20),
    folha VARCHAR(20),
    data DATE,

    -- ───────────────────────────────────────────────────────────────
    -- Campos visíveis APENAS quando tipo_origem = 'fim_cadeia'
    -- ───────────────────────────────────────────────────────────────
    tipo_fim_cadeia TEXT
        CHECK(tipo_fim_cadeia IN ('destacamento_publico', 'outra', 'sem_origem')),
    especificacao_fim_cadeia TEXT,
    classificacao_fim_cadeia TEXT
        CHECK(classificacao_fim_cadeia IN ('origem_lidima', 'sem_origem', 'inconclusa')),

    -- Constraints
    UNIQUE(lancamento_id, indice_origem)
);

-- Índices para performance
CREATE INDEX idx_lancamento_origem_lancamento ON lancamento_origem(lancamento_id);
CREATE INDEX idx_lancamento_origem_documento ON lancamento_origem(documento_numero);
CREATE INDEX idx_lancamento_origem_tipo ON lancamento_origem(tipo_origem);
```

### 3.2 TypeScript Interface

```typescript
// Tipos base
type TipoOrigem = "matricula" | "transcricao" | "fim_cadeia";
type TipoFimCadeia = "destacamento_publico" | "outra" | "sem_origem";
type ClassificacaoFimCadeia = "origem_lidima" | "sem_origem" | "inconclusa";

interface LancamentoOrigem {
  id: string;
  lancamentoId: string;
  indiceOrigem: number;

  // CAMPO PRINCIPAL: tipo_origem determina preenchimento dos demais
  tipoOrigem: TipoOrigem;

  // ───────────────────────────────────────────────────────────────
  // Grupo: Dados de Registro (visíveis quando tipoOrigem !== 'fim_cadeia')
  // ───────────────────────────────────────────────────────────────
  documentoNumero: string | null; // "M50", "T20"
  cartorioId: string | null;
  cartorio?: Cartorio; // FK reversa
  livro: string | null;
  folha: string | null;
  data: Date | null;

  // ───────────────────────────────────────────────────────────────
  // Grupo: Dados de Fim de Cadeia (visíveis quando tipoOrigem === 'fim_cadeia')
  // ───────────────────────────────────────────────────────────────
  tipoFimCadeia: TipoFimCadeia | null;
  especificacaoFimCadeia: string | null;
  classificacaoFimCadeia: ClassificacaoFimCadeia | null;
}

// Relacionamento no Lancamento
interface Lancamento {
  id: string;
  documentoId: string;
  tipo: LancamentoTipo;
  origens: LancamentoOrigem[]; // hasMany - substitui campo 'origem' string
}
```

### 3.3 Exemplo de Dados

```json
{
  "lancamento": {
    "id": 1,
    "documento_id": 100,
    "tipo": "inicio_matricula",
    "origens": [
      {
        "indice_origem": 0,
        "tipo_origem": "matricula",
        "documento_numero": "M50",
        "cartorio_id": 1,
        "cartorio": { "id": 1, "nome": "1º CRI Salvador" },
        "livro": "3",
        "folha": "45",
        "data": "1990-01-15",
        "tipo_fim_cadeia": null,
        "especificacao_fim_cadeia": null,
        "classificacao_fim_cadeia": null
      },
      {
        "indice_origem": 1,
        "tipo_origem": "transcricao",
        "documento_numero": "T20",
        "cartorio_id": 2,
        "cartorio": { "id": 2, "nome": "2º CRI Salvador" },
        "livro": "5",
        "folha": "12",
        "data": "1985-06-20",
        "tipo_fim_cadeia": null,
        "especificacao_fim_cadeia": null,
        "classificacao_fim_cadeia": null
      },
      {
        "indice_origem": 2,
        "tipo_origem": "fim_cadeia",
        "documento_numero": null,
        "cartorio_id": null,
        "livro": null,
        "folha": null,
        "data": null,
        "tipo_fim_cadeia": "destacamento_publico",
        "especificacao_fim_cadeia": "INCRA",
        "classificacao_fim_cadeia": "origem_lidima"
      }
    ]
  }
}
```

---

## 4. Frontend - Fluxo de Interface

### 4.1 Componente de Origem Individual

```tsx
interface OrigemFieldProps {
  index: number;
  value: LancamentoOrigem;
  onChange: (value: LancamentoOrigem) => void;
  errors: Record<string, string>;
}

export function OrigemField({ index, value, onChange, errors }: OrigemFieldProps) {
  const isFimCadeia = value.tipoOrigem === "fim_cadeia";
  const isRegistro = value.tipoOrigem === "matricula" || value.tipoOrigem === "transcricao";

  return (
    <div className="origem-container border p-4 rounded">
      <h4 className="font-bold mb-2">Origem {index + 1}</h4>

      {/* CAMPO PRINCIPAL: Tipo de Origem */}
      <select
        value={value.tipoOrigem || ""}
        onChange={(e) => onChange({ ...value, tipoOrigem: e.target.value as TipoOrigem })}
        className="w-full p-2 border rounded"
        required
      >
        <option value="">Selecione o tipo de origem</option>
        <option value="matricula">Matrícula</option>
        <option value="transcricao">Transcrição</option>
        <option value="fim_cadeia">Fim de Cadeia</option>
      </select>

      {/* ─────────────────────────────────────────────────────────── */}
      {/* Campos visíveis APENAS para Matrícula/Transcrição */}
      {/* ─────────────────────────────────────────────────────────── */}
      {isRegistro && (
        <div className="registro-fields mt-4">
          <label>Número do Documento:</label>
          <input
            type="text"
            value={value.documentoNumero || ""}
            onChange={(e) => onChange({ ...value, documentoNumero: e.target.value })}
            placeholder={value.tipoOrigem === "matricula" ? "M50" : "T20"}
            className="w-full p-2 border rounded"
            required={isRegistro}
          />

          <label>Cartório:</label>
          <select
            value={value.cartorioId || ""}
            onChange={(e) => onChange({ ...value, cartorioId: e.target.value })}
            className="w-full p-2 border rounded"
            required={isRegistro}
          >
            <option value="">Selecione o cartório</option>
            {cartorios.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nome}
              </option>
            ))}
          </select>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label>Livro:</label>
              <input
                type="text"
                value={value.livro || ""}
                onChange={(e) => onChange({ ...value, livro: e.target.value })}
                className="w-full p-2 border rounded"
                required={isRegistro}
              />
            </div>
            <div>
              <label>Folha:</label>
              <input
                type="text"
                value={value.folha || ""}
                onChange={(e) => onChange({ ...value, folha: e.target.value })}
                className="w-full p-2 border rounded"
                required={isRegistro}
              />
            </div>
            <div>
              <label>Data:</label>
              <input
                type="date"
                value={value.data || ""}
                onChange={(e) => onChange({ ...value, data: e.target.value })}
                className="w-full p-2 border rounded"
              />
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────── */}
      {/* Campos visíveis APENAS para Fim de Cadeia */}
      {/* ─────────────────────────────────────────────────────────── */}
      {isFimCadeia && (
        <div className="fim-cadeia-fields mt-4 bg-yellow-50 p-4 rounded">
          <h5 className="font-bold text-yellow-800 mb-2">Dados do Fim de Cadeia</h5>

          <label>Tipo de Fim de Cadeia:</label>
          <select
            value={value.tipoFimCadeia || ""}
            onChange={(e) => onChange({ ...value, tipoFimCadeia: e.target.value as TipoFimCadeia })}
            className="w-full p-2 border rounded"
            required={isFimCadeia}
          >
            <option value="">Selecione o tipo</option>
            <option value="destacamento_publico">Destacamento do Patrimônio Público</option>
            <option value="outra">Outra</option>
            <option value="sem_origem">Sem Origem</option>
          </select>

          {value.tipoFimCadeia === "outra" && (
            <>
              <label>Especificação:</label>
              <textarea
                value={value.especificacaoFimCadeia || ""}
                onChange={(e) => onChange({ ...value, especificacaoFimCadeia: e.target.value })}
                className="w-full p-2 border rounded"
                placeholder="Descreva a situação..."
                required={value.tipoFimCadeia === "outra"}
              />
            </>
          )}

          <label>Classificação:</label>
          <select
            value={value.classificacaoFimCadeia || ""}
            onChange={(e) =>
              onChange({
                ...value,
                classificacaoFimCadeia: e.target.value as ClassificacaoFimCadeia
              })
            }
            className="w-full p-2 border rounded"
            required={isFimCadeia}
          >
            <option value="">Selecione a classificação</option>
            <option value="origem_lidima">Origem Lídima</option>
            <option value="sem_origem">Sem Origem</option>
            <option value="inconclusa">Situação Inconclusa</option>
          </select>
        </div>
      )}

      {/* Botão remover */}
      <button type="button" onClick={() => onRemove(index)} className="text-red-500 mt-2">
        Remover Origem
      </button>
    </div>
  );
}
```

### 4.2 Componente Principal do Formulário

```tsx
interface LancamentoFormProps {
  lancamento?: Lancamento;
  onSubmit: (data: LancamentoFormData) => void;
}

export function LancamentoForm({ lancamento, onSubmit }: LancamentoFormProps) {
  const [origens, setOrigens] = useState<LancamentoOrigem[]>([
    { tipoOrigem: "matricula" } // Padrão: primeira origem
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const formData: LancamentoFormData = {
      lancamento: {
        /* dados do lançamento */
      },
      origens: origens.filter((o) => o.tipoOrigem) // Remove vazias
    };

    onSubmit(formData);
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* Outros campos do lançamento... */}

      {/* SEÇÃO DE ORIGENS */}
      <div className="origens-section">
        <h3 className="text-lg font-bold mb-2">Origens do Lançamento</h3>
        <p className="text-sm text-gray-600 mb-4">
          Informe de quais documentos este imóvel se originou. Selecione "Fim de Cadeia" quando não
          houver documento rastreável.
        </p>

        {origens.map((origem, index) => (
          <OrigemField
            key={index}
            index={index}
            value={origem}
            onChange={(newValue) => {
              const newOrigens = [...origens];
              newOrigens[index] = newValue;
              setOrigens(newOrigens);
            }}
            errors={errors}
          />
        ))}

        <button
          type="button"
          onClick={() => setOrigens([...origens, { tipoOrigem: "matricula" }])}
          className="mt-2 bg-blue-500 text-white px-4 py-2 rounded"
        >
          + Adicionar Origem
        </button>
      </div>

      <button type="submit" className="mt-4 bg-green-500 text-white px-6 py-2 rounded">
        Salvar Lançamento
      </button>
    </form>
  );
}
```

---

## 5. Backend - Processamento

### 5.1 Service de Processamento de Origens

```python
class LancamentoOrigemService:
    """
    Service para processamento de origens com tipo unificado
    """

    @staticmethod
    def processar_origens(lancamento, origens_data):
        """
        Processa array de origens com tipos diferenciados

        Args:
            lancamento: Instância do lançamento
            origens_data: Lista de dicionários com dados das origens
        """
        from ..models import LancamentoOrigem, Documento, DocumentoTipo

        # Limpar origens existentes
        lancamento.origens.all().delete()

        for i, origem_data in enumerate(origens_data):
            # Criar registro na nova tabela
            lancamento_origem = LancamentoOrigem.objects.create(
                lancamento=lancamento,
                indice_origem=i,
                tipo_origem=origem_data['tipo_origem'],
                documento_numero=origem_data.get('documento_numero'),
                cartorio_id=origem_data.get('cartorio_id'),
                livro=origem_data.get('livro'),
                folha=origem_data.get('folha'),
                data=origem_data.get('data'),
                tipo_fim_cadeia=origem_data.get('tipo_fim_cadeia'),
                especificacao_fim_cadeia=origem_data.get('especificacao_fim_cadeia'),
                classificacao_fim_cadeia=origem_data.get('classificacao_fim_cadeia'),
            )

            # Se não é fim de cadeia, criar documento automaticamente
            if origem_data['tipo_origem'] in ['matricula', 'transcricao']:
                LancamentoOrigemService._criar_documento_se_nao_existe(
                    lancamento, origem_data
                )

    @staticmethod
    def _criar_documento_se_nao_existe(lancamento, origem_data):
        """
        Cria documento automaticamente se não existir
        """
        from ..models import Documento, DocumentoTipo
        from .cache_service import CacheService

        # Determinar tipo de documento
        doc_tipo = DocumentoTipo.objects.get(
            tipo='transcricao' if origem_data['tipo_origem'] == 'transcricao' else 'matricula'
        )

        # Formatar número
        numero = origem_data['documento_numero']
        if origem_data['tipo_origem'] == 'matricula' and not numero.startswith('M'):
            numero = f'M{numero}'
        elif origem_data['tipo_origem'] == 'transcricao' and not numero.startswith('T'):
            numero = f'T{numero}'

        # Verificar se documento já existe
        documento_existente = Documento.objects.filter(
            numero=numero,
            cartorio_id=origem_data['cartorio_id']
        ).first()

        if documento_existente:
            return documento_existente

        # Criar novo documento
        return Documento.objects.create(
            imovel=lancamento.documento.imovel,
            tipo=doc_tipo,
            numero=numero,
            cartorio_id=origem_data['cartorio_id'],
            livro=origem_data.get('livro', '0'),
            folha=origem_data.get('folha', '0'),
            origem=f'Criado automaticamente a partir de {origem_data["tipo_origem"]}: {numero}',
        )

    @staticmethod
    def validar_origens(origens_data):
        """
        Valida array de origens antes de salvar

        Returns:
            dict: {'valid': bool, 'errors': list}
        """
        errors = []

        for i, origem in enumerate(origens_data):
            # Validar tipo obrigatório
            if not origem.get('tipo_origem'):
                errors.append(f'Origem {i+1}: Tipo de origem é obrigatório')
                continue

            # Validação por tipo
            if origem['tipo_origem'] in ['matricula', 'transcricao']:
                if not origem.get('documento_numero'):
                    errors.append(f'Origem {i+1}: Número do documento é obrigatório')
                if not origem.get('cartorio_id'):
                    errors.append(f'Origem {i+1}: Cartório é obrigatório')
                if not origem.get('livro'):
                    errors.append(f'Origem {i+1}: Livro é obrigatório')
                if not origem.get('folha'):
                    errors.append(f'Origem {i+1}: Folha é obrigatória')

            elif origem['tipo_origem'] == 'fim_cadeia':
                if not origem.get('tipo_fim_cadeia'):
                    errors.append(f'Origem {i+1}: Tipo de fim de cadeia é obrigatório')
                if not origem.get('classificacao_fim_cadeia'):
                    errors.append(f'Origem {i+1}: Classificação é obrigatória')
                if origem.get('tipo_fim_cadeia') == 'outra' and not origem.get('especificacao_fim_cadeia'):
                    errors.append(f'Origem {i+1}: Especificação é obrigatória para tipo "Outra"')

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
```

### 5.2 View de Processamento

```python
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json

@require_POST
def criar_lancamento(request, documento_id):
    """
    Cria lançamento com origens do novo formato
    """
    try:
        data = json.loads(request.body)

        # Validar origens
        validacao = LancamentoOrigemService.validar_origens(data.get('origens', []))
        if not validacao['valid']:
            return JsonResponse({'valid': False, 'errors': validacao['errors']}, status=400)

        # Criar lançamento
        lancamento = Lancamento.objects.create(
            documento_id=documento_id,
            tipo_id=data['tipo_id'],
            data=data['data'],
            # ... outros campos
        )

        # Processar origens
        LancamentoOrigemService.processar_origens(lancamento, data.get('origens', []))

        return JsonResponse({
            'valid': True,
            'lancamento_id': lancamento.id,
            'message': 'Lançamento criado com sucesso'
        })

    except Exception as e:
        return JsonResponse({'valid': False, 'error': str(e)}, status=500)
```

---

## 6. Visualização na Árvore (React Flow)

### 6.1 Builder da Árvore

```typescript
interface ArvoreBuilderOptions {
  lancamentos: Lancamento[];
  documentos: Documento[];
}

function construirArvore({ lancamentos, documentos }: ArvoreBuilderOptions): {
  nodes: Node[];
  edges: Edge[];
} {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const documentosProcessados = new Set<string>();

  for (const lancamento of lancamentos) {
    const docAtual = lancamento.documento;
    const docNodeId = `doc-${docAtual.id}`;

    // Criar nó do documento atual (se não existir)
    if (!documentosProcessados.has(docNodeId)) {
      nodes.push({
        id: docNodeId,
        type: "documentoNode",
        position: { x: 0, y: 0 }, // será ajustado pelo layout
        data: {
          tipo: docAtual.tipo.tipo, // 'matricula' | 'transcricao'
          numero: docAtual.numero,
          cartorio: docAtual.cartorio?.nome,
          livro: docAtual.livro,
          folha: docAtual.folha
        }
      });
      documentosProcessados.add(docNodeId);
    }

    // Processar origens
    for (const origem of lancamento.origens) {
      if (origem.tipoOrigem === "fim_cadeia") {
        // Criar nó de fim de cadeia
        nodes.push({
          id: `fim-${lancamento.id}-${origem.indiceOrigem}`,
          type: "fimCadeiaNode",
          position: { x: -300, y: 0 },
          data: {
            tipo: origem.tipoFimCadeia,
            classificacao: origem.classificacaoFimCadeia,
            especificacao: origem.especificacaoFimCadeia
          }
        });

        edges.push({
          id: `edge-fim-${lancamento.id}-${origem.indiceOrigem}`,
          source: `fim-${lancamento.id}-${origem.indiceOrigem}`,
          target: docNodeId,
          type: "smoothstep",
          label: "Fim de Cadeia",
          style: { stroke: "#dc3545", strokeDasharray: "5,5" }
        });
      } else {
        // Criar documento de origem e aresta
        const docOrigemNodeId = `doc-${origem.documentoNumero}-${origem.cartorioId}`;

        if (!documentosProcessados.has(docOrigemNodeId)) {
          nodes.push({
            id: docOrigemNodeId,
            type: "documentoNode",
            position: { x: -300, y: 0 },
            data: {
              tipo: origem.tipoOrigem,
              numero: origem.documentoNumero,
              cartorio: origem.cartorio?.nome,
              livro: origem.livro,
              folha: origem.folha
            }
          });
          documentosProcessados.add(docOrigemNodeId);
        }

        edges.push({
          id: `edge-${lancamento.id}-${origem.indiceOrigem}`,
          source: docOrigemNodeId,
          target: docNodeId,
          type: "smoothstep"
        });
      }
    }
  }

  return { nodes, edges };
}
```

### 6.2 Componente de Nó de Fim de Cadeia

```tsx
import { Handle, Position, NodeProps } from "@xyflow/react";

export function FimCadeiaNode({ data }: NodeProps) {
  const coresPorClassificacao = {
    origem_lidima: "border-green-500 bg-green-50",
    sem_origem: "border-red-500 bg-red-50",
    inconclusa: "border-yellow-500 bg-yellow-50"
  };

  const labelsPorTipo = {
    destacamento_publico: "Destacamento Público",
    outra: "Outra",
    sem_origem: "Sem Origem"
  };

  return (
    <div className={`p-3 rounded-lg border-2 ${coresPorClassificacao[data.classificacao]}`}>
      <Handle type="target" position={Position.Left} />

      <div className="font-bold text-sm mb-1">🔚 Fim de Cadeia</div>

      <div className="text-xs">
        <div>
          <strong>Tipo:</strong> {labelsPorTipo[data.tipo]}
        </div>
        {data.especificacao && (
          <div>
            <strong>Espec.:</strong> {data.especificacao}
          </div>
        )}
        <div className="capitalize">
          <strong>Class.:</strong> {data.classificacao?.replace("_", " ")}
        </div>
      </div>

      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```

---

## 7. Migration de Dados

### 7.1 SQL de Migration

```sql
-- ================================================================
-- Migration: Substituir OrigemFimCadeia por LancamentoOrigem
-- ================================================================

-- 1. Criar nova tabela
CREATE TABLE lancamento_origem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lancamento_id INTEGER NOT NULL REFERENCES lancamento(id),
    indice_origem INTEGER NOT NULL,
    tipo_origem TEXT NOT NULL DEFAULT 'matricula',
    documento_numero VARCHAR(50),
    cartorio_id INTEGER REFERENCES cartorios(id),
    livro VARCHAR(20),
    folha VARCHAR(20),
    data DATE,
    tipo_fim_cadeia TEXT,
    especificacao_fim_cadeia TEXT,
    classificacao_fim_cadeia TEXT,
    UNIQUE(lancamento_id, indice_origem)
);

-- 2. Migrar origens existentes (string concatenada -> registros individuais)
-- Para dados legados, assumimos tipo_origem = 'matricula'
INSERT INTO lancamento_origem (
    lancamento_id,
    indice_origem,
    tipo_origem,
    documento_numero,
    cartorio_id,
    livro,
    folha,
    data
)
SELECT
    l.id AS lancamento_id,
    n.digit AS indice_origem,
    'matricula' AS tipo_origem,
    TRIM(SUBSTR(
        SUBSTR(l.origem, INSTR(l.origem, ';') + 1 + n.digit * INSTR(SUBSTR(l.origem, INSTR(l.origem, ';') + 1), ';') + n.digit),
        0,
        INSTR(SUBSTR(l.origem, INSTR(l.origem, ';') + 1 + n.digit * INSTR(SUBSTR(l.origem, INSTR(l.origem, ';') + 1), ';') + n.digit), ';')
    )) AS documento_numero,
    l.cartorio_origem_id,
    l.livro_origem,
    l.folha_origem,
    l.data_origem
FROM lancamento l
CROSS JOIN (
    SELECT 0 AS digit UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3
) n
WHERE l.origem IS NOT NULL
  AND (LENGTH(l.origem) - LENGTH(REPLACE(l.origem, ';', ''))) >= n.digit;

-- 3. Migrar fins de cadeia existentes para a nova estrutura
INSERT INTO lancamento_origem (
    lancamento_id,
    indice_origem,
    tipo_origem,
    tipo_fim_cadeia,
    especificacao_fim_cadeia,
    classificacao_fim_cadeia
)
SELECT
    lancamento_id,
    indice_origem,
    'fim_cadeia',
    tipo_fim_cadeia,
    especificacao_fim_cadeia,
    classificacao_fim_cadeia
FROM origemfimcadeia
WHERE fim_cadeia = TRUE;

-- 4. Marcar migration
INSERT INTO drizzleorm.schema_migrations (version) VALUES ('20260128_tipo_origem_unificado');
```

### 7.2 Python/Django Migration (Se aplicável)

```python
# Generated migration for Django if still using Django
class Migration(migrations.Migration):

    dependencies = [
        ('dominial', 'previous_migration'),
    ]

    operations = [
        # Rename table
        migrations.RenameModel('OrigemFimCadeia', 'LancamentoOrigem'),

        # Add new fields
        migrations.AddField(
            model_name='lancamentoorigem',
            name='tipo_origem',
            field=models.CharField(
                max_length=20,
                choices=[('matricula', 'Matrícula'), ('transcricao', 'Transcrição'), ('fim_cadeia', 'Fim de Cadeia')],
                default='matricula'
            ),
        ),
        migrations.AddField(
            model_name='lancamentoorigem',
            name='documento_numero',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='lancamentoorigem',
            name='livro',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='lancamentoorigem',
            name='folha',
            field=models.CharField(max_length=20, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='lancamentoorigem',
            name='data',
            field=models.DateField(null=True, blank=True),
        ),

        # Make cartorio_origem nullable (now per-origin)
        migrations.AlterField(
            model_name='lancamento',
            name='cartorio_origem',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=models.PROTECT,
                related_name='cartorio_origem_lancamento'
            ),
        ),
    ]
```

---

## 8. Deprecação de Campos Legados

### 8.1 Campos a Remover do Modelo `Lancamento`

```sql
-- Estes campos podem ser deprecados após período de transição:
ALTER TABLE lancamento DROP COLUMN origem;           -- "M50; T20; M30"
ALTER TABLE lancamento DROP COLUMN cartorio_origem;  -- Agora é por origem
ALTER TABLE lancamento DROP COLUMN livro_origem;
ALTER TABLE lancamento DROP COLUMN folha_origem;
ALTER TABLE lancamento DROP COLUMN data_origem;
```

### 8.2 Campos a Remover do Modelo `OrigemFimCadeia`

```sql
-- A tabela OrigemFimCadeia pode ser dropada após migração:
DROP TABLE origemfimcadeia;
```

### 8.3 Campos Mantidos com Nova Semântica

```typescript
// Lancamento ainda mantém estes campos para compatibilidade:
interface Lancamento {
  id: string;
  documento: Documento;
  tipo: LancamentoTipo;
  data: Date;

  // Campos que ainda fazem sentido no contexto do lançamento:
  forma: string | null;
  descricao: string | null;
  titulo: string | null;

  // Campos de transação (separados dos campos de origem):
  cartorio_transmissao: Cartorio | null;
  livro_transacao: string | null;
  folha_transacao: string | null;
  data_transacao: Date | null;

  // Campo indicador
  eh_inicio_matricula: boolean;

  // Relacionamentos
  origens: LancamentoOrigem[]; // NOVO - substitui campo 'origem' string
}
```

---

## 9. Avaliação de Viabilidade

### 9.1 Matriz de Impacto

| Aspecto                           | Avaliação       | Justificativa                                            |
| --------------------------------- | --------------- | -------------------------------------------------------- |
| **Complexidade de implementação** | ✅ Baixa        | Simplifica, não complica                                 |
| **Migração de dados**             | ✅ Trivial      | Todos os dados legados viram `tipo_origem = 'matricula'` |
| **Consistência do modelo**        | ✅ Melhor       | Tipo explícito, não inferido                             |
| **UX do usuário**                 | ✅ Melhor       | Fluxo mais claro e linear                                |
| **Validação**                     | ✅ Mais simples | Tipo determina obrigatoriedade                           |
| **Manutenção**                    | ✅ Melhor       | Menos condicionais no código                             |
| **Retrocompatibilidade**          | ⚠️ Média        | Requer período de transição                              |
| **Performance**                   | ✅ Melhor       | Índices por tipo_origem                                  |

### 9.2 Riscos e Mitigações

| Risco                                 | Probabilidade | Impacto | Mitigação                         |
| ------------------------------------- | ------------- | ------- | --------------------------------- |
| **Usuários acostumados com checkbox** | Média         | Baixo   | Treinamento e tooltip explicativo |
| **Dados legados mal interpretados**   | Baixa         | Médio   | Migration explícita documentada   |
| **Campos órfãos em migrate**          | Baixa         | Baixo   | Validação no backend              |

### 9.3 Checklist de Implementação

- [ ] Criar tabela `lancamento_origem` no schema Drizzle
- [ ] Definir interfaces TypeScript
- [ ] Implementar migration SQL
- [ ] Atualizar service `LancamentoCamposService` para novo formato
- [ ] Criar service `LancamentoOrigemService`
- [ ] Atualizar componente React `OrigemField`
- [ ] Atualizar endpoint de criação de lançamento
- [ ] Implementar validação no frontend
- [ ] Implementar validação no backend
- [ ] Atualizar builder da árvore React Flow
- [ ] Criar componente `FimCadeiaNode`
- [ ] Criar testes unitários
- [ ] Criar testes de integração
- [ ] Documentar na wiki

---

## 10. Referências

| Arquivo                                              | Descrição                               |
| ---------------------------------------------------- | --------------------------------------- |
| `old/dominial/models/lancamento_models.py`           | Modelos `Lancamento`, `OrigemFimCadeia` |
| `old/dominial/services/lancamento_campos_service.py` | Processamento de campos por tipo        |
| `old/dominial/services/lancamento_origem_service.py` | Service de origens automáticas          |
| `docs/db/MULTIPLAS_ORIGENS_CARTORIOS_ANALISE.md`     | Análise do problema atual               |
| `docs/cadeia-dominial/TIPOS_LANCAMENTO.md`           | Documentação de tipos de lançamento     |

---

**Data da Proposta:** 2026-01-28
**Autor:** Claude Code
**Status:** Aguardando Aprovação
