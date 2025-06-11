# Importação de Terras Indígenas da FUNAI

Este documento descreve o processo de importação de Terras Indígenas (TIs) do GeoServer da FUNAI para o sistema Cadeia Dominial.

## Visão Geral

O sistema permite a importação automática de dados de terras indígenas diretamente do GeoServer da FUNAI, facilitando o cadastro inicial das TIs no sistema. O processo é realizado através de um script Python que:

1. Conecta ao GeoServer da FUNAI
2. Obtém os dados das TIs
3. Processa e formata os dados
4. Salva no banco de dados local

## Arquivos Envolvidos

1. `dominial/management/commands/import_funai_tis.py`
   - Script principal de importação
   - Gerencia a conexão com o GeoServer
   - Processa os dados recebidos

2. `dominial/models.py`
   - Modelo `TerraReferencia` para armazenar dados da FUNAI
   - Modelo `TIs` para dados cadastrados no sistema

## Como Funciona

### 1. Conexão com o GeoServer

O script se conecta ao GeoServer da FUNAI usando a biblioteca `owslib`:

```python
from owslib.wfs import WebFeatureService

wfs = WebFeatureService(
    url='https://geoserver.funai.gov.br/geoserver/ows',
    version='1.1.0'
)
```

### 2. Obtenção dos Dados

Os dados são obtidos através de uma requisição WFS (Web Feature Service):

```python
response = wfs.getfeature(
    typename='funai:ti_sirgas2000_quilombola',
    srsname='EPSG:4326',
    outputFormat='application/json'
)
```

### 3. Processamento dos Dados

Os dados recebidos são processados e convertidos para o formato do sistema:

- Nome da TI
- Código
- Etnia
- Estado
- Fase
- Área (em hectares)
- Geometria (polígono)

### 4. Salvamento no Banco de Dados

Os dados processados são salvos no modelo `TerraReferencia`:

```python
TerraReferencia.objects.create(
    nome=ti_nome,
    codigo=ti_codigo,
    etnia=ti_etnia,
    estado=ti_estado,
    fase=ti_fase,
    area_ha=ti_area,
    geometria=ti_geometria
)
```

## Como Usar

### Importação Manual

Para importar os dados manualmente, execute o comando:

```bash
python manage.py import_funai_tis
```

### Importação Automática

O sistema pode ser configurado para importar automaticamente através de:

1. Tarefas agendadas (cron jobs)
2. Webhooks do GeoServer
3. API REST

## Estrutura dos Dados

### TerraReferencia

Armazena os dados brutos da FUNAI:

- `nome`: Nome da Terra Indígena
- `codigo`: Código único da TI
- `etnia`: Etnia associada
- `estado`: Estado onde está localizada
- `fase`: Fase do processo de demarcação
- `area_ha`: Área em hectares
- `geometria`: Polígono da TI (GeoJSON)

### TIs

Armazena os dados cadastrados no sistema:

- `nome`: Nome da TI
- `codigo`: Código da TI
- `etnia`: Etnia
- `data_cadastro`: Data do cadastro
- `terra_referencia`: Relacionamento com TerraReferencia

## Considerações Técnicas

1. **Geometria**
   - Os dados são importados no sistema de coordenadas SIRGAS 2000
   - A geometria é armazenada em formato GeoJSON
   - O sistema suporta polígonos complexos

2. **Performance**
   - A importação é otimizada para grandes volumes de dados
   - Os dados são processados em lotes
   - Índices espaciais são utilizados para consultas eficientes

3. **Segurança**
   - Conexão segura com o GeoServer
   - Validação dos dados recebidos
   - Log de todas as operações

## Manutenção

### Atualização dos Dados

Os dados podem ser atualizados de duas formas:

1. **Incremental**: Atualiza apenas TIs modificadas
2. **Completa**: Recria todos os registros

### Limpeza

Para limpar dados obsoletos:

```bash
python manage.py import_funai_tis --clean
```

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

1. Verificar logs em `logs/import_funai.log`
2. Consultar documentação do GeoServer
3. Contatar equipe de desenvolvimento

## Próximos Passos

1. Implementar importação incremental
2. Adicionar suporte a mais formatos de dados
3. Melhorar sistema de logs
4. Implementar interface web para importação 