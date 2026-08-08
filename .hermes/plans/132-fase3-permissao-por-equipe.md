# Plano — Fase 3: permissão por equipe como modelo primário

## Resumo executivo

Esta fase consolida a equipe como unidade operacional de concessão de acesso. O acesso efetivo continua sendo calculado dinamicamente e continua sendo a união de TIs herdadas das equipes com exceções diretas em `UserTI`, mas a interface passa a conduzir o superusuário primeiro para **equipe → TIs**. A atribuição direta a usuário permanece disponível como exceção secundária, conforme D6, e deve ser visualmente separada e desestimulada.

Para representar “equipe D vê todas as TIs”, recomenda-se acrescentar a `GrupoAcesso` a propriedade explícita `acesso_todas_tis`. Uma equipe global não gera centenas de linhas em `GroupTI`: seus membros veem o queryset inteiro de TIs e, por derivação, todos os imóveis dessas TIs. Uma TI cadastrada no futuro entra automaticamente no escopo dessa equipe. Essa semântica deve aparecer na confirmação e na tela da equipe.

A gestão permanece no `/admin/`, exclusiva de superusuário, preservando D3. O fluxo atual já oferece atribuição em massa, edição de membros e TIs na equipe, atalhos nos changelists e edição TI → equipes; a fase melhora essas superfícies em vez de criar uma segunda administração no app. A listagem de equipes passa a distinguir equipes globais e a manter as contagens de membros e TIs já existentes.

A criação manual de TI no app passa a exigir o perfil **Administrador** (ou superusuário), tanto na view quanto no template. Isso altera de forma deliberada D4: Editor e Administrador continuam podendo escrever nos objetos das TIs acessíveis, porém cadastrar uma nova TI torna-se um segundo diferencial do Administrador, além de entrar no `/admin/`. `is_staff` isolado não será o critério de negócio.

Não mudam: acesso sempre por TI inteira (D2); superusuário como único gestor de atribuições (D3); vínculo de equipe e acesso calculados por join, sem materialização; revogação imediata ao sair de equipe; `GroupTI` para equipes de escopo parcial; `UserTI` como exceção; segregação derivada para imóveis, documentos, lançamentos e pessoas; legado `UserImovel` e sua estratégia de retirada; nem os gates de segurança já aprovados.

## Decisões de produto e design

### F1. Equipe é o caminho primário; usuário direto é exceção

**Opções avaliadas:** remover `UserTI`; manter equipe e usuário com o mesmo destaque; manter `UserTI`, mas separar os fluxos.

**Recomendação:** manter `UserTI` por compatibilidade e casos excepcionais, sem ampliar sua semântica, mas apresentar primeiro a gestão por equipe. Na atribuição em massa, “Equipes” vem antes e “Usuários (exceção)” fica em seção recolhida, com aviso de que a preferência é criar/usar uma equipe. Na página do usuário, TIs diretas devem ser rotuladas como exceções. Não remover dados nem capacidade previstos em D6.

**Trade-off:** ainda existem duas fontes de acesso, porém isso evita migração destrutiva e preserva exceções legítimas. A UI e relatórios deixam claro de onde cada acesso veio.

### F2. Equipe global é uma propriedade, não 600 vínculos

**Opções avaliadas:**

1. Criar 600+ `GroupTI`: reutiliza tudo, mas torna a operação pesada, produz muitas linhas redundantes e exige sincronizar toda TI futura.
2. Nome reservado, por exemplo “Equipe Global”: não exige migration, mas é frágil a renome e cria regra escondida.
3. Uma linha sentinela em `GroupTI` com `tis=NULL`: mistura “todas” com “uma”, exige retirar a obrigatoriedade da FK e aumenta a chance de consultas incorretas.
4. Campo explícito na metadata da equipe: regra legível, barata e consultável.

