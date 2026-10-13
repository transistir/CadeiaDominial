Li o código. Segue o plano.

> **Revisão 2 (decisões do produto fechadas pelo Hiure).** Este documento foi consolidado: o perfil *Leitor* e o gate de escrita saíram do MVP, a delegação de atribuição para Administrador saiu, o acesso passa a ser **sempre por TI inteira** e a camada `UserImovel` sai da UI. As decisões de produto estão resumidas em **Decisões fechadas (D1–D9)**, no fim do documento, e **prevalecem** sobre qualquer coisa escrita aqui. As decisões *de design* da Parte A foram renumeradas para **A1–A11** para não colidir com a numeração do produto.

---

# Plano — Simplificação de permissões e atribuição de acesso por TI (issue #132, fase 2)

## Resumo executivo

O que existe hoje funciona e é seguro, mas atribui acesso na granularidade errada: uma linha de `UserImovel` por imóvel, um usuário por vez. A proposta troca a *unidade de atribuição* de **imóvel** para **Terra Indígena**, e o *destinatário* de **usuário** para **equipe ou usuário** — com a **equipe como veículo principal** (D6). Acesso é sempre por **TI inteira**: quem tem a TI vê todos os imóveis sobrepostos a ela, atuais e futuros, e importa de uma cadeia para outra dentro da TI sem pedir permissão extra (D2). Acesso parcial a imóveis de uma TI **deixa de existir** no produto: a camada `UserImovel` sai da UI e as atribuições existentes são migradas para nível de TI por um command com **dry-run obrigatório** (D7).

O acesso efetivo passa a ser a união dinâmica de duas fontes de TI (TIs diretas e TIs herdadas de equipes), resolvida em **uma query com `IN` de subquery — sem `distinct()` e sem N+1**. Em paralelo, o cadastro de usuário no admin some com `groups`/`user_permissions`/`is_staff`/`is_superuser` e passa a expor um único campo **Perfil** com **duas opções** — Editor e Administrador (D1). Ambos escrevem; o **único** diferencial do Administrador é entrar no `/admin/` (D4). Nada disso afrouxa os 9 rounds de segurança já aprovados: os novos models de atribuição nascem `superuser-only` (D3) e o campo `perfil` entra em `CAMPOS_DE_ESCALACAO`.

---

## Parte A — Decisões de design

### A1. Perfil de acesso = um campo, duas opções, Django Groups por trás

**Decisão:** o `UserAdmin` deixa de mostrar `groups`, `user_permissions`, `is_staff` e `is_superuser` para quem não é superusuário, e mostra um único `ChoiceField` **"Perfil de acesso"** com radio buttons:

| Perfil | O que faz | `is_staff` | Grupo Django |
|---|---|---|---|
| **Editor** *(padrão)* | Consulta, exporta e **cadastra** imóveis, documentos e lançamentos nas TIs atribuídas. Importa entre cadeias da mesma TI. | `False` | `Perfil: Editor` |
| **Administrador** | Tudo do Editor + acessa o admin do Django (cartórios, pessoas, correções, `alterar_ti`). | `True` | `Perfil: Administrador` |

**Justificativa (D1 + D4):** os dois perfis são a única distinção que o sistema hoje consegue sustentar **de fato**, porque o app não usa as permissões do Django nas views — elas só têm `@login_required`. Um perfil "Leitor" sem trabalho adicional seria **teatro de segurança**: o usuário continuaria conseguindo POSTar em `imovel_editar`. Torná-lo real exigiria um gate de escrita em ~13 views; o produto decidiu que isso **não entra no MVP**. Consequência: o eixo "o que o usuário pode fazer" tem hoje **um único degrau** — entrar ou não no `/admin/` —, e todo o resto da segurança é o eixo "o que ele vê", que é a segregação por TI.

**Editor é `is_staff=False`, sem exceção (D4).** Operações que hoje só existem no admin — cadastrar cartório, corrigir pessoa, `alterar_ti` — continuam exclusivas de Administrador/superusuário. Isso mantém a superfície endurecida nos 9 rounds restrita a poucas contas.

**O que os grupos de perfil carregam:** `Perfil: Administrador` carrega as `Permission` dos models que ele opera no admin (cartório, pessoas, etc.) e implica `is_staff=True`. `Perfil: Editor` **não carrega permissão nenhuma** no MVP — é um rótulo com `is_staff=False`. Isso é intencional e deve ficar escrito no código: o grupo existe para que, quando o gate de escrita for feito (pós-MVP), haja onde pendurar a permissão sem mexer no cadastro de ninguém.

`is_superuser` continua sendo o que é: bypass total da segregação, concedido só por outro superusuário, num fieldset colapsado visível apenas a superusuários.

### A2. Perfil ≠ Equipe: dois tipos de Group, discriminados por um model lateral

Usar `auth.Group` para as duas coisas (carregar permissões *e* carregar TIs) é o caminho que o Django favorece, mas confunde a UI e cria um risco real: atribuir uma TI ao grupo `Perfil: Editor` daria essa TI a **todos os editores do sistema**, silenciosamente.

**Decisão:** manter um único `auth.Group`, discriminado por um model lateral:

```python
class GrupoAcesso(models.Model):
    """Metadados do auth.Group: é um perfil (permissões) ou uma equipe (TIs)?"""
    PERFIL, EQUIPE = 'perfil', 'equipe'
    group = models.OneToOneField('auth.Group', on_delete=models.CASCADE, related_name='acesso')
    tipo = models.CharField(max_length=10, choices=[(PERFIL, 'Perfil'), (EQUIPE, 'Equipe')])
    protegido = models.BooleanField(default=False)  # os 2 perfis seedados
```

- `GroupTI.clean()` recusa grupo com `tipo != EQUIPE`, e a UI só oferece equipes.
- `UserAdmin` mostra "Perfil" (radio, 1 de 2) e "Equipes" (checkbox, N de N) como campos separados — ambos gravando em `user.groups`.
- Perfis `protegido=True` não podem ser renomeados nem excluídos (`GroupAdmin.has_delete_permission`).

**Equipes não têm seed (D8):** o superusuário cria cada equipe na mão, com **nome + descrição opcional**. Nada de lista pré-definida por região/instituição — o produto não fechou uma taxonomia e inventar uma criaria grupos vazios que ninguém usa. `GrupoAcesso` ganha, portanto, um campo `descricao = models.CharField(max_length=255, blank=True)`.

**Justificativa:** custa um model de 5 campos e elimina uma classe inteira de erro operacional. Alternativa avaliada e descartada: convenção de nome (`Perfil: *`) — frágil, quebra ao renomear.

### A3. Semântica formal do acesso efetivo

```
imóveis_visíveis(u) =
      { i : i.terra_indigena_id ∈ tis_atribuídas(u) }           -- regra única (D2)
    ∪ { i : ∃ UserImovel(user=u, imovel=i) }                    -- legado, some após a Fase 6 (D7)

tis_atribuídas(u) =
      { t : ∃ GroupTI(group=g, tis=t) ∧ u ∈ g.user_set }        -- por equipe (principal)
    ∪ { t : ∃ UserTI(user=u, tis=t) }                           -- direto (secundário)

is_superuser(u) ⟹ imóveis_visíveis(u) = todos    (bypass inalterado)
                  tis_visíveis(u)     = todas
```

