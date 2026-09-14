# Issue #210 — Sincronização de cartório do imóvel e documento principal Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Impedir que uma edição de `Imovel.cartorio` deixe o documento principal em outro cartório, sincronizando o caso inequívoco e bloqueando os casos sem candidato, ambíguos ou conflitantes.

**Architecture:** `Documento.imovel` é uma `ForeignKey(..., related_name='documentos')`; portanto, o documento principal candidato será localizado entre `imovel.documentos` pelo mesmo `tipo__tipo` e `numero_normalizado` do imóvel, sem usar cartório nessa primeira busca. Um service concentrará a regra “exatamente um candidato + identidade livre no cartório destino”; o formulário público e um `ModelForm` próprio do admin apresentarão o mesmo erro, enquanto view e admin farão a atualização de imóvel e documento em uma transação e invalidarão o cache do tronco. A auditoria será um management command estritamente read-only, com tabela no stdout e CSV opcional também no stdout.

**Tech Stack:** Python 3.13, Django 5.2, Django ORM, SQLite nos testes, `django.test`, management commands.

---

## Investigação confirmada

- `dominial/models/documento_models.py:31`: `Documento.imovel = models.ForeignKey('Imovel', on_delete=models.CASCADE, related_name='documentos')`.
- A identidade do imóvel é `Imovel.tipo_documento_principal + Imovel.matricula_normalizada + Imovel.cartorio_id`.
- A identidade do documento é `Documento.tipo + Documento.numero_normalizado + Documento.cartorio_id`.
- `dominial/utils/ordenacao_cadeia.py:58` e `dominial/utils/hierarquia_utils.py:190` exigem as três partes, inclusive cartório, para reconhecer o documento do imóvel e iniciar o tronco principal.
- O candidato a documento principal antes da troca de cartório é, portanto, o documento vinculado ao imóvel com `tipo__tipo=imovel.tipo_documento_principal` e `numero_normalizado=imovel.matricula_normalizada`. O cartório fica fora desse filtro para que uma divergência já existente continue localizável.
- A sincronização é segura somente quando esse filtro retorna exatamente um documento e não existe outro documento com a mesma identidade no cartório destino. Zero candidatos não permite saber o que atualizar; dois ou mais candidatos não permitem escolher sem decisão humana.
- `dominial/views/imovel_views.py` usa `ImovelForm` e hoje só cria documento no cadastro. Na edição, salva apenas o imóvel.
- `dominial/admin.py:91` usa o `ModelForm` automático de `ImovelAdmin`; não reutiliza `ImovelForm` e salva diretamente pelo `ModelAdmin`.
- `criar_documento_matricula_automatico` permanece intocado: a criação de imóvel já usa o cartório selecionado.
- Baseline de 14/09/2026: 66/68 testes de `dominial.tests.test_identidade_documento` passam. Os dois erros preexistentes são somente `VerificarEstruturaAmbienteCommandTest`, causados por `IndexError` no parser de introspecção SQLite/Django sob Python 3.13. Cada tarefa deve preservar exatamente esse baseline e passar nos testes focados da #210.

### Task 1: Centralizar a resolução segura do documento principal

**Objective:** Criar um service que encontre exatamente um documento principal, liste IDs em estados ambíguos e recuse colisão no cartório destino.

**Files:**
- Create: `dominial/services/imovel_documento_service.py`
- Modify: `dominial/tests/test_identidade_documento.py`

**Step 1: Write failing tests**

Adicionar o import e a classe abaixo em `dominial/tests/test_identidade_documento.py`:

