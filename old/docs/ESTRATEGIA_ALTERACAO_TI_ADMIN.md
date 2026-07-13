# Estratégia de Implementação: Correção de TI no Admin

## 📋 Resumo

Foi implementada uma ferramenta no painel administrativo do Django para permitir que administradores corrijam a Terra Indígena (TI) de um imóvel que foi cadastrado incorretamente.

## 🎯 Objetivo

Permitir que administradores corrijam a TI de um imóvel diretamente no painel admin, com:
- Validações de segurança
- Informações sobre impactos da mudança
- Registro de auditoria da alteração
- Interface intuitiva e clara

## 🏗️ Arquitetura da Solução

### 1. **ImovelAdmin Customizado** (`dominial/admin.py`)

Substituiu o registro básico do modelo `Imovel` por uma classe `ImovelAdmin` customizada que inclui:

#### Funcionalidades Principais:
- **Listagem melhorada**: Mostra informações sobre documentos e lançamentos relacionados
- **View customizada**: Página dedicada para alteração de TI com confirmação
- **Validações**: Verifica se há dados relacionados antes de permitir a mudança
- **Auditoria**: Registra a alteração no campo `observacoes` do imóvel

#### Campos e Filtros:
- `list_display`: Matrícula, nome, TI, proprietário, cartório, tipo documento, arquivado, data cadastro, info documentos/lançamentos
- `list_filter`: TI, tipo documento, arquivado, cartório, data cadastro
- `search_fields`: Matrícula, nome, TI, proprietário, cartório

### 2. **View de Alteração de TI** (`alterar_ti_view`)

View customizada que:
1. **Coleta informações** sobre o imóvel e dados relacionados
2. **Valida a mudança** antes de permitir
3. **Mostra avisos** se houver documentos/lançamentos
4. **Registra a alteração** no campo observações com:
   - Data e hora
   - Usuário que fez a alteração
   - TI anterior e nova
   - Motivo (opcional)

### 3. **Templates**

#### `templates/admin/dominial/imovel/alterar_ti.html`
- Página de confirmação e alteração
- Mostra informações do imóvel
- Lista documentos relacionados (se houver)
- Formulário para selecionar nova TI
- Campo opcional para motivo da alteração

#### `templates/admin/dominial/imovel/change_form.html`
- Template customizado para página de edição do imóvel
- Adiciona botão "Alterar Terra Indígena (TI)" na seção de ferramentas administrativas

## 🔒 Validações e Segurança

### Validações Implementadas:

1. **Verificação de TI selecionada**: Não permite selecionar a TI atual
2. **Avisos para dados relacionados**: 
   - Se houver documentos ou lançamentos, mostra aviso claro
   - Informa sobre possíveis impactos (URLs, relatórios, buscas)
3. **Confirmação dupla**: 
   - Confirmação JavaScript no botão
   - Confirmação no formulário antes de submeter
4. **Registro de auditoria**: Toda alteração é registrada nas observações

### Impactos Identificados:

⚠️ **Atenção**: A alteração da TI pode afetar:
- **URLs**: Todas as URLs do sistema incluem `tis_id`, então links salvos podem quebrar
- **Relatórios**: Relatórios filtrados por TI podem não incluir o imóvel na TI antiga
- **Buscas**: Buscas por TI podem não encontrar o imóvel na TI antiga
- **Navegação**: Usuários podem ter bookmarks ou links diretos que não funcionarão mais

## 📝 Fluxo de Uso

1. **Acesso**: Admin → Imóveis → Selecionar um imóvel → Botão "Alterar Terra Indígena (TI)"
2. **Visualização**: 
   - Ver informações do imóvel
   - Ver quantidade de documentos e lançamentos relacionados
   - Ver lista de documentos (se houver)
3. **Seleção**: 
   - Escolher nova TI do dropdown
   - (Opcional) Informar motivo da alteração
4. **Confirmação**: 
   - Confirmar a alteração
   - Sistema valida e registra a mudança
5. **Resultado**: 
   - Mensagem de sucesso
   - Redirecionamento para página de edição do imóvel
   - Alteração registrada nas observações

## 🔍 Informações Exibidas

### Na Listagem de Imóveis:
- Coluna "Documentos/Lançamentos" mostra:
  - ✓ Verde: Sem documentos/lançamentos (alteração segura)
  - 📄 Laranja: Quantidade de documentos e lançamentos

### Na Página de Alteração:
- **Informações do Imóvel**: Matrícula, nome, proprietário, TI atual, cartório
- **Avisos**: 
  - Verde: Sem dados relacionados (seguro)
  - Amarelo: Com dados relacionados (atenção necessária)
- **Lista de Documentos**: Primeiros 10 documentos relacionados (se houver)

## 📊 Registro de Auditoria

Toda alteração é registrada no campo `observacoes` do imóvel no formato:

```
--- ALTERAÇÃO DE TI ---
Data: DD/MM/YYYY HH:MM
Usuário: Nome do Usuário
TI Anterior: Nome da TI (ID: X)
TI Nova: Nome da TI (ID: Y)
Motivo: [se informado]
---
```

## 🛠️ Arquivos Modificados/Criados

### Modificados:
- `dominial/admin.py`: Adicionado `ImovelAdmin` customizado

### Criados:
- `templates/admin/dominial/imovel/alterar_ti.html`: Template da página de alteração
- `templates/admin/dominial/imovel/change_form.html`: Template customizado do formulário de edição

## ✅ Testes Recomendados

1. **Teste básico**: Alterar TI de imóvel sem documentos/lançamentos
2. **Teste com dados**: Alterar TI de imóvel com documentos e lançamentos
3. **Teste de validação**: Tentar selecionar a TI atual
4. **Teste de auditoria**: Verificar se a alteração foi registrada nas observações
5. **Teste de permissões**: Verificar se apenas admins podem acessar

## 🚀 Melhorias Futuras (Opcional)

1. **Modelo de Auditoria Dedicado**: Criar tabela específica para log de alterações
2. **Notificações**: Enviar email para administradores sobre alterações críticas
3. **Histórico Visual**: Mostrar histórico de alterações de TI no admin
4. **Validação de Integridade**: Verificar se a mudança não quebra cadeias dominiais
5. **Reversão**: Permitir reverter alterações recentes

## 📚 Referências

- Django Admin Customization: https://docs.djangoproject.com/en/stable/ref/contrib/admin/
- Django Admin Views: https://docs.djangoproject.com/en/stable/ref/contrib/admin/#django.contrib.admin.ModelAdmin.get_urls
- Django Templates: https://docs.djangoproject.com/en/stable/topics/templates/

---

**Data de Implementação**: 2025
**Versão**: 1.0.0