O termo `UserImovel` é **transitório**: continua no `for_user` enquanto houver linhas legadas, e vira conjunto vazio depois que o command da Fase 6 rodar. Nenhuma UI cria linhas novas ali.

Documentos, lançamentos, alterações, documentos digitais e pessoas continuam derivando de `imóveis_visíveis(u)` por FK — nenhuma regra nova, só a fonte trocada alimentando o mesmo conjunto.

### A4. Atribuir uma TI dá acesso a **todos** os imóveis dela, inclusive futuros

**Decisão (D2):** o vínculo é **dinâmico** (join na hora da query), não materializado em linhas de `UserImovel`. Quem recebe a TI Alfa vê todos os imóveis sobrepostos à TI Alfa, hoje e amanhã.

**Justificativa:** é a regra de negócio, não uma otimização. A cadeia dominial é sobre **todos** os imóveis sobrepostos à mesma TI — trabalhar com um subconjunto é trabalhar com uma cadeia incompleta. Se materializássemos, todo imóvel novo exigiria um passo de sincronização (signal ou cron) e voltaríamos ao problema de escala, agora com risco de dessincronização silenciosa.

**Consequências, todas desejadas e a documentar na UI:**
- **Imóvel novo em TI atribuída aparece automaticamente** para todo mundo que tem a TI — sem nenhuma ação de quem administra. É o comportamento pedido; ver R13.
- **Importação entre cadeias da mesma TI funciona sem permissão extra**: `importacao_cadeia_service` / `nova_importacao_view` operam sobre `Imovel.objects.for_user(...)`, e origem e destino da mesma TI estão ambos nesse conjunto por construção. Não há nenhum gate adicional a escrever — mas **há um teste a escrever** (Parte C), porque hoje isso só funciona por acidente de `UserImovel`.
- O Editor com a TI atribuída pode **cadastrar** um imóvel novo naquela TI e continua vendo-o — hoje isso só funciona por causa do `UserImovel.get_or_create` em `imovel_views.py:71`, que passa a ser redundante (ver A7).

### A5. Imóvel que muda de TI: o acesso segue a TI **atual**, sem exceções

**Decisão (D5):** imóvel **não deve mudar de TI**. A tela `ImovelAdmin.alterar_ti_view` (`admin.py:422`) permanece **como caminho de correção de erro de cadastro**, restrita a Administrador/superusuário. Ao salvar, o acesso segue a TI: quem tinha pela TI antiga perde, quem tem a nova ganha.

**Sem checkbox "Preservar acesso atual".** A opção foi avaliada e **descartada pelo produto** em nome da simplicidade: preservar acesso materializaria `UserImovel`, que é exatamente a camada que estamos eliminando (D7), e reintroduziria acesso parcial a uma TI, que não existe no produto (D2).

**Mitigação:** (a) a tela de confirmação mostra explicitamente o impacto — *"N usuários e M equipes perdem acesso a este imóvel; K passam a ter"* —, (b) a mudança já é registrada em `observacoes`, e (c) o `alterar_ti_view` já é gated por `has_change_permission` + `for_user`.

### A6. Equipes: saída perde acesso na hora

**Decisão:** membership é `auth.User.groups` nativo. Remover o usuário da equipe, ou excluir a equipe, revoga o acesso **imediatamente na próxima query** — não há cache nem materialização. `GroupTI.group` é `on_delete=CASCADE`: excluir a equipe apaga suas linhas de TI.

**Justificativa:** revogação instantânea é requisito não-negociável num sistema de dados sensíveis; qualquer materialização introduz janela de acesso residual.

**Ponto fraco assumido:** o M2M nativo `User.groups` não tem `through` com auditoria (não dá para customizar sem substituir `Group`). **Mitigação:** a tela de atribuição em massa grava um `django.contrib.admin.models.LogEntry` por alteração de membership, e `UserTI`/`GroupTI` carregam `atribuido_por`/`data_atribuicao` como o `UserImovel` já faz. Quem editar membership pelo `GroupAdmin` de série também gera `LogEntry` automaticamente.

### A7. `UserImovel` sai da UI e é migrado para nível de TI

**Decisão (D7):** a camada de atribuição por imóvel **deixa de existir para o usuário**. Concretamente:

1. **Migração de dados por command, com dry-run obrigatório** — `migrar_userimovel_para_userti`, dry-run por padrão, `--aplicar` explícito. Para cada usuário, agrupa suas linhas de `UserImovel` por TI e propõe um `UserTI` por TI envolvida. O relatório mostra, **antes de aplicar**: usuário, TI, quantos imóveis ele já via, quantos passará a ver **hoje**, e o aviso de que passará a ver também os **futuros**. Converter *amplia* acesso — por isso é uma decisão revisada por humano, nunca um efeito colateral de migration (ver R12).
2. **`UserImovelAdmin` e o inline no `UserAdmin` saem do menu** depois que o command rodar em produção. O model e o termo no `for_user` permanecem por um release, como rede de segurança de rollback; a remoção definitiva (model + migration de drop) fica para PR próprio, fora desta issue.
3. **`imovel_views.py:71` (`UserImovel.get_or_create` no autor do cadastro) é removido.** Ele era a rede de segurança de quem criava imóvel sem ter a TI; com D2, quem cadastra um imóvel numa TI **tem** a TI (o dropdown de TI só oferece TIs atribuídas), então a linha é redundante. Superusuário criando em TI não atribuída continua vendo tudo pelo bypass.

**Justificativa:** manter `UserImovel` como "camada de exceção" era a proposta anterior; o produto fechou que **acesso parcial a uma TI não existe** — a cadeia dominial é sobre todos os imóveis sobrepostos à mesma TI. Manter a camada só na UI seria oferecer uma configuração que produz cadeia incompleta.

### A8. Resolução do filtro: uma query, `IN` de subquery, zero `distinct()`

O caminho ingênuo — `filter(Q(usuarios_atribuidos__user=u) | Q(terra_indigena_id__usuarios_ti__user=u) | Q(terra_indigena_id__grupos_ti__group__user=u))` — produz três LEFT JOINs e **duplica linhas** (um imóvel com 3 atribuições diretas de outros usuários vira 3 linhas), exigindo `.distinct()`, que quebra `annotate(Count(...))` e degrada com volume. Pior: quebraria `test_atribuicao_nao_duplica_imovel_no_queryset`.

**Decisão:** subqueries de PK.

```python
# dominial/managers.py

def tis_atribuidas_ids(user):
    """PKs das TIs atribuídas ao usuário: via equipe ou direta. Subquery, não lista."""
    from .models import TIs
    return TIs.objects.filter(
        Q(grupos_ti__group__user=user) | Q(usuarios_ti__user=user)
    ).values('pk')


def imoveis_diretos_ids(user):
    """PKs dos imóveis atribuídos um-a-um. LEGADO: some após a migração da Fase 6 (A7)."""
    from .models import UserImovel
    return UserImovel.objects.filter(user=user).values('imovel_id')


class SegregacaoQuerySet(models.QuerySet):
    def for_user(self, user):
        if not usuario_autenticado(user):
            return self.none()
        if usuario_ve_tudo(user):
            return self
        return self.filter(
            Q(terra_indigena_id__in=tis_atribuidas_ids(user))
            | Q(pk__in=imoveis_diretos_ids(user))   # legado
        )
```

