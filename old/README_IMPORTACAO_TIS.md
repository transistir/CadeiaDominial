# Sistema de Importação e Criação Automática de Terras Indígenas (TIs)

## Visão Geral

O sistema permite importar terras indígenas da API da FUNAI e criar automaticamente registros no modelo `TIs` para que todas as terras importadas apareçam na página inicial sem necessidade de cadastro manual prévio.

## Arquitetura

### Modelos Relacionados

1. **TerraIndigenaReferencia**: Dados brutos importados da FUNAI
2. **TIs**: Terras indígenas cadastradas no sistema (pode ser criada manualmente ou automaticamente)

### Relacionamento

- Uma `TIs` pode ter uma referência opcional (`terra_referencia`)
- TIs criadas automaticamente têm a referência preenchida
- TIs criadas manualmente não têm referência (para aldeias novas, por exemplo)

## Comandos Disponíveis

### 1. Importar Terras Indígenas da FUNAI

```bash
# Importar e criar TIs automaticamente
python manage.py importar_terras_indigenas

# Importar apenas referências (sem criar TIs)
python manage.py importar_terras_indigenas --apenas-referencia
```

**Funcionalidades:**
- Conecta à API WFS da FUNAI
- Importa dados de terras indígenas
- Cria/atualiza registros em `TerraIndigenaReferencia`
- Opcionalmente cria registros em `TIs` automaticamente
- Evita duplicatas verificando códigos existentes

### 2. Criar TIs a partir de Referências Existentes

```bash
# Criar TIs para todas as referências
python manage.py criar_tis_da_referencia

# Criar TI para código específico
python manage.py criar_tis_da_referencia --codigo 101
```

**Funcionalidades:**
- Cria TIs a partir das referências já importadas
- Permite criação seletiva por código
- Evita duplicatas
- Mantém relacionamento com a referência

## Fluxo de Trabalho

### Cenário 1: Primeira Importação
1. Executar `python manage.py importar_terras_indigenas`
2. Sistema importa dados da FUNAI
3. Sistema cria automaticamente TIs para todas as terras importadas
4. TIs aparecem na página inicial

### Cenário 2: Atualização de Dados
1. Executar `python manage.py importar_terras_indigenas`
2. Sistema atualiza dados existentes
3. Sistema cria TIs apenas para novas terras
4. TIs existentes são preservadas

### Cenário 3: Criação Manual
1. Usar interface web para cadastrar nova TI
2. TI criada sem referência (para aldeias novas)
3. TI aparece na página inicial

## Estrutura de Dados

### TerraIndigenaReferencia
```python
{
    'codigo': '101',
    'nome': 'Acapuri de Cima',
    'etnia': 'Kokama',
    'estado': 'AM',
    'area_ha': 12345.67,
    'municipio': 'Manaus',
    'fase': 'Regularizada',
    'modalidade': 'Tradicionalmente Ocupada',
    'coordenacao_regional': 'CR Manaus',
    'data_regularizada': '2020-01-01',
    'data_homologada': '2019-01-01',
    'data_declarada': '2018-01-01',
    'data_delimitada': '2017-01-01',
    'data_em_estudo': '2016-01-01'
}
```

### TIs (criada automaticamente)
```python
{
    'terra_referencia': <TerraIndigenaReferencia>,
    'nome': 'Acapuri de Cima',
    'codigo': '101',
    'etnia': 'Kokama'
}
```

## Interface Web

### Página Inicial (`/dominial/`)
- Lista todas as TIs cadastradas
- Ordenação por quantidade de imóveis
- Busca por nome, etnia ou código
- Separação visual entre TIs cadastradas e referências não cadastradas

### Funcionalidades
- **Busca**: Filtra TIs por nome, etnia ou código
- **Ordenação**: TIs com mais imóveis aparecem primeiro
- **Visualização**: Cards organizados com informações principais

## Vantagens do Sistema

1. **Automatização**: Elimina necessidade de cadastro manual de terras existentes
2. **Consistência**: Dados sempre atualizados com a FUNAI
3. **Flexibilidade**: Permite cadastro manual para terras novas
4. **Rastreabilidade**: Mantém relacionamento com dados originais
5. **Performance**: Busca e ordenação otimizadas

## Manutenção

### Atualização Regular
Recomenda-se executar a importação periodicamente para manter dados atualizados:

```bash
# Atualizar dados da FUNAI
python manage.py importar_terras_indigenas
```

### Limpeza de Dados
Para limpar dados de teste:

```bash
python manage.py limpar_dados_teste
```

## Troubleshooting

### Problema: TI não aparece na página inicial
**Solução**: Verificar se a TI foi criada corretamente:
```bash
python manage.py shell -c "from dominial.models import TIs; print(TIs.objects.filter(nome='Nome da TI').count())"
```

### Problema: Erro na importação da FUNAI
**Solução**: Verificar conectividade e formato da API:
```bash
python manage.py importar_terras_indigenas --apenas-referencia
```

### Problema: Duplicatas criadas
**Solução**: O sistema já previne duplicatas, mas se ocorrer:
```bash
python manage.py shell -c "from dominial.models import TIs; TIs.objects.filter(codigo='CODIGO').delete()"
```

## Próximas Melhorias

1. **Interface de administração**: Painel para gerenciar importações
2. **Logs detalhados**: Registro de todas as operações
3. **Validação de dados**: Verificação de integridade
4. **Sincronização incremental**: Importar apenas mudanças
5. **API REST**: Endpoints para integração externa 