```python
from dominial.services.imovel_documento_service import ImovelDocumentoService


class ImovelDocumentoServiceTest(IdentidadeDocumentoFixture):
    def test_documento_principal_e_o_unico_com_tipo_e_numero_do_imovel(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        principal = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_a
        )
        self.criar_documento(
            imovel, self.tipo_transcricao, 'T14511', self.cartorio_a
        )

        encontrado = ImovelDocumentoService.obter_documento_principal(imovel)

        self.assertEqual(encontrado, principal)

    def test_sem_documento_principal_informa_imovel_tipo_e_numero(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)

        with self.assertRaisesMessage(ValidationError, 'nenhum documento principal'):
            ImovelDocumentoService.obter_documento_principal(imovel)

    def test_documentos_principais_ambiguos_listam_ids(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        documento_a = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_a
        )
        documento_b = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_b
        )

        with self.assertRaises(ValidationError) as contexto:
            ImovelDocumentoService.obter_documento_principal(imovel)

        mensagem = ' '.join(contexto.exception.messages)
        self.assertIn(str(documento_a.pk), mensagem)
        self.assertIn(str(documento_b.pk), mensagem)

    def test_cartorio_destino_com_identidade_ocupada_lista_documento(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        principal = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_a
        )
        outro_imovel = self.criar_imovel('999', self.cartorio_b, nome='Outro')
        conflito = self.criar_documento(
            outro_imovel, self.tipo_matricula, 'M14511', self.cartorio_b
        )

        with self.assertRaises(ValidationError) as contexto:
            ImovelDocumentoService.validar_destino(principal, self.cartorio_b)

        self.assertIn(str(conflito.pk), ' '.join(contexto.exception.messages))
```

**Step 2: Run test to verify failure**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento.ImovelDocumentoServiceTest -v 2`

Expected: FAIL — `ModuleNotFoundError: No module named 'dominial.services.imovel_documento_service'`.

**Step 3: Write minimal implementation**

Criar `dominial/services/imovel_documento_service.py`:

```python
"""Mantém alinhados o cartório do imóvel e o de seu documento principal."""

from django.core.exceptions import ValidationError

from ..models import Documento
from .cache_service import CacheService


class ImovelDocumentoService:
    """Resolve e sincroniza o documento que representa a identidade do imóvel."""

    @staticmethod
    def candidatos_documento_principal(imovel):
        if not imovel.pk:
            return Documento.objects.none()
        return Documento.objects.filter(
            imovel_id=imovel.pk,
            tipo__tipo=imovel.tipo_documento_principal,
            numero_normalizado=imovel.matricula_normalizada,
        ).select_related('tipo', 'cartorio').order_by('pk')

    @classmethod
    def obter_documento_principal(cls, imovel):
        candidatos = list(cls.candidatos_documento_principal(imovel))
        tipo = imovel.get_tipo_documento_principal_display()
        numero = imovel.matricula_normalizada

        if not candidatos:
            raise ValidationError(
                'Não é possível alterar o cartório do imóvel '
                f'ID {imovel.pk}: nenhum documento principal foi encontrado '
                f'para {tipo} {numero}. Corrija os documentos vinculados antes '
                'de tentar novamente.'
            )
        if len(candidatos) > 1:
            ids = ', '.join(str(documento.pk) for documento in candidatos)
            raise ValidationError(
                'Não é possível alterar o cartório do imóvel '
                f'ID {imovel.pk}: há {len(candidatos)} documentos principais '
                f'candidatos para {tipo} {numero} (IDs: {ids}). Corrija a '
                'ambiguidade antes de tentar novamente.'
            )
        return candidatos[0]

    @staticmethod
    def validar_destino(documento, novo_cartorio):
        conflitos = Documento.objects.filter(
            tipo_id=documento.tipo_id,
            numero_normalizado=documento.numero_normalizado,
            cartorio_id=novo_cartorio.pk,
        ).exclude(pk=documento.pk).order_by('pk')
        ids = list(conflitos.values_list('pk', flat=True))
        if ids:
            ids_formatados = ', '.join(str(documento_id) for documento_id in ids)
            raise ValidationError(
                'Não é possível alterar o cartório do imóvel: o cartório de '
                'destino já possui documento com a mesma identidade '
                f'(IDs: {ids_formatados}).'
            )

    @classmethod
    def validar_alteracao_cartorio(cls, imovel, novo_cartorio):
        if not imovel.pk or not novo_cartorio:
            return None
        if imovel.cartorio_id == novo_cartorio.pk:
            return None
        documento = cls.obter_documento_principal(imovel)
        cls.validar_destino(documento, novo_cartorio)
        return documento

    @classmethod
    def sincronizar_cartorio_documento_principal(cls, imovel):
        documento = cls.obter_documento_principal(imovel)
        cls.validar_destino(documento, imovel.cartorio)
        if documento.cartorio_id != imovel.cartorio_id:
            documento.cartorio_id = imovel.cartorio_id
            documento.save(update_fields=['cartorio'])
            CacheService.invalidate_tronco_principal(imovel.pk)
        return documento
