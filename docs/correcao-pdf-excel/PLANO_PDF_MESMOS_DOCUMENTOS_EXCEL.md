# Plano de correção — PDF com os mesmos documentos do Excel

Atualizado em: 2026-07-13 (America/Sao_Paulo).

## Objetivo

Fazer a exportação PDF acionada na página da cadeia dominial apresentar o
mesmo conjunto de documentos, na mesma ordem padrão, que a exportação Excel.
O Excel é a referência funcional considerada correta.

Esta entrega é independente da investigação maior chamada de “bagunça da
árvore”. Não inclui correções de identidade documental, limpeza de documentos
fantasma, alterações de hierarquia, migrações ou mudanças de dependências.

## Isolamento

- Branch de trabalho: `fix/pdf-documentos-igual-excel`.
- Base: `origin/main` no commit `29d04b7`.
- A branch `feature/identidade-documento-cartorio` e seu worktree permanecem
  intactos.
- Não usar `git add -A`; há artefatos locais que não pertencem à entrega.

## Diagnóstico confirmado

O problema não está no WeasyPrint nem no template deixando de imprimir itens.
Os botões PDF e Excel recebem listas diferentes antes da renderização:

1. O botão **Exportar PDF** em
   `templates/dominial/cadeia_dominial_tabela.html:304` aponta para
   `exportar_cadeia_dominial_pdf`.
2. Essa view, em `dominial/views/cadeia_dominial_views.py:290`, usa
   `CadeiaDominialTabelaService.get_cadeia_dominial_tabela()` e entrega ao
   template a chave `cadeia`.
3. O serviço de tabela parte do tronco principal sujeito às escolhas de sessão
   e o expande com importados (`cadeia_dominial_tabela_service.py:39-70`). Ele
   representa a visualização linear/selecionada, não a exportação completa.
4. O Excel, em `cadeia_dominial_views.py:392-403`, usa
   `CadeiaCompletaService.get_cadeia_completa()` e percorre a chave
   `cadeia_completa`.
5. Já existe a view `exportar_cadeia_completa_pdf`, em
   `cadeia_dominial_views.py:342-369`, que usa exatamente o mesmo
   `CadeiaCompletaService.get_cadeia_completa()` do Excel quando não recebe uma
   sequência personalizada.
6. O template `cadeia_completa_pdf.html` percorre
   `cadeia_completa -> tronco.documentos`, a mesma estrutura percorrida pelo
   Excel.
7. O fluxo de PDF com sequência personalizada já usa essa view completa em
   `static/dominial/js/cadeia_dominial_tabela.js:1171-1189`, mas o botão padrão
   não a utiliza.

Portanto, a divergência é de roteamento/fonte de dados: o botão padrão chama o
PDF de tabela, enquanto o Excel e o PDF completo compartilham a fonte correta.

## Decisão de implementação

Aplicar a correção mínima e reversível:

- Alterar o botão padrão **Exportar PDF** para apontar para a rota nomeada
  `exportar_cadeia_completa_pdf`.
- Manter `exportar_cadeia_dominial_pdf` e sua rota existentes por
  compatibilidade com links diretos e com a semântica de cadeia
  linear/selecionada. Não apagar nem reescrever esse fluxo nesta entrega.
- Manter o fluxo de sequência personalizada como está.
- Não duplicar no PDF a lógica do Excel e não converter manualmente contextos:
  ambos devem continuar consumindo `CadeiaCompletaService` como fonte única.

Com isso, a exportação padrão em PDF e o Excel percorrem o mesmo contexto
produzido por `get_cadeia_completa()`, preservando os IDs e a ordem dos
documentos. A diferença fica restrita à apresentação (HTML/PDF versus XLSX).

## Plano de execução

### P01 — Registrar a regressão antes da mudança

Adicionar testes focados para demonstrar que o botão padrão atualmente aponta
para o endpoint de tabela e fixar o contrato desejado:

- renderizar a página da cadeia e verificar que o link **Exportar PDF** resolve
  para `exportar_cadeia_completa_pdf`;
- verificar que o link **Exportar Excel** continua resolvendo para
  `exportar_cadeia_dominial_excel`;
- preservar a rota antiga `exportar_cadeia_dominial_pdf`, garantindo que links
  diretos não passem a retornar 404.

