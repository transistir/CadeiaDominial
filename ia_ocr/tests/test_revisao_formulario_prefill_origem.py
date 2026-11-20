"""``OrigemTest`` — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_prefill.py`` (Etapa 13 do
plano de 400 linhas).
"""
from django.test import RequestFactory

from dominial.models import Cartorios
from dominial.views.lancamento_views import _origens_separadas_do_post
from ia_ocr.formulario import prefill_do_ato

from .payloads_extracao import payload_registro

class OrigemTestParte:
    def _payload_origem(self, **origem):
        payload = self._registro()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        payload['acts'][0]['origem'].update(origem)
        return payload

    def test_origem_no_formato_do_post(self):
        resultado = self._prefill(self._payload_origem())

        self.assertEqual(resultado['origens_separadas'], [{
            'texto': 'T366', 'index': 0,
            'tipo_origem': 'T', 'numero_origem': '366',
            'cartorio_nome': 'CRI de Origem', 'cartorio_id': '',
            'livro': '2', 'folha': '123',
            'fim_cadeia': False, 'tipo_fim_cadeia': '',
            'classificacao_fim_cadeia': '', 'especificacao_fim_cadeia': '',
            'sigla_patrimonio_publico': '', 'info_adicional_fim_cadeia': '',
            'is_destacamento_publico': False,
        }])

    def test_origem_com_cartorio_escolhido_leva_id_e_nome_do_cadastro(self):
        cartorio = self._cartorio('Cartório de Origem Cadastrado')
        extracao = self._aberta(self._payload_origem())
        extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=cartorio,
        )

        (origem,) = prefill_do_ato(extracao, 0, self.documento)['origens_separadas']

        self.assertEqual(origem['cartorio_id'], str(cartorio.pk))
        self.assertEqual(origem['cartorio_nome'], 'Cartório de Origem Cadastrado')

    def test_origem_cartorio_criar_novo_deixa_o_id_vazio(self):
        extracao = self._aberta(self._payload_origem())
        extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            criar_novo=True,
        )

        (origem,) = prefill_do_ato(extracao, 0, self.documento)['origens_separadas']

        self.assertEqual(origem['cartorio_id'], '')
        self.assertEqual(origem['cartorio_nome'], 'CRI de Origem')
        self.assertFalse(Cartorios.objects.filter(nome='CRI de Origem').exists())

    def test_prefixo_pelo_tipo_documental(self):
        for tipo, numero, esperado in (
            ('matricula', '123', 'M123'),
            ('transcricao', '45', 'T45'),
            ('matricula', 'M77', 'M77'),
            (None, 'T8', 'T8'),
        ):
            with self.subTest(tipo=tipo, numero=numero):
                origem = {'numero': self._campo(numero, '42.718')}
                if tipo is not None:
                    origem['tipo_documento'] = self._campo(tipo, '42.718')
                payload = self._registro(origem=origem)

                (item,) = self._prefill(payload)['origens_separadas']

                self.assertEqual(item['texto'], esperado)
                self.assertEqual(item['tipo_origem'], esperado[0])
                self.assertEqual(item['numero_origem'], esperado[1:])

    def test_numero_incompativel_com_o_tipo_nao_vira_texto(self):
        payload = self._payload_origem(
            tipo_documento=self._campo('matricula', '42.718'),
            numero=self._campo('T366', '42.718'),
        )

        (item,) = self._prefill(payload)['origens_separadas']

        self.assertEqual(item['texto'], '')
        self.assertEqual(item['tipo_origem'], '')
        self.assertEqual(item['numero_origem'], '')
        self.assertEqual(item['cartorio_nome'], 'CRI de Origem')

    def test_sem_origem_a_lista_e_vazia(self):
        self.assertEqual(
            self._prefill(payload_registro(self.job.job_id))['origens_separadas'],
            [],
        )

    def test_round_trip_pelo_origens_separadas_do_post(self):
        cartorio = self._cartorio('Cartório de Origem Round Trip')
        casos = {
            'com_cartorio_escolhido': True,
            'cartorio_so_com_o_nome': False,
        }
        for nome, escolher in casos.items():
            with self.subTest(caso=nome):
                extracao = self._aberta(self._payload_origem())
                if escolher:
                    extracao.campos.filter(
                        chave='/acts/0/origem/cartorio',
                    ).update(cartorio_escolhido=cartorio)
                (item,) = prefill_do_ato(
                    extracao, 0, self.documento,
                )['origens_separadas']

                requisicao = RequestFactory().post('/', {
                    'origem_completa[]': [item['texto']],
                    'cartorio_origem[]': [item['cartorio_id']],
                    'cartorio_origem_nome[]': [item['cartorio_nome']],
                    'livro_origem[]': [item['livro']],
                    'folha_origem[]': [item['folha']],
                })

                self.assertEqual(_origens_separadas_do_post(requisicao), [item])
                extracao.delete()