```

**Step 4: Run test to verify pass**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento.ImovelDocumentoServiceTest -v 2`

Expected: `Ran 4 tests ... OK`.

**Step 5: Run required module and commit**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento -v 2`

Expected here: all prior 66 tests plus the 4 new tests pass; only the same two preexisting introspection errors remain.

```bash
git add dominial/services/imovel_documento_service.py dominial/tests/test_identidade_documento.py
git commit -m "fix(#210): identificar documento principal com segurança"
```

### Task 2: Sincronizar a edição pela view de imóvel

**Objective:** Tornar o `ImovelForm` inválido nos estados inseguros e atualizar imóvel + documento atomicamente no fluxo `imovel_editar`.

**Files:**
- Modify: `dominial/forms/imovel_forms.py`
- Modify: `dominial/views/imovel_views.py`
- Modify: `dominial/tests/test_identidade_documento.py`

**Step 1: Write failing tests**

Adicionar a `IdentidadeImovelFormTest`:

```python
    def test_edicao_com_um_principal_sincroniza_cartorio_e_preserva_tronco(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        documento = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_a
        )
        dados = self.dados_formulario(self.cartorio_b)
        dados['matricula'] = '14511'
        form = ImovelForm(data=dados, instance=imovel)

        self.assertTrue(form.is_valid(), form.errors.as_json())
        form.save()
        documento.refresh_from_db()
        imovel.refresh_from_db()
        self.assertEqual(documento.cartorio, self.cartorio_b)
        self.assertEqual(identificar_tronco_principal(imovel)[0], documento)

    def test_edicao_sem_principal_e_invalida_e_mantem_cartorio(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        dados = self.dados_formulario(self.cartorio_b)
        dados['matricula'] = '14511'
        form = ImovelForm(data=dados, instance=imovel)

        self.assertFalse(form.is_valid())
        self.assertIn('nenhum documento principal', form.non_field_errors()[0])
        imovel.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)

    def test_edicao_com_principais_ambiguos_e_invalida_e_lista_ids(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        documento_a = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_a
        )
        documento_b = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_b
        )
        cartorio_c = Cartorios.objects.create(
            nome='Cartório C', cns='CNS-C', cidade='Cidade C', estado='GO'
        )
        dados = self.dados_formulario(cartorio_c)
        dados['matricula'] = '14511'
        form = ImovelForm(data=dados, instance=imovel)

        self.assertFalse(form.is_valid())
        mensagem = ' '.join(form.non_field_errors())
        self.assertIn(str(documento_a.pk), mensagem)
        self.assertIn(str(documento_b.pk), mensagem)
        imovel.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)
```

Adicionar imports de `get_user_model` e `reverse`, e a classe:

```python
from django.contrib.auth import get_user_model
from django.urls import reverse


class Issue210ImovelViewTest(IdentidadeDocumentoFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.usuario = get_user_model().objects.create_user(username='issue210')

    def setUp(self):
        self.client.force_login(self.usuario)

    def dados_edicao(self, imovel, cartorio):
        return {
            'nome': imovel.nome,
            'matricula': imovel.matricula,
            'tipo_documento_principal': imovel.tipo_documento_principal,
            'observacoes': imovel.observacoes or '',
            'proprietario_nome': self.pessoa.nome,
            'proprietario': str(self.pessoa.pk),
            'estado': cartorio.estado,
            'cidade': cartorio.cidade,
            'cartorio': str(cartorio.pk),
        }

    def test_view_sincroniza_e_informa_documento_principal(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        documento = self.criar_documento(
            imovel, self.tipo_matricula, 'M14511', self.cartorio_a
        )
        url = reverse('imovel_editar', kwargs={
            'tis_id': self.ti.pk, 'imovel_id': imovel.pk,
        })

        resposta = self.client.post(
            url, self.dados_edicao(imovel, self.cartorio_b), follow=True
        )

        self.assertRedirects(resposta, reverse('tis_detail', args=[self.ti.pk]))
        self.assertContains(resposta, f'documento principal ID {documento.pk}')
        documento.refresh_from_db()
        self.assertEqual(documento.cartorio, self.cartorio_b)

    def test_view_exibe_erro_e_nao_salva_sem_documento_principal(self):
        imovel = self.criar_imovel('14511', self.cartorio_a)
        url = reverse('imovel_editar', kwargs={
            'tis_id': self.ti.pk, 'imovel_id': imovel.pk,
        })

        resposta = self.client.post(url, self.dados_edicao(imovel, self.cartorio_b))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'nenhum documento principal')
        imovel.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)
