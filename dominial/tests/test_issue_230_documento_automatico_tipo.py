"""Testes de regressão para issues #230 e #114.

Bug #230 (produção, imóvel 691): imóvel criado com
tipo_documento_principal='transcricao' ganha documento automático
``M{nº}``/matrícula porque ``criar_documento_matricula_automatico``
(lancamento_documento_service.py:32-62) hardcode tipo ``matricula``
+ prefixo ``M``.

Bug #114: ``cartorio=imovel.cartorio if ... else None`` no mesmo método
viola FK não-nullable — ``Imovel.cartorio`` é ``ForeignKey`` sem
``null=True``, e ler ``imovel.cartorio`` com ``cartorio_id=None`` levanta
``RelatedObjectDoesNotExist`` (que herda de ``AttributeError``).
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.hierarquia_arvore_service import HierarquiaArvoreService
from dominial.services.lancamento_documento_service import LancamentoDocumentoService


class Issue230Fixture:
    """Mixin de fixtures — não herda de TestCase para não ser coletado
    como caso de teste vazio. Classes filhas devem herdar de
    (Issue230Fixture, TestCase).

    O fixture NÃO cria DocumentoTipo: o service faz ``get_or_create``,
    como em produção. Testes que precisam do tipo usam ``get_or_create``.
    """

    @classmethod
    def setUpTestData(cls):
        cls.tis = TIs.objects.create(
            nome='TI Issue 230', codigo='TI-230', etnia='Teste',
        )
        cls.pessoa = Pessoas.objects.create(nome='Pessoa Issue 230')
        cls.cartorio = Cartorios.objects.create(
            nome='Cartório Issue 230',
            cns='CNS-ISSUE-230',
            cidade='Cidade 230',
            estado='MS',
        )
        cls.user = User.objects.create_user(
            username='issue230', password='issue230pass',
        )

    def criar_imovel(self, numero, tipo='matricula'):
        return Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome=f'Imóvel {numero}',
            proprietario=self.pessoa,
            matricula=numero,
            tipo_documento_principal=tipo,
            cartorio=self.cartorio,
        )


# ---------------------------------------------------------------------------
# Classe A: service direto
# ---------------------------------------------------------------------------


class CriarDocumentoAutomaticoRespeitaTipoTest(Issue230Fixture, TestCase):
    """Chama ``criar_documento_matricula_automatico`` diretamente."""

    def test_imovel_transcricao_gera_documento_T_do_tipo_transcricao(self):
        """A1: imóvel transcrição 7188 → documento T7188/transcrição."""
        imovel = self.criar_imovel('7188', 'transcricao')

        doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)

        self.assertEqual(doc.tipo.tipo, 'transcricao')
        self.assertEqual(doc.numero, 'T7188')
        self.assertEqual(doc.cartorio_id, imovel.cartorio_id)
        self.assertEqual(doc.data, timezone.localdate())
        self.assertTrue(doc.data_presumida)
        self.assertEqual(doc.livro, '0')
        self.assertEqual(doc.folha, '0')

    def test_imovel_matricula_continua_gerando_documento_M_do_tipo_matricula(self):
        """A2: imóvel matrícula 7189 → documento M7189/matrícula (regressão)."""
        imovel = self.criar_imovel('7189', 'matricula')

        doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)

        self.assertEqual(doc.tipo.tipo, 'matricula')
        self.assertEqual(doc.numero, 'M7189')
        self.assertEqual(doc.cartorio_id, imovel.cartorio_id)
        self.assertEqual(doc.data, timezone.localdate())
        self.assertTrue(doc.data_presumida)
        self.assertEqual(doc.livro, '0')
        self.assertEqual(doc.folha, '0')

    def test_prefixo_ja_digitado_nao_e_duplicado(self):
        """A3: prefixo já digitado não é duplicado, com ou sem maiúscula."""
        with self.subTest('T7188 → T7188 (transcrição)'):
            imovel = self.criar_imovel('T7188', 'transcricao')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(doc.numero, 'T7188')

        with self.subTest('t7191 → T7191 (transcrição)'):
            imovel = self.criar_imovel('t7191', 'transcricao')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(doc.numero, 'T7191')

        with self.subTest('M7190 → M7190 (matrícula)'):
            imovel = self.criar_imovel('M7190', 'matricula')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(doc.numero, 'M7190')

        with self.subTest('m7192 → M7192 (matrícula)'):
            imovel = self.criar_imovel('m7192', 'matricula')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(doc.numero, 'M7192')

    def test_documento_criado_casa_identidade_registral_do_imovel(self):
        """A4: filtro por identidade devolve exatamente o doc criado."""
        with self.subTest('transcrição'):
            imovel = self.criar_imovel('7194', 'transcricao')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            doc.refresh_from_db()
            encontrados = Documento.objects.filter(
                imovel=imovel,
                tipo__tipo=imovel.tipo_documento_principal,
                numero_normalizado=imovel.matricula_normalizada,
                cartorio_id=imovel.cartorio_id,
            )
            self.assertEqual(list(encontrados), [doc])

        with self.subTest('matrícula'):
            imovel = self.criar_imovel('7195', 'matricula')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            doc.refresh_from_db()
            encontrados = Documento.objects.filter(
                imovel=imovel,
                tipo__tipo=imovel.tipo_documento_principal,
                numero_normalizado=imovel.matricula_normalizada,
                cartorio_id=imovel.cartorio_id,
            )
            self.assertEqual(list(encontrados), [doc])

    def test_textos_de_origem_e_observacoes_acompanham_o_tipo(self):
        """A5: origem e observações usam o rótulo do tipo do documento."""
        with self.subTest('transcrição'):
            imovel = self.criar_imovel('7196', 'transcricao')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(doc.origem, 'Transcrição atual do imóvel')
            self.assertEqual(
                doc.observacoes,
                'Documento de transcrição criado automaticamente para iniciar a cadeia dominial',
            )

        with self.subTest('matrícula'):
            imovel = self.criar_imovel('7197', 'matricula')
            doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(doc.origem, 'Matrícula atual do imóvel')
            self.assertEqual(
                doc.observacoes,
                'Documento de matrícula criado automaticamente para iniciar a cadeia dominial',
            )

    def test_tipo_principal_ausente_ou_invalido_cai_no_default_matricula(self):
        """A6: tipo vazio, None ou inválido cai em matrícula."""
        casos = [('', '7210'), (None, '7211'), ('M', '7212')]
        for valor, numero in casos:
            with self.subTest(tipo=valor):
                imovel = self.criar_imovel(numero, 'matricula')
                # Aplicar o tipo anormal só em memória
                imovel.tipo_documento_principal = valor if valor is not None else ''
                doc = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
                self.assertEqual(doc.tipo.tipo, 'matricula')
                self.assertTrue(doc.numero.upper().startswith('M'))

    def test_numero_invalido_recusa_sem_criar_documento(self):
        """A7: prefixo contraditório, vazio ou só prefixo → ValueError, 0 docs."""
        with self.subTest('prefixo contraditório M7193 em transcrição'):
            imovel = self.criar_imovel('7198', 'transcricao')
            imovel.matricula = 'M7193'
            with self.assertRaises(ValueError):
                LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(imovel.documentos.count(), 0)

        with self.subTest('número vazio'):
            imovel = self.criar_imovel('7199', 'transcricao')
            imovel.matricula = ''
            with self.assertRaises(ValueError):
                LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(imovel.documentos.count(), 0)

        with self.subTest('só prefixo T'):
            imovel = self.criar_imovel('7200', 'transcricao')
            imovel.matricula = 'T'
            with self.assertRaises(ValueError):
                LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(imovel.documentos.count(), 0)

    def test_sem_cartorio_levanta_validation_error_sem_criar_documento(self):
        """A8 (#114): sem cartório → ValidationError, 0 docs, sem criar tipo."""
        tipos_antes = DocumentoTipo.objects.count()

        with self.subTest('cartorio_id=None'):
            imovel = self.criar_imovel('7201', 'transcricao')
            imovel.cartorio_id = None
            with self.assertRaisesMessage(
                ValidationError,
                'Cartório é obrigatório para criar o documento principal',
            ):
                LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(imovel.documentos.count(), 0)

        with self.subTest('cartorio=None (simula RelatedObjectDoesNotExist)'):
            imovel = self.criar_imovel('7202', 'transcricao')
            imovel.cartorio_id = None
            with self.assertRaisesMessage(
                ValidationError,
                'Cartório é obrigatório para criar o documento principal',
            ):
                LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
            self.assertEqual(imovel.documentos.count(), 0)

        self.assertEqual(DocumentoTipo.objects.count(), tipos_antes)


# ---------------------------------------------------------------------------
# Classe B: view (form de cadastro + novo_lancamento)
# ---------------------------------------------------------------------------


class ImovelFormTranscricaoTest(Issue230Fixture, TestCase):
    """B1/B2/B3: fluxo via ``imovel_form`` e ``novo_lancamento``."""

    def setUp(self):
        self.client.force_login(self.user)

    def test_cadastro_via_view_de_imovel_transcricao_cria_documento_T(self):
        """B1: POST no form cria T7188/transcrição + mensagem do CA6."""
        url = reverse('imovel_cadastro', kwargs={'tis_id': self.tis.id})

        response = self.client.post(url, {
            'nome': 'Imóvel Transcrição 230',
            'matricula': '7188',
            'tipo_documento_principal': 'transcricao',
            'cartorio': self.cartorio.id,
            'proprietario_nome': 'Proprietário 230',
            'estado': self.cartorio.estado,
            'cidade': self.cartorio.cidade,
        })

        self.assertEqual(response.status_code, 302)

        imovel = Imovel.objects.get(matricula='7188', tipo_documento_principal='transcricao')
        docs = Documento.objects.filter(imovel=imovel)
        self.assertEqual(docs.count(), 1)
        doc = docs.first()
        self.assertEqual(doc.tipo.tipo, 'transcricao')
        self.assertEqual(doc.numero, 'T7188')

        # Mensagem do CA6
        msgs = [m.message for m in response.wsgi_request._messages]
        self.assertTrue(
            any('transcrição' in m.lower() and 'T7188' in m for m in msgs),
            f'Esperada mensagem com "transcrição" e "T7188", obtido: {msgs}',
        )

    def test_novo_lancamento_sem_documento_id_abre_no_documento_T(self):
        """B2: GET novo_lancamento sem documento_id abre o T7188."""
        imovel = self.criar_imovel('7188', 'transcricao')
        LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
        doc = imovel.documentos.first()

        url = reverse('novo_lancamento', args=[self.tis.id, imovel.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['documento'].id, doc.id)
        self.assertEqual(response.context['documento'].tipo.tipo, 'transcricao')

    def test_novo_lancamento_sem_documento_id_com_documento_mais_recente_abre_o_mais_recente(self):
        """B3: caracterização do CA7b — fora do escopo do #230.

        ``lancamento_views.py:453`` + ``Meta.ordering`` fazem o GET sem
        ``documento_id`` abrir o documento mais recente. Se a issue de
        follow-up mudar a regra, atualizar este teste.
        """
        tipo_t, _ = DocumentoTipo.objects.get_or_create(tipo='transcricao')
        tipo_m, _ = DocumentoTipo.objects.get_or_create(tipo='matricula')
        imovel = self.criar_imovel('7300', 'transcricao')
        LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
        # Criar documento matrícula mais recente no mesmo imóvel
        Documento.objects.create(
            imovel=imovel,
            tipo=tipo_m,
            numero='M9001',
            data=timezone.localdate(),
            cartorio=self.cartorio,
            livro='0',
            folha='0',
        )

        url = reverse('novo_lancamento', args=[self.tis.id, imovel.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # O mais recente (M9001) é aberto, não o T7300
        self.assertEqual(response.context['documento'].numero, 'M9001')


# ---------------------------------------------------------------------------
# Classe C: árvore de hierarquia
# ---------------------------------------------------------------------------


class IdentificarDocumentoPrincipalTranscricaoTest(Issue230Fixture, TestCase):
    """C1/C2: a árvore escolhe T7188 como documento principal."""

    def test_arvore_escolhe_T_do_imovel_mesmo_com_origem_mais_recente(self):
        """C1: com T3858 mais recente, _identificar_documento_principal
        devolve o automático (T7188), tipo transcricao."""
        tipo_t, _ = DocumentoTipo.objects.get_or_create(tipo='transcricao')
        imovel = self.criar_imovel('7188', 'transcricao')
        doc_auto = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
        # T3858 mais recente
        Documento.objects.create(
            imovel=imovel,
            tipo=tipo_t,
            numero='T3858',
            data=timezone.localdate(),
            cartorio=self.cartorio,
            livro='0',
            folha='0',
        )

        principal = HierarquiaArvoreService._identificar_documento_principal(imovel)

        self.assertEqual(principal.id, doc_auto.id)
        self.assertEqual(principal.tipo.tipo, 'transcricao')

    def test_arvore_e_exportacao_preservam_a_origem_do_T(self):
        """C2: existe conexão from=T7188 → to=T3858 na árvore, e a
        cadeia completa preserva a ordem T7188 antes de T3858."""
        tipo_t, _ = DocumentoTipo.objects.get_or_create(tipo='transcricao')
        tipo_inicio, _ = LancamentoTipo.objects.get_or_create(tipo='inicio_matricula')
        imovel = self.criar_imovel('7188', 'transcricao')
        doc_auto = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
        t3858 = Documento.objects.create(
            imovel=imovel,
            tipo=tipo_t,
            numero='T3858',
            data=timezone.localdate(),
            cartorio=self.cartorio,
            livro='0',
            folha='0',
        )

        # Criar lançamento inicio_matricula no automático com origem T3858
        lancamento = Lancamento(
            documento=doc_auto,
            tipo=tipo_inicio,
            data=timezone.localdate(),
            origem='T3858',
            cartorio_origem=self.cartorio,
        )
        Lancamento.objects.bulk_create([lancamento])
        lancamento = Lancamento.objects.get(pk=lancamento.pk)
        LancamentoOrigem.objects.create(
            lancamento=lancamento,
            indice_origem=0,
            tipo_documento='transcricao',
            numero='T3858',
            cartorio=self.cartorio,
        )

        arvore = HierarquiaArvoreService.construir_arvore_cadeia_dominial(imovel)

        # (a) Conexão from=auto → to=t3858
        conexoes = arvore['conexoes']
        conexoes_relevantes = [
            c for c in conexoes
            if c['from'] == doc_auto.id and c['to'] == t3858.id
        ]
        self.assertTrue(
            len(conexoes_relevantes) >= 1,
            f'Esperada conexão from={doc_auto.id} to={t3858.id}, conexões: {conexoes}',
        )

        # (b) T7188 aparece antes de T3858 na lista de documentos da árvore
        ids_docs = [d['id'] for d in arvore['documentos'] if d.get('id')]
        idx_auto = ids_docs.index(doc_auto.id)
        idx_t3858 = ids_docs.index(t3858.id)
        self.assertLess(
            idx_auto, idx_t3858,
            f'T7188 (idx={idx_auto}) deve aparecer antes de T3858 (idx={idx_t3858})',
        )