Propriedades: uma única ida ao banco (o Postgres resolve `IN (subquery)` como semi-join), **sem duplicação de linhas**, continua encadeável nos dois sentidos (`test_for_user_e_encadeavel_com_outros_filtros` passa sem alteração), e o bypass de superuser continua devolvendo `self` — ou seja, `escopar()` e todos os `select_related`/`annotate` do admin seguem intactos.

Os demais helpers passam a **derivar** de `for_user`, eliminando as 10 ocorrências de `usuarios_atribuidos__user=` espalhadas por `managers.py`, `admin.py` e `segregacao_utils.py` (hoje cada uma é uma chance de esquecer a nova fonte):

```python
def documentos_for_user(user):
    from .models import Documento, Imovel
    if not usuario_autenticado(user): return Documento.objects.none()
    if usuario_ve_tudo(user):         return Documento.objects.all()
    return Documento.objects.filter(imovel__in=Imovel.objects.for_user(user))

def lancamentos_for_user(user):
    ... Lancamento.objects.filter(documento__imovel__in=Imovel.objects.for_user(user))

def pessoas_for_user(user):
    imoveis = Imovel.objects.for_user(user)
    return Pessoas.objects.filter(
        Q(imovel__in=imoveis)
        | Q(transmitente_lancamento__documento__imovel__in=imoveis)
        | Q(adquirente_lancamento__documento__imovel__in=imoveis)
        | Q(lancamentopessoa__lancamento__documento__imovel__in=imoveis)
        | Q(transmitente__imovel_id__in=imoveis)
        | Q(adquirente__imovel_id__in=imoveis)
    ).distinct()   # distinct segue necessário: uma pessoa casa por vários caminhos
```

E `segregacao_utils.usuario_tem_acesso_imovel` deixa de ter regra própria:

```python
return Imovel.objects.for_user(user).filter(pk=imovel_id).exists()
```

**`tis_for_user` muda de semântica** — hoje é "TIs que têm ao menos um imóvel meu"; passa a ser "TIs atribuídas a mim" (D6):

```python
def tis_for_user(user):
    if not usuario_autenticado(user): return TIs.objects.none()
    if usuario_ve_tudo(user):         return TIs.objects.all()      # superuser vê as 646
    return TIs.objects.filter(
        Q(pk__in=tis_atribuidas_ids(user))          # atribuída (mesmo vazia)
        | Q(imovel__in=imoveis_diretos_ids(user))   # legado, some após a Fase 6
    ).distinct()
```

Isso define diretamente a **home de não-superusuário (D6)**: aparecem **só** as TIs atribuídas às equipes de que o usuário participa e/ou diretamente a ele. Quem não está em equipe nenhuma e não tem `UserTI` vê **home vazia** — é o estado correto, não um bug.

**Uma TI atribuída e ainda sem imóveis aparece (D6).** É necessário: sem ela, o Editor recém-atribuído vê a home vazia e não tem por onde cadastrar o primeiro imóvel — e o `ImovelAdmin.formfield_for_foreignkey` (`admin.py:392`) não ofereceria a TI no dropdown. Das 646 TIs, só 24 têm imóveis hoje (D9); atribuir uma das 622 vazias é justamente o gesto de "vamos começar a mapear esta TI".

**Dívida a pagar junto (`tis_views.py:76-104`):** `tis_detail` monta o filtro de segregação em **SQL cru**:

```sql
AND i.id IN (SELECT imovel_id FROM dominial_userimovel WHERE user_id = %s)
```

Esse subselect ignora completamente `UserTI`/`GroupTI` e é o ponto onde a nova regra vaza silenciosamente — depois da Fase 2 ele passa a **negar acesso legítimo** a quem tem a TI e nenhum `UserImovel`. Recomendo **eliminar o raw SQL** e reescrever com o ORM, o que também derruba o hack de instanciar `Imovel()` na mão:

```python
imoveis_ordenados = (
    Imovel.objects.for_user(request.user)
    .filter(terra_indigena_id=tis, arquivado=is_arquivado)
    .annotate(
        ultimo_documento=Max('documentos__data_cadastro'),
        ultimo_lancamento=Max('documentos__lancamentos__data_cadastro'),
        atividade=Greatest(  # COALESCE(max_doc, max_lanc, data_cadastro)
            Coalesce('ultimo_documento', 'ultimo_lancamento', 'data_cadastro'), ...
        ),
    )
    .order_by('-atividade', 'matricula')
)
```

Se o ordering exato do `COALESCE(MAX(d), MAX(l), i.data_cadastro)` for difícil de reproduzir 1:1, o fallback mínimo é trocar o subselect por `AND i.id IN %s` com os IDs de `Imovel.objects.for_user(...).values_list('pk')` (tratando lista vazia com `AND 1=0`). Mas a versão ORM é a certa.

**Outros pontos que a união toca (verificados, todos já centralizados):** `services/hierarquia_service.py`, `cadeia_completa_service.py`, `cadeia_dominial_tabela_service.py`, `duplicata_verificacao_service.py`, `importacao_cadeia_service.py`, `lancamento_criacao_service.py` — todos consomem `documentos_for_user`/`Imovel.objects.for_user`, herdam a mudança de graça (é o que faz a importação entre cadeias da mesma TI funcionar sem permissão extra — A4). `admin.py:111` (`AlteracoesAdmin`) e `admin.py:164` (`DocumentoDigitalAdmin`) usam `usuarios_atribuidos__user=` na mão e **precisam ser trocados** por `imovel_id__in=Imovel.objects.for_user(...)` / `documento__in=documentos_for_user(...)`.

### A9. Quem pode atribuir: **só superusuário**

**Decisão (D3):** `UserTIAdmin`, `GroupTIAdmin`, `GrupoAcessoAdmin` e a tela de atribuição em massa replicam o pacote de `UserImovelAdmin` (`admin.py:264-277`): `has_module_permission`, `has_view/add/change/delete_permission` todos `return request.user.is_superuser`.

**Justificativa:** sem isso, um staff com `add_userti` se atribui todas as TIs em um POST — escalação total, pior que o vetor que o round 9 fechou. A delegação restrita a Administrador (conceder só TIs que já possui, nunca a si mesmo, sempre auditado) foi avaliada e **descartada do escopo pelo produto**: com 30 usuários e um punhado de superusuários, a centralização não é gargalo e elimina a fase mais arriscada do plano.

### A10. `TIs_Imovel` é código morto

A junction `TIs_Imovel` (`tis_models.py:58`) não é referenciada por nenhuma query, view, service ou admin — só existe na `0001_initial` e no `__init__`. O vínculo real é a FK `Imovel.terra_indigena_id`. **Não usar como fonte de acesso**; propor remoção em PR separado (fora do escopo desta issue).

### A11. Escala real: `FilteredSelectMultiple` basta, sem paginação

**Números fechados (D9):** 30 usuários, **646 TIs** (só **24 com imóveis**), ~**50 imóveis** no total; projeção de **triplicar em 12 meses** (≈90 usuários, ~150 imóveis; o número de TIs é o universo da Funai, praticamente estático).