**Recomendação:** adicionar `GrupoAcesso.acesso_todas_tis = BooleanField(default=False, verbose_name='Acesso a todas as TIs')`. O campo só é válido para `tipo=EQUIPE`; perfis protegidos nunca podem ativá-lo. O nome da equipe continua livre.

Semântica canônica revisada:

```text
equipe_global(u) = existe equipe de u com GrupoAcesso(tipo='equipe', acesso_todas_tis=True)

tis_atribuidas(u) =
    todas as TIs, se superuser(u) ou equipe_global(u)
    senão TIs de GroupTI das equipes de u ∪ TIs de UserTI(u)
```

Consequentemente, “todas” inclui TIs sem imóveis e toda TI cadastrada depois da concessão. Não há job, signal ou criação automática de `GroupTI`. Desmarcar a flag revoga imediatamente o acesso global; permanecem válidos eventuais `GroupTI` explícitos e `UserTI`.

**Trade-off:** o campo cria um caminho adicional na query de autorização, mas evita crescimento e sincronização. Ele deve ser centralizado em `managers.py`, nunca reimplementado em views.

### F3. Ativação global exige confirmação explícita

Na tela da equipe, ativar a flag deve exibir e exigir confirmação: “Esta equipe verá todas as TIs atuais, todas as TIs futuras e todos os imóveis atuais e futuros dessas TIs”. A prévia informa quantidade atual de TIs, imóveis e membros afetados. A mudança fica em `LogEntry`, incluindo valor anterior/novo e contagens.

Ao ativar uma equipe global que já possui `GroupTI`, não apagar os vínculos automaticamente: eles são redundantes durante a vigência da flag, mas funcionam como escopo residual caso ela seja desmarcada. Oferecer uma ação separada de limpeza somente depois de prévia, nunca como efeito colateral. No MVP desta fase, basta sinalizar “N vínculos explícitos preservados”.

### F4. Gestão permanece no `/admin/`

**Opções avaliadas:** nova UI no app; somente tela em massa; combinar as telas do admin já existentes.

**Recomendação:** permanecer no `/admin/`, pois D3 restringe atribuição a superusuários e as superfícies necessárias já existem:

- equipe → membros/TIs/global: `GroupAdmin`;
- TI → equipes/usuários: inlines de `TIsAdmin`;
- matriz em massa: `UserTIAdmin.atribuicao_em_massa_view`;
- atalhos: actions de TI, equipe e usuário.

Criar UI no app duplicaria autorização, validação, auditoria e manutenção sem beneficiar o operador autorizado. Se D3 mudar no futuro, reavaliar uma área própria no app.

### F5. Fluxo recomendado de operação

1. O superusuário cria a equipe com nome e descrição.
2. Inclui membros na própria tela da equipe.
3. Escolhe “todas as TIs” ou seleciona o escopo parcial.
4. Revisa impacto e salva.
5. Usa a visão TI → equipes apenas para ajustes pontuais e a tela em massa para alterações cruzadas.
6. Usa usuário → TI somente como exceção documentada.

Na listagem de equipes, manter `Nº de membros` e `Nº de TIs`, que já existem, e acrescentar “Escopo”: `Todas (dinâmico)` ou `N TIs`. Para global, não exibir `0 TIs` com base em `GroupTI`, pois seria enganoso. Acrescentar filtros “Global/parcial” e “Com/sem membros”.

### F6. Busca e seleção para 600+ TIs

**Recomendação:** evoluir o widget atual sem introduzir paginação, consistente com D9:

- rótulo de opção: `Nome — código — UFs`;
- busca textual do `FilteredSelectMultiple` passa a encontrar nome, código e UF pelo próprio texto da opção;
- botões explícitos “Selecionar todas as filtradas” e “Limpar seleção”, preservando a prévia obrigatória;
- filtros rápidos por UF na página em massa, tratando `TIs.estado` como lista separada por vírgula e comparando tokens, não substring solta (`PA` não pode casar texto arbitrário);
- mostrar total filtrado, total selecionado e total já vinculado;
- na revogação iniciada pela equipe, oferecer filtro “somente TIs já atribuídas a esta equipe”.

