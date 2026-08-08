"""
Testes de segregação de dados por usuário (issue #132).

Cenários cobertos:
- superuser vê tudo (bypass);
- usuário comum vê apenas os imóveis atribuídos;
- usuário sem atribuição vê listas vazias;
- guard de posse bloqueia leitura E escrita fora do escopo (404);
- Cartorios/Pessoas permanecem globais.
"""

import re
from datetime import date
from pathlib import Path

from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.core.cache import cache
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

import dominial
from dominial.managers import (
    documentos_for_user,
    lancamentos_for_user,
    pessoas_for_user,
    tis_for_user,
)
from dominial.models import (
    ImportacaoCartorios,
    Alteracoes,
    AlteracoesTipo,
    Cartorios,
    Documento,
    DocumentoImportado,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoPessoa,
    LancamentoTipo,
    Pessoas,
    TIs,
    UserImovel,
)
from dominial.admin import (
    ERRO_IMPORTACAO,
    AlteracoesAdmin,
    DocumentoDigitalAdmin,
    ImovelAdmin,
    ImportacaoCartoriosAdmin,
    PessoasAdmin,
    TIsAdmin,
    TIsSegregadaFilter,
    UserAdmin,
)
from dominial.models.documento_digital_models import DocumentoDigital
from dominial.utils.segregacao_utils import usuario_tem_acesso_imovel
from dominial.services.hierarquia_service import HierarquiaService
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.importacao_cadeia_service import ImportacaoCadeiaService
from dominial.services.cadeia_completa_service import CadeiaCompletaService
from dominial.services.lancamento_criacao_service import (
    ERRO_ATUALIZACAO,
    ERRO_CRIACAO,
    ERRO_DUPLICATA,
    NAO_AUTORIZADO_DOCUMENTO,
    NAO_AUTORIZADO_LANCAMENTO,
    LancamentoCriacaoService,
)


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

    @patch(
        'dominial.views.imovel_views.LancamentoDocumentoService.criar_documento_matricula_automatico',
        side_effect=RuntimeError('falha simulada'),
    )
    def test_falha_no_documento_inicial_desfaz_imovel_e_atribuicao(self, _mock):
        response = self.client.post(
            reverse('imovel_cadastro', kwargs={'tis_id': self.tis_a.id}),
            {
                'matricula': '3001',
                'nome': 'Imóvel com falha',
                'tipo_documento_principal': 'matricula',
                'proprietario_nome': 'Proprietário que deve ser revertido',
                'cartorio': self.cartorio.id,
                'estado': 'SP',
                'cidade': 'São Paulo',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Imovel.objects.filter(matricula='3001').exists())
        self.assertFalse(UserImovel.objects.filter(user=self.dono, imovel__matricula='3001').exists())
        self.assertFalse(
            Pessoas.objects.filter(nome='Proprietário que deve ser revertido').exists()
        )


class BlockersRound3Test(SegregacaoBaseTestCase):
    """Regressões dos vetores cross-tenant encontrados na terceira revisão."""

    def setUp(self):
        self.client = Client()

    def test_staff_sem_atribuicao_nao_exclui_ti_alheia(self):
        self.sem_acesso.is_staff = True
        self.sem_acesso.save(update_fields=['is_staff'])
        self.client.force_login(self.sem_acesso)

        response = self.client.post(reverse('tis_delete', kwargs={'tis_id': self.tis_b.id}))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(TIs.objects.filter(pk=self.tis_b.pk).exists())
        self.assertTrue(Imovel.objects.filter(pk=self.imovel_b.pk).exists())

    def test_duplicata_de_imovel_alheio_retorna_apenas_conflito_generico(self):
        self.client.force_login(self.dono)
        response = self.client.post(
            reverse('verificar_duplicata_ajax', kwargs={
                'tis_id': self.tis_a.id,
                'imovel_id': self.imovel_a.id,
                'documento_id': self.documento_a.id,
            }),
            {
                'origem_completa[]': [self.documento_b.numero],
                'cartorio_origem[]': [str(self.cartorio.id)],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['tem_duplicata'])
        self.assertIsNone(payload['dados_template'])
        self.assertNotIn('documento_origem', payload)
        self.assertNotIn(self.imovel_b.nome, response.content.decode())
        self.assertNotIn(str(self.documento_b.id), response.content.decode())

    def test_importacao_revalida_documentos_no_escopo_do_usuario(self):
        resultado = ImportacaoCadeiaService.importar_cadeia_dominial(
            imovel_destino_id=self.imovel_a.id,
            documento_origem_id=self.documento_b.id,
            documentos_importaveis_ids=[self.documento_b.id],
            usuario_id=self.dono.id,
        )

        self.assertFalse(resultado['sucesso'])
        self.assertFalse(DocumentoImportado.objects.exists())

    def test_services_hierarquicos_nao_cruzam_escopo_nem_cache(self):
        self.lancamento_a.origem = self.documento_b.numero
        self.lancamento_a.cartorio_origem = self.cartorio
        self.lancamento_a.save(update_fields=['origem', 'cartorio_origem'])
        cache.clear()

        # Simula um cálculo global anterior que colocaria a origem alheia no
        # cache legado do imóvel.
        tronco_global = HierarquiaService.obter_tronco_principal(self.imovel_a)
        self.assertIn(self.documento_b, tronco_global)

        tronco_usuario = HierarquiaService.obter_tronco_principal(
            self.imovel_a,
            user=self.dono,
        )
        self.assertEqual([doc.id for doc in tronco_usuario], [self.documento_a.id])

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(
            self.imovel_a,
            documentos_queryset=documentos_for_user(self.dono),
        )
        ids_arvore = {
            node['id'] for node in arvore['documentos']
            if not node.get('is_fim_cadeia')
        }
        self.assertEqual(ids_arvore, {self.documento_a.id})

        contexto = CadeiaCompletaService(user=self.dono).get_cadeia_completa_com_sequencia_personalizada(
            self.tis_a.id,
            self.imovel_a.id,
            str(self.documento_b.id),
        )
        ids_exportados = {
            item['documento'].id
            for tronco in contexto['cadeia_completa']
            for item in tronco['documentos']
        }
        self.assertNotIn(self.documento_b.id, ids_exportados)

    def test_staff_nao_ve_admin_de_atribuicoes_nem_acessa_url_direta(self):
        self.sem_acesso.is_staff = True
        self.sem_acesso.save(update_fields=['is_staff'])
        permissoes = Permission.objects.filter(
            content_type__app_label='dominial',
            codename__in=[
                'add_userimovel',
                'change_userimovel',
                'view_userimovel',
            ],
        )
        self.sem_acesso.user_permissions.set(permissoes)
        self.client.force_login(self.sem_acesso)
        changelist_url = reverse('admin:dominial_userimovel_changelist')

        index = self.client.get(reverse('admin:index'))
        self.assertEqual(index.status_code, 200)
        self.assertNotContains(index, changelist_url)
        self.assertEqual(self.client.get(changelist_url).status_code, 403)


class MustFixRound6Test(SegregacaoBaseTestCase):
    """Regressões dos três vazamentos encontrados na re-review 3."""

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.dono)

    def test_edicao_nao_herda_metadados_de_documento_alheio(self):
        tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')
        self.documento_b.numero = '9000'
        self.documento_b.save(update_fields=['numero'])
        self.lancamento_b.livro_origem = 'LIVRO-SECRETO'
        self.lancamento_b.folha_origem = 'FOLHA-SECRETA'
        self.lancamento_b.save(
            update_fields=['livro_origem', 'folha_origem'],
        )
        lancamento_editado = Lancamento(
            documento=self.documento_a,
            tipo=tipo_inicio,
            numero_lancamento='INICIO-A',
            data=date(2024, 3, 1),
        )
        # Evita executar o signal antes de montar o cenário da edição.
        Lancamento.objects.bulk_create([lancamento_editado])

        response = self.client.post(
            reverse('editar_lancamento', kwargs={
                'tis_id': self.tis_a.id,
                'imovel_id': self.imovel_a.id,
                'lancamento_id': lancamento_editado.id,
            }),
            {
                'tipo_lancamento': str(tipo_inicio.id),
                'numero_lancamento': lancamento_editado.numero_lancamento,
                'data': '2024-03-02',
                'origem_completa[]': ['9000'],
                'cartorio_origem[]': [str(self.cartorio.id)],
                'cartorio_origem_nome[]': [self.cartorio.nome],
                'livro_origem[]': [''],
                'folha_origem[]': [''],
            },
        )

        self.assertEqual(response.status_code, 302)
        lancamento_editado.refresh_from_db()
        self.assertIsNone(lancamento_editado.livro_origem)
        self.assertIsNone(lancamento_editado.folha_origem)
        origem = lancamento_editado.origens_estruturadas.get()
        self.assertIsNone(origem.livro)
        self.assertIsNone(origem.folha)

    def test_edicao_de_imovel_em_url_de_outra_ti_da_404(self):
        response = self.client.post(
            reverse('imovel_editar', kwargs={
                'tis_id': self.tis_b.id,
                'imovel_id': self.imovel_a.id,
            }),
            {
                'matricula': self.imovel_a.matricula,
                'nome': 'Tentativa de mover imóvel',
                'tipo_documento_principal': 'matricula',
                'proprietario_nome': self.proprietario.nome,
                'cartorio': self.cartorio.id,
                'estado': 'SP',
                'cidade': 'São Paulo',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.imovel_a.refresh_from_db()
        self.assertEqual(self.imovel_a.terra_indigena_id_id, self.tis_a.id)

    @patch(
        'dominial.services.lancamento_criacao_service.'
        'LancamentoDuplicataService.verificar_duplicata_antes_criacao',
        return_value={
            'tem_duplicata': True,
            'mensagem': 'duplicata bloqueada',
        },
    )
    def test_flag_apos_importacao_do_post_nao_pula_duplicata(self, verificar):
        request = RequestFactory().post('/', {
            'tipo_lancamento': str(self.lanc_tipo.id),
            'numero_lancamento_simples': '2',
            'numero_lancamento': 'R2M1000',
            'apos_importacao': 'true',
        })
        request.user = self.dono
        quantidade_antes = Lancamento.objects.count()

        resultado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request,
            self.tis_a,
            self.imovel_a,
            self.documento_a,
        )

        verificar.assert_called_once_with(request, self.documento_a)
        self.assertEqual(resultado['tipo'], 'duplicata_encontrada')
        self.assertEqual(mensagem, 'duplicata bloqueada')
        self.assertEqual(Lancamento.objects.count(), quantidade_antes)


class AdminSegregacaoRound4Test(SegregacaoBaseTestCase):
    """Admins derivados de imóvel respeitam a atribuição do usuário."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dono.is_staff = True
        cls.dono.save(update_fields=['is_staff'])
        tipo_alteracao = AlteracoesTipo.objects.create(tipo='registro')
        cls.alteracao_a = Alteracoes.objects.create(
            imovel_id=cls.imovel_a,
            tipo_alteracao_id=tipo_alteracao,
            cartorio=cls.cartorio,
            cartorio_origem=cls.cartorio,
        )
        cls.alteracao_b = Alteracoes.objects.create(
            imovel_id=cls.imovel_b,
            tipo_alteracao_id=tipo_alteracao,
            cartorio=cls.cartorio,
            cartorio_origem=cls.cartorio,
        )
        cls.digital_a = DocumentoDigital.objects.create(
            documento=cls.documento_a,
            arquivo='documentos_digitais/a.pdf',
            nome_original='a.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=1,
            upload_por=cls.superuser,
        )
        cls.digital_b = DocumentoDigital.objects.create(
            documento=cls.documento_b,
            arquivo='documentos_digitais/b.pdf',
            nome_original='b.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=1,
            upload_por=cls.superuser,
        )

    def _request_for(self, user):
        request = RequestFactory().get('/admin/')
        request.user = user
        return request

    def test_staff_ve_apenas_registros_dos_imoveis_atribuidos(self):
        request = self._request_for(self.dono)

        self.assertCountEqual(
            TIsAdmin(TIs, admin.site).get_queryset(request),
            [self.tis_a],
        )
        self.assertCountEqual(
            AlteracoesAdmin(Alteracoes, admin.site).get_queryset(request),
            [self.alteracao_a],
        )
        self.assertCountEqual(
            DocumentoDigitalAdmin(DocumentoDigital, admin.site).get_queryset(request),
            [self.digital_a],
        )

    def test_superuser_mantem_bypass_global(self):
        request = self._request_for(self.superuser)

        self.assertCountEqual(
            TIsAdmin(TIs, admin.site).get_queryset(request),
            [self.tis_a, self.tis_b],
        )
        self.assertCountEqual(
            AlteracoesAdmin(Alteracoes, admin.site).get_queryset(request),
            [self.alteracao_a, self.alteracao_b],
        )
        self.assertCountEqual(
            DocumentoDigitalAdmin(DocumentoDigital, admin.site).get_queryset(request),
            [self.digital_a, self.digital_b],
        )

    def test_staff_ve_apenas_fks_dos_imoveis_atribuidos(self):
        request = self._request_for(self.dono)

        imovel_field = Alteracoes._meta.get_field('imovel_id')
        imovel_formfield = AlteracoesAdmin(
            Alteracoes, admin.site
        ).formfield_for_foreignkey(imovel_field, request)
        self.assertCountEqual(imovel_formfield.queryset, [self.imovel_a])

        documento_field = DocumentoDigital._meta.get_field('documento')
        documento_formfield = DocumentoDigitalAdmin(
            DocumentoDigital, admin.site
        ).formfield_for_foreignkey(documento_field, request)
        self.assertCountEqual(documento_formfield.queryset, [self.documento_a])

    def test_superuser_ve_todas_as_fks(self):
        request = self._request_for(self.superuser)

        imovel_field = Alteracoes._meta.get_field('imovel_id')
        imovel_formfield = AlteracoesAdmin(
            Alteracoes, admin.site
        ).formfield_for_foreignkey(imovel_field, request)
        self.assertCountEqual(
            imovel_formfield.queryset,
            [self.imovel_a, self.imovel_b],
        )

        documento_field = DocumentoDigital._meta.get_field('documento')
        documento_formfield = DocumentoDigitalAdmin(
            DocumentoDigital, admin.site
        ).formfield_for_foreignkey(documento_field, request)
        self.assertCountEqual(
            documento_formfield.queryset,
            [self.documento_a, self.documento_b],
        )


class GuardsSecundariosRound3Test(SegregacaoBaseTestCase):
    def setUp(self):
        self.client = Client()

    def test_endpoints_de_cartorio_exigem_login(self):
        for nome in ['verificar_cartorios_estado', 'importar_cartorios_estado']:
            with self.subTest(endpoint=nome):
                response = self.client.post(reverse(nome), {'estado': 'SP'})
                self.assertEqual(response.status_code, 302)

    def test_api_nao_grava_escolha_para_documento_alheio(self):
        self.client.force_login(self.dono)
        response = self.client.post(
            reverse('escolher_origem_documento'),
            data={
                'documento_id': self.documento_b.id,
                'origem_numero': 'M999',
                'tis_id': self.tis_a.id,
                'imovel_id': self.imovel_a.id,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(
            f'origem_documento_{self.documento_b.id}',
            self.client.session,
        )

    def test_api_nao_grava_escolha_para_lancamento_alheio(self):
        self.client.force_login(self.dono)
        response = self.client.post(
            reverse('escolher_origem_lancamento'),
            data={
                'lancamento_id': self.lancamento_b.id,
                'origem_numero': 'M999',
                'tis_id': self.tis_a.id,
                'imovel_id': self.imovel_a.id,
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(
            f'origem_lancamento_{self.lancamento_b.id}',
            self.client.session,
        )

    def test_view_nao_grava_escolha_para_documento_alheio(self):
        self.client.force_login(self.dono)
        response = self.client.get(
            reverse('cadeia_dominial_tabela', kwargs={
                'tis_id': self.tis_a.id,
                'imovel_id': self.imovel_a.id,
            }),
            {'origem': 'M999', 'documento_id': self.documento_b.id},
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(
            f'origem_documento_{self.documento_b.id}',
            self.client.session,
        )


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

        operacao = migracao.Migration.operations[0]
        self.assertIsNone(operacao.reverse_code)
        self.assertFalse(operacao.reversible)


class MediaSegregacaoTest(SegregacaoBaseTestCase):
    """
    M-11: /media/ não pode ser servido publicamente.

    O nginx serve /media/ apenas via `internal` (X-Accel-Redirect). A view
    protegida delega o download ao nginx e nunca expõe a URL pública direta.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.digital_a = DocumentoDigital.objects.create(
            documento=cls.documento_a,
            arquivo='documentos_digitais/a.pdf',
            nome_original='a.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=1,
            upload_por=cls.superuser,
        )
        cls.digital_b = DocumentoDigital.objects.create(
            documento=cls.documento_b,
            arquivo='documentos_digitais/b.pdf',
            nome_original='b.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=1,
            upload_por=cls.superuser,
        )

    def setUp(self):
        self.client = Client()

    def _url(self, arquivo):
        imovel = arquivo.documento.imovel
        return reverse('servir_documento_digital', kwargs={
            'tis_id': imovel.terra_indigena_id_id,
            'imovel_id': imovel.id,
            'documento_id': arquivo.documento_id,
            'arquivo_id': arquivo.id,
        })

    def test_media_nao_servido_direto_por_django(self):
        # /media/ é responsabilidade do nginx (internal); o Django não tem rota
        # pública para ele — request direto não deve devolver o arquivo.
        response = self.client.get('/media/documentos_digitais/a.pdf')
        self.assertEqual(response.status_code, 404)

    def test_servir_documento_delega_via_x_accel_redirect(self):
        self.client.force_login(self.dono)
        response = self.client.get(self._url(self.digital_a))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Accel-Redirect'], self.digital_a.arquivo.url)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_cross_tenant_nao_baixa_documento_alheio(self):
        self.client.force_login(self.dono)
        response = self.client.get(self._url(self.digital_b))
        self.assertEqual(response.status_code, 404)

    def test_anonimo_nao_baixa_documento(self):
        response = self.client.get(self._url(self.digital_a))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)


class MustFixRound8Test(SegregacaoBaseTestCase):
    """Achados da review de arquitetura (M-12 a M-17 + nice-to-haves)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dono.is_staff = True
        cls.dono.save(update_fields=['is_staff'])
        cls.pessoa_a = Pessoas.objects.create(nome='Parte do Imóvel A', cpf='11111111111')
        cls.pessoa_b = Pessoas.objects.create(nome='Parte do Imóvel B', cpf='22222222222')
        LancamentoPessoa.objects.create(
            lancamento=cls.lancamento_a, pessoa=cls.pessoa_a, tipo='transmitente'
        )
        LancamentoPessoa.objects.create(
            lancamento=cls.lancamento_b, pessoa=cls.pessoa_b, tipo='transmitente'
        )

    def setUp(self):
        self.client = Client()

    def _request_for(self, user):
        request = RequestFactory().get('/admin/')
        request.user = user
        return request

    def _post_de_lancamento(self, user, **extras):
        dados = {
            'tipo_lancamento': str(self.lanc_tipo.id),
            'numero_lancamento_simples': '9',
            'numero_lancamento': 'R9M9999',
            'data': '2024-05-01',
        }
        dados.update(extras)
        request = RequestFactory().post('/', dados)
        request.user = user
        return request

    # ------------------------------------------------------------------
    # M-12: o filtro de TI da sidebar lia TIs._default_manager sem filtro
    # ------------------------------------------------------------------
    def test_filtro_de_ti_do_changelist_nao_oferece_ti_alheia(self):
        request = self._request_for(self.dono)
        campo = Imovel._meta.get_field('terra_indigena_id')

        opcoes = TIsSegregadaFilter.field_choices(
            None, campo, request, ImovelAdmin(Imovel, admin.site)
        )

        self.assertEqual([nome for _, nome in opcoes], [str(self.tis_a)])

    def test_changelist_de_imovel_nao_vaza_ti_alheia_na_sidebar(self):
        self.dono.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label='dominial', codename='view_imovel'
            )
        )
        self.client.force_login(self.dono)

        response = self.client.get(reverse('admin:dominial_imovel_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.tis_a.nome)
        self.assertNotContains(response, self.tis_b.nome)

    def test_superuser_continua_vendo_todas_as_tis_no_filtro(self):
        request = self._request_for(self.superuser)
        campo = Imovel._meta.get_field('terra_indigena_id')

        opcoes = TIsSegregadaFilter.field_choices(
            None, campo, request, ImovelAdmin(Imovel, admin.site)
        )

        self.assertCountEqual(
            [nome for _, nome in opcoes], [str(self.tis_a), str(self.tis_b)]
        )

    # ------------------------------------------------------------------
    # M-13: UserAdmin de série deixava staff marcar is_superuser em si mesmo
    # ------------------------------------------------------------------
    def test_staff_com_change_user_nao_se_promove_a_superuser(self):
        grupo = Group.objects.create(name='Privilegiados')
        self.dono.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label='auth',
                codename__in=['change_user', 'view_user'],
            )
        )
        self.client.force_login(self.dono)

        response = self.client.post(
            reverse('admin:auth_user_change', args=[self.dono.pk]),
            {
                'username': self.dono.username,
                'first_name': 'Promovido',
                'last_name': '',
                'email': '',
                'is_active': 'on',
                'is_staff': 'on',
                'is_superuser': 'on',
                'groups': [str(grupo.pk)],
                'date_joined_0': '2024-01-01',
                'date_joined_1': '00:00:00',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.dono.refresh_from_db()
        # O form salvou (não é um falso negativo por validação)...
        self.assertEqual(self.dono.first_name, 'Promovido')
        # ...mas os campos de escalação foram ignorados.
        self.assertFalse(self.dono.is_superuser)
        self.assertFalse(self.dono.groups.exists())

    def test_superuser_continua_podendo_conceder_privilegio(self):
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse('admin:auth_user_change', args=[self.sem_acesso.pk]),
            {
                'username': self.sem_acesso.username,
                'first_name': '',
                'last_name': '',
                'email': '',
                'is_active': 'on',
                'is_staff': 'on',
                'is_superuser': 'on',
                'date_joined_0': '2024-01-01',
                'date_joined_1': '00:00:00',
                'imoveis_atribuidos-TOTAL_FORMS': '0',
                'imoveis_atribuidos-INITIAL_FORMS': '0',
                'imoveis_atribuidos-MIN_NUM_FORMS': '0',
                'imoveis_atribuidos-MAX_NUM_FORMS': '1000',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.sem_acesso.refresh_from_db()
        self.assertTrue(self.sem_acesso.is_superuser)

    # ------------------------------------------------------------------
    # M-14: Pessoas estava registrada sem segregação nenhuma (PII)
    # ------------------------------------------------------------------
    def test_staff_ve_apenas_pessoas_dos_imoveis_atribuidos(self):
        request = self._request_for(self.dono)

        self.assertCountEqual(
            PessoasAdmin(Pessoas, admin.site).get_queryset(request),
            # `proprietario` é dono do imóvel A (e do B) — o vínculo com A basta.
            [self.proprietario, self.pessoa_a],
        )

    def test_superuser_ve_todas_as_pessoas(self):
        request = self._request_for(self.superuser)

        self.assertCountEqual(
            PessoasAdmin(Pessoas, admin.site).get_queryset(request),
            [self.proprietario, self.pessoa_a, self.pessoa_b],
        )

    def test_changelist_de_pessoas_nao_vaza_pii_alheio(self):
        self.dono.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label='dominial', codename='view_pessoas'
            )
        )
        self.client.force_login(self.dono)

        response = self.client.get(reverse('admin:dominial_pessoas_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.pessoa_a.cpf)
        self.assertNotContains(response, self.pessoa_b.cpf)

    # ------------------------------------------------------------------
    # M-15: has_*_permission hardcoded em True ignorava as permissões de model
    # ------------------------------------------------------------------
    def test_staff_sem_permissao_nao_escreve_em_importacao_nem_fim_cadeia(self):
        self.client.force_login(self.dono)

        self.assertEqual(
            self.client.get(
                reverse('admin:dominial_importacaocartorios_add')
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('admin:dominial_fimcadeia_add')).status_code, 403
        )

    def test_staff_sem_permissao_nao_dispara_importacao_pela_url_customizada(self):
        self.client.force_login(self.dono)

        self.assertEqual(
            self.client.get(reverse('admin:nova-importacao')).status_code, 403
        )

    def test_staff_com_permissao_de_add_continua_entrando(self):
        self.dono.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label='dominial',
                codename__in=['add_importacaocartorios', 'view_importacaocartorios'],
            )
        )
        self.client.force_login(self.dono)

        self.assertEqual(
            self.client.get(reverse('admin:nova-importacao')).status_code, 200
        )

    # ------------------------------------------------------------------
    # M-16: documento/lançamento eram aceitos do caller sem revalidação
    # ------------------------------------------------------------------
    def test_criacao_recusa_documento_de_outro_usuario(self):
        request = self._post_de_lancamento(self.dono)
        quantidade_antes = Lancamento.objects.count()

        resultado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.tis_b, self.imovel_b, self.documento_b
        )

        self.assertIsNone(resultado)
        self.assertEqual(mensagem, NAO_AUTORIZADO_DOCUMENTO)
        self.assertEqual(Lancamento.objects.count(), quantidade_antes)

    def test_atualizacao_recusa_lancamento_de_outro_usuario(self):
        request = self._post_de_lancamento(self.dono)

        ok, mensagem = LancamentoCriacaoService.atualizar_lancamento_completo(
            request, self.lancamento_b, self.imovel_b
        )

        self.assertFalse(ok)
        self.assertEqual(mensagem, NAO_AUTORIZADO_LANCAMENTO)
        # O `pessoas.all().delete()` do método nem chegou a rodar.
        self.assertTrue(self.lancamento_b.pessoas.exists())

    # ------------------------------------------------------------------
    # M-17: sem atomic, uma falha entre o delete e a recriação perdia as partes
    # ------------------------------------------------------------------
    @patch(
        'dominial.services.lancamento_criacao_service.'
        'LancamentoPessoaService.processar_pessoas_lancamento',
        side_effect=RuntimeError('falha logo depois do delete'),
    )
    def test_falha_apos_o_delete_devolve_as_partes_do_lancamento(self, _mock):
        request = self._post_de_lancamento(
            self.dono, numero_lancamento=self.lancamento_a.numero_lancamento
        )

        ok, mensagem = LancamentoCriacaoService.atualizar_lancamento_completo(
            request, self.lancamento_a, self.imovel_a
        )

        self.assertFalse(ok)
        self.assertEqual(mensagem, ERRO_ATUALIZACAO)
        self.assertNotIn('falha logo depois do delete', mensagem)
        self.assertCountEqual(
            [vinculo.pessoa for vinculo in self.lancamento_a.pessoas.all()],
            [self.pessoa_a],
        )

    @patch(
        'dominial.services.lancamento_criacao_service.'
        'LancamentoPessoaService.processar_pessoas_lancamento',
        side_effect=RuntimeError('falha no meio da criação'),
    )
    def test_falha_na_criacao_nao_deixa_lancamento_orfao(self, _mock):
        request = self._post_de_lancamento(self.dono, apos_importacao='')
        quantidade_antes = Lancamento.objects.count()

        resultado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.tis_a, self.imovel_a, self.documento_a, apos_importacao=True
        )

        self.assertIsNone(resultado)
        self.assertEqual(mensagem, ERRO_CRIACAO)
        self.assertEqual(Lancamento.objects.count(), quantidade_antes)

    # ------------------------------------------------------------------
    # N-3/N-4: verificação de duplicata falhava aberto e vazava o str(e)
    # ------------------------------------------------------------------
    @patch(
        'dominial.services.lancamento_criacao_service.'
        'LancamentoDuplicataService.verificar_duplicata_antes_criacao',
        side_effect=RuntimeError('coluna dominial_documento.numero fora do ar'),
    )
    def test_falha_na_verificacao_de_duplicata_aborta_a_criacao(self, _mock):
        request = self._post_de_lancamento(self.dono)
        quantidade_antes = Lancamento.objects.count()

        resultado, mensagem = LancamentoCriacaoService.criar_lancamento_completo(
            request, self.tis_a, self.imovel_a, self.documento_a
        )

        self.assertIsNone(resultado)
        self.assertEqual(mensagem, ERRO_DUPLICATA)
        self.assertNotIn('dominial_documento', mensagem)
        self.assertEqual(Lancamento.objects.count(), quantidade_antes)

    # ------------------------------------------------------------------
    # N-5: nome do arquivo ia cru para o Content-Disposition
    # ------------------------------------------------------------------
    def test_content_disposition_escapa_nome_do_arquivo(self):
        arquivo = DocumentoDigital.objects.create(
            documento=self.documento_a,
            arquivo='documentos_digitais/a.pdf',
            nome_original='rela"torio.pdf',
            tipo_mime='application/pdf',
            tamanho_bytes=1,
            upload_por=self.superuser,
        )
        self.client.force_login(self.dono)

        response = self.client.get(
            reverse('servir_documento_digital', kwargs={
                'tis_id': self.tis_a.id,
                'imovel_id': self.imovel_a.id,
                'documento_id': self.documento_a.id,
                'arquivo_id': arquivo.id,
            })
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Disposition'], r'inline; filename="rela\"torio.pdf"'
        )


class MustFixRound9Test(SegregacaoBaseTestCase):
    """Achados da review final: senha de superuser, actions e vazamento de erro."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dono.is_staff = True
        cls.dono.save(update_fields=['is_staff'])
        # Username improvável de aparecer solto no HTML do admin — as asserções
        # de "não vaza no changelist" dependem disso.
        cls.raiz = User.objects.create_superuser(
            username='raiz-do-sistema', password='senha-raiz', email='raiz@example.com'
        )

    def setUp(self):
        self.client = Client()

    def _dar_permissoes(self, app_label, *codenames):
        self.dono.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label=app_label, codename__in=codenames
            )
        )

    def _request_do_dono(self):
        # Recarrega do banco: `has_perm` cacheia as permissões na instância.
        request = RequestFactory().get('/admin/')
        request.user = User.objects.get(pk=self.dono.pk)
        return request

    # ------------------------------------------------------------------
    # F-1: /admin/auth/user/<id>/password/ só olhava has_change_permission,
    # então quem tinha `auth.change_user` resetava a senha de um superuser
    # e entrava como ele — o mesmo destino que travar `is_superuser` fechou.
    # ------------------------------------------------------------------
    def test_staff_com_change_user_nao_ve_superuser_no_changelist(self):
        self._dar_permissoes('auth', 'view_user', 'change_user')
        self.client.force_login(self.dono)

        response = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.dono.username)
        self.assertNotContains(response, self.raiz.username)

    def test_staff_com_change_user_nao_troca_senha_de_superuser(self):
        self._dar_permissoes('auth', 'view_user', 'change_user')
        self.client.force_login(self.dono)
        url = reverse('admin:auth_user_password_change', args=[self.raiz.pk])

        self.assertEqual(self.client.get(url).status_code, 404)

        response = self.client.post(url, {
            'password1': 'senha-invadida-321',
            'password2': 'senha-invadida-321',
            'usable_password': 'true',
        })

        self.assertEqual(response.status_code, 404)
        self.raiz.refresh_from_db()
        self.assertFalse(self.raiz.check_password('senha-invadida-321'))
        self.assertTrue(self.raiz.check_password('senha-raiz'))

    def test_staff_com_change_user_nao_abre_o_change_de_superuser(self):
        self._dar_permissoes('auth', 'view_user', 'change_user')
        self.client.force_login(self.dono)
        url = reverse('admin:auth_user_change', args=[self.raiz.pk])

        # O admin redireciona para o índice com "objeto não existe".
        self.assertEqual(self.client.get(url).status_code, 302)

        self.client.post(url, {
            'username': 'raiz-sequestrada',
            'first_name': '', 'last_name': '', 'email': '',
            'is_active': 'on',
            'date_joined_0': '2024-01-01', 'date_joined_1': '00:00:00',
        })

        self.raiz.refresh_from_db()
        self.assertEqual(self.raiz.username, 'raiz-do-sistema')
        self.assertTrue(self.raiz.is_superuser)

    def test_staff_com_delete_user_nao_apaga_superuser(self):
        self._dar_permissoes('auth', 'view_user', 'change_user', 'delete_user')
        self.client.force_login(self.dono)

        response = self.client.post(
            reverse('admin:auth_user_delete', args=[self.raiz.pk]), {'post': 'yes'}
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.raiz.pk).exists())

    def test_permissoes_de_objeto_recusam_superuser_mas_liberam_o_resto(self):
        self._dar_permissoes('auth', 'view_user', 'change_user', 'delete_user')
        user_admin = UserAdmin(User, admin.site)
        request = self._request_do_dono()

        self.assertFalse(user_admin.has_view_permission(request, self.raiz))
        self.assertFalse(user_admin.has_change_permission(request, self.raiz))
        self.assertFalse(user_admin.has_delete_permission(request, self.raiz))
        # ...e continua funcionando para quem não é superuser.
        self.assertTrue(user_admin.has_change_permission(request, self.sem_acesso))
        self.assertNotIn(self.raiz, user_admin.get_queryset(request))
        self.assertIn(self.sem_acesso, user_admin.get_queryset(request))

    def test_superuser_continua_gerenciando_outros_superusers(self):
        self.client.force_login(self.superuser)

        changelist = self.client.get(reverse('admin:auth_user_changelist'))
        senha = self.client.get(
            reverse('admin:auth_user_password_change', args=[self.raiz.pk])
        )

        self.assertContains(changelist, self.raiz.username)
        self.assertEqual(senha.status_code, 200)

    # ------------------------------------------------------------------
    # F-2: sem `allowed_permissions` o Django não filtra a action, então
    # quem só tinha `view_importacaocartorios` disparava a importação.
    # ------------------------------------------------------------------
    def test_staff_so_com_view_nao_recebe_a_action_de_importacao(self):
        self._dar_permissoes('dominial', 'view_importacaocartorios')

        acoes = ImportacaoCartoriosAdmin(ImportacaoCartorios, admin.site).get_actions(
            self._request_do_dono()
        )

        self.assertNotIn('importar_cartorios', acoes)

    def test_staff_com_change_recebe_a_action_de_importacao(self):
        self._dar_permissoes(
            'dominial', 'view_importacaocartorios', 'change_importacaocartorios'
        )

        acoes = ImportacaoCartoriosAdmin(ImportacaoCartorios, admin.site).get_actions(
            self._request_do_dono()
        )

        self.assertIn('importar_cartorios', acoes)

    @patch('dominial.admin.ImportarCartoriosCommand')
    def test_staff_so_com_view_nao_dispara_a_action_pelo_post(self, comando):
        importacao = ImportacaoCartorios.objects.create(estado='SP')
        self._dar_permissoes('dominial', 'view_importacaocartorios')
        self.client.force_login(self.dono)

        response = self.client.post(
            reverse('admin:dominial_importacaocartorios_changelist'),
            {'action': 'importar_cartorios', '_selected_action': [str(importacao.pk)]},
        )

        # Action recusada: o changelist volta com "nenhuma ação selecionada".
        self.assertEqual(response.status_code, 200)
        comando.assert_not_called()
        importacao.refresh_from_db()
        self.assertEqual(importacao.status, 'pendente')

    def test_toda_action_customizada_declara_allowed_permissions(self):
        sem_gate = []
        for model_admin in admin.site._registry.values():
            for nome in model_admin.actions or ():
                if not isinstance(nome, str):
                    continue
                funcao = getattr(model_admin, nome, None)
                if funcao is not None and not hasattr(funcao, 'allowed_permissions'):
                    sem_gate.append(f'{type(model_admin).__name__}.{nome}')

        self.assertEqual(sem_gate, [])

    # ------------------------------------------------------------------
    # F-3: str(e) ia para o JSON e ficava gravado em `erro`, que
    # `verificar_progresso` devolve ao usuário.
    # ------------------------------------------------------------------
    @patch(
        'dominial.admin.ImportarCartoriosCommand.handle',
        side_effect=RuntimeError('conexão recusada em postgres://cadeia:hunter2@db'),
    )
    def test_erro_da_importacao_nao_vaza_a_excecao(self, _mock):
        importacao = ImportacaoCartorios.objects.create(estado='SP')
        self._dar_permissoes(
            'dominial', 'view_importacaocartorios', 'change_importacaocartorios'
        )
        self.client.force_login(self.dono)

        with self.assertLogs('dominial.admin', level='ERROR'):
            response = self.client.get(
                reverse('admin:iniciar-importacao', args=[importacao.pk])
            )

        self.assertEqual(response.json()['message'], ERRO_IMPORTACAO)
        self.assertNotIn('hunter2', response.content.decode())
        importacao.refresh_from_db()
        self.assertEqual(importacao.status, 'erro')
        self.assertEqual(importacao.erro, ERRO_IMPORTACAO)

        # E o que `verificar_progresso` devolve também sai limpo.
        progresso = self.client.get(
            reverse('admin:verificar-progresso', args=[importacao.pk])
        )
        self.assertEqual(progresso.json()['erro'], ERRO_IMPORTACAO)

    def test_importacao_inexistente_devolve_json_em_vez_de_500(self):
        self._dar_permissoes(
            'dominial', 'view_importacaocartorios', 'change_importacaocartorios'
        )
        self.client.force_login(self.dono)

        with self.assertLogs('dominial.admin', level='ERROR'):
            # Antes, o `if importacao` do except batia em UnboundLocalError.
            response = self.client.get(reverse('admin:iniciar-importacao', args=[999999]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['message'], ERRO_IMPORTACAO)


class ManagerOptInRegressaoTest(TestCase):
    """
    N-1: o manager é opt-in, então esquecer `.for_user()` falha aberto.

    Guarda a camada onde existe `request.user` — `dominial/views/` e
    `dominial/admin.py`. Ali todo acesso a `Imovel.objects` tem de passar por
    `for_user`, e todo acesso a `Documento.objects` tem de estar preso a um
    imóvel já escopado (`imovel=`). Os management commands e os services que
    recebem `documentos_queryset` pronto ficam de fora: não têm usuário.
    """

    # `(?<![A-Za-z_])` evita casar `UserImovel.objects` / `DocumentoTipo.objects`.
    CHAMADA_IMOVEL = re.compile(r'(?<![A-Za-z_])Imovel\.objects\.(\w+)')
    CHAMADA_DOCUMENTO = re.compile(r'(?<![A-Za-z_])Documento\.objects\.(\w+)')

    def _arquivos_com_request(self):
        raiz = Path(dominial.__file__).parent
        return sorted(raiz.glob('views/*.py')) + [raiz / 'admin.py']

    @staticmethod
    def _argumentos_da_chamada(fonte, inicio):
        """Texto entre os parênteses da chamada que começa em `inicio`."""
        abre = fonte.index('(', inicio)
        profundidade = 0
        for i in range(abre, len(fonte)):
            if fonte[i] == '(':
                profundidade += 1
            elif fonte[i] == ')':
                profundidade -= 1
                if profundidade == 0:
                    return fonte[abre + 1:i]
        return fonte[abre:]

    def test_views_e_admin_so_alcancam_imovel_via_for_user(self):
        for caminho in self._arquivos_com_request():
            fonte = caminho.read_text(encoding='utf-8')
            for match in self.CHAMADA_IMOVEL.finditer(fonte):
                linha = fonte.count('\n', 0, match.start()) + 1
                self.assertEqual(
                    match.group(1),
                    'for_user',
                    f'{caminho.name}:{linha} usa Imovel.objects.{match.group(1)}() '
                    f'sem passar por for_user()',
                )

    def test_views_e_admin_so_alcancam_documento_preso_a_um_imovel(self):
        for caminho in self._arquivos_com_request():
            fonte = caminho.read_text(encoding='utf-8')
            for match in self.CHAMADA_DOCUMENTO.finditer(fonte):
                linha = fonte.count('\n', 0, match.start()) + 1
                argumentos = self._argumentos_da_chamada(fonte, match.start())
                self.assertIn(
                    'imovel=',
                    argumentos,
                    f'{caminho.name}:{linha} usa Documento.objects.'
                    f'{match.group(1)}() sem prender a um imóvel já escopado',
                )


class TisDetailOrderingTest(SegregacaoBaseTestCase):
    """
    `tis_detail` saiu do SQL cru (#132, fase 0): o ordering tem de continuar
    sendo `COALESCE(MAX(doc), MAX(lanc), imovel.data_cadastro) DESC, matricula ASC`.
    """

    def setUp(self):
        self.client = Client()
        # TI isolada: os imóveis/documentos da SegregacaoBaseTestCase (tis_a/tis_b)
        # não podem interferir na ordenação testada aqui.
        self.tis_gama = TIs.objects.create(nome='TI Gama', codigo='TI-G', etnia='Gama')

    def _criar_imovel(self, matricula, data_cadastro):
        imovel = Imovel.objects.create(
            nome=f'Imóvel {matricula}', matricula=matricula,
            terra_indigena_id=self.tis_gama,
            proprietario=self.proprietario, cartorio=self.cartorio,
        )
        # `data_cadastro` é auto_now_add: só dá para "voltar no tempo" via update(),
        # que ignora o auto_now_add por não passar pelo save().
        Imovel.objects.filter(pk=imovel.pk).update(data_cadastro=data_cadastro)
        imovel.refresh_from_db()
        return imovel

    def _criar_documento(self, imovel, numero, data_cadastro):
        documento = Documento.objects.create(
            imovel=imovel, tipo=self.doc_tipo, numero=numero,
            data=data_cadastro, cartorio=self.cartorio, livro='1', folha='1',
        )
        Documento.objects.filter(pk=documento.pk).update(data_cadastro=data_cadastro)
        documento.refresh_from_db()
        return documento

    def _criar_lancamento(self, documento, numero, data_cadastro):
        lancamento = Lancamento.objects.create(
            documento=documento, tipo=self.lanc_tipo,
            numero_lancamento=numero, data=data_cadastro,
        )
        Lancamento.objects.filter(pk=lancamento.pk).update(data_cadastro=data_cadastro)
        lancamento.refresh_from_db()
        return lancamento

    def _get_como_superuser(self):
        self.assertTrue(self.client.login(username='super', password='senha-super'))
        return self.client.get(reverse('tis_detail', kwargs={'tis_id': self.tis_gama.id}))

    def test_ordena_por_atividade_mais_recente_com_fallback_ao_cadastro(self):
        """
        Três níveis de atividade diferentes: a matrícula mais alta tem a
        atividade mais recente e a mais baixa tem a mais antiga (via
        fallback, por não ter documento algum) — de forma que nem "ordem de
        inserção" nem "ordem crescente de matrícula" batem com o resultado
        esperado.
        """
        # Inseridos em ordem crescente de matrícula — oposta ao resultado esperado.
        imovel_sem_documento = self._criar_imovel('9100', date(2019, 1, 1))
        imovel_intermediario = self._criar_imovel('9200', date(2020, 1, 1))
        imovel_recente = self._criar_imovel('9300', date(2020, 1, 1))

        self._criar_documento(imovel_intermediario, 'M9200', date(2022, 1, 1))
        self._criar_documento(imovel_recente, 'M9300', date(2024, 6, 1))
        # imovel_sem_documento não tem nenhum documento: cai para o próprio
        # data_cadastro (2019-01-01), o mais antigo dos três.

        response = self._get_como_superuser()

        self.assertEqual(
            [i.id for i in response.context['imoveis']],
            [imovel_recente.id, imovel_intermediario.id, imovel_sem_documento.id],
        )

    def test_documento_antigo_com_lancamento_recente_ordena_pela_data_do_documento(self):
        """
        `COALESCE(MAX(documento), MAX(lançamento), cadastro)` devolve o
        primeiro termo não nulo. Como o LEFT JOIN encadeia lançamento →
        documento → imóvel, todo imóvel com lançamento necessariamente tem
        documento — logo o segundo termo do COALESCE é inalcançável na
        prática. O comportamento pré-existente (e que este teste preserva) é
        ordenar pela data do DOCUMENTO, mesmo que exista um lançamento com
        data mais recente.
        """
        imovel_doc_velho_lanc_novo = self._criar_imovel('9250', date(2020, 1, 1))
        documento_velho = self._criar_documento(
            imovel_doc_velho_lanc_novo, 'M9250', date(2021, 1, 1)
        )
        self._criar_lancamento(documento_velho, 'R1M9250', date(2025, 1, 1))

        imovel_doc_novo = self._criar_imovel('9150', date(2020, 1, 1))
        self._criar_documento(imovel_doc_novo, 'M9150', date(2023, 1, 1))

        response = self._get_como_superuser()

        self.assertEqual(
            [i.id for i in response.context['imoveis']],
            [imovel_doc_novo.id, imovel_doc_velho_lanc_novo.id],
        )

    def test_desempate_por_matricula_ascendente(self):
        mesma_data = date(2022, 5, 5)
        imovel_alto = self._criar_imovel('9400', mesma_data)
        imovel_baixo = self._criar_imovel('9300', mesma_data)

        response = self._get_como_superuser()

        self.assertEqual(
            [i.id for i in response.context['imoveis']],
            [imovel_baixo.id, imovel_alto.id],
        )

    def test_segregacao_continua_valendo_com_a_query_orm(self):
        # `self.dono` só está atribuído ao `imovel_a`, que é de outra TI
        # (tis_a, da SegregacaoBaseTestCase) — nada aqui deve aparecer para ele,
        # e as novas annotations não podem ressuscitar nenhum imóvel alheio.
        imovel = self._criar_imovel('9500', date(2020, 1, 1))
        self._criar_documento(imovel, 'M9500', date(2024, 1, 1))

        self.assertTrue(self.client.login(username='dono', password='senha-dono'))
        response = self.client.get(
            reverse('tis_detail', kwargs={'tis_id': self.tis_gama.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['imoveis']), [])

    def test_annotations_ultimo_documento_e_ultimo_lancamento_continuam_expostas(self):
        # Paridade com os objetos montados à mão no SQL cru antigo: o template
        # não lê esses atributos hoje, mas o refactor não pode deixar de
        # anexá-los ao objeto.
        imovel = self._criar_imovel('9600', date(2020, 1, 1))
        documento = self._criar_documento(imovel, 'M9600', date(2023, 3, 3))
        self._criar_lancamento(documento, 'R1M9600', date(2023, 4, 4))

        response = self._get_como_superuser()

        (obtido,) = [i for i in response.context['imoveis'] if i.id == imovel.id]
        self.assertEqual(obtido.ultimo_documento, date(2023, 3, 3))
        self.assertEqual(obtido.ultimo_lancamento, date(2023, 4, 4))
