"""
Testes de segregação de dados por usuário (issue #132).

Cenários cobertos:
- superuser vê tudo (bypass);
- usuário comum vê apenas os imóveis atribuídos;
- usuário sem atribuição vê listas vazias;
- guard de posse bloqueia leitura E escrita fora do escopo (404);
- Cartorios/Pessoas permanecem globais.
"""

from datetime import date

from django.contrib.auth.models import AnonymousUser, User
from django.test import Client, TestCase
from django.urls import reverse

from dominial.managers import (
    documentos_for_user,
    lancamentos_for_user,
    tis_for_user,
)
from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
    UserImovel,
)
from dominial.utils.segregacao_utils import usuario_tem_acesso_imovel


class SegregacaoBaseTestCase(TestCase):
    """
    Cenário comum: duas TIs, dois imóveis, três usuários.

    - `superuser`  → nenhuma atribuição, mas vê tudo pelo bypass.
    - `dono`       → atribuído somente ao `imovel_a`.
    - `sem_acesso` → nenhuma atribuição.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username='super', password='senha-super', email='super@example.com'
        )
        cls.dono = User.objects.create_user(username='dono', password='senha-dono')
        cls.sem_acesso = User.objects.create_user(username='zeca', password='senha-zeca')

        cls.tis_a = TIs.objects.create(nome='TI Alfa', codigo='TI-A', etnia='Alfa')
        cls.tis_b = TIs.objects.create(nome='TI Beta', codigo='TI-B', etnia='Beta')

        # estado/cidade preenchidos: ImovelForm estreita o queryset de cartório
        # por estado+cidade vindos do POST.
        cls.cartorio = Cartorios.objects.create(
            nome='CRI Central', cns='111111', estado='SP', cidade='São Paulo'
        )
        cls.proprietario = Pessoas.objects.create(nome='Proprietário Teste')

        cls.imovel_a = Imovel.objects.create(
            nome='Imóvel A', matricula='1000', terra_indigena_id=cls.tis_a,
            proprietario=cls.proprietario, cartorio=cls.cartorio,
        )
        cls.imovel_b = Imovel.objects.create(
            nome='Imóvel B', matricula='2000', terra_indigena_id=cls.tis_b,
            proprietario=cls.proprietario, cartorio=cls.cartorio,
        )

        cls.doc_tipo = DocumentoTipo.objects.create(tipo='matricula')
        cls.documento_a = Documento.objects.create(
            imovel=cls.imovel_a, tipo=cls.doc_tipo, numero='M1000',
            data=date(2024, 1, 1), cartorio=cls.cartorio, livro='1', folha='1',
        )
        cls.documento_b = Documento.objects.create(
            imovel=cls.imovel_b, tipo=cls.doc_tipo, numero='M2000',
            data=date(2024, 1, 1), cartorio=cls.cartorio, livro='1', folha='1',
        )

        cls.lanc_tipo = LancamentoTipo.objects.create(tipo='registro')
        cls.lancamento_a = Lancamento.objects.create(
            documento=cls.documento_a, tipo=cls.lanc_tipo,
            numero_lancamento='R1M1000', data=date(2024, 2, 1),
        )
        cls.lancamento_b = Lancamento.objects.create(
            documento=cls.documento_b, tipo=cls.lanc_tipo,
            numero_lancamento='R1M2000', data=date(2024, 2, 1),
        )

        UserImovel.objects.create(
            user=cls.dono, imovel=cls.imovel_a, atribuido_por=cls.superuser
        )


class ManagerSegregacaoTest(SegregacaoBaseTestCase):
    """Ponto 2 do plano: `Imovel.objects.for_user()` e helpers."""

    def test_superuser_ve_todos_os_imoveis(self):
        visiveis = Imovel.objects.for_user(self.superuser)
        self.assertCountEqual(visiveis, [self.imovel_a, self.imovel_b])

    def test_usuario_comum_ve_apenas_imovel_atribuido(self):
        visiveis = Imovel.objects.for_user(self.dono)
        self.assertCountEqual(visiveis, [self.imovel_a])

    def test_usuario_sem_atribuicao_ve_lista_vazia(self):
        self.assertEqual(Imovel.objects.for_user(self.sem_acesso).count(), 0)

    def test_usuario_anonimo_nao_ve_nada(self):
        self.assertEqual(Imovel.objects.for_user(AnonymousUser()).count(), 0)
        self.assertEqual(Imovel.objects.for_user(None).count(), 0)

    def test_for_user_e_encadeavel_com_outros_filtros(self):
        # A ordem não deve importar: o manager expõe o método no queryset.
        self.assertCountEqual(
            Imovel.objects.filter(terra_indigena_id=self.tis_a).for_user(self.dono),
            [self.imovel_a],
        )
        self.assertEqual(
            Imovel.objects.for_user(self.dono).filter(terra_indigena_id=self.tis_b).count(),
            0,
        )

    def test_documentos_seguem_o_imovel(self):
        self.assertCountEqual(
            documentos_for_user(self.superuser), [self.documento_a, self.documento_b]
        )
        self.assertCountEqual(documentos_for_user(self.dono), [self.documento_a])
        self.assertEqual(documentos_for_user(self.sem_acesso).count(), 0)
        self.assertEqual(documentos_for_user(AnonymousUser()).count(), 0)

    def test_lancamentos_seguem_o_documento(self):
        self.assertCountEqual(
            lancamentos_for_user(self.superuser), [self.lancamento_a, self.lancamento_b]
        )
        self.assertCountEqual(lancamentos_for_user(self.dono), [self.lancamento_a])
        self.assertEqual(lancamentos_for_user(self.sem_acesso).count(), 0)
        self.assertEqual(lancamentos_for_user(AnonymousUser()).count(), 0)

    def test_tis_listadas_apenas_quando_tem_imovel_acessivel(self):
        self.assertCountEqual(tis_for_user(self.superuser), [self.tis_a, self.tis_b])
        self.assertCountEqual(tis_for_user(self.dono), [self.tis_a])
        self.assertEqual(tis_for_user(self.sem_acesso).count(), 0)

    def test_atribuicao_nao_duplica_imovel_no_queryset(self):
        # Dois usuários no mesmo imóvel não podem gerar linhas repetidas.
        UserImovel.objects.create(user=self.sem_acesso, imovel=self.imovel_a)
        self.assertEqual(Imovel.objects.for_user(self.dono).count(), 1)

    def test_cartorios_e_pessoas_permanecem_globais(self):
        # Referência compartilhada: não recebe manager segregado.
        self.assertFalse(hasattr(Cartorios.objects, 'for_user'))
        self.assertFalse(hasattr(Pessoas.objects, 'for_user'))


class GuardPosseTest(SegregacaoBaseTestCase):
    """Ponto 3 do plano: verificação de posse."""

    def test_usuario_tem_acesso_imovel(self):
        self.assertTrue(usuario_tem_acesso_imovel(self.superuser, self.imovel_b.id))
        self.assertTrue(usuario_tem_acesso_imovel(self.dono, self.imovel_a.id))
        self.assertFalse(usuario_tem_acesso_imovel(self.dono, self.imovel_b.id))
        self.assertFalse(usuario_tem_acesso_imovel(self.sem_acesso, self.imovel_a.id))
        self.assertFalse(usuario_tem_acesso_imovel(AnonymousUser(), self.imovel_a.id))
        self.assertFalse(usuario_tem_acesso_imovel(self.dono, None))

    def test_aceita_instancia_de_imovel(self):
        self.assertTrue(usuario_tem_acesso_imovel(self.dono, self.imovel_a))
        self.assertFalse(usuario_tem_acesso_imovel(self.dono, self.imovel_b))

    def test_unique_together_impede_atribuicao_duplicada(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            UserImovel.objects.create(user=self.dono, imovel=self.imovel_a)


class ViewsLeituraSegregadaTest(SegregacaoBaseTestCase):
    """Ponto 5 do plano: leitura nas views."""

    def setUp(self):
        self.client = Client()

    def _login(self, user, senha):
        self.assertTrue(self.client.login(username=user.username, password=senha))

    def test_home_lista_apenas_tis_com_imovel_acessivel(self):
        self._login(self.dono, 'senha-dono')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        tis_exibidas = [tis.id for tis in response.context['terras_indigenas']]
        self.assertEqual(tis_exibidas, [self.tis_a.id])

    def test_home_do_superuser_lista_todas_as_tis(self):
        self._login(self.superuser, 'senha-super')
        response = self.client.get(reverse('home'))
        tis_exibidas = {tis.id for tis in response.context['terras_indigenas']}
        self.assertEqual(tis_exibidas, {self.tis_a.id, self.tis_b.id})

    def test_home_avisa_usuario_sem_imoveis(self):
        self._login(self.sem_acesso, 'senha-zeca')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['terras_indigenas']), [])
        mensagens = [str(m) for m in response.context['messages']]
        self.assertTrue(
            any('Nenhum imóvel atribuído' in m for m in mensagens),
            f'Esperava aviso de ausência de imóveis, veio: {mensagens}',
        )

    def test_lista_de_imoveis_da_tis_e_filtrada(self):
        self._login(self.dono, 'senha-dono')
        response = self.client.get(reverse('imoveis', kwargs={'tis_id': self.tis_a.id}))
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context['imoveis'], [self.imovel_a])

        response = self.client.get(reverse('imoveis', kwargs={'tis_id': self.tis_b.id}))
        self.assertEqual(list(response.context['imoveis']), [])

    def test_tis_detail_lista_apenas_imoveis_atribuidos(self):
        self._login(self.dono, 'senha-dono')
        response = self.client.get(reverse('tis_detail', kwargs={'tis_id': self.tis_a.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([i.id for i in response.context['imoveis']], [self.imovel_a.id])

        response = self.client.get(reverse('tis_detail', kwargs={'tis_id': self.tis_b.id}))
        self.assertEqual(list(response.context['imoveis']), [])

    def test_tis_detail_do_superuser_lista_tudo(self):
        self._login(self.superuser, 'senha-super')
        response = self.client.get(reverse('tis_detail', kwargs={'tis_id': self.tis_b.id}))
        self.assertEqual([i.id for i in response.context['imoveis']], [self.imovel_b.id])

    def test_cartorios_continuam_visiveis_a_todos(self):
        # Referência global: usuário sem imóvel algum ainda enxerga cartórios.
        self._login(self.sem_acesso, 'senha-zeca')
        response = self.client.get(reverse('cartorios'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.cartorio, list(response.context['cartorios']))

    def test_listagem_de_lancamentos_e_segregada(self):
        self._login(self.dono, 'senha-dono')
        response = self.client.get(reverse('lancamentos'))
        self.assertEqual(response.status_code, 200)
        ids = {lanc.id for lanc in response.context['lancamentos']}
        self.assertEqual(ids, {self.lancamento_a.id})

    def test_listagem_de_lancamentos_do_superuser_traz_tudo(self):
        self._login(self.superuser, 'senha-super')
        response = self.client.get(reverse('lancamentos'))
        ids = {lanc.id for lanc in response.context['lancamentos']}
        self.assertEqual(ids, {self.lancamento_a.id, self.lancamento_b.id})


class ViewsEscritaBloqueadaTest(SegregacaoBaseTestCase):
    """
    Ponto 3/5 do plano: conhecer a URL não basta.

    Todas as rotas abaixo devem responder 404 para o imóvel não atribuído —
    404 e não 403, para não revelar a existência do registro.
    """

    def setUp(self):
        self.client = Client()
        self.assertTrue(self.client.login(username='dono', password='senha-dono'))

    def _url_imovel_b(self, nome, **extra):
        kwargs = {'tis_id': self.tis_b.id, 'imovel_id': self.imovel_b.id}
        kwargs.update(extra)
        return reverse(nome, kwargs=kwargs)

    def test_leitura_de_imovel_alheio_da_404(self):
        for nome in ['imovel_detail', 'cadeia_dominial', 'cadeia_dominial_tabela',
                     'tronco_principal', 'obter_arvore_cadeia_dominial']:
            with self.subTest(rota=nome):
                response = self.client.get(self._url_imovel_b(nome))
                self.assertEqual(response.status_code, 404)

    def test_edicao_de_imovel_alheio_da_404(self):
        response = self.client.get(self._url_imovel_b('imovel_editar'))
        self.assertEqual(response.status_code, 404)

    def test_post_de_edicao_de_imovel_alheio_da_404(self):
        response = self.client.post(self._url_imovel_b('imovel_editar'), {
            'matricula': 'HACK', 'nome': 'Invadido',
            'proprietario_nome': 'Invasor', 'cartorio': self.cartorio.id,
        })
        self.assertEqual(response.status_code, 404)
        self.imovel_b.refresh_from_db()
        self.assertEqual(self.imovel_b.nome, 'Imóvel B')

    def test_exclusao_de_imovel_alheio_da_404(self):
        response = self.client.post(self._url_imovel_b('imovel_excluir'))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Imovel.objects.filter(pk=self.imovel_b.pk).exists())

    def test_arquivar_imovel_alheio_da_404(self):
        response = self.client.get(self._url_imovel_b('arquivar_imovel'))
        self.assertEqual(response.status_code, 404)
        self.imovel_b.refresh_from_db()
        self.assertFalse(self.imovel_b.arquivado)

    def test_novo_documento_em_imovel_alheio_da_404(self):
        response = self.client.get(self._url_imovel_b('novo_documento'))
        self.assertEqual(response.status_code, 404)

    def test_novo_lancamento_em_imovel_alheio_da_404(self):
        response = self.client.get(self._url_imovel_b('novo_lancamento'))
        self.assertEqual(response.status_code, 404)

    def test_documento_alheio_detalhado_da_404(self):
        response = self.client.get(self._url_imovel_b(
            'documento_detalhado', documento_id=self.documento_b.id
        ))
        self.assertEqual(response.status_code, 404)

    def test_upload_digital_em_documento_alheio_da_404(self):
        response = self.client.get(self._url_imovel_b(
            'upload_documento_digital', documento_id=self.documento_b.id
        ))
        self.assertEqual(response.status_code, 404)

    def test_lancamento_alheio_da_404(self):
        for nome in ['lancamento_detail', 'editar_lancamento', 'excluir_lancamento']:
            with self.subTest(rota=nome):
                response = self.client.get(self._url_imovel_b(
                    nome, lancamento_id=self.lancamento_b.id
                ))
                self.assertEqual(response.status_code, 404)
        self.assertTrue(Lancamento.objects.filter(pk=self.lancamento_b.pk).exists())

    def test_duplicata_em_documento_alheio_da_404(self):
        response = self.client.post(self._url_imovel_b(
            'verificar_duplicata_ajax', documento_id=self.documento_b.id
        ))
        self.assertEqual(response.status_code, 404)

    def test_api_cadeia_atualizada_de_imovel_alheio_da_404(self):
        response = self.client.get(self._url_imovel_b('get_cadeia_dominial_atualizada'))
        self.assertEqual(response.status_code, 404)

    def test_imovel_proprio_continua_acessivel(self):
        # Contraprova: o mesmo usuário acessa normalmente o que lhe pertence.
        response = self.client.get(reverse('imovel_detail', kwargs={
            'tis_id': self.tis_a.id, 'imovel_id': self.imovel_a.id
        }))
        self.assertEqual(response.status_code, 200)


class SuperuserBypassViewsTest(SegregacaoBaseTestCase):
    """Ponto 3 do plano: superuser sem nenhuma atribuição acessa tudo."""

    def setUp(self):
        self.client = Client()
        self.assertTrue(self.client.login(username='super', password='senha-super'))

    def test_superuser_acessa_imovel_sem_atribuicao(self):
        self.assertFalse(UserImovel.objects.filter(user=self.superuser).exists())
        for tis, imovel in [(self.tis_a, self.imovel_a), (self.tis_b, self.imovel_b)]:
            with self.subTest(imovel=imovel.matricula):
                response = self.client.get(reverse('imovel_detail', kwargs={
                    'tis_id': tis.id, 'imovel_id': imovel.id
                }))
                self.assertEqual(response.status_code, 200)

    def test_superuser_acessa_cadeia_de_qualquer_imovel(self):
        response = self.client.get(reverse('cadeia_dominial_tabela', kwargs={
            'tis_id': self.tis_b.id, 'imovel_id': self.imovel_b.id
        }))
        self.assertEqual(response.status_code, 200)


class AutocompleteSegregadoTest(SegregacaoBaseTestCase):
    """Autocomplete não pode virar canal de vazamento."""

    def setUp(self):
        self.client = Client()

    def test_cartorio_autocomplete_continua_global(self):
        self.client.login(username='zeca', password='senha-zeca')
        response = self.client.get(reverse('cartorio-autocomplete'), {'q': 'Central'})
        self.assertEqual(response.status_code, 200)
        nomes = [c['nome'] for c in response.json()['results']]
        self.assertIn('CRI Central', nomes)

    def test_pessoa_autocomplete_continua_global(self):
        self.client.login(username='zeca', password='senha-zeca')
        response = self.client.get(reverse('pessoa-autocomplete'), {'q': 'Propriet'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['results'])

    def test_autocomplete_exige_autenticacao(self):
        response = self.client.get(reverse('cartorio-autocomplete'), {'q': 'Central'})
        self.assertIn(response.status_code, (302, 403))


class CriacaoAtribuiAoAutorTest(SegregacaoBaseTestCase):
    """
    Quem cria um imóvel precisa continuar enxergando-o.

    Sem a atribuição automática, um usuário comum cadastraria o imóvel e o
    perderia de vista no redirect seguinte.
    """

    def setUp(self):
        self.client = Client()
        self.assertTrue(self.client.login(username='dono', password='senha-dono'))

    def test_imovel_criado_fica_atribuido_ao_autor(self):
        response = self.client.post(
            reverse('imovel_cadastro', kwargs={'tis_id': self.tis_a.id}),
            {
                'matricula': '3000',
                'nome': 'Imóvel Novo',
                'tipo_documento_principal': 'matricula',
                'proprietario_nome': 'Proprietário Teste',
                'cartorio': self.cartorio.id,
                'estado': 'SP',
                'cidade': 'São Paulo',
            },
        )
        self.assertEqual(response.status_code, 302)

        novo = Imovel.objects.get(matricula='3000')
        self.assertTrue(
            UserImovel.objects.filter(user=self.dono, imovel=novo).exists(),
            'O autor do cadastro deve receber a atribuição automaticamente.',
        )
        self.assertIn(novo, Imovel.objects.for_user(self.dono))


class DataMigrationAtribuicaoTest(TestCase):
    """Ponto 6 do plano: data migration defensiva."""

    def test_funcao_atribui_todos_os_imoveis_aos_superusers(self):
        import importlib

        from django.apps import apps

        # O nome do módulo começa com dígito: só é importável por importlib.
        migracao = importlib.import_module(
            'dominial.migrations.0058_atribui_imoveis_existentes_superusers'
        )

        superuser = User.objects.create_superuser(
            username='raiz', password='x', email='raiz@example.com'
        )
        comum = User.objects.create_user(username='comum', password='x')
        tis = TIs.objects.create(nome='TI Mig', codigo='TI-MIG', etnia='Mig')
        cartorio = Cartorios.objects.create(nome='CRI Mig', cns='999999')
        pessoa = Pessoas.objects.create(nome='Dono Mig')
        imovel = Imovel.objects.create(
            nome='Imóvel Mig', matricula='9000', terra_indigena_id=tis,
            proprietario=pessoa, cartorio=cartorio,
        )

        migracao.atribuir_imoveis_aos_superusers(apps, None)

        self.assertTrue(UserImovel.objects.filter(user=superuser, imovel=imovel).exists())
        self.assertFalse(UserImovel.objects.filter(user=comum).exists())

        # Idempotência: rodar de novo não duplica (unique_together protegeria,
        # mas o bulk_create quebraria).
        migracao.atribuir_imoveis_aos_superusers(apps, None)
        self.assertEqual(UserImovel.objects.filter(user=superuser).count(), 1)

        migracao.remover_atribuicoes_dos_superusers(apps, None)
        self.assertFalse(UserImovel.objects.filter(user=superuser).exists())