Não enviar “todas” como centenas de checkboxes implícitos sem prévia. A seleção global é a flag da equipe; “selecionar todas as filtradas” continua criando `GroupTI` apenas para o conjunto parcial explicitamente revisado.

**CSV:** não incluir no primeiro incremento. Com 646 TIs, busca por nome/código/UF, seleção filtrada e equipe global resolvem os casos apresentados. CSV adicionaria problemas de encoding, identificação por nome, duplicidade, revogação acidental e relatório de erros. Se métricas mostrarem necessidade, criar depois um command/admin upload exclusivo de superusuário, aceitando apenas `codigo_ti` + identificador inequívoco da equipe, com dry-run obrigatório, idempotência e arquivo de resultado por linha.

### F7. Atribuição nos dois sentidos sem duas regras

Manter equipe → TIs em `GroupAdmin` e TI → equipes em `TIsAdmin`, mas ambas devem persistir o mesmo `GroupTI`, usar o mesmo mixin de auditoria e validar `GrupoAcesso.tipo=EQUIPE`. A tela em massa continua sendo a implementação canônica para operações grandes; actions apenas a abrem pré-preenchida.

A flag global só é editável na equipe e nunca como uma pseudoatribuição na TI. Na tela de uma TI, equipes globais aparecem em bloco somente leitura “Também têm acesso por escopo global”, separadas dos `GroupTI` explícitos, para o operador não tentar revogar uma TI isolada de uma equipe global. Excluir uma única TI de uma equipe global não é suportado: a semântica é “todas”, sem lista de negação.

### F8. Gate de criação de TI usa perfil Administrador, não `is_staff` isolado

**Opções avaliadas:**

- `is_staff`: é detalhe de acesso ao admin e pode existir em conta legada sem perfil coerente;
- somente `is_superuser`: mais restritivo do que “admin” pedido e inutiliza o perfil Administrador;
- grupo `Perfil: Administrador`: expressa a regra de produto, mas deve considerar superusuário;
- permissão Django `dominial.add_tis`: semanticamente boa, mas hoje D1/D4 definem perfis por grupo e as views do app não adotam permissões Django de forma geral.

**Recomendação:** criar um predicado central `usuario_pode_criar_ti(user)` que retorne verdadeiro para usuário autenticado que seja superusuário **ou** pertença ao grupo protegido `Perfil: Administrador`. Como defesa de consistência, a rotina de seed/sincronização deve garantir que esse perfil tenha `is_staff=True`, mas o gate não deve aceitar qualquer `is_staff` legado.

Isso muda D4 de forma mínima e explícita: o Administrador passa a ter dois diferenciais — acessar `/admin/` e cadastrar TI; Editor continua podendo cadastrar imóveis, documentos e lançamentos dentro das TIs atribuídas. D1 (“ambos escrevem”) permanece verdadeira para objetos operacionais, mas deixa de abranger a criação do contêiner global TI por nova decisão do produto.

### F9. Defesa em profundidade para toda criação HTTP de TI

Aplicar o gate no início de `tis_form`, antes de instanciar/processar `TIsForm`, para GET e POST. Recomendação de resposta: `403 PermissionDenied` para usuário autenticado sem perfil (não é enumeração de objeto); anônimo continua redirecionado ao login. O template recebe `pode_criar_ti` calculado pelo mesmo helper/contexto e omite o botão.

O endpoint atual `path('tis/', tis_form, name='tis_form')` concentra GET e POST; não existe `tis_save` separado neste worktree. Ainda assim, fazer uma busca de rotas antes da implementação e aplicar o helper a qualquer nova rota que chame `TIsForm.save()` ou `TIs.objects.create()` via HTTP. `TIsAdmin` continua sujeito às permissões do admin. Management commands (`importar_terras_indigenas` e `criar_tis_da_referencia`) são operações de shell/deploy, não rotas de usuário, e ficam fora do gate HTTP.

