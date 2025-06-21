# Convenção de Commits

Este documento define as convenções para mensagens de commit neste projeto.

## Formato da Mensagem

```
<tipo>(<escopo>): <descrição>

[corpo opcional]

[rodapé opcional]
```

## Tipos de Commit

### ✨ `feat`
Nova funcionalidade para o usuário
```
feat(auth): adiciona autenticação com JWT
feat(ui): implementa visualização em árvore
```

### 🐛 `fix`
Correção de bug
```
fix(api): corrige erro 404 nas URLs de autenticação
fix(ui): corrige posicionamento dos cards na árvore
```

### 📝 `docs`
Mudanças na documentação
```
docs(readme): atualiza instruções de instalação
docs(api): adiciona documentação dos endpoints
```

### 🎨 `style`
Mudanças que não afetam o código (espaços em branco, formatação, etc.)
```
style(ui): ajusta espaçamento entre elementos
style(css): padroniza cores do tema
```

### ♻️ `refactor`
Refatoração de código que não corrige bug nem adiciona funcionalidade
```
refactor(models): reorganiza relacionamentos entre modelos
refactor(views): simplifica lógica de validação
```

### ⚡ `perf`
Melhoria de performance
```
perf(query): otimiza consultas do banco de dados
perf(ui): reduz tempo de carregamento da árvore
```

### ✅ `test`
Adição ou correção de testes
```
test(api): adiciona testes para endpoints de documento
test(models): corrige testes de validação
```

### 🔧 `chore`
Mudanças em arquivos de build, configuração, etc.
```
chore(deps): atualiza dependências do projeto
chore(ci): configura GitHub Actions
```

## Escopos

Use escopos específicos para identificar a área do código afetada:

- `auth` - Autenticação e autorização
- `api` - Endpoints da API
- `ui` - Interface do usuário
- `models` - Modelos de dados
- `admin` - Interface administrativa
- `migrations` - Migrações do banco
- `docs` - Documentação
- `test` - Testes
- `ci` - Integração contínua
- `deps` - Dependências

## Descrição

- Use imperativo: "adiciona" não "adicionado"
- Não capitalize a primeira letra
- Não termine com ponto
- Máximo de 72 caracteres

## Corpo (Opcional)

Use para explicar o que e por que, não como:
```
feat(auth): implementa autenticação OAuth2

- Adiciona suporte ao Google OAuth2
- Implementa refresh tokens
- Adiciona middleware de autenticação

Resolve: #123
```

## Rodapé (Opcional)

Use para referenciar issues, breaking changes, etc.:
```
feat(api): remove endpoint deprecated

BREAKING CHANGE: O endpoint /api/v1/old foi removido
Use /api/v2/new como alternativa.

Closes: #456
```

## Exemplos

### Commit Simples
```
feat(ui): adiciona zoom na visualização da árvore
```

### Commit com Corpo
```
fix(api): corrige erro de validação em documentos

- Valida CPF antes de salvar
- Adiciona mensagens de erro mais claras
- Corrige problema com caracteres especiais

Resolve: #789
```

### Commit com Breaking Change
```
refactor(models): reorganiza estrutura de documentos

BREAKING CHANGE: O campo 'numero' foi renomeado para 'numero_documento'
Atualize suas migrações e código que usa este campo.

Closes: #101
```

## Dicas

1. **Seja específico**: Evite mensagens vagas como "corrige bug"
2. **Use escopos**: Ajude a identificar rapidamente a área afetada
3. **Seja consistente**: Mantenha o mesmo padrão em todo o projeto
4. **Pense no futuro**: Outros desenvolvedores vão ler essas mensagens
5. **Use imperativo**: Como se estivesse dando uma ordem

## Ferramentas

Para ajudar a seguir esta convenção:

- **Commitizen**: Ferramenta para criar commits padronizados
- **Husky**: Git hooks para validar commits
- **Conventional Changelog**: Gera changelog automaticamente

## Configuração do Commitizen

Adicione ao `package.json`:
```json
{
  "config": {
    "commitizen": {
      "path": "cz-conventional-changelog"
    }
  }
}
```

Use `git cz` em vez de `git commit` para commits padronizados. 