# Diferenças entre Transcrição e Matrícula

## Análise Baseada no Código

### Definição dos Tipos

**Matrícula**: Documento principal de registro do imóvel no sistema de registro imobiliário.

**Transcrição**: Documento que transcreve informações de outro documento, geralmente para transferir dados entre diferentes sistemas ou cartórios.

### Tipos de Lançamento Disponíveis

#### Matrícula
- ✅ **Averbação**: Alterações e anotações na matrícula
- ✅ **Registro**: Registro de transmissão de propriedade
- ✅ **Início de Matrícula**: Criação inicial da matrícula

#### Transcrição
- ✅ **Averbação**: Alterações e anotações na transcrição
- ❌ **Registro**: Não disponível (transcrições não registram transmissões)
- ✅ **Início de Matrícula**: Criação inicial da transcrição

### Lógica de Negócio

#### Matrícula
```python
# Do código: lancamento_tipo_service.py
if documento.tipo.tipo == 'matricula':
    return LancamentoTipo.objects.filter(
        tipo__in=['averbacao', 'registro', 'inicio_matricula']
    ).order_by('tipo')
```

- **Propósito**: Documento principal que registra a propriedade
- **Funcionalidade**: Pode registrar transmissões de propriedade
- **Validade**: Documento oficial e definitivo
- **Uso**: Para registrar mudanças de proprietário, hipotecas, etc.

#### Transcrição
```python
# Do código: lancamento_tipo_service.py
elif documento.tipo.tipo == 'transcricao':
    return LancamentoTipo.objects.filter(
        tipo__in=['averbacao', 'inicio_matricula']
    ).order_by('tipo')
```

- **Propósito**: Documento que copia informações de outro documento
- **Funcionalidade**: Não registra transmissões, apenas transcreve dados
- **Validade**: Documento secundário, depende do documento original
- **Uso**: Para transferir informações entre cartórios ou sistemas

### Implicações Práticas

#### Matrícula
- **Transmissões**: Pode registrar compra e venda, doações, heranças
- **Averbações**: Pode registrar hipotecas, penhoras, limitações
- **Hierarquia**: Documento principal na cadeia dominial
- **Responsabilidade**: Cartório de registro imobiliário

#### Transcrição
- **Transmissões**: Não registra transmissões (apenas transcreve)
- **Averbações**: Pode registrar informações complementares
- **Hierarquia**: Documento secundário na cadeia dominial
- **Responsabilidade**: Cartório que faz a transcrição

### Exemplos de Uso

#### Matrícula
```
Matrícula M123 - Cartório Central
├── Início de Matrícula (criação)
├── Registro R1M123 (compra e venda)
├── Averbação AV2M123 (hipoteca)
└── Registro R3M123 (doação)
```

#### Transcrição
```
Transcrição T456 - Cartório Auxiliar
├── Início de Matrícula (transcrição inicial)
├── Averbação AV1T456 (informação complementar)
└── Averbação AV2T456 (observação)
```

### Regras de Validação

#### Matrícula
- Pode ter lançamentos de **Registro** (transmissões)
- Pode ter lançamentos de **Averbação** (anotações)
- Pode ter **Início de Matrícula** (criação)

#### Transcrição
- ❌ **NÃO** pode ter lançamentos de **Registro**
- Pode ter lançamentos de **Averbação** (anotações)
- Pode ter **Início de Matrícula** (transcrição inicial)

### Impacto na Cadeia Dominial

#### Matrícula
- **Posição**: Geralmente no topo da cadeia
- **Função**: Documento de referência principal
- **Validade**: Documento oficial e definitivo
- **Responsabilidade**: Cartório de registro imobiliário

#### Transcrição
- **Posição**: Documento intermediário ou secundário
- **Função**: Documento de transferência de informações
- **Validade**: Depende do documento original
- **Responsabilidade**: Cartório que faz a transcrição

### Considerações para o Sistema

1. **Validação**: O sistema impede que transcrições tenham registros
2. **Interface**: Formulários mostram apenas opções válidas
3. **Relatórios**: Separação clara entre matrículas e transcrições
4. **Cadeia Dominial**: Matrículas são mais importantes na hierarquia

### Recomendações para Usuários

#### Ao Criar Matrículas
- Use para documentos principais de propriedade
- Pode registrar transmissões de propriedade
- Documento oficial e definitivo

#### Ao Criar Transcrições
- Use para copiar informações de outros documentos
- Não registra transmissões de propriedade
- Documento secundário na cadeia dominial 