Não confiar apenas em esconder o botão; POST direto e acesso direto por URL são testes obrigatórios.

### F10. Auditoria e observabilidade

Registrar em `LogEntry`:

- ativação/desativação de escopo global;
- mudança de membros, já auditada no `GroupAdmin`;
- concessão/revogação parcial, já auditada na atribuição em massa;
- limpeza opcional de vínculos redundantes, se implementada.

Adicionar na prévia o número de membros e o alcance atual. Não materializar a lista de usuários afetados no banco. Documentar consulta operacional para listar: equipe, escopo, membros, `GroupTI` explícitos e usuários com `UserTI` excepcional.

## Impacto nos models existentes

### Migration necessária

É necessária uma schema migration para `GrupoAcesso`:

```text
acesso_todas_tis: BooleanField(default=False, db_index=True,
                               verbose_name='Acesso a todas as TIs')
```

O índice é pequeno e ajuda o `EXISTS`/filtro pelas poucas equipes globais. Não alterar `GroupTI`, `UserTI`, suas constraints únicas ou índices. Não criar tabela de materialização.

Validações:

- formulário/admin recusa `acesso_todas_tis=True` quando `tipo != EQUIPE`;
- `GrupoAcesso.clean()` replica a regra para usos programáticos com `full_clean()`;
- perfis `protegido=True` mantêm o campo falso e somente leitura;
- não é possível transformar equipe global em perfil sem antes desativar o escopo global.

Uma `CheckConstraint` não consegue validar campo do `auth.Group` relacionado, mas consegue garantir localmente `NOT acesso_todas_tis OR tipo='equipe'`; adicioná-la para defesa no banco SQLite/Django.

### Dados existentes

A migration é compatível: `default=False` faz toda equipe existente permanecer parcial, e todas as linhas `GroupTI`/`UserTI` continuam produzindo exatamente o acesso atual. Não inferir automaticamente que alguma equipe com 646 vínculos é global, pois isso alteraria o acesso a TIs futuras sem consentimento.

Fornecer command opcional `promover_equipe_global` (ou ação admin equivalente), exclusivo de superusuário:

```text
python manage.py promover_equipe_global --equipe-id ID          # dry-run padrão
python manage.py promover_equipe_global --equipe-id ID --aplicar
```

O dry-run mostra membros, total de `GroupTI`, TIs ainda não cobertas e a consequência para TIs futuras. `--aplicar` apenas ativa a flag e preserva os `GroupTI`. Não é data migration automática.

## Fases de implementação

### Fase 1 — Predicado e semântica global

- `dominial/models/acesso_models.py`: adicionar campo, constraint e validação a `GrupoAcesso`.
- `dominial/migrations/`: schema migration com default falso; sem conversão automática de dados.
- `dominial/managers.py`: criar helper/subquery de membership global e ajustar `tis_atribuidas_ids`, `SegregacaoQuerySet.for_user` e `tis_for_user` sem avaliar QuerySets em Python. Manter bypass de superusuário e legado `UserImovel`.
- `dominial/utils/segregacao_utils.py`: continuar derivando acesso de `Imovel.objects.for_user`, sem regra paralela.
- Verificar planos de query para usuário de equipe parcial, global e com fontes combinadas; evitar duplicatas e N+1.

### Fase 2 — Gestão da equipe global no admin

- `dominial/admin.py`, `GroupAdminForm`/`GroupAdmin`: campo global, confirmação, prévia, auditoria, filtros e coluna “Escopo”. Preservar contagens anotadas de membros/TIs.
- `dominial/admin.py`, `GroupTIPorGroupInline`: ocultar/desabilitar edição parcial enquanto global estiver marcada ou exibir aviso de que os vínculos são residuais; nunca apagá-los implicitamente.
- Criar template específico de change form de equipe ou bloco JS/admin mínimo para confirmação e prévia.
- Na tela de TI (`TIsAdmin` e seus inlines), listar equipes globais somente para leitura.
- Manter todas essas mutações exclusivas de superusuário conforme D3 e `CAMPOS_DE_ESCALACAO`.

### Fase 3 — Fluxo em massa escalável

- `dominial/admin.py`, `AtribuicaoEmMassaForm`: melhorar labels de TI com nome/código/UF, filtro de UF e separação visual de usuários excepcionais.
- `UserTIAdmin.atribuicao_em_massa_view`, `_dados_previa` e `atribuicao_previa_view`: contagens filtradas/selecionadas, efeito em membros e mensagem distinta para concessão/revogação; não usar o fluxo parcial para ativar “todas”.
- `templates/admin/atribuicao_em_massa.html`: selecionar/limpar filtradas, contadores e prévia invalidada a cada alteração.
- Não criar `templates/admin/selecao_com_previa.html`: ele não existe no worktree; a prévia atual está incorporada em `atribuicao_em_massa.html`. Só criar template separado se a implementação decidir reutilizá-lo em mais de uma tela.
- Preservar actions existentes de `TIsAdmin`, `GroupAdmin` e `UserAdmin`, gates, CSRF, atomicidade, idempotência e `LogEntry`.

### Fase 4 — Gate de criação de TI

- Criar helper central em `dominial/utils/` (ou módulo de permissões existente apropriado): `usuario_pode_criar_ti`.
- `dominial/views/tis_views.py`: aplicar o gate a GET e POST de `tis_form`; manter `@login_required`; responder 403 ao autenticado não autorizado.
- `dominial/views/tis_views.py`, `home`: incluir `pode_criar_ti` no contexto usando o helper, ou disponibilizá-lo por context processor somente se houver mais consumidores reais.
- `templates/dominial/home.html`: renderizar “Cadastrar Nova Terra Indígena” apenas quando `pode_criar_ti`.
- `dominial/urls.py` e `dominial/views/__init__.py`: auditoria de todas as rotas de criação; não é esperada mudança de URL.
- Revisar `TIsAdmin` e a migration de seed dos perfis para coerência entre grupo Administrador e `is_staff`, sem transformar `is_staff` no gate.

### Fase 5 — Promoção assistida e documentação operacional

- `dominial/management/commands/promover_equipe_global.py`: dry-run padrão, `--aplicar` explícito, transação, idempotência e preservação de `GroupTI`.
- Documentar o procedimento de escolha entre parcial/global, rollback por desmarcação e significado de TIs futuras.
- CSV fica fora desta fase; registrar como melhoria condicionada a evidência de necessidade.

## Testes

Usar o padrão de `dominial/tests/test_segregacao_usuario.py` e os testes focados de `test_fase1_models_ti.py`. Não enfraquecer regressões de hardening existentes.

### Testes existentes que mudam

- `SegregacaoFase2BaseTestCase`: adicionar `equipe_global` e membro global sem `GroupTI`.
- testes de união/revogação/home: incluir a nova fonte global sem remover cenários `GroupTI`, `UserTI` e legado.
- `GroupAdminUXTest` (classe equivalente na suíte): ajustar fieldsets/form, coluna de escopo, confirmação e auditoria; manter testes atuais de contagem de membros/TIs.
- `AtribuicaoEmMassaTest`: ajustar labels/HTML e prévia, preservando testes de 403, CSRF, idempotência, `atribuido_por`, revogação seletiva e actions.
- testes da home que esperem o botão para qualquer autenticado devem passar a criar usuário Administrador ou esperar ausência.

### Novos testes obrigatórios

**Equipe global:**

- `test_equipe_d_global_ve_todas_as_tis_sem_groupti`: membro vê todas as TIs e imóveis com zero linhas `GroupTI` para a equipe.
- `test_equipe_global_ve_ti_criada_depois_da_ativacao`: cadastrar nova TI e imóvel após ativar a flag; acesso aparece sem sincronização.
- `test_equipe_global_ve_ti_vazia_na_home`.
- `test_desativar_global_preserva_apenas_groupti_e_userti_explicitos`.
- `test_global_com_groupti_e_userti_nao_duplica_querysets`.
- `test_perfil_nao_pode_ser_global_por_form_full_clean_e_constraint`.
- `test_staff_nao_superuser_nao_ativa_global_por_post_forjado`.

**Membership e revogação:**

- `test_membro_da_equipe_perde_acesso_ao_sair_da_equipe` tanto para equipe parcial quanto global; a próxima query não inclui TI/imóvel.
- `test_excluir_equipe_global_revoga_acesso`.
- `test_membro_em_duas_equipes_mantem_acesso_pela_fonte_restante`.

**Criação de TI:**

- `test_editor_nao_ve_botao_nova_ti`.
- `test_administrador_ve_botao_nova_ti` e `test_superuser_ve_botao_nova_ti`.
- `test_editor_get_direto_tis_form_retorna_403` (bypass direto por URL).
- `test_editor_post_direto_tis_form_retorna_403_e_nao_cria_ti`, usando payload válido para provar que o bloqueio ocorre antes do form.
- `test_staff_legado_sem_grupo_administrador_nao_ve_nem_cria_ti`.
- `test_administrador_consegue_get_e_postar_criacao_de_ti`.
- `test_anonimo_e_redirecionado_ao_login_no_get_e_post`.
- se surgir rota `tis_save`, repetir GET/POST/bypass nela; hoje ela não existe.

**Admin/UX e comando:**

- listagem mostra `Todas (dinâmico)`, número de membros e filtros corretos sem N+1;
- TI mostra equipes globais em leitura e não oferece revogação individual falsa;
- busca encontra por nome, código e UF; “selecionar filtradas” não inclui itens fora do filtro;
- prévia é invalidada após mudar seleção;
- command de promoção é dry-run por padrão, idempotente, exige equipe válida e preserva `GroupTI`.

**Performance/consultas:** manter limites de query da home e de `for_user`; adicionar caso global para garantir que o número de TIs/membros não produz N+1. Não fixar SQL literal específico do SQLite; testar resultado e limite de queries.

## Riscos e compatibilidade

1. **Mudança consciente de D4:** cadastro de TI passa a diferenciar Administrador de Editor. Mitigação: registrar a exceção explicitamente, manter toda escrita operacional de D1 e não usar a mudança para criar um perfil Leitor.
2. **Acesso futuro amplo:** ativar global inclui automaticamente TIs futuras. É requisito da representação recomendada; prévia e confirmação devem dizer isso sem ambiguidade.
3. **Revogação individual impossível em equipe global:** não criar lista de negação, pois ela torna o modelo difícil de explicar. Para excluir uma TI, usar equipe parcial ou equipe separada.
4. **Dados existentes:** `GroupTI` e `UserTI` permanecem válidos; migration não promove nem remove nada. `UserImovel` legado continua como previsto em D7.
5. **Equipe global com vínculos explícitos:** redundância é permitida e não pode duplicar linhas de query. Preservá-los possibilita rollback de escopo.
6. **Flag ligada a perfil por escrita fora do admin:** constraint + `clean()` + filtros canônicos impedem que grupo de perfil ganhe escopo global.
7. **`is_staff` inconsistente:** uma conta legada staff não deve criar TI sem o grupo Administrador. Fazer relatório pré-deploy de inconsistências e corrigi-las conscientemente, sem alargar o gate.
8. **Estado multivalorado em texto:** filtro por UF precisa tokenizar valores separados por vírgula; busca ingênua por substring pode retornar falsos positivos. Não propor migration de normalização nesta fase.
9. **Operação concorrente:** prévia pode ficar desatualizada antes do POST. Revalidar autorização e objetos no POST, usar `transaction.atomic()` e constraints; a prévia é informativa, não fonte de verdade.
10. **Admin duplicado no app:** evitado ao manter gestão no `/admin/`. D3 permanece integral.
11. **Escalação:** `acesso_todas_tis` é campo crítico equivalente a atribuir todas as TIs. Incluir em controles de escalada, readonly de não-superuser e testes de POST forjado.
12. **Template divergente do resumo:** `templates/admin/selecao_com_previa.html` não existe; não planejar alteração fantasma. Validar novamente no início da implementação.