```

**Step 2: Run test to verify failure**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento.IdentidadeImovelFormTest dominial.tests.test_identidade_documento.Issue210ImovelViewTest -v 2`

Expected: FAIL — edição ainda aceita 0/2 candidatos e o documento continua no cartório antigo.

**Step 3: Write minimal implementation**

Em `dominial/forms/imovel_forms.py`, importar `ValidationError` e o service, e acrescentar ao final de `clean`, antes do `return`:

```python
from django.core.exceptions import ValidationError

from ..services.imovel_documento_service import ImovelDocumentoService


        if cartorio:
            try:
                ImovelDocumentoService.validar_alteracao_cartorio(
                    self.instance, cartorio
                )
            except ValidationError as erro:
                self.add_error(None, erro)
```

Em `dominial/views/imovel_views.py`, adicionar imports:

```python
from django.db import transaction

from ..services.imovel_documento_service import ImovelDocumentoService
```

Substituir o bloco de salvamento por:

```python
            try:
                documento_principal = None
                with transaction.atomic():
                    imovel.save()
                    if not imovel_id:
                        try:
                            documento_matricula = (
                                LancamentoDocumentoService
                                .criar_documento_matricula_automatico(imovel)
                            )
                            messages.info(
                                request,
                                f'Documento de matrícula "{documento_matricula.numero}" '
                                'criado automaticamente.',
                            )
                        except Exception as erro:
                            messages.warning(
                                request,
                                'Imóvel criado, mas houve um problema ao criar o '
                                f'documento de matrícula: {erro}',
                            )
                    elif 'cartorio' in form.changed_data:
                        documento_principal = (
                            ImovelDocumentoService
                            .sincronizar_cartorio_documento_principal(imovel)
                        )

                if documento_principal:
                    messages.info(
                        request,
                        'Cartório do imóvel e do documento principal '
                        f'ID {documento_principal.pk} sincronizados.',
                    )
                messages.success(request, 'Imóvel cadastrado com sucesso!')
                return redirect('tis_detail', tis_id=tis_id)
            except Exception as erro:
                messages.error(request, f'Erro ao salvar imóvel: {erro}')
                return render(
                    request,
                    'dominial/imovel_form.html',
                    {'form': form, 'tis': tis, 'imovel': imovel},
                )
```

**Step 4: Run test to verify pass**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento.IdentidadeImovelFormTest dominial.tests.test_identidade_documento.Issue210ImovelViewTest -v 2`

Expected: all tests pass; the trunk begins with `M14511` after the edit.

**Step 5: Run required module and commit**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento -v 2`

Expected: #210 and prior functional tests pass; only the two unchanged baseline introspection errors remain.

```bash
git add dominial/forms/imovel_forms.py dominial/views/imovel_views.py dominial/tests/test_identidade_documento.py
git commit -m "fix(#210): sincronizar cartório na edição de imóvel"
```

### Task 3: Aplicar a mesma regra no Django admin

**Objective:** Validar e sincronizar a edição feita pelo `ImovelAdmin`, exibindo mensagem útil no próprio formulário administrativo.

**Files:**
- Modify: `dominial/admin.py`
- Create: `dominial/tests/test_issue_210_divergencia_cartorio.py`

**Step 1: Write failing tests**

Criar `dominial/tests/test_issue_210_divergencia_cartorio.py`:

```python
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from dominial.models import Cartorios, Documento, DocumentoTipo, Imovel, Pessoas, TIs


class Issue210Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ti = TIs.objects.create(nome='TI #210', codigo='TI-210', etnia='Teste')
        cls.pessoa = Pessoas.objects.create(nome='Pessoa #210', cpf='210')
        cls.cartorio_a = Cartorios.objects.create(
            nome='Cartório A #210', cns='CNS-210-A', cidade='A', estado='MS'
        )
        cls.cartorio_b = Cartorios.objects.create(
            nome='Cartório B #210', cns='CNS-210-B', cidade='B', estado='MT'
        )
        cls.tipo = DocumentoTipo.objects.create(tipo='matricula')

    def criar_imovel(self):
        return Imovel.objects.create(
            terra_indigena_id=self.ti, nome='Imóvel #210',
            proprietario=self.pessoa, matricula='14511',
            tipo_documento_principal='matricula', cartorio=self.cartorio_a,
        )

    def criar_documento(self, imovel, cartorio=None):
        return Documento.objects.create(
            imovel=imovel, tipo=self.tipo, numero='M14511', data='2026-09-14',
            cartorio=cartorio or self.cartorio_a, livro='1', folha='1',
        )

    def dados_admin(self, imovel, cartorio):
        return {
            'matricula': imovel.matricula,
            'nome': imovel.nome,
            'tipo_documento_principal': imovel.tipo_documento_principal,
            'terra_indigena_id': str(self.ti.pk),
            'proprietario': str(self.pessoa.pk),
            'cartorio': str(cartorio.pk),
            'arquivado': '',
            'observacoes': '',
            '_save': 'Salvar',
        }


class ImovelAdminIssue210Test(Issue210Fixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = get_user_model().objects.create_superuser(
            username='admin210', email='admin210@example.com', password='senha'
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_sincroniza_cartorio_do_documento_principal(self):
        imovel = self.criar_imovel()
        documento = self.criar_documento(imovel)
        url = reverse('admin:dominial_imovel_change', args=[imovel.pk])

        resposta = self.client.post(url, self.dados_admin(imovel, self.cartorio_b))

        self.assertEqual(resposta.status_code, 302)
        documento.refresh_from_db()
        self.assertEqual(documento.cartorio, self.cartorio_b)

    def test_admin_exibe_erro_e_nao_salva_sem_documento_principal(self):
        imovel = self.criar_imovel()
        url = reverse('admin:dominial_imovel_change', args=[imovel.pk])

        resposta = self.client.post(url, self.dados_admin(imovel, self.cartorio_b))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'nenhum documento principal')
        imovel.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)
```

**Step 2: Run test to verify failure**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_issue_210_divergencia_cartorio.ImovelAdminIssue210Test -v 2`

Expected: FAIL — o admin ainda aceita o caso sem documento e não sincroniza o caso único.

**Step 3: Write minimal implementation**

Em `dominial/admin.py`, adicionar:

```python
from django.core.exceptions import ValidationError

from .services.imovel_documento_service import ImovelDocumentoService


class ImovelAdminForm(forms.ModelForm):
    class Meta:
        model = Imovel
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        cartorio = cleaned_data.get('cartorio')
        try:
            ImovelDocumentoService.validar_alteracao_cartorio(
                self.instance, cartorio
            )
        except ValidationError as erro:
            self.add_error(None, erro)
        return cleaned_data
```

Configurar e estender `ImovelAdmin`:

```python
@admin.register(Imovel)
class ImovelAdmin(admin.ModelAdmin):
    form = ImovelAdminForm

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change and 'cartorio' in form.changed_data:
            documento = (
                ImovelDocumentoService
                .sincronizar_cartorio_documento_principal(obj)
            )
            messages.success(
                request,
                'Cartório do imóvel e do documento principal '
                f'ID {documento.pk} sincronizados.',
            )
```

**Step 4: Run test to verify pass**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_issue_210_divergencia_cartorio.ImovelAdminIssue210Test -v 2`

Expected: `Ran 2 tests ... OK`.