**Decisão:** o widget de duas colunas do admin (`FilteredSelectMultiple`, que já vem com caixa de busca) é suficiente para as 646 TIs e para os 30 usuários. **Sem paginação, sem autocomplete customizado, sem select2.** 646 `<option>` renderizam em milissegundos e a busca embutida resolve a navegação.

**O que a escala *de fato* muda:** nada no desenho de queries — 50 imóveis não estressam nada. O único ponto de atenção é o `COUNT` por TI na home (R6), que com 646 TIs no caso do superusuário vira 646 queries se ficar como está.

---

## Parte B — Sketches por fase

### Fase 0 — Centralizar o filtro (refactor puro, sem mudança de comportamento)

**PR:** `refactor(#132): centraliza o filtro de segregação em for_user`

- `managers.py`: criar `imoveis_diretos_ids(user)`; reescrever `documentos_for_user`, `lancamentos_for_user`, `pessoas_for_user`, `tis_for_user` para derivar de `Imovel.objects.for_user`.
- `segregacao_utils.usuario_tem_acesso_imovel` → `for_user().filter(pk=...).exists()`.
- `admin.py:111` e `admin.py:164` → parar de escrever `usuarios_atribuidos__user=` na mão.
- `tis_views.tis_detail` → **sair do raw SQL** (o `AND i.id IN (SELECT imovel_id FROM dominial_userimovel WHERE user_id = %s)` de `tis_views.py:78`, transcrito em A8). É a razão de esta fase existir antes de qualquer coisa: enquanto ele estiver lá, a Fase 2 nega acesso legítimo.

**Aceite:**
- [ ] Toda a suíte atual passa **sem alterar um único teste**.
- [ ] `grep -rn "usuarios_atribuidos__user" dominial/ --include=*.py | grep -v tests` retorna **apenas** `managers.py`.
- [ ] `grep -rn "dominial_userimovel" dominial/ --include=*.py` não retorna nada em `views/`.
- [ ] `test_tis_detail_lista_apenas_imoveis_atribuidos` e `test_tis_detail_do_superuser_lista_tudo` verdes com o ORM.
- [ ] Ordering de `tis_detail` idêntico ao anterior (teste novo com 3 imóveis de atividades diferentes).

### Fase 1 — Models de atribuição por TI e por equipe

**PR:** `feat(#132): models UserTI, GroupTI e GrupoAcesso`

```python
# dominial/models/acesso_models.py  (novo)

class UserTI(models.Model):
    """Atribuição de uma TI inteira a um usuário: cobre os imóveis atuais e futuros."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='tis_atribuidas', verbose_name='Usuário')
    tis = models.ForeignKey('TIs', on_delete=models.CASCADE,
                            related_name='usuarios_ti', verbose_name='Terra Indígena')
    data_atribuicao = models.DateTimeField(auto_now_add=True)
    atribuido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='atribuicoes_ti_feitas')
    class Meta:
        unique_together = ('user', 'tis')
        indexes = [models.Index(fields=['tis'], name='dom_userti_tis_idx')]
        verbose_name, verbose_name_plural = 'Atribuição de TI', 'Atribuições de TI'
        ordering = ['user__username', 'tis__nome']

class GroupTI(models.Model):
    """Atribuição de uma TI a uma equipe: todo membro herda, entra e sai na hora."""
    group = models.ForeignKey('auth.Group', on_delete=models.CASCADE,
                              related_name='tis_atribuidas', verbose_name='Equipe')
    tis = models.ForeignKey('TIs', on_delete=models.CASCADE, related_name='grupos_ti')
    data_atribuicao = models.DateTimeField(auto_now_add=True)
    atribuido_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='atribuicoes_grupo_feitas')
    class Meta:
        unique_together = ('group', 'tis')
        indexes = [models.Index(fields=['tis'], name='dom_groupti_tis_idx')]
    def clean(self):
        if getattr(self.group, 'acesso', None) is None or self.group.acesso.tipo != GrupoAcesso.EQUIPE:
            raise ValidationError('TIs só podem ser atribuídas a equipes, não a perfis.')

class GrupoAcesso(models.Model):   # ver A2 — inclui `descricao` (opcional)
    ...
```

Migrations: `0059_userti_groupti_grupoacesso` (schema) + `0060_seed_perfis` (data: cria os **2** `Group` de perfil — `Perfil: Editor` sem permissões, `Perfil: Administrador` com as permissões de admin —, marca `GrupoAcesso(tipo=PERFIL, protegido=True)`, e marca todo `Group` pré-existente como `tipo=EQUIPE`). **Nenhuma equipe é seedada** (D8). A data migration segue o padrão da `0058`: **irreversível formalmente** (`reverse_code=None`) e **idempotente** (`get_or_create`).

Admin nesta fase: `UserTIAdmin` e `GroupTIAdmin` standalone, superuser-only, cópia fiel do `UserImovelAdmin` (incluindo `save_model` que carimba `atribuido_por`).

**Aceite:**
- [ ] `makemigrations --check` limpo.
- [ ] `GroupTI` com grupo de perfil falha no `full_clean`.
- [ ] Staff com `add_userti`/`change_userti` recebe **403** no changelist e a entrada **não aparece** no `admin:index` (espelhar `test_staff_nao_ve_admin_de_atribuicoes_nem_acessa_url_direta`).
- [ ] `unique_together` bloqueia duplicata em ambos os models.
- [ ] Excluir um `Group` apaga seus `GroupTI` (CASCADE) e não deixa órfão.
- [ ] A `0060` cria exatamente 2 grupos de perfil e **zero** equipes; rodar duas vezes não duplica nada.
- [ ] Nenhuma mudança de comportamento no filtro ainda (a união é a Fase 2).

### Fase 2 — União das fontes no filtro

**PR:** `feat(#132): acesso efetivo = TIs de equipe ∪ TIs diretas (∪ imóveis legados)`

- `managers.py`: `tis_atribuidas_ids`, novo `for_user`, novo `tis_for_user` (A8).
- `tis_views.home`: passa a listar `tis_for_user(request.user)` — TIs atribuídas, inclusive vazias (D6) — e troca o `COUNT` por TI do dict comprehension por `annotate(Count(...))` (R6).
- `AtribuicaoAuditoriaMixin.save_formset` (`admin.py:199`) generalizado: hoje testa `formset.model is not UserImovel` e devolve ao `super()`; passa a tratar `{UserImovel, UserTI}` — senão o inline novo grava **sem** `atribuido_por` e **sem** o gate de superuser.
- `UserAdmin.inlines += [UserTIPorUserInline]`; `TIsAdmin.inlines = [GroupTIPorTIInline, UserTIPorTIInline]` (equipe primeiro — é o veículo principal, D6).
- Docstring do módulo `managers.py` reescrita com a semântica formal (A3) — ela é a documentação canônica da regra.

**Aceite:** (detalhado na Parte C)
- [ ] Os cenários de união, o imóvel futuro, as duas revogações e o bypass de superuser.
- [ ] Usuário sem equipe e sem `UserTI` vê **home vazia** e nenhuma TI.
- [ ] Importação de uma cadeia para outra da **mesma TI** funciona só com a TI atribuída.
- [ ] `assertNumQueries` em `Imovel.objects.for_user(u).count()` == 1.
- [ ] Nenhum teste existente de segregação alterado (exceto os que ganham cenário novo).
- [ ] `ManagerOptInRegressaoTest` continua verde (nenhum `Imovel.objects.<algo>` novo em `views/`+`admin.py` fora de `for_user`).