### P02 — Fixar a paridade da fonte de dados

Adicionar teste de view com `CadeiaCompletaService` e contexto controlados por
mock para confirmar que:

- o PDF completo sem `?sequencia=` chama `get_cadeia_completa(tis_id,
  imovel_id)`;
- o Excel chama o mesmo método com os mesmos IDs;
- o PDF renderiza `dominial/cadeia_completa_pdf.html` com a estrutura
  `cadeia_completa` retornada pelo serviço;
- o caminho de sequência personalizada continua chamando
  `get_cadeia_completa_com_sequencia_personalizada()`.

O teste não deve comparar bytes de PDF com bytes de Excel. A invariável útil é
a igualdade da sequência de IDs fornecida aos dois renderizadores.

### P03 — Alterar somente o ponto de entrada padrão

Em `templates/dominial/cadeia_dominial_tabela.html`, trocar a URL do botão
padrão de `exportar_cadeia_dominial_pdf` para
`exportar_cadeia_completa_pdf`. Se necessário para evitar ambiguidade na
interface, ajustar apenas o texto para **Exportar PDF completo**.

Não alterar services, models, migrations, requisitos Python ou o algoritmo da
árvore nesta tarefa.

### P04 — Validar automaticamente

Executar, no mínimo:

```bash
python manage.py test <modulo_de_teste_da_exportacao>
python manage.py check
python manage.py makemigrations --check --dry-run
git diff --check
```

Os testes devem cobrir:

- cadeia com um único documento;
- cadeia com documentos importados/ramificações, na qual o PDF antigo omitia
  pelo menos um documento mostrado no Excel;
- igualdade exata da lista ordenada de IDs do PDF padrão e do Excel;
- manutenção do PDF com sequência personalizada;
- respostas com `Content-Type` esperado (`application/pdf` e formato XLSX).

### P05 — Homologar no servidor de teste

1. Publicar a branch e atualizá-la no servidor de teste via Git.
2. Usar um imóvel real em que a divergência já foi observada.
3. Gerar PDF e Excel pelo mesmo painel, sem sequência personalizada.
4. Anotar, na ordem, tipo, número, cartório e ID de cada documento.
5. Confirmar que as duas listas são idênticas e que o conteúdo de cada
   lançamento permanece legível no PDF.
6. Repetir com uma cadeia simples e com uma cadeia que contenha importados.
7. Confirmar que o modal de sequência personalizada ainda gera somente os
   documentos escolhidos e na ordem escolhida.
8. Verificar logs do `web` durante as exportações e confirmar ausência de erro
   do WeasyPrint.

## Critérios de aceite

- O botão PDF padrão e o botão Excel usam `CadeiaCompletaService` como fonte.
- PDF e Excel sem sequência personalizada contêm os mesmos IDs, na mesma
  ordem.
- Documentos importados presentes no Excel também aparecem no PDF.
- O fluxo de sequência personalizada continua funcionando.
- A rota antiga de PDF permanece disponível para compatibilidade.
- Nenhuma migration é criada ou aplicada.
- Nenhuma mudança da branch `feature/identidade-documento-cartorio` entra no
  diff.

## Riscos e limites

- `CadeiaCompletaService` depende atualmente do serviço de árvore. Eventuais
  documentos incorretos produzidos por essa árvore aparecerão igualmente no
  Excel e no PDF; corrigir essa origem pertence ao plano separado da “bagunça
  da árvore”.
- Igualdade entre formatos não significa que a cadeia está semanticamente
  correta; significa apenas que o PDF passa a refletir a fonte considerada
  correta pelo usuário.
- A view antiga usa escolhas armazenadas na sessão. Ao manter sua rota, não se
  altera o comportamento de consumidores que dependam dessa exportação
  linear.
- O tratamento atual de exceções devolve HTML com status 200 em alguns erros de
  geração. Melhorar status/logging é recomendável em uma entrega separada para
  não ampliar este fix.

## Fora de escopo

- Busca de documentos por número isolado e homônimos entre cartórios.
- Criação ou remoção de documentos fantasma.
- Ordenação semântica da árvore e ramos repetidos.
- Migrações 0043–0049 da feature de identidade canônica.
- Refatoração geral das duas views de PDF.
- Atualização de WeasyPrint/pydyf, já estabilizados em `main`.