**Step 5: Run required module and commit**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento -v 2`

Expected: baseline funcional preservado, com somente os dois erros de introspecção já registrados.

```bash
git add dominial/admin.py dominial/tests/test_issue_210_divergencia_cartorio.py
git commit -m "fix(#210): sincronizar cartório também no admin"
```

### Task 4: Adicionar auditoria read-only com saída texto e CSV

**Objective:** Listar divergências atuais entre imóvel e candidato principal sem alterar o banco.

**Files:**
- Create: `dominial/management/commands/auditar_divergencia_cartorio_imovel_documento.py`
- Modify: `dominial/tests/test_issue_210_divergencia_cartorio.py`

**Step 1: Write failing tests**

Adicionar imports e a classe:

```python
from io import StringIO

from django.core.management import call_command


class AuditoriaDivergenciaCartorioCommandTest(Issue210Fixture):
    def test_comando_lista_uma_divergencia_conhecida_sem_escrever(self):
        imovel = self.criar_imovel()
        documento = self.criar_documento(imovel, self.cartorio_b)
        saida = StringIO()

        call_command('auditar_divergencia_cartorio_imovel_documento', stdout=saida)

        texto = saida.getvalue()
        self.assertIn('IMOVEL_ID', texto)
        self.assertIn(str(imovel.pk), texto)
        self.assertIn(str(documento.pk), texto)
        self.assertIn(str(self.cartorio_a.pk), texto)
        self.assertIn(str(self.cartorio_b.pk), texto)
        self.assertIn('Total de divergências: 1', texto)
        imovel.refresh_from_db()
        documento.refresh_from_db()
        self.assertEqual(imovel.cartorio, self.cartorio_a)
        self.assertEqual(documento.cartorio, self.cartorio_b)

    def test_flag_csv_emite_cabecalho_e_divergencia(self):
        imovel = self.criar_imovel()
        documento = self.criar_documento(imovel, self.cartorio_b)
        saida = StringIO()

        call_command(
            'auditar_divergencia_cartorio_imovel_documento', '--csv', stdout=saida
        )

        linhas = saida.getvalue().splitlines()
        self.assertEqual(
            linhas[0],
            'imovel_id,documento_id,tipo,numero_normalizado,'
            'cartorio_imovel_id,cartorio_documento_id',
        )
        self.assertIn(f'{imovel.pk},{documento.pk},matricula,14511', linhas[1])
```

**Step 2: Run test to verify failure**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_issue_210_divergencia_cartorio.AuditoriaDivergenciaCartorioCommandTest -v 2`

Expected: FAIL — `Unknown command: 'auditar_divergencia_cartorio_imovel_documento'`.

**Step 3: Write minimal implementation**

Criar `dominial/management/commands/auditar_divergencia_cartorio_imovel_documento.py`:

```python
"""Audita divergências de cartório entre imóveis e documentos principais."""

import csv

from django.core.management.base import BaseCommand
from django.db.models import F

from dominial.models import Documento


CAMPOS = (
    'imovel_id',
    'documento_id',
    'tipo',
    'numero_normalizado',
    'cartorio_imovel_id',
    'cartorio_documento_id',
)


class Command(BaseCommand):
    help = (
        'Lista, sem alterar dados, documentos principais cujo cartório diverge '
        'do cartório do imóvel.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv', action='store_true', dest='usar_csv',
            help='Emite CSV no stdout em vez da tabela de texto.',
        )

    def handle(self, *args, **options):
        documentos = Documento.objects.filter(
            tipo__tipo=F('imovel__tipo_documento_principal'),
            numero_normalizado=F('imovel__matricula_normalizada'),
        ).exclude(
            cartorio_id=F('imovel__cartorio_id'),
        ).select_related('tipo', 'imovel').order_by('imovel_id', 'pk')

        linhas = [self._linha(documento) for documento in documentos]
        if options['usar_csv']:
            self._escrever_csv(linhas)
        else:
            self._escrever_tabela(linhas)

    @staticmethod
    def _linha(documento):
        return {
            'imovel_id': documento.imovel_id,
            'documento_id': documento.pk,
            'tipo': documento.tipo.tipo,
            'numero_normalizado': documento.numero_normalizado,
            'cartorio_imovel_id': documento.imovel.cartorio_id,
            'cartorio_documento_id': documento.cartorio_id,
        }

    def _escrever_csv(self, linhas):
        escritor = csv.DictWriter(self.stdout, fieldnames=CAMPOS)
        escritor.writeheader()
        escritor.writerows(linhas)

    def _escrever_tabela(self, linhas):
        self.stdout.write(
            'IMOVEL_ID | DOCUMENTO_ID | TIPO | NUMERO_NORMALIZADO | '
            'CARTORIO_IMOVEL_ID | CARTORIO_DOCUMENTO_ID'
        )
        for linha in linhas:
            self.stdout.write(
                f"{linha['imovel_id']} | {linha['documento_id']} | "
                f"{linha['tipo']} | {linha['numero_normalizado']} | "
                f"{linha['cartorio_imovel_id']} | "
                f"{linha['cartorio_documento_id']}"
            )
        self.stdout.write(f'Total de divergências: {len(linhas)}')
```