### Fase 3 — UserAdmin simplificado + 2 perfis + equipes

**PR:** `feat(#132): cadastro de usuário com perfil único (Editor/Administrador); esconde permissões cruas`

```python
PERFIS = {'editor': 'Perfil: Editor', 'admin': 'Perfil: Administrador'}

class UserPerfilForm(DjangoUserChangeForm):
    perfil = forms.ChoiceField(
        label='Perfil de acesso', widget=forms.RadioSelect,
        choices=[('editor', 'Editor — consulta e cadastra imóveis, documentos e lançamentos'),
                 ('admin',  'Administrador — Editor + acesso ao admin do sistema')],
        initial='editor',
        help_text='Define se o usuário entra ou não no admin do sistema. O que ele VÊ é '
                  'definido pelas equipes e Terras Indígenas atribuídas abaixo.')
    equipes = forms.ModelMultipleChoiceField(
        queryset=Group.objects.filter(acesso__tipo=GrupoAcesso.EQUIPE),
        required=False, widget=forms.CheckboxSelectMultiple, label='Equipes')

class UserAdmin(AtribuicaoAuditoriaMixin, DjangoUserAdmin):
    form = UserPerfilForm
    inlines = [UserTIPorUserInline]          # UserImovel sai da UI (A7)
    list_display  = ['username', 'first_name', 'last_name', 'perfil_exibido', 'is_active']
    list_filter   = ['is_active', 'groups', PerfilListFilter, TIAtribuidaListFilter]
    search_fields = ['username', 'first_name', 'last_name', 'email']

    # 'perfil' e 'equipes' gravam em user.groups → são campos de escalação (round 9).
    CAMPOS_DE_ESCALACAO = ('is_superuser', 'is_staff', 'groups', 'user_permissions',
                           'perfil', 'equipes')

    FIELDSETS_SIMPLES = (
        (None,            {'fields': ('username', 'password')}),
        ('Identificação', {'fields': ('first_name', 'last_name', 'email')}),
        ('Acesso',        {'fields': ('perfil', 'equipes', 'is_active'),
                           'description': 'Perfil = entra ou não no admin. '
                                          'Equipes e TIs (abaixo) = o que pode ver.'}),
    )
    FIELDSET_AVANCADO = ('Avançado — somente superusuário', {
        'classes': ('collapse',),
        'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions',
                   'last_login', 'date_joined')})

    add_fieldsets = ((None, {'classes': ('wide',),
        'fields': ('username', 'first_name', 'email', 'password1', 'password2', 'perfil')}),)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return self.add_fieldsets
        if request.user.is_superuser:
            return self.FIELDSETS_SIMPLES + (self.FIELDSET_AVANCADO,)
        return self.FIELDSETS_SIMPLES

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if request.user.is_superuser:   # gate duplo: get_form já marca disabled
            self._sincronizar_perfil(obj, form.cleaned_data['perfil'],
                                     form.cleaned_data.get('equipes', []))
```

`_sincronizar_perfil` remove os 2 grupos de perfil, adiciona o escolhido, ajusta **`is_staff = (perfil == 'admin')`** — Editor é sempre `is_staff=False` (D4) — e faz `set()` das equipes, tudo dentro de um `transaction.atomic()`. O `get_form` herdado do round 9 continua marcando `disabled=True` nos `CAMPOS_DE_ESCALACAO` para não-superusuários; `perfil` e `equipes` entram nessa lista, então um POST forjado por staff é ignorado pelo próprio Django.

**UX do cadastro:** a tela de criação passa a ter **6 campos** (usuário, nome, e-mail, senha ×2, perfil). Depois de salvar, `response_add` redireciona para a tela de atribuição em massa já filtrada pelo novo usuário — "criei o usuário, agora coloco na equipe / dou as TIs" vira um fluxo contínuo.

**Aceite:**
- [ ] Superusuário: tela de criação mostra exatamente os 6 campos; nenhum `user_permissions`/`groups` visível.
- [ ] Staff com `auth.change_user`: não vê o fieldset Avançado **e** um POST com `perfil=admin` não muda nada (regressão direta de `test_staff_com_change_user_nao_se_promove_a_superuser`).
- [ ] Salvar com `perfil=admin` ⟹ `is_staff=True` e grupo `Perfil: Administrador`; salvar com `perfil=editor` ⟹ `is_staff=False` e o grupo antigo removido.
- [ ] Editor recebe **302 para o login do admin** ao tentar `/admin/` (D4).
- [ ] Os 2 grupos de perfil não podem ser excluídos nem renomeados no `GroupAdmin`.
- [ ] `test_superuser_continua_podendo_conceder_privilegio` continua verde (o fieldset Avançado ainda funciona).

### Fase 4 — Atribuição em massa

**PR:** `feat(#132): tela de atribuição em massa de TIs a equipes e usuários`

**URLs** (registradas em `UserTIAdmin.get_urls()` — assim a tela nasce dentro do menu "Atribuições de TI"):

```
/admin/dominial/userti/em-massa/         GET+POST   name='dominial_atribuicao_em_massa'
/admin/dominial/userti/em-massa/previa/  POST(JSON) name='dominial_atribuicao_previa'
```

Ambas envoltas em `self.admin_site.admin_view(...)` **e** com `if not request.user.is_superuser: raise PermissionDenied` explícito no corpo (D3) — `admin_view` só exige `is_staff`, e o projeto já aprendeu isso em `nova_importacao_view` (`admin.py:800`).

**Form** (widget de duas colunas do próprio admin, com busca — suficiente para as 646 TIs, ver A11):

```python
class AtribuicaoEmMassaForm(forms.Form):
    acao = forms.ChoiceField(choices=[('conceder', 'Conceder acesso'),
                                      ('revogar',  'Revogar acesso')],
                             initial='conceder', widget=forms.RadioSelect)
    tis = forms.ModelMultipleChoiceField(
        queryset=TIs.objects.order_by('nome'), label='Terras Indígenas',
        widget=FilteredSelectMultiple('Terras Indígenas', is_stacked=False))
    equipes = forms.ModelMultipleChoiceField(          # veículo principal (D6): vem primeiro
        queryset=Group.objects.filter(acesso__tipo=GrupoAcesso.EQUIPE).order_by('name'),
        required=False, widget=FilteredSelectMultiple('equipes', False))
    usuarios = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True, is_superuser=False).order_by('username'),
        required=False, widget=FilteredSelectMultiple('usuários', False),
        help_text='Use só quando a atribuição não couber em nenhuma equipe.')

    def clean(self):
        if not (self.cleaned_data.get('equipes') or self.cleaned_data.get('usuarios')):
            raise ValidationError('Selecione ao menos uma equipe ou um usuário.')
```

**UX:** uma tela, um form, dois sentidos atendidos pelo mesmo widget — escolher 3 TIs e 2 equipes, ou 1 equipe e 40 TIs, é a mesma operação. Antes de aplicar, um bloco de **prévia** (AJAX em `previa/`, ou `POST` com botão "Revisar" ⟶ tela de confirmação) mostra:

> Conceder **TI Alfa, TI Beta** a **1 equipe (Equipe Norte — 8 membros)** e **2 usuários**.
> Isso dá acesso a **17 imóveis** (hoje) **e a todos os imóveis futuros dessas TIs**.
> 2 vínculos já existem e serão ignorados.

A frase "e a todos os imóveis futuros" é obrigatória na tela — é a diferença semântica que o produto está comprando (D2/R13).

Aplicação, em `transaction.atomic()`:

```python
UserTI.objects.bulk_create(
    [UserTI(user=u, tis=t, atribuido_por=request.user) for u in usuarios for t in tis],
    ignore_conflicts=True,   # unique_together absorve o que já existia
)
GroupTI.objects.bulk_create(
    [GroupTI(group=g, tis=t, atribuido_por=request.user) for g in equipes for t in tis],
    ignore_conflicts=True,
)
```

Revogação é `UserTI.objects.filter(user__in=usuarios, tis__in=tis).delete()` (idem `GroupTI`).

**Segurança:** CSRF pelo `{% csrf_token %}` (nenhum `csrf_exempt`), método POST obrigatório para mutação, `GET` só renderiza, `atribuido_por=request.user` em toda linha criada, e um `LogEntry` de resumo por operação. A contagem de imóveis da prévia usa `Imovel.objects.for_user(request.user).filter(terra_indigena_id__in=tis).count()` — respeita `ManagerOptInRegressaoTest` e, como só superusuário chega ali, conta tudo.

**Admin actions** (atalhos que caem na mesma tela, pré-preenchida):
- `TIsAdmin.actions = ['atribuir_tis_selecionadas']` → `redirect(url + '?tis=1,2,3')`.
- `UserAdmin.actions = ['atribuir_tis_aos_usuarios']` → `?usuarios=4,5`.
- `GroupAdmin.actions = ['atribuir_tis_as_equipes']` → `?equipes=1,2`.
- Todas **obrigatoriamente** com `allowed_permissions = ('view',)` + gate de superuser no corpo — `test_toda_action_customizada_declara_allowed_permissions` (`test_segregacao_usuario.py:1477`) varre o registry inteiro e falha sem isso.

**Onde fica no menu:** seção **DOMINIAL** do admin — *Atribuições de TI* (com o botão "Atribuição em massa" no topo do changelist) e *Atribuições de TI por equipe*. *Atribuições de Imóveis* permanece visível só até a migração da Fase 6, e some depois (A7). Só superusuários veem qualquer uma.

**Aceite:**
- [ ] Superusuário atribui 2 TIs a 1 equipe + 2 usuários em um POST; todas as linhas nascem com `atribuido_por` correto.
- [ ] Reaplicar a mesma operação não cria duplicatas nem estoura `IntegrityError`.
- [ ] Revogar remove só o que foi pedido.
- [ ] Staff não-superuser: **403** no `GET` e no `POST` da tela e da prévia; a tela não aparece no `admin:index`.
- [ ] POST sem CSRF → 403.
- [ ] A prévia conta corretamente 0 imóveis para TI vazia **e ainda assim menciona os imóveis futuros**.
- [ ] `assertNumQueries` da aplicação é O(1) em relação ao número de destinos (bulk, não loop de `save`).
- [ ] A tela renderiza com as 646 TIs sem degradar perceptivelmente (teste de fumaça, não benchmark).

### Fase 5 — Equipes na UX

**PR:** `feat(#132): gestão de equipes e membership em massa`

`GroupAdmin` customizado: criação de equipe com **nome + descrição opcional** (D8), `list_display` com nome, tipo, nº de membros, nº de TIs; inline de `GroupTI`; widget de membros (o `Group` de série não edita membership — adicionar um `ModelMultipleChoiceField` `usuarios` que faz `group.user_set.set(...)`, gravando `LogEntry`). Perfis (`protegido=True`) aparecem em modo leitura.

**Aceite:** criar equipe com nome e descrição, adicionar 5 usuários e 3 TIs em uma tela; remover 1 usuário e ele perde acesso na requisição seguinte; excluir a equipe revoga todos; equipe não pode receber `tipo=PERFIL`.

### Fase 6 — Migrar `UserImovel` → `UserTI` e tirar a camada da UI

**PR:** `feat(#132): command de migração das atribuições por imóvel para nível de TI`

```
python manage.py migrar_userimovel_para_userti            # DRY-RUN (padrão)
python manage.py migrar_userimovel_para_userti --aplicar  # aplica
```

O dry-run é o **modo padrão e obrigatório** — sem `--aplicar` o command nunca escreve (D7). Relatório, por usuário e TI:

```
usuario  | TI            | imóveis que vê hoje | passará a ver (hoje) | delta
---------|---------------|---------------------|----------------------|------
mariana  | TI Alfa       | 3 de 7              | 7                    | +4
mariana  | TI Beta       | 2 de 2              | 2                    |  0
...
TOTAL: 12 UserTI a criar, 31 UserImovel a remover, 18 imóveis a mais visíveis hoje.
ATENÇÃO: após a conversão, estes usuários também verão TODO imóvel FUTURO destas TIs.
```

Aplicação em `transaction.atomic()`, com `bulk_create(..., ignore_conflicts=True)` e `atribuido_por` = o superusuário que rodou (ou `None`, com `--como-usuario <username>` para carimbar). O command é **idempotente**: rodar de novo com tudo migrado não faz nada.

Depois que o command rodar em produção, no mesmo PR ou no seguinte:
- `UserImovelAdmin` e o inline no `UserAdmin` saem do menu;
- `imovel_views.py:71` (`UserImovel.get_or_create`) é removido (A7);
- o termo `imoveis_diretos_ids` **permanece** no `for_user` por um release, como rede de rollback, com comentário datado apontando para o PR de remoção.

**Aceite:**
- [ ] Sem `--aplicar`, o banco não muda (`assertNumQueries` só de leitura, contagens antes/depois iguais).
- [ ] O relatório mostra o delta correto num cenário com acesso parcial (3 de 7).
- [ ] Com `--aplicar`, o usuário passa a ver os 7 imóveis; um imóvel novo criado depois na mesma TI também aparece.
- [ ] Rodar duas vezes com `--aplicar` não duplica `UserTI` nem estoura.
- [ ] Depois da remoção do `get_or_create`, cadastrar imóvel numa TI atribuída continua visível para o autor (cobertura vem da TI).
- [ ] `UserImovel` não aparece em nenhuma tela do admin.

---

## Parte C — Testes (padrão de `dominial/tests/test_segregacao_usuario.py`)

Estender `SegregacaoBaseTestCase` com um cenário adicional — `tis_c` + `imovel_c1`, `imovel_c2`; `tis_vazia` (atribuída, sem imóveis); usuários `via_ti` (UserTI em `tis_c`), `via_equipe` (membro de `Group('Equipe Norte')` com `GroupTI` em `tis_c`) e `sem_nada` (nenhuma equipe, nenhum `UserTI`) — e uma classe por tema:

```python
class UniaoDeFontesTest(SegregacaoBaseTestCase):
    def test_uniao_das_fontes(self)                         # equipe ∪ TI direta, sem duplicata
    def test_acesso_por_ti_alcanca_todos_os_imoveis_da_ti(self)
    def test_acesso_por_equipe_alcanca_os_mesmos_imoveis(self)
    def test_ti_nao_atribuida_continua_invisivel(self)
    def test_for_user_faz_uma_unica_query(self)             # assertNumQueries(1)
    def test_for_user_nao_duplica_linhas(self)              # TI atribuída por equipe E direta

class HomeTest(SegregacaoBaseTestCase):                     # D6
    def test_usuario_sem_equipe_e_sem_ti_direta_nao_ve_nenhuma_ti(self)   # home vazia
    def test_superuser_ve_todas_as_tis(self)                              # inclusive as vazias
    def test_ti_atribuida_sem_imoveis_aparece_na_home(self)
    def test_ti_atribuida_so_por_equipe_aparece_na_home(self)
    def test_home_nao_faz_um_count_por_ti(self)             # assertNumQueries limitado (R6)

class ImovelFuturoDeTIAtribuidaTest(SegregacaoBaseTestCase):
    def test_imovel_criado_depois_da_atribuicao_ja_nasce_visivel(self)    # D2/R13
    def test_editor_com_ti_cadastra_imovel_e_continua_vendo(self)         # via POST em imovel_cadastro
    def test_imovel_que_muda_de_ti_troca_de_dono(self)                    # A5: perde de um lado, ganha do outro
    def test_alterar_ti_mostra_quem_perde_e_quem_ganha(self)              # A5

class ImportacaoEntreCadeiasTest(SegregacaoBaseTestCase):   # D2
    def test_importa_de_uma_cadeia_para_outra_da_mesma_ti_com_a_ti_atribuida(self)
    def test_importacao_de_cadeia_de_ti_nao_atribuida_continua_404(self)

class RevogacaoTest(SegregacaoBaseTestCase):
    def test_remover_userti_revoga_na_hora(self)
    def test_sair_da_equipe_revoga_na_hora(self)
    def test_excluir_equipe_revoga_na_hora(self)            # CASCADE em GroupTI
    def test_excluir_usuario_limpa_userti(self)             # CASCADE

class TisForUserTest(SegregacaoBaseTestCase):
    def test_ti_atribuida_sem_imoveis_aparece(self)         # semântica nova (A8)
    def test_dropdown_de_ti_do_imovel_admin_oferece_ti_atribuida(self)  # formfield_for_foreignkey
    def test_filtro_da_sidebar_nao_vaza_ti_alheia(self)     # TIsSegregadaFilter com a nova fonte

class SuperuserBypassFase2Test(SegregacaoBaseTestCase):
    def test_superuser_sem_userti_nem_equipe_ve_tudo(self)
    def test_superuser_ve_ti_vazia(self)

class PerfilUsuarioAdminTest(SegregacaoBaseTestCase):       # Fase 3
    def test_cadastro_de_usuario_mostra_apenas_campos_simples(self)
    def test_radio_de_perfil_tem_exatamente_duas_opcoes(self)
    def test_fieldset_avancado_some_para_nao_superuser(self)
    def test_staff_nao_muda_o_proprio_perfil_por_post_forjado(self)   # 'perfil' em CAMPOS_DE_ESCALACAO
    def test_perfil_administrador_marca_is_staff(self)
    def test_perfil_editor_nao_e_staff_e_nao_entra_no_admin(self)     # D4
    def test_trocar_de_perfil_remove_o_grupo_anterior(self)
    def test_grupos_de_perfil_sao_protegidos(self)

class AtribuicaoEmMassaTest(SegregacaoBaseTestCase):        # Fase 4
    def test_superuser_atribui_varias_tis_a_equipes_e_usuarios(self)
    def test_operacao_e_idempotente(self)
    def test_staff_recebe_403_na_tela_e_no_post(self)
    def test_post_sem_csrf_e_recusado(self)                 # Client(enforce_csrf_checks=True)
    def test_atribuido_por_carimbado_em_todas_as_linhas(self)
    def test_previa_conta_imoveis_corretamente(self)
    def test_actions_declaram_allowed_permissions(self)     # já coberto pelo varredor global

class MigracaoUserImovelTest(SegregacaoBaseTestCase):       # Fase 6
    def test_dry_run_nao_escreve_nada(self)
    def test_dry_run_relata_ampliacao_de_acesso(self)       # 3 de 7 → 7
    def test_aplicar_cria_userti_e_amplia_acesso(self)
    def test_aplicar_duas_vezes_e_idempotente(self)
```

**Removidos desta revisão:** `GateDeEscritaTest` inteira e todo cenário de perfil Leitor (fora do MVP, D1); `test_imovel_direto_de_ti_nao_coberta_continua_visivel`, `test_userimovel_direto_sobrevive_a_mudanca_de_ti`, `test_revogar_ti_nao_derruba_imovel_direto` e `test_revogacao_em_massa_nao_toca_userimovel` (acesso parcial deixa de existir, D2/D7 — o legado é coberto por `MigracaoUserImovelTest`).

Regressões que **não podem** ser alteradas para passar: `MustFixRound8Test`, `MustFixRound9Test`, `ManagerOptInRegressaoTest`, `ViewsEscritaBloqueadaTest`, `MediaSegregacaoTest`. Se alguma quebrar, é sinal de regressão de segurança real, não de teste desatualizado. Os 9 rounds de hardening já aprovados **não são tocados** por nenhuma fase deste plano.

Rodar `/security-review` ao final das Fases 2, 3, 4 e 6.

---

## Parte D — Riscos e edge cases