Compatibilidade D1–D9: D2, D3, D5, D6, D7, D8 e D9 são preservadas; D1 é preservada para escrita dentro das TIs atribuídas; D4 recebe a única alteração necessária e explicitada em F8. A equipe global reforça D6 e mantém o bypass exclusivo de superusuário separado da herança por equipe.

## Checklist de verificação manual

### Antes do deploy

- [ ] Backup do SQLite realizado e restauração ensaiada.
- [ ] `git diff` contém apenas alterações planejadas; nenhum dado foi convertido implicitamente.
- [ ] Levantar equipes, membros, contagem de `GroupTI`, `UserTI` e `UserImovel`.
- [ ] Listar usuários `is_staff=True` sem grupo Administrador e usuários do grupo com `is_staff=False`; decidir correção individual.
- [ ] Rodar suíte completa e testes focados de segregação/admin.
- [ ] Conferir plano de migration: somente campo/constraint/índice, default falso.

### Deploy

- [ ] Colocar aplicação em janela de manutenção compatível com SQLite.
- [ ] Aplicar migration de schema.
- [ ] Verificar que nenhuma equipe existente foi marcada global e contagens de `GroupTI`/`UserTI` não mudaram.
- [ ] Subir aplicação e executar checks do Django.
- [ ] Não executar promoção global sem revisar primeiro o dry-run.

### Teste local/staging funcional

- [ ] Criar equipe D, adicionar dois membros e ativar “todas as TIs” após conferir a prévia.
- [ ] Confirmar que não foram criadas centenas de linhas `GroupTI`.
- [ ] Entrar como membro da equipe D e verificar TIs com/sem imóveis.
- [ ] Como superusuário, criar uma TI nova; confirmar que ela aparece imediatamente para equipe D.
- [ ] Remover um membro da equipe D; atualizar a sessão/página e confirmar perda imediata de acesso.
- [ ] Desativar global e confirmar que só acessos explícitos restantes sobrevivem.
- [ ] Criar equipe parcial e atribuir por nome, código, UF e “selecionar filtradas”; revisar contadores e revogar apenas parte.
- [ ] Abrir uma TI e conferir equipes explícitas editáveis e equipes globais somente leitura.
- [ ] Conferir listagem de equipes: membros, escopo global/parcial e contagem coerente.
- [ ] Como Editor, confirmar ausência do botão, GET direto 403 e POST válido direto 403 sem nova linha.
- [ ] Como staff legado sem grupo Administrador, repetir ausência/403.
- [ ] Como Administrador e superusuário, confirmar botão, GET e POST bem-sucedidos.
- [ ] Como anônimo, confirmar redirecionamento ao login.
- [ ] Conferir `LogEntry` de global, membership e massa com ator e impacto.
- [ ] Conferir que documentos, lançamentos, pessoas e imóveis continuam segregados por TI.

### Promoção em produção

- [ ] Rodar `promover_equipe_global --equipe-id ID` sem `--aplicar` e arquivar/revisar a saída.
- [ ] Confirmar com o dono do produto que TIs futuras devem entrar automaticamente.
- [ ] Rodar com `--aplicar` somente após aprovação.
- [ ] Repetir dry-run para confirmar idempotência/estado final.
- [ ] Monitorar erros 403 inesperados no cadastro de TI e consultas da home/admin.
