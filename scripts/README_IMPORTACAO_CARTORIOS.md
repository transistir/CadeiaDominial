# Importação de Cartórios - Cadeia Dominial

Este diretório contém scripts para importar cartórios de registro de imóveis de todos os estados do Brasil.

## 📋 Scripts Disponíveis

### 1. `importar_cartorios_completo.sh`
Script principal para importar todos os cartórios do Brasil de forma automatizada.

**Características:**
- ✅ Verifica status dos containers Docker
- ✅ Cria backup automático do banco antes da importação
- ✅ Mostra estatísticas antes e depois da importação
- ✅ Opção de executar em background
- ✅ Logs coloridos e informativos
- ✅ Verifica cartórios existentes para evitar duplicação

### 2. `importar_todos_cartorios.py`
Script Python que executa a importação de todos os estados.

**Características:**
- ✅ Importa cartórios de todos os 27 estados do Brasil
- ✅ Pula estados que já possuem cartórios
- ✅ Delays entre importações para evitar rate limiting
- ✅ Logs detalhados salvos em arquivo
- ✅ Relatório final com estatísticas

## 🚀 Como Usar

### Opção 1: Script Completo (Recomendado)
```bash
# No servidor, no diretório do projeto
./scripts/importar_cartorios_completo.sh
```

### Opção 2: Script Python Direto
```bash
# Executar dentro do container
docker exec cadeia_dominial_web python /app/scripts/importar_todos_cartorios.py
```

### Opção 3: Importação Individual por Estado
```bash
# Importar um estado específico
docker exec cadeia_dominial_web python manage.py importar_cartorios_estado SP
```

## 📊 Estados que Serão Importados

O script importa cartórios de todos os 27 estados do Brasil:

**Região Norte:** AC, AP, AM, PA, RO, RR, TO
**Região Nordeste:** AL, BA, CE, MA, PB, PE, PI, RN, SE
**Região Centro-Oeste:** DF, GO, MT, MS
**Região Sudeste:** ES, MG, RJ, SP
**Região Sul:** PR, RS, SC

## ⏱️ Tempo Estimado

- **Por estado:** 5-15 minutos (dependendo do número de cidades)
- **Total:** 3-6 horas para todos os estados
- **Em background:** Pode ser executado sem manter a sessão SSH ativa

## 📝 Logs e Monitoramento

### Logs do Script
- **Arquivo:** `importacao_cartorios.log`
- **Acompanhar progresso:** `tail -f importacao_cartorios.log`

### Logs do Django
- **Container web:** `docker-compose logs web`
- **Container nginx:** `docker-compose logs nginx`

## 🔧 Verificações Automáticas

O script verifica automaticamente:

1. **Status dos containers** - Garante que estão rodando e saudáveis
2. **Cartórios existentes** - Evita importação desnecessária
3. **Backup do banco** - Cria backup antes da importação
4. **Rate limiting** - Delays entre requisições para evitar bloqueios

## 📈 Estatísticas

### Antes da Importação
- Total de cartórios no banco
- Cartórios por estado
- Estados que já possuem dados

### Durante a Importação
- Progresso por estado
- Novos cartórios importados
- Erros e tentativas de retry

### Após a Importação
- Total final de cartórios
- Estatísticas por estado
- Estados com sucesso/erro

## ⚠️ Considerações Importantes

### Rate Limiting
- O script inclui delays entre requisições
- Retry automático em caso de erro 403
- Pode ser interrompido e retomado

### Dados Importados
- Apenas cartórios de **registro de imóveis**
- Filtra automaticamente outros tipos de cartório
- Usa `update_or_create` para evitar duplicatas

### Backup
- Backup automático antes da importação
- Arquivo: `backup_cartorios_YYYYMMDD_HHMMSS.sql`
- Recomendado manter backups por segurança

## 🛠️ Solução de Problemas

### Container não saudável
```bash
# Verificar status
docker-compose ps

# Reiniciar se necessário
docker-compose restart web
```

### Erro de permissão
```bash
# Dar permissão de execução
chmod +x scripts/importar_cartorios_completo.sh
```

### Importação interrompida
```bash
# Verificar log
tail -f importacao_cartorios.log

# Retomar importação (pula estados já importados)
./scripts/importar_cartorios_completo.sh
```

### Verificar cartórios importados
```bash
# Total de cartórios
docker exec cadeia_dominial_web python manage.py shell -c "from dominial.models import Cartorios; print(Cartorios.objects.count())"

# Por estado
docker exec cadeia_dominial_web python manage.py shell -c "from dominial.models import Cartorios; from collections import Counter; estados = Cartorios.objects.values_list('estado', flat=True); contador = Counter(estados); [print(f'{estado}: {count}') for estado, count in sorted(contador.items())]"
```

## 📞 Suporte

Em caso de problemas:
1. Verifique os logs em `importacao_cartorios.log`
2. Confirme que os containers estão rodando
3. Verifique a conectividade com a internet
4. Consulte a documentação do projeto principal 