**Step 4: Run test to verify pass**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_issue_210_divergencia_cartorio.AuditoriaDivergenciaCartorioCommandTest -v 2`

Expected: `Ran 2 tests ... OK`; os objetos continuam divergentes após a auditoria.

**Step 5: Run required suites and commit**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento dominial.tests.test_issue_210_divergencia_cartorio -v 2`

Expected: testes da #210 verdes; somente os dois erros preexistentes de `VerificarEstruturaAmbienteCommandTest` permanecem no módulo legado.

```bash
git add dominial/management/commands/auditar_divergencia_cartorio_imovel_documento.py dominial/tests/test_issue_210_divergencia_cartorio.py
git commit -m "fix(#210): adicionar auditoria de divergência de cartório"
```

### Task 5: Registrar #210 na fila R3

**Objective:** Atualizar a fonte de verdade da fila sem criar seção de release e sem declarar a issue como encerrada.

**Files:**
- Modify: `docs/produto-3/ROADMAP.md`

**Step 1: Update the roadmap**

Adicionar no topo da lista de R3, antes de #144:

```markdown
1. **#210** 🔨 **IMPLEMENTADA, AGUARDANDO REVISÃO** — edição do cartório do
   imóvel sincroniza o documento principal quando há um único candidato;
   estados ausente/ambíguo/conflitante são bloqueados; auditoria read-only
   disponível em `auditar_divergencia_cartorio_imovel_documento`.
```

Renumerar os itens seguintes de R3. Não alterar `CHANGELOG.md`: ele só contém releases históricas e a restrição desta issue proíbe criar uma nova seção de release.

**Step 2: Verify documentation diff**

```bash
git diff --check
git diff -- docs/produto-3/ROADMAP.md
```

Expected: nenhuma falha de whitespace; apenas #210 e a renumeração local de R3 aparecem.

**Step 3: Run required suites before commit**

Run: `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento dominial.tests.test_issue_210_divergencia_cartorio -v 2`

Expected: testes da #210 passam e o baseline continua limitado aos mesmos dois erros preexistentes.

**Step 4: Commit**

```bash
git add docs/produto-3/ROADMAP.md
git commit -m "fix(#210): registrar implementação na fila R3"
```

## Verificação final e parada

1. Rodar `git diff --check` — esperado: sem saída.
2. Rodar `/root/dev/cadeia-dominial/CadeiaDominial/.venv/bin/python manage.py test dominial.tests.test_identidade_documento dominial.tests.test_issue_210_divergencia_cartorio -v 2` — esperado: testes da #210 verdes; registrar separadamente os dois erros preexistentes de introspecção.
3. Rodar `git status --short --branch` e `git log --oneline --decorate -8` — esperado: worktree limpo, commits locais no branch `fix/issue-210-cartorio-divergencia`, sem push.
4. Reportar hash do plano, hashes de implementação, arquivos modificados, resultados exatos e a regra de segurança para aprovação humana.
5. Não fazer push, não abrir PR, não executar integração lenta e não alterar dados de produção.