| # | Risco | Avaliação / mitigação |
|---|---|---|
| R1 | **Imóvel sem TI** | Impossível pelo schema: `Imovel.terra_indigena_id` é FK sem `null=True` desde a `0001_initial` (`imovel_models.py:23`). Com a regra passando a ser **exclusivamente** por TI (D2), isso deixa de ser detalhe e vira pré-condição: um imóvel sem TI seria invisível para todo mundo menos superusuário. Confirmar em produção com `Imovel.objects.filter(terra_indigena_id__isnull=True).count()` antes do deploy — deve ser 0. |
| R2 | **`PROTECT` em `TIs`** | `Imovel.terra_indigena_id` é `PROTECT`: TI com imóveis não é excluível — `tis_delete` (`tis_views.py:141`) contorna apagando os imóveis antes, e só superuser chega lá. `UserTI`/`GroupTI` são **CASCADE** de propósito: `PROTECT` neles impediria excluir uma TI vazia só porque alguém a tinha atribuída. |
| R3 | **Escalação via novos admins** | O maior risco do PR. `UserTIAdmin`/`GroupTIAdmin`/`GrupoAcessoAdmin` e a tela em massa **precisam** dos cinco `has_*_permission → is_superuser` (D3). Um staff com `add_userti` se dá o sistema inteiro em um POST. Teste dedicado, obrigatório. |
| R4 | **`perfil` contornando `CAMPOS_DE_ESCALACAO`** | O campo `perfil` grava em `groups` e mexe em `is_staff`; se ficar fora de `CAMPOS_DE_ESCALACAO`, reabre exatamente o buraco do round 9 por uma porta nova. Entra na tupla **e** o gate em `save_model` é duplicado. Vale o mesmo para `equipes`, que concede TIs. |
| R5 | **Granularidade só por TI é grossa por decisão** | Não existe mais "dar um imóvel só". Se algum dia aparecer o caso legítimo (perícia pontual, consultoria externa), a resposta é **criar uma TI-escopo** ou reabrir a camada `UserImovel` num PR próprio — não improvisar. Registrado aqui para que a ausência seja lida como decisão (D2), não como esquecimento. |
| R6 | **Performance da home com 646 TIs** | `tis_views.home` (`tis_views.py:23-26`) faz **um `COUNT` por TI num dict comprehension**. Com o superusuário vendo as 646 TIs (D6/D9), isso é 646 queries por pageview — e piora com TIs vazias entrando na lista. Trocar por `annotate(Count(...))` sobre `tis_for_user` **na mesma fase** (Fase 2). O filtro em si é 1 query com semi-joins; `UserTI(tis)`/`GroupTI(tis)` indexados e `Imovel.terra_indigena_id` já tem índice de FK. Com ~50 imóveis (triplicando em 12 meses), nada mais aqui é gargalo. |
| R7 | **`distinct()` sumindo/aparecendo** | `for_user` deixa de precisar de `distinct` (bom: `distinct` quebra `annotate(Count)`), mas `tis_for_user` e `pessoas_for_user` **continuam** precisando. Não remover por engano. |
| R8 | **Raw SQL de `tis_detail`** | `tis_views.py:78` filtra por `dominial_userimovel` na mão — depois da Fase 2 ele passa a **negar acesso legítimo** a quem tem só a TI, que passará a ser *todo mundo*. É o ponto mais fácil de esquecer; por isso está na Fase 0, com item de aceite próprio. |
| R9 | **`AtribuicaoAuditoriaMixin` míope** | `save_formset` (`admin.py:200`) faz `if formset.model is not UserImovel: return super()...` — com o inline de `UserTI`, o `super()` grava **sem** `atribuido_por` e **sem** `PermissionDenied` para não-superuser. Generalizar na Fase 2. |
| R10 | **Confusão perfil × equipe** | Mitigado por A2 (`GrupoAcesso.tipo` + validação em `GroupTI.clean`). Sem isso, atribuir uma TI ao grupo `Perfil: Editor` dá a TI a **todos** os editores, silenciosamente. |
| R11 | **`TIs_Imovel` órfão** | Ninguém consulta; não usar como fonte de acesso. Remoção fica para PR próprio (A10). |
| R12 | **A migração `UserImovel` → `UserTI` AMPLIA acesso** | Quem hoje tem 3 dos 7 imóveis de uma TI passa a ter os 7 — **e todos os futuros**. É o efeito pretendido (D2), mas é irreversível na prática e não pode acontecer por acidente. Por isso: **dry-run é o modo padrão**, `--aplicar` é explícito, o relatório mostra o delta por usuário/TI antes de qualquer escrita, e o comando roda **uma vez, revisado por humano**. Nunca embutir essa conversão numa data migration. |
| R13 | **Imóvel novo em TI atribuída aparece para todo mundo automaticamente** | Comportamento **desejado** (D2): não há passo de aprovação entre "cadastrei o imóvel" e "a equipe inteira o vê". A consequência operacional é que **atribuir uma TI é um ato permanente e amplo** — quem recebe a TI Alfa recebe tudo que um dia for cadastrado nela. Mitigação: (a) a prévia da atribuição em massa diz isso com todas as letras, (b) revogar a TI corta tudo na hora (A6), (c) documentar na tela de ajuda do admin. Não é risco de segurança; é expectativa a alinhar. |
| R14 | **Editor não entra no `/admin/`** | Cadastrar cartório, corrigir pessoa e `alterar_ti` seguem exclusivos de Administrador/superusuário (D4). Se na prática o Editor precisar cadastrar cartório com frequência, a resposta **não** é promovê-lo a `is_staff` — é expor essa operação numa view do app, fora do admin. Promover Editor a staff espalharia a superfície endurecida dos 9 rounds por 30 contas. |
| R15 | **Ordem dos PRs** | F0 → F1 → F2 são estritamente sequenciais. F3 depende de F1 (grupos de perfil). F4 depende de F1+F2. F5 depende de F4. F6 depende de F2 (precisa do `for_user` novo) e deve rodar **depois** de F4/F5 estarem em produção, para que o superusuário tenha as ferramentas de correção antes de converter os dados. F3 e F4 podem ir em paralelo depois de F2. |

---

## Decisões fechadas (Hiure — produto)

Estas decisões estão fechadas e **prevalecem** sobre qualquer coisa escrita acima. Substituem a seção "Perguntas abertas" da revisão 1.

| # | Decisão | Onde entra no plano |
|---|---|---|
| **D1** | **MVP com 2 perfis: Editor e Administrador.** O perfil *Leitor* sai. O **gate de escrita sai do MVP** — ambos os perfis escrevem. | A1, Fase 3; `GateDeEscritaTest` removida |
| **D2** | **Acesso é sempre por TI inteira.** Quem tem a TI vê **todos** os imóveis sobrepostos a ela (atuais e futuros) e **importa de uma cadeia para outra dentro da TI** automaticamente, sem permissão extra. **Acesso parcial a imóveis de uma TI não existe** — a cadeia dominial é sobre todos os imóveis sobrepostos à mesma TI. | A3, A4, A8; R5, R13 |
| **D3** | **Só superusuário atribui acesso.** A delegação para Administrador (antiga Fase 7) sai. | A9, Fase 4; R3 |
| **D4** | **Editor não entra no `/admin/`** (`is_staff=False`). Operações que só existem no admin (cadastrar cartório, etc.) continuam exclusivas de Administrador/superusuário. | A1, Fase 3; R14 |
| **D5** | **Imóvel não deve mudar de TI**, exceto para corrigir erro de cadastro. `alterar_ti` permanece como caminho de correção: ao salvar, mostra quem perde e quem ganha acesso. **O acesso segue a TI** — sem checkbox "Preservar acesso atual". | A5 |
| **D6** | **Home de não-superusuário: só as TIs atribuídas** às equipes de que o usuário participa e/ou diretamente a ele. **TI atribuída sem imóveis também aparece** (é o caminho para cadastrar o primeiro imóvel). Superusuário vê todas. **Equipes são o veículo principal**; atribuição direta usuário→TI é caminho secundário. | A8, Fase 2; `HomeTest` |
| **D7** | **Eliminar a camada `UserImovel` da UI.** Migrar as atribuições por imóvel existentes para nível de TI via management command com **dry-run obrigatório** (mostra o impacto antes de aplicar — a conversão amplia acesso, pois passa a cobrir imóveis futuros). | A7, Fase 6; R12 |
| **D8** | **Equipes criadas pelo superusuário** de forma simples (nome + descrição opcional), **sem seed** pré-definido. | A2, Fase 1 (só os 2 perfis são seedados), Fase 5 |
| **D9** | **Escala real: 30 usuários, 646 TIs (24 com imóveis), ~50 imóveis; deve triplicar em 12 meses.** `FilteredSelectMultiple` com busca é suficiente; **sem paginação**. | A11, Fase 4; R6 |
| **D10** | **Cartórios: leitura/uso para todos os usuários; só admin/superusuário cadastra novos cartórios** (CRI de registro de imóveis). Não complexificar — se Editor precisar de operação de cartório, expor leitura/uso no app, nunca cadastro. Editor **nunca** vira `is_staff` por causa de cartório. | A1, Fase 3; R14 |
