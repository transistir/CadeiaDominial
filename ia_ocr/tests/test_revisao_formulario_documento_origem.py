"""Aceite c7: o formulário vincula documento de origem no escopo do usuário."""

from datetime import date

from dominial.models import Documento, DocumentoTipo, Imovel, Lancamento, LancamentoOrigem, TIs
from dominial.services.lancamento_origem_service import LancamentoOrigemService

from .test_revisao_formulario_view_base import RevisaoFormularioBase, post_do_html


class _QuerysetAmbiguo:
    """Queryset mínimo que representa um estado legado ambíguo para o resolvedor."""

    def __init__(self, documentos):
        self.documentos = documentos

    def filter(self, **kwargs):
        return self

    def select_related(self, *args):
        return self

    def order_by(self, *args):
        return self.documentos


class DocumentoOrigemFormularioTest(RevisaoFormularioBase):
    def setUp(self):
        super().setUp()
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.cartorio_origem = self._cartorio('CRI de origem c7')
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo(self.cartorio_origem.nome, 'CRI de Guaíra'),
            'livro': self._campo('', 'Livro 2-RG'),
            'folha': self._campo('', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=self.cartorio_origem,
        )

    def _documento_origem(self, imovel=None, numero='T366'):
        return Documento.objects.create(
            imovel=imovel or self.imovel,
            tipo=self.tipo_transcricao, numero=numero, data=date(1990, 1, 1),
            cartorio=self.cartorio_origem, livro='1', folha='1',
        )

    def _inicio_com_origem_inexistente(self):
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'MATRÍCULA Nº 42.718',
        )
        payload['acts'][0]['rotulo'] = self._campo('M-237', 'M237')
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T999', '42.718'),
            'cartorio': self._campo(self.cartorio_origem.nome, 'CRI de Guaíra'),
            'livro': self._campo('', 'Livro 2-RG'),
            'folha': self._campo('', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=self.cartorio_origem,
        )

    def test_c7_origem_encontrada_vincula_sem_criar_outro_documento(self):
        existente = self._documento_origem()

        self.salvar(0)

        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.documento_origem_id, existente.pk)
        self.assertEqual(Documento.objects.filter(imovel=self.imovel).count(), 2)
        self._inicio_com_origem_inexistente()
        antes = Documento.objects.count()

        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Documento.objects.count(), antes)
        self.assertIsNone(Lancamento.objects.get(
            documento=self.documento, tipo=self.tipo_inicio,
        ).documento_origem)
        Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_inicio,
            numero_lancamento='M999', data=date(2020, 1, 1),
            origem='T999', cartorio_origem=self.cartorio_origem,
        )
        self.assertTrue(Documento.objects.filter(
            tipo=self.tipo_transcricao, numero='T999', cartorio=self.cartorio_origem,
        ).exists())

    def test_c7_origem_fora_do_escopo_nao_vincula(self):
        ti_restrita = TIs.objects.create(
            nome='TI restrita c7', codigo='TI-C7', etnia='Teste',
        )
        de_outro_usuario = Imovel.objects.create(
            nome='Imóvel restrito', matricula='M-restrita',
            terra_indigena_id=ti_restrita,
            proprietario=self.imovel.proprietario, cartorio=self.imovel.cartorio,
        )
        restrito = self._documento_origem(de_outro_usuario)

        self.salvar(0)

        self.assertEqual(
            LancamentoOrigemService._resolver_documento(
                'transcricao', 'T366', self.cartorio_origem, Documento.objects.all(),
            ),
            restrito,
        )
        self.assertIsNone(Lancamento.objects.get(documento=self.documento).documento_origem)

    def test_c7_origem_ambigua_nao_vincula(self):
        primeiro = self._documento_origem()
        segundo = self._documento_origem(numero='T367')
        segundo.numero = primeiro.numero
        lancamento = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R99 M237', data=date(2020, 1, 1),
        )
        LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=0, tipo_documento='transcricao',
            numero='T366', cartorio=self.cartorio_origem,
        )

        self.assertIsNone(LancamentoOrigemService.vincular_documento_origem(
            lancamento, documentos_queryset=_QuerysetAmbiguo([primeiro, segundo]),
        ))

        lancamento.refresh_from_db()
        self.assertIsNone(lancamento.documento_origem)

    def test_c7_duas_origens_nao_vinculam_documento_origem(self):
        existente = self._documento_origem()
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        post['origem_completa[]'].append('M237')
        post['cartorio_origem[]'].append(str(self.documento.cartorio_id))
        post['cartorio_origem_nome[]'].append(self.documento.cartorio.nome)
        post['livro_origem[]'].append('')
        post['folha_origem[]'].append('')

        self.client.post(self.url_ato(0), post)

        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertIsNone(lancamento.documento_origem)
        self.assertTrue(Documento.objects.filter(pk=existente.pk).exists())

    def test_c5_origem_sem_livro_folha_nao_bloqueia(self):
        from ia_ocr import revisao

        avisos = revisao.avisos(self.extracao)
        self.assertEqual(
            sorted(
                aviso['motivo'] for aviso in avisos
                if aviso['motivo'].endswith('_nao_consta')
            ),
            ['folha_origem_nao_consta', 'livro_origem_nao_consta'],
        )
        self.assertFalse([
            pendencia for pendencia in revisao.pendencias(self.extracao)
            if pendencia['motivo'].endswith('_nao_consta')
        ])

        pagina = self.client.get(self.url_ato(0))
        resposta = self.client.post(self.url_ato(0), post_do_html(pagina))

        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(Lancamento.objects.filter(documento=self.documento).exists())
