"""Testes do pré-preenchimento do formulário de lançamento (I-14 / #341, fase 1).

``prefill_do_ato`` lê o estado ATUAL da revisão (job em ``extraido``, nada
finalizado) e devolve o que o formulário manual consome: ``form_data`` com o
nome dos inputs, ``origens_separadas``, ``transmitentes``/``adquirentes``,
``evidencias`` e avisos do que foi lido sem campo no lançamento. Um caso por
destino, mais o round-trip do ``origens_separadas`` pelo
``_origens_separadas_do_post`` do formulário.
"""

import json
from copy import deepcopy

from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from dominial.models import Cartorios, Documento, LancamentoTipo, Pessoas
from dominial.views.lancamento_views import _origens_separadas_do_post
from ia_ocr import destinos
from ia_ocr.formulario import (
    CHAVE_PARA_INPUT, TEXTO_LIDO_SEM_CAMPO, AtoInexistente, input_do_campo,
    prefill_do_ato,
)
from ia_ocr.models import CampoSugerido, ExtracaoSugerida
from ia_ocr.revisao import desnormalizar

from .payloads_extracao import (
    SCHEMA_VERSION, payload_averbacao, payload_registro,
)
from .test_importacao import ImportacaoFixture


class PrefillBase(ImportacaoFixture, TestCase):
    """Job em ``extraido`` e documento sem livro/folha, com os três tipos."""

    def setUp(self):
        super().setUp()
        self.job.status = 'extraido'
        self.job.save(update_fields=['status'])
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')
        self.tipo_inicio = LancamentoTipo.objects.create(
            tipo='inicio_matricula',
        )
        # A fábrica do documento define livro/folha; aqui ele ainda não os tem.
        Documento.objects.filter(pk=self.documento.pk).update(
            livro='', folha='', numero='M237',
        )
        self.documento.refresh_from_db()

    def _aberta(self, payload):
        """Extração em revisão: nada escolhido, nada finalizado."""
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        CampoSugerido.objects.bulk_create(
            desnormalizar(extracao, payload, [self.pagina]),
        )
        return extracao

    def _registro(self, **campos):
        """Payload do registro com os campos do ato acrescentados/trocados."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0].update(campos)
        return payload

    def _averbacao(self, **campos):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'][0].update(campos)
        return payload

    def _prefill(self, payload, indice=0):
        return prefill_do_ato(self._aberta(payload), indice, self.documento)

    def _cartorio(self, nome='Cartório sintético do prefill'):
        return Cartorios.objects.create(
            nome=nome, cns=f'CNS-{nome[:8]}', estado='SP',
        )


class TipoENumeroTest(PrefillBase):
    def test_tipo_e_numero_simples_do_registro(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        form_data = resultado['form_data']
        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_registro.pk))
        self.assertEqual(form_data['numero_lancamento_simples'], '1')

    def test_numero_composto_nunca_e_preenchido(self):
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('numero_lancamento', form_data)

    def test_averbacao_pelo_rotulo(self):
        form_data = self._prefill(self._averbacao(
            rotulo=self._campo('Av-6', 'Av-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_averbacao.pk))
        self.assertEqual(form_data['numero_lancamento_simples'], '6')

    def test_tipo_segue_o_resolvedor_da_gravacao(self):
        # Rótulo R × tipo_sugerido averbação: o rótulo vence, como na
        # gravação — o prefill não decide o tipo por conta própria.
        form_data = self._prefill(self._registro(
            rotulo=self._campo('R-5', 'R-1/42.718'),
            tipo_sugerido=self._campo('averbacao', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_registro.pk))
        self.assertEqual(form_data['numero_lancamento_simples'], '5')

    def test_rotulo_de_matricula_usa_o_numero_de_ato_da_revisao(self):
        form_data = self._prefill(self._registro(
            rotulo=self._campo('M-3-14511', 'R-1/42.718'),
            numero_lancamento=self._campo('R-7', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['numero_lancamento_simples'], '7')

    def test_sem_numero_de_ato_nao_inventa_numero(self):
        form_data = self._prefill(self._registro(
            rotulo=self._campo('M-3-14511', 'R-1/42.718'),
        ))['form_data']

        self.assertNotIn('numero_lancamento_simples', form_data)

    def test_tipo_nao_configurado_fica_de_fora(self):
        LancamentoTipo.objects.filter(tipo='registro').delete()

        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('tipo_lancamento', form_data)


class FormaETituloTest(PrefillBase):
    def test_forma_da_averbacao_vai_para_forma_averbacao(self):
        form_data = self._prefill(self._averbacao(
            forma=self._campo('Retificação', 'Av-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['forma_averbacao'], 'Retificação')
        self.assertNotIn('forma_transacao', form_data)

    def test_forma_do_registro_vai_para_forma_transacao(self):
        form_data = self._prefill(self._registro(
            forma=self._campo('Compra e Venda', 'Escritura Pública'),
        ))['form_data']

        self.assertEqual(form_data['forma_transacao'], 'Compra e Venda')
        self.assertNotIn('forma_averbacao', form_data)

    def test_forma_do_inicio_de_matricula_vai_para_forma_transacao(self):
        form_data = self._prefill(self._registro(
            tipo_sugerido=self._campo('inicio_matricula', 'R-1/42.718'),
            rotulo=self._campo('M-1', 'R-1/42.718'),
            forma=self._campo('Abertura', 'R-1/42.718'),
        ))['form_data']

        self.assertEqual(form_data['tipo_lancamento'], str(self.tipo_inicio.pk))
        self.assertEqual(form_data['forma_transacao'], 'Abertura')
        self.assertNotIn('forma_averbacao', form_data)

    def test_titulo_so_em_titulo_transacao(self):
        form_data = self._prefill(self._registro(
            titulo=self._campo('Escritura de compra', 'Escritura Pública'),
        ))['form_data']

        self.assertEqual(form_data['titulo_transacao'], 'Escritura de compra')
        self.assertNotIn('titulo', form_data)


class TransmissaoETextosTest(PrefillBase):
    def test_transmissao_com_cartorio_escolhido(self):
        cartorio = self._cartorio('Cartório de Registro da Transmissão')
        extracao = self._aberta(self._registro(
            cartorio_transmissao=self._campo('CRI de Guaíra', 'CRI de Guaíra'),
            livro_transacao=self._campo('10-A', 'Livro 2-RG'),
            folha_transacao=self._campo('25v', 'Folha 087'),
            data_transacao=self._campo('2019-12-20', '10 de janeiro de 2020'),
        ))
        extracao.campos.filter(chave='/acts/0/cartorio_transmissao').update(
            cartorio_escolhido=cartorio,
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['cartorio_transmissao'], str(cartorio.pk))
        # O nome é o do CADASTRO (o que o autocomplete grava no input), não
        # o texto que o OCR leu.
        self.assertEqual(
            form_data['cartorio_transmissao_nome'],
            'Cartório de Registro da Transmissão',
        )
        self.assertEqual(form_data['livro_transacao'], '10-A')
        self.assertEqual(form_data['folha_transacao'], '25v')
        self.assertEqual(form_data['data_transacao'], '2019-12-20')

    def test_cartorio_criar_novo_entra_so_com_o_nome(self):
        extracao = self._aberta(self._registro(
            cartorio_transmissao=self._campo('CRI de Guaíra', 'CRI de Guaíra'),
        ))
        extracao.campos.filter(chave='/acts/0/cartorio_transmissao').update(
            criar_novo=True,
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['cartorio_transmissao_nome'], 'CRI de Guaíra')
        self.assertNotIn('cartorio_transmissao', form_data)
        self.assertFalse(Cartorios.objects.filter(nome='CRI de Guaíra').exists())

    def test_cartorio_sem_decisao_entra_so_com_o_nome(self):
        form_data = self._prefill(self._registro(
            cartorio_transmissao=self._campo('CRI de Guaíra', 'CRI de Guaíra'),
        ))['form_data']

        self.assertEqual(form_data['cartorio_transmissao_nome'], 'CRI de Guaíra')
        self.assertNotIn('cartorio_transmissao', form_data)

    def test_data_area_descricao_e_observacoes(self):
        form_data = self._prefill(self._registro(
            descricao=self._campo('Descrição do ato', 'Escritura Pública'),
            observacoes=self._campo('Observação do ato', 'Escritura Pública'),
        ))['form_data']

        self.assertEqual(form_data['data'], '2020-02-15')
        self.assertEqual(form_data['area'], '12.50')
        self.assertEqual(form_data['descricao'], 'Descrição do ato')
        self.assertEqual(form_data['observacoes'], 'Observação do ato')

    def test_campo_descartado_nao_entra(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/area').update(
            status_revisao='descartado',
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertNotIn('area', form_data)

    def test_valor_editado_na_revisao_vence_o_lido(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/data').update(
            valor_final='2020-03-01', status_revisao='editado',
        )

        form_data = prefill_do_ato(extracao, 0, self.documento)['form_data']

        self.assertEqual(form_data['data'], '2020-03-01')

    def test_livro_e_folha_do_documento_so_se_ainda_nao_definidos(self):
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']
        self.assertEqual(form_data['livro_documento'], '2-RG')
        self.assertEqual(form_data['folha_documento'], '087')

        # '0' conta como não definido (#218); livro já definido é travado.
        Documento.objects.filter(pk=self.documento.pk).update(
            livro='7', folha='0',
        )
        self.documento.refresh_from_db()
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('livro_documento', form_data)
        self.assertEqual(form_data['folha_documento'], '087')

    def test_form_data_so_tem_valores_em_texto(self):
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertTrue(form_data)
        for nome, valor in form_data.items():
            with self.subTest(nome=nome):
                self.assertIsInstance(valor, str)
                self.assertTrue(valor.strip())


class OrigemTest(PrefillBase):
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


class PartesTest(PrefillBase):
    def test_partes_no_formato_do_pessoa_form(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        self.assertEqual(resultado['transmitentes'], [
            {'id': '', 'nome': 'JOÃO DA SILVA'},
            {'id': '', 'nome': 'MARIA DA SILVA'},
        ])
        self.assertEqual(resultado['adquirentes'], [
            {'id': '', 'nome': 'PEDRO SANTOS'},
        ])

    def test_pessoa_escolhida_leva_id_e_nome_do_cadastro(self):
        pessoa = Pessoas.objects.create(nome='João da Silva (cadastro)')
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            pessoa_escolhida=pessoa,
        )
        extracao.campos.filter(chave='/acts/0/partes/1').update(criar_novo=True)

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['transmitentes'], [
            {'id': str(pessoa.pk), 'nome': 'João da Silva (cadastro)'},
            {'id': '', 'nome': 'MARIA DA SILVA'},
        ])
        self.assertFalse(Pessoas.objects.filter(nome='MARIA DA SILVA').exists())

    def test_conjuge_e_parte_descartada_ficam_de_fora(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            valor_final='conjuge', status_revisao='editado',
        )
        extracao.campos.filter(chave='/acts/0/partes/2').update(
            status_revisao='descartado',
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['transmitentes'], [
            {'id': '', 'nome': 'MARIA DA SILVA'},
        ])
        self.assertEqual(resultado['adquirentes'], [])

    def test_cpf_e_rg_nao_aparecem_em_lugar_nenhum(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        serializado = json.dumps(resultado, ensure_ascii=False, default=str)
        for sensivel in ('123.456.789-00', '12345678900', '987.654.321-00'):
            self.assertNotIn(sensivel, serializado)


class EvidenciaTest(PrefillBase):
    def test_evidencia_dos_campos_do_ato(self):
        evidencias = self._prefill(payload_registro(self.job.job_id))['evidencias']

        self.assertEqual(evidencias['data'], {
            'pagina': 1, 'trecho': '15 de fevereiro de 2020',
            'confianca_baixa': False,
        })
        self.assertEqual(evidencias['tipo_lancamento']['trecho'], 'R-1/42.718')
        self.assertEqual(
            evidencias['numero_lancamento_simples']['trecho'], 'R-1/42.718',
        )
        self.assertEqual(evidencias['area']['trecho'], 'área 12,50 ha')
        self.assertEqual(evidencias['livro_documento']['trecho'], 'Livro 2-RG')

    def test_chave_da_evidencia_segue_a_forma_da_averbacao(self):
        evidencias = self._prefill(self._averbacao(
            forma=self._campo('Retificação', 'Av-1/42.718'),
        ))['evidencias']

        self.assertIn('forma_averbacao', evidencias)
        self.assertNotIn('forma_transacao', evidencias)

    def test_evidencia_das_partes_pela_posicao_na_lista(self):
        evidencias = self._prefill(payload_registro(self.job.job_id))['evidencias']

        self.assertEqual(evidencias['transmitente_nome[0]']['trecho'], 'JOÃO DA SILVA')
        self.assertEqual(evidencias['transmitente_nome[1]']['trecho'], 'MARIA DA SILVA')
        self.assertEqual(evidencias['adquirente_nome[0]']['trecho'], 'PEDRO SANTOS')

    def test_posicao_conta_so_as_partes_que_entraram(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            status_revisao='descartado',
        )

        evidencias = prefill_do_ato(extracao, 0, self.documento)['evidencias']

        self.assertEqual(evidencias['transmitente_nome[0]']['trecho'], 'MARIA DA SILVA')
        self.assertNotIn('transmitente_nome[1]', evidencias)

    def test_trecho_sai_mascarado(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][0]['nome'] = self._campo(
            'JOÃO DA SILVA', 'JOÃO DA SILVA (CPF 123.456.789-00)',
        )

        evidencias = self._prefill(payload)['evidencias']

        trecho = evidencias['transmitente_nome[0]']['trecho']
        self.assertEqual(trecho, 'JOÃO DA SILVA (CPF ***)')
        self.assertNotIn('123.456.789-00', json.dumps(evidencias))

    def test_baixa_confianca_marca_a_evidencia(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['data']['confianca'] = 0.4

        evidencias = self._prefill(payload)['evidencias']

        self.assertTrue(evidencias['data']['confianca_baixa'])
        self.assertFalse(evidencias['area']['confianca_baixa'])

    def test_evidencia_so_dos_inputs_preenchidos(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        extracao.campos.filter(chave='/acts/0/area').update(
            status_revisao='descartado',
        )
        Documento.objects.filter(pk=self.documento.pk).update(livro='7')
        self.documento.refresh_from_db()

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertNotIn('area', resultado['evidencias'])
        self.assertNotIn('livro_documento', resultado['evidencias'])
        self.assertLessEqual(
            {
                nome for nome in resultado['evidencias']
                if '[' not in nome
            },
            set(resultado['form_data']),
        )

    def test_evidencia_da_origem_pela_posicao_zero(self):
        payload = self._registro()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }

        evidencias = self._prefill(payload)['evidencias']

        self.assertEqual(evidencias['numero_origem[0]']['trecho'], '42.718')
        self.assertEqual(evidencias['cartorio_origem_nome[0]']['trecho'], 'CRI de Guaíra')
        self.assertEqual(evidencias['livro_origem[0]']['trecho'], 'Livro 2-RG')
        self.assertEqual(evidencias['folha_origem[0]']['trecho'], 'Folha 087')

    def test_tabela_unica_de_inputs(self):
        self.assertEqual(input_do_campo('/acts/3/data'), 'data')
        self.assertEqual(input_do_campo('/acts/*/data'), 'data')
        self.assertEqual(input_do_campo('/acts/0/forma', 'registro'), 'forma_transacao')
        self.assertEqual(input_do_campo('/acts/0/forma', 'averbacao'), 'forma_averbacao')
        self.assertEqual(
            input_do_campo('/acts/0/partes/4/nome', papel='adquirente'),
            'adquirente_nome',
        )
        self.assertIsNone(input_do_campo('/acts/0/valor_transacao'))
        self.assertIsNone(input_do_campo('/acts/0/partes/0/documento_identificacao/valor'))
        # As chaves da tabela são padrões reais do mapa de destinos (sem
        # erro de digitação que deixaria uma linha sem input).
        for padrao in CHAVE_PARA_INPUT:
            with self.subTest(padrao=padrao):
                self.assertIn(padrao, destinos.DESTINOS)


class SemLugarNoFormularioTest(PrefillBase):
    def _rotulos(self, resultado):
        return [aviso['rotulo'] for aviso in resultado['pendencias']]

    def test_campos_lidos_sem_lugar_viram_aviso_informativo(self):
        payload = self._registro(
            detalhes=self._campo('Detalhes do ato', 'Escritura Pública'),
        )
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'data': self._campo('1990-01-02', '10 de janeiro de 2020'),
        }

        resultado = self._prefill(payload)

        self.assertEqual(self._rotulos(resultado), [
            'Data da origem', 'CPF/RG das partes', 'Valor da transação',
            'Detalhes',
        ])
        for aviso in resultado['pendencias']:
            with self.subTest(rotulo=aviso['rotulo']):
                self.assertFalse(aviso['bloqueante'])
                self.assertEqual(aviso['texto'], TEXTO_LIDO_SEM_CAMPO)
                self.assertEqual(aviso['texto'], 'lido, sem campo no lançamento')

    def test_nada_disso_entra_no_form_data_nem_cita_a_chave(self):
        payload = self._registro(
            detalhes=self._campo('Detalhes do ato', 'Escritura Pública'),
        )
        payload['acts'][0]['origem'] = {
            'numero': self._campo('T366', '42.718'),
            'data': self._campo('1990-01-02', '10 de janeiro de 2020'),
        }

        resultado = self._prefill(payload)

        valores = ' '.join(resultado['form_data'].values())
        for lido in ('150000', 'Detalhes do ato', '1990-01-02', '12345678900'):
            self.assertNotIn(lido, valores)
        for nome in resultado['form_data']:
            self.assertNotIn('valor', nome)
            self.assertNotIn('detalhes', nome)
        for aviso in resultado['pendencias']:
            self.assertNotIn('/acts/', json.dumps(aviso, ensure_ascii=False))

    def test_valor_e_detalhes_de_linha_antiga_tambem_avisam(self):
        # Extração salva antes do #328: a linha existe, é ignorada na
        # leitura, e o payload segue com o valor lido.
        payload = self._registro()
        extracao = self._aberta(payload)
        CampoSugerido.objects.create(
            extracao=extracao, chave='/acts/0/valor_transacao',
            raw='150000.00', normalized='150000.00', tipo_valor='texto',
        )

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertIn('Valor da transação', self._rotulos(resultado))

    def test_sem_nada_lido_sem_lugar_nao_ha_aviso(self):
        resultado = self._prefill(payload_averbacao(self.job.job_id))

        self.assertEqual(resultado['pendencias'], [])

    def test_folha_vazia_nao_gera_aviso(self):
        resultado = self._prefill(self._averbacao(
            valor_transacao={
                'raw': None, 'normalized': None, 'confianca': 0.9,
                'requer_revisao': False,
            },
        ))

        self.assertEqual(resultado['pendencias'], [])


class ContratoDaFuncaoTest(PrefillBase):
    def test_devolve_as_seis_chaves(self):
        resultado = self._prefill(payload_registro(self.job.job_id))

        self.assertEqual(set(resultado), {
            'form_data', 'origens_separadas', 'transmitentes', 'adquirentes',
            'evidencias', 'pendencias',
        })

    def test_funciona_com_job_extraido_e_nada_finalizado(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        self.assertEqual(self.job.status, 'extraido')
        self.assertIsNone(extracao.finalizada_em)

        resultado = prefill_do_ato(extracao, 0, self.documento)

        self.assertEqual(resultado['form_data']['data'], '2020-02-15')

    def test_cada_ato_pelo_proprio_indice(self):
        payload = payload_registro(self.job.job_id)
        segundo = payload_averbacao(self.job.job_id)['acts'][0]
        segundo['ordem'] = 2
        payload['acts'].append(segundo)
        extracao = self._aberta(payload)

        primeiro = prefill_do_ato(extracao, 0, self.documento)['form_data']
        outro = prefill_do_ato(extracao, 1, self.documento)['form_data']

        self.assertEqual(primeiro['tipo_lancamento'], str(self.tipo_registro.pk))
        self.assertEqual(primeiro['data'], '2020-02-15')
        self.assertEqual(outro['tipo_lancamento'], str(self.tipo_averbacao.pk))
        self.assertEqual(outro['data'], '2021-03-20')
        self.assertEqual(outro['descricao'], 'averbação de construção de casa sede')

    def test_indice_inexistente_ou_ato_descartado(self):
        extracao = self._aberta(payload_registro(self.job.job_id))

        with self.assertRaises(AtoInexistente):
            prefill_do_ato(extracao, 5, self.documento)

        extracao.campos.filter(chave='/acts/0').update(status_revisao='descartado')
        with self.assertRaises(AtoInexistente):
            prefill_do_ato(extracao, 0, self.documento)

    def test_consultas_nao_crescem_com_o_numero_de_partes(self):
        def consultas(quantas):
            payload = payload_registro(self.job.job_id)
            parte = payload['acts'][0]['partes'][2]
            payload['acts'][0]['partes'] = [deepcopy(parte) for _ in range(quantas)]
            extracao = self._aberta(payload)
            for posicao in range(quantas):
                pessoa = Pessoas.objects.create(nome='Pessoa %d' % posicao)
                extracao.campos.filter(
                    chave='/acts/0/partes/%d' % posicao,
                ).update(pessoa_escolhida=pessoa)
            with CaptureQueriesContext(connection) as capturadas:
                resultado = prefill_do_ato(extracao, 0, self.documento)
            self.assertEqual(len(resultado['adquirentes']), quantas)
            extracao.delete()
            return len(capturadas)

        self.assertEqual(consultas(1), consultas(8))

    def test_nao_escreve_nada(self):
        extracao = self._aberta(payload_registro(self.job.job_id))
        antes = (
            CampoSugerido.objects.count(), Pessoas.objects.count(),
            Cartorios.objects.count(),
        )

        with CaptureQueriesContext(connection) as capturadas:
            prefill_do_ato(extracao, 0, self.documento)

        escritas = [
            consulta['sql'] for consulta in capturadas.captured_queries
            if consulta['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'),
            )
        ]
        self.assertEqual(escritas, [])
        self.assertEqual(antes, (
            CampoSugerido.objects.count(), Pessoas.objects.count(),
            Cartorios.objects.count(),
        ))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'extraido')
