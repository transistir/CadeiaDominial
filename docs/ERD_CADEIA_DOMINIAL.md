# Diagrama ERD — Cadeia Dominial

## Schema do Banco de Dados

```mermaid
erDiagram
    TIs {
        int id PK
        string nome
        string codigo UK
        string etnia
        string estado
        decimal area
        date data_cadastro
    }

    TerraIndigenaReferencia {
        int id PK
        string codigo UK
        string nome
        string etnia
        string estado
        string municipio
        float area_ha
        string fase
        string modalidade
        date data_regularizada
        datetime created_at
        datetime updated_at
    }

    Imovel {
        int id PK
        string nome
        string matricula
        string tipo_documento_principal
        text observacoes
        date data_cadastro
        boolean arquivado
    }

    Cartorios {
        int id PK
        string nome
        string cns UK
        string endereco
        string telefone
        string email
        string estado
        string cidade
        string tipo
    }

    ImportacaoCartorios {
        int id PK
        string estado
        datetime data_inicio
        datetime data_fim
        int total_cartorios
        string status
        text erro
    }

    Pessoas {
        int id PK
        string nome
        string cpf UK
        string rg
        date data_nascimento
        string email
        string telefone
    }

    DocumentoTipo {
        int id PK
        string tipo
    }

    Documento {
        int id PK
        string numero
        date data
        string livro
        string folha
        text origem
        text observacoes
        date data_cadastro
        int nivel_manual
        string classificacao_fim_cadeia
        string sigla_patrimonio_publico
    }

    LancamentoTipo {
        int id PK
        string tipo
        boolean requer_transmissao
        boolean requer_detalhes
        boolean requer_titulo
        boolean requer_cartorio_origem
        boolean requer_livro_origem
        boolean requer_folha_origem
        boolean requer_data_origem
        boolean requer_forma
        boolean requer_descricao
        boolean requer_observacao
    }

    Lancamento {
        int id PK
        string numero_lancamento
        date data
        decimal valor_transacao
        decimal area
        string origem
        text detalhes
        text observacoes
        date data_cadastro
        string forma
        text descricao
        string titulo
        string livro_transacao
        string folha_transacao
        date data_transacao
        string livro_origem
        string folha_origem
        date data_origem
        boolean eh_inicio_matricula
    }

    LancamentoPessoa {
        int id PK
        string tipo
        string nome_digitado
    }

    OrigemFimCadeia {
        int id PK
        int indice_origem
        boolean fim_cadeia
        string tipo_fim_cadeia
        text especificacao_fim_cadeia
        string classificacao_fim_cadeia
    }

    FimCadeia {
        int id PK
        string nome UK
        string tipo
        string classificacao
        string sigla
        text descricao
        boolean ativo
        datetime data_criacao
        datetime data_atualizacao
    }

    AlteracoesTipo {
        int id PK
        string tipo
    }

    RegistroTipo {
        int id PK
        string tipo
    }

    AverbacoesTipo {
        int id PK
        string tipo
    }

    Alteracoes {
        int id PK
        string livro
        string folha
        date data_alteracao
        string titulo
        string livro_origem
        string folha_origem
        date data_origem
        decimal valor_transacao
        decimal area
        text observacoes
        date data_cadastro
    }

    TIs_Imovel {
        int id PK
    }

    DocumentoImportado {
        int id PK
        datetime data_importacao
    }

    %% ==================== RELACIONAMENTOS ====================

    %% Terra Indigena
    TIs ||--o| TerraIndigenaReferencia : "terra_referencia"
    TIs ||--o{ TIs_Imovel : "tem"
    Imovel ||--o{ TIs_Imovel : "associado_a"

    %% Imovel
    Imovel ||--o{ Documento : "possui"
    Imovel ||--o{ Alteracoes : "historico"
    Imovel }o--|| Pessoas : "proprietario"
    Imovel }o--|| TIs : "terra_indigena"

    %% Cartorio
    Cartorios ||--o{ Imovel : "registra"
    Cartorios ||--o{ Documento : "emissor"
    Cartorios ||--o{ Lancamento : "cartorio_origem"
    Cartorios ||--o{ Lancamento : "cartorio_transacao"
    Cartorios ||--o{ Lancamento : "cartorio_transmissao"
    Cartorios ||--o{ Alteracoes : "cartorio_responsavel"
    Documento }o--|| Cartorios : "cri_atual"
    Documento }o--|| Cartorios : "cri_origem"

    %% Pessoa
    Pessoas ||--o{ Lancamento : "transmitente"
    Pessoas ||--o{ Lancamento : "adquirente"
    Pessoas ||--o{ LancamentoPessoa : "envolvida"
    Pessoas ||--o{ Alteracoes : "transmitente_alt"
    Pessoas ||--o{ Alteracoes : "adquirente_alt"

    %% Documento
    Documento }o--|| DocumentoTipo : "classificado_como"
    Documento ||--o{ Lancamento : "lancamentos"
    Documento ||--o{ Lancamento : "documento_origem"
    Documento ||--o{ DocumentoImportado : "importacoes"

    %% Lancamento
    Lancamento }o--|| LancamentoTipo : "tipo_de_lancamento"
    Lancamento ||--o{ LancamentoPessoa : "pessoas"
    Lancamento ||--o{ OrigemFimCadeia : "origens_fim_cadeia"

    %% Alteracao
    Alteracoes }o--|| AlteracoesTipo : "tipo_alteracao"
    Alteracoes }o--|| RegistroTipo : "tipo_registro"
    Alteracoes }o--|| AverbacoesTipo : "tipo_averbacao"

    %% DocumentoImportado
    %% (relação Documento -> DocumentoImportado já declarada em Documento acima; manter só a referência ao imóvel de origem)
    DocumentoImportado }o--|| Imovel : "imovel_origem"
```

## Legenda das Entidades

| Entidade | Descrição |
|----------|-----------|
| **Imovel** | Entidade central — imóveis registrados com matrícula única por cartório |
| **Documento** | Documentos (matrículas/transcrições) associados a um imóvel |
| **Lancamento** | Lançamentos da cadeia dominial (registros, averbações, início de matrícula) |
| **LancamentoPessoa** | Pessoas (transmitentes/adquirentes) associadas a lançamentos |
| **Pessoas** | Pessoas físicas/jurídicas envolvidas |
| **Cartorios** | Cartórios de Registro de Imóveis |
| **Alteracoes** | Alterações sobre imóveis (registros/averbações) |
| **TIs** | Terras Indígenas sobrepostas |
| **FimCadeia** | Tipos configuráveis de fim de cadeia dominial |
| **DocumentoImportado** | Rastreamento de documentos importados entre cadeias |

## Relacionamentos Principais

- **Imovel ↔ Documento**: 1:N — um imóvel pode ter múltiplos documentos
- **Documento ↔ Lancamento**: 1:N — um documento pode ter vários lançamentos
- **Lancamento ↔ LancamentoPessoa**: 1:N — um lançamento pode ter múltiplas pessoas
- **Imovel ↔ Alteracoes**: 1:N — um imóvel tem um histórico de alterações
- **Imovel ↔ TIs**: 1:N via `Imovel.terra_indigena_id` (FK direta para uma TI) + N:N via `TIs_Imovel` (junction) — a FK cobre a relação principal; o junction modela sobreposições históricas/opcional
- **Documento → Lancamento (documento_origem)**: cada Documento é o documento de origem de N Lancamentos (chain link) — FK `Lancamento.documento_origem_id` aponta para `Documento`
