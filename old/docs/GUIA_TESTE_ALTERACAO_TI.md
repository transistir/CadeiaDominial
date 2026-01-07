# 🧪 Guia de Teste: Alteração de TI no Admin

## 📋 Pré-requisitos

1. **Servidor Django rodando**
   ```bash
   # Se estiver usando ambiente virtual
   source venv/bin/activate  # ou o caminho do seu venv
   
   # Iniciar servidor de desenvolvimento
   python manage.py runserver
   ```

2. **Usuário admin criado**
   - Você precisa ter um usuário com permissões de staff/superuser
   - Se não tiver, crie com:
   ```bash
   python manage.py createsuperuser
   ```

3. **Dados de teste no banco**
   - Pelo menos uma Terra Indígena (TI) cadastrada
   - Pelo menos um Imóvel cadastrado
   - (Opcional) Imóveis com documentos e lançamentos para testar avisos

---

## 🚀 Passo a Passo para Testar

### 1. Iniciar o Servidor

```bash
cd /home/hiure/gits/CadeiaDominial
python manage.py runserver
```

Você verá algo como:
```
Starting development server at http://127.0.0.1:8000/
```

### 2. Acessar o Admin

Abra seu navegador e acesse:

```
http://127.0.0.1:8000/admin/
```

ou

```
http://localhost:8000/admin/
```

**Nota:** O sistema redireciona automaticamente para `/accounts/login/` se você não estiver logado.

### 3. Fazer Login

- Use suas credenciais de admin (usuário e senha)
- Após login, você será redirecionado para o painel admin

### 4. Navegar até Imóveis

No painel admin, você verá uma lista de modelos. Procure por:

**"IMÓVEIS"** ou **"Imóveis"** (na seção DOMINIAL)

Clique em **"Imóveis"**

### 5. Selecionar um Imóvel

Na listagem de imóveis, você verá:
- Matrícula
- Nome
- Terra Indígena (TI atual)
- Proprietário
- Cartório
- **Documentos/Lançamentos** (nova coluna!)

Clique em um imóvel para editá-lo.

### 6. Acessar a Ferramenta de Alteração de TI

Na página de edição do imóvel:

1. Role a página até o final
2. Procure pela seção **"🔧 Ferramentas Administrativas"** (fundo amarelo)
3. Clique no botão **"🔄 Alterar Terra Indígena (TI)"**

### 7. Página de Alteração de TI

Você verá:

#### **Informações do Imóvel**
- Matrícula
- Nome
- Proprietário
- **TI Atual** (destacada em vermelho)
- Cartório

#### **Avisos**
- **Verde**: Se não houver documentos/lançamentos → "Alteração segura"
- **Amarelo**: Se houver documentos/lançamentos → Aviso sobre impactos

#### **Formulário**
- Dropdown para selecionar nova TI
- Campo opcional para motivo da alteração

### 8. Testar Cenários

#### **Cenário 1: Imóvel sem dados relacionados**
1. Selecione um imóvel sem documentos/lançamentos
2. Você verá aviso verde: "✓ Este imóvel não possui documentos ou lançamentos"
3. Selecione uma nova TI diferente da atual
4. (Opcional) Preencha o motivo
5. Clique em "Confirmar Alteração de TI"
6. Confirme no popup
7. ✅ Deve mostrar mensagem de sucesso
8. Verifique o campo "Observações" do imóvel - deve ter o registro da alteração

#### **Cenário 2: Imóvel com dados relacionados**
1. Selecione um imóvel que tenha documentos ou lançamentos
2. Você verá aviso amarelo com informações sobre impactos
3. Pode expandir para ver lista de documentos
4. Selecione uma nova TI
5. Preencha o motivo (recomendado)
6. Confirme a alteração
7. ✅ Deve mostrar aviso + mensagem de sucesso
8. Verifique as observações

#### **Cenário 3: Validação - TI atual**
1. Tente selecionar a mesma TI que o imóvel já possui
2. O sistema deve mostrar: "O imóvel já está associado a esta Terra Indígena"
3. ✅ Validação funcionando!

#### **Cenário 4: Sem seleção**
1. Não selecione nenhuma TI
2. Tente confirmar
3. ✅ Deve mostrar erro: "Por favor, selecione uma nova Terra Indígena"

### 9. Verificar Registro de Auditoria

Após alterar a TI:

1. Volte para a página de edição do imóvel
2. Role até o campo **"Observações"**
3. Expanda se estiver colapsado
4. Você deve ver algo como:

```
--- ALTERAÇÃO DE TI ---
Data: 15/01/2025 14:30
Usuário: Nome do Usuário
TI Anterior: Nome da TI Anterior (ID: 1)
TI Nova: Nome da TI Nova (ID: 2)
Motivo: Correção de cadastro - TI incorreta
---
```

---

## 🔍 Verificações Adicionais

### Na Listagem de Imóveis

Verifique a coluna **"Documentos/Lançamentos"**:
- ✓ Verde: Sem dados relacionados
- 📄 Laranja: Quantidade de documentos e lançamentos

### Filtros e Buscas

Teste os filtros na listagem:
- Filtrar por TI
- Filtrar por tipo de documento
- Buscar por matrícula
- Buscar por nome da TI

### Navegação

Após alterar a TI:
- O imóvel deve aparecer na nova TI quando você filtrar
- Links antigos com `tis_id` antigo podem não funcionar (comportamento esperado)

---

## 🐛 Troubleshooting

### Problema: Botão não aparece
**Solução:**
- Verifique se você está logado como admin/staff
- Verifique se está na página de edição (não na listagem)
- Role até o final da página
- Limpe o cache do navegador (Ctrl+F5)

### Problema: Erro 404 ao clicar no botão
**Solução:**
- Verifique se o servidor está rodando
- Verifique se a URL está correta: `/admin/dominial/imovel/<id>/alterar-ti/`
- Verifique os logs do servidor Django

### Problema: Template não encontrado
**Solução:**
- Verifique se os templates estão em:
  - `templates/admin/dominial/imovel/alterar_ti.html`
  - `templates/admin/dominial/imovel/change_form.html`
- Reinicie o servidor Django

### Problema: Erro ao salvar
**Solução:**
- Verifique os logs do servidor
- Verifique se há erros de validação no formulário
- Verifique se a TI selecionada existe no banco

---

## 📸 Screenshots Esperados

### 1. Listagem de Imóveis
- Coluna "Documentos/Lançamentos" visível
- Filtros funcionando

### 2. Página de Edição
- Seção "Ferramentas Administrativas" no final
- Botão "Alterar Terra Indígena (TI)" visível

### 3. Página de Alteração
- Informações do imóvel
- Avisos (verde ou amarelo)
- Formulário de seleção
- Botões de ação

### 4. Após Alteração
- Mensagem de sucesso
- Observações atualizadas

---

## ✅ Checklist de Teste

- [ ] Servidor Django rodando
- [ ] Login no admin funcionando
- [ ] Listagem de imóveis acessível
- [ ] Coluna "Documentos/Lançamentos" visível
- [ ] Botão "Alterar TI" aparece na edição
- [ ] Página de alteração carrega corretamente
- [ ] Informações do imóvel são exibidas
- [ ] Avisos aparecem corretamente (verde/amarelo)
- [ ] Dropdown de TIs funciona
- [ ] Validação de TI atual funciona
- [ ] Validação de seleção vazia funciona
- [ ] Alteração salva com sucesso
- [ ] Observações são atualizadas
- [ ] Mensagem de sucesso aparece
- [ ] Redirecionamento funciona

---

## 🎯 Testes Recomendados por Prioridade

### Alta Prioridade (Testar Primeiro)
1. ✅ Alterar TI de imóvel sem dados relacionados
2. ✅ Verificar registro nas observações
3. ✅ Validação de TI atual

### Média Prioridade
4. ✅ Alterar TI de imóvel com documentos
5. ✅ Verificar avisos e impactos
6. ✅ Testar com motivo preenchido

### Baixa Prioridade (Opcional)
7. ✅ Testar com múltiplas alterações
8. ✅ Verificar filtros após alteração
9. ✅ Testar navegação com URLs antigas

---

## 📝 Notas Importantes

1. **Backup**: Antes de testar em produção, faça backup do banco de dados
2. **Ambiente de Teste**: Prefira testar em ambiente de desenvolvimento primeiro
3. **Dados Reais**: Use dados de teste, não dados de produção
4. **Reversão**: Se precisar reverter, você pode alterar novamente ou editar manualmente o campo `terra_indigena_id`

---

**Boa sorte com os testes! 🚀**

Se encontrar algum problema, verifique os logs do servidor Django e os erros no console do navegador (F12).
