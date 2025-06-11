# Importação de Terras Indígenas da FUNAI

Este documento descreve o processo de importação de Terras Indígenas (TIs) do GeoServer da FUNAI para o sistema Cadeia Dominial.

## Instruções para Testes

Antes de começar a testar o sistema, é necessário importar os dados das terras indígenas da FUNAI. Para isso, execute o comando:

```bash
python manage.py importar_terras_indigenas
```

Este comando irá:
1. Conectar ao GeoServer da FUNAI via WFS (Web Feature Service)
2. Importar todas as terras indígenas disponíveis
3. Criar registros na tabela `TerraIndigenaReferencia`
4. Permitir que você selecione uma terra indígena ao cadastrar uma nova TI no sistema

**Importante**: Sem executar este comando, o select de terras indígenas ficará vazio no formulário de cadastro.

## Visão Geral

O sistema permite a importação automática de dados de terras indígenas diretamente do GeoServer da FUNAI, facilitando o cadastro inicial das TIs no sistema. O processo é realizado através de um script Python que:

1. Conecta ao GeoServer da FUNAI via WFS
2. Obtém os dados das TIs
3. Processa e formata os dados
4. Salva no banco de dados local

## Arquivos Envolvidos

1. `dominial/management/commands/importar_terras_indigenas.py`
   - Script principal de importação
   - Gerencia a conexão com o GeoServer
   - Processa os dados recebidos

2. `dominial/models.py`
   - Modelo `TerraReferencia` para armazenar dados da FUNAI
   - Modelo `TIs` para dados cadastrados no sistema

## Como Funciona

### 1. Conexão com o GeoServer

O script se conecta ao GeoServer da FUNAI usando a biblioteca `requests`:

```python
url = 'https://geoserver.funai.gov.br/geoserver/wfs'
params = {
    'service': 'WFS',
    'version': '1.1.0',
    'request': 'GetFeature',
    'typeName': 'Funai:tis_poligonais_portarias',
    'outputFormat': 'application/json',
    'srsName': 'EPSG:4674'
}
```

### 2. Obtenção dos Dados

Os dados são obtidos através de uma requisição WFS (Web Feature Service) e incluem:
- Nome da TI
- Código
- Etnia
- Estado
- Fase
- Área (em hectares)
- Datas importantes (regularização, homologação, etc.)

### 3. Processamento dos Dados

Os dados recebidos são processados e convertidos para o formato do sistema:
- Limpeza de datas
- Formatação de valores
- Validação de campos obrigatórios

### 4. Salvamento no Banco de Dados

Os dados processados são salvos no modelo `TerraReferencia`:

```python
TerraReferencia.objects.update_or_create(
    codigo=codigo,
    defaults={
        'nome': nome,
        'etnia': etnia,
        'estado': estado,
        'area_ha': area,
        # ... outros campos
    }
)
```

## Estrutura dos Dados

### TerraReferencia

Armazena os dados brutos da FUNAI:

- `nome`: Nome da Terra Indígena
- `codigo`: Código único da TI
- `etnia`: Etnia associada
- `estado`: Estado onde está localizada
- `fase`: Fase do processo de demarcação
- `area_ha`: Área em hectares
- `municipio`: Município onde está localizada
- `modalidade`: Modalidade da TI
- `coordenacao_regional`: Coordenação Regional da FUNAI
- `data_regularizada`: Data de regularização
- `data_homologada`: Data de homologação
- `data_declarada`: Data de declaração
- `data_delimitada`: Data de delimitação
- `data_em_estudo`: Data de início do estudo

### TIs

Armazena os dados cadastrados no sistema:

- `nome`: Nome da TI
- `codigo`: Código da TI
- `etnia`: Etnia
- `data_cadastro`: Data do cadastro
- `terra_referencia`: Relacionamento com TerraReferencia

## Considerações Técnicas

1. **Geometria**
   - Os dados são importados no sistema de coordenadas SIRGAS 2000 (EPSG:4674)
   - O sistema suporta polígonos complexos

2. **Performance**
   - A importação é otimizada para grandes volumes de dados
   - Os dados são processados em lotes
   - Índices espaciais são utilizados para consultas eficientes

3. **Segurança**
   - Conexão segura com o GeoServer
   - Validação dos dados recebidos
   - Log de todas as operações

## Troubleshooting

### Problemas Comuns

1. **Conexão com GeoServer**
   - Verificar URL do servidor
   - Confirmar credenciais
   - Checar firewall

2. **Dados Inconsistentes**
   - Validar formato dos dados
   - Verificar codificação
   - Confirmar sistema de coordenadas

3. **Erros de Importação**
   - Verificar logs
   - Confirmar permissões
   - Validar espaço em disco

## Suporte

Em caso de problemas:

1. Verificar logs do Django
2. Consultar documentação do GeoServer
3. Contatar equipe de desenvolvimento

## Próximos Passos

1. Implementar importação incremental
2. Adicionar suporte a mais formatos de dados
3. Melhorar sistema de logs
4. Implementar interface web para importação 