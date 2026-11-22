"""Testes de aplicar_linha/versao_linha — migração VERBATIM de
``ia_ocr/tests/test_revisao.py`` (Etapa 5, grupo 3 do plano de
400 linhas). Corpos verbatim; só imports e a linha de classe mudam.
"""

from datetime import timedelta
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.utils import timezone

from dominial.models import LancamentoTipo
from ia_ocr import destinos, valores
from ia_ocr.models import ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    _valor_explicito,
    aplicar_linha,
    desnormalizar,
    versao_linha,
)

from .payloads_extracao import TEXTO_PAGINA_1, payload_registro


class AplicarLinhaTest(SimpleTestCase):
    def setUp(self):
        job = OcrJob()
        extracao = ExtracaoSugerida(ocr_job=job)
        pagina = PaginaOcr(
            ocr_job=job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1
        )
        payload = payload_registro(job.job_id)
        # Ato com unidade NÃO conversível (alqueires): é ela que exige a
        # decisão de conversão testada aqui. O documento fica em m², sem
        # destino, para provar que a conversão automática não o alcança.
        payload['acts'][0]['area'].update(
            normalized='120.00', raw='120,00 alqueires', unidade='alqueires',
            evidencia={'pagina': 1, 'trecho': '120,00 m2'},
        )
        payload['document']['area'].update(
            normalized='120.00', raw='120,00 m2', unidade='m2',
            evidencia={'pagina': 1, 'trecho': '120,00 m2'},
        )
        self.linhas = {
            linha.chave: linha
            for linha in desnormalizar(extracao, payload, [pagina])
        }
        self.usuario = get_user_model()(username='revisor')
        self.agora = timezone.now()

    def test_tipo_ato_invalido_recusado_no_codec(self):
        with self.assertRaises(valores.ValorInvalido):
            valores.do_formulario(
                'enum', 'registroo', destinos.destino_de('/acts/0/tipo_sugerido'),
            )

    def test_tipo_ato_invalido_recusado_ao_aplicar_linha(self):
        campo = self.linhas['/acts/0/tipo_sugerido']
        with self.assertRaises(valores.ValorInvalido):
            aplicar_linha(campo, incluir=True, valor='registroo')

    def test_tipo_ato_invalido_recusado_ao_conferir_ou_reincluir(self):
        for reincluir in (False, True):
            with self.subTest(reincluir=reincluir):
                campo = self.linhas['/acts/0/tipo_sugerido']
                campo.normalized = 'registro' if reincluir else 'registroo'
                campo.valor_final = 'registroo' if reincluir else None
                campo.status_revisao = 'descartado' if reincluir else 'sugerido'
                with self.assertRaises(valores.ValorInvalido):
                    aplicar_linha(campo, incluir=True, conferido=True)

    def test_tipos_ato_validos_aceitos(self):
        for tipo, _rotulo in LancamentoTipo.TIPO_CHOICES:
            with self.subTest(tipo=tipo):
                campo = self.linhas['/acts/0/tipo_sugerido']
                aplicar_linha(campo, incluir=True, valor=tipo, conferido=True)
                self.assertEqual(campo.valor_final or campo.normalized, tipo)

    def test_descartar_apos_editar_preserva_valor_final(self):
        campo = self.linhas['/document/data']
        aplicar_linha(campo, incluir=True, valor='2020-01-11')
        self.assertEqual(campo.status_revisao, 'editado')
        self.assertEqual(campo.valor_final, '2020-01-11')

        resultado = aplicar_linha(
            campo, incluir=False, valor='ignorado no descarte',
            usuario=self.usuario, agora=self.agora,
        )

        self.assertIs(resultado, campo)
        self.assertIsNone(campo.pk)
        self.assertEqual(campo.status_revisao, 'descartado')
        self.assertEqual(campo.valor_final, '2020-01-11')
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

        aplicar_linha(
            campo, incluir=False, agora=self.agora + timedelta(seconds=1)
        )
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

    def test_reincluir_volta_a_editado(self):
        for valor in ('2020-01-11', '', None):
            with self.subTest(valor=valor):
                campo = self.linhas['/document/data']
                aplicar_linha(campo, incluir=True, valor=valor)
                valor_final = campo.valor_final
                aplicar_linha(campo, incluir=False)

                aplicar_linha(campo, incluir=True)

                self.assertEqual(
                    campo.status_revisao,
                    'sugerido' if valor_final is None else 'editado',
                )
                self.assertEqual(campo.valor_final, valor_final)

    def test_aceitar_apos_editar_igual_ao_sugerido(self):
        campo = self.linhas['/document/data']
        aplicar_linha(campo, incluir=True, valor='2020-01-11')

        aplicar_linha(
            campo, incluir=True, valor='2020-01-10', conferido=True,
            usuario=self.usuario, agora=self.agora,
        )

        self.assertEqual(campo.status_revisao, 'aceito')
        self.assertIsNone(campo.valor_final)
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

        aplicar_linha(
            campo, incluir=True, valor=campo.normalized, conferido=True,
            agora=self.agora + timedelta(seconds=1),
        )
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

    def test_confirmar_o_valor_igual_ao_sugerido_marca_escolha_explicita(self):
        # P1 (Greptile, #322/PR #327): conferir o card sem digitar limpa o
        # ``valor_final`` (canonico == normalized) e antes a precedência do
        # tipo não via escolha nenhuma — o rótulo do ato vencia a decisão
        # do revisor. A flag separa "qual é o valor" de "o revisor escolheu
        # esse valor"; o estado novo também autora a linha.
        campo = self.linhas['/acts/0/tipo_sugerido']

        aplicar_linha(
            campo, incluir=True, conferido=True,
            usuario=self.usuario, agora=self.agora,
        )

        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'aceito')
        self.assertTrue(campo.escolha_explicita)
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

    def test_reenviar_o_mesmo_valor_marca_escolha_explicita(self):
        # O outro caminho do card: o revisor reenvia o MESMO valor —
        # ``canonico == normalized`` deixa ``valor_final`` nulo e o status
        # nem muda; só a flag registra a decisão (e autora a linha).
        campo = self.linhas['/acts/0/tipo_sugerido']

        aplicar_linha(
            campo, incluir=True, valor=campo.normalized,
            usuario=self.usuario, agora=self.agora,
        )

        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'sugerido')
        self.assertTrue(campo.escolha_explicita)
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

    def test_descartar_e_reincluir_preservam_a_escolha_explicita(self):
        campo = self.linhas['/acts/0/tipo_sugerido']
        aplicar_linha(campo, incluir=True, conferido=True)
        self.assertTrue(campo.escolha_explicita)

        aplicar_linha(campo, incluir=False)
        self.assertEqual(campo.status_revisao, 'descartado')
        self.assertTrue(campo.escolha_explicita)

        # Reincluir sem novo valor: a escolha anterior continua valendo.
        aplicar_linha(campo, incluir=True)
        self.assertEqual(campo.status_revisao, 'sugerido')
        self.assertTrue(campo.escolha_explicita)

    def test_sem_decisao_do_revisor_a_flag_nao_e_marcada(self):
        campo = self.linhas['/acts/0/tipo_sugerido']

        aplicar_linha(campo, incluir=True)

        self.assertFalse(campo.escolha_explicita)

    def test_valor_explicito_cobre_as_quatro_decisoes(self):
        # A regra que alimenta a precedência do tipo (``tipo_exp`` do
        # ``dados_revisados`` e ``_tipos_efetivos``): descartado não decide;
        # edição vence; confirmação devolve o sugerido; sem decisão, None.
        campo = self.linhas['/acts/0/tipo_sugerido']
        self.assertIsNone(_valor_explicito(campo))

        campo.escolha_explicita = True
        self.assertEqual(_valor_explicito(campo), campo.normalized)

        campo.valor_final = 'averbacao'
        self.assertEqual(_valor_explicito(campo), 'averbacao')

        campo.status_revisao = 'descartado'
        self.assertIsNone(_valor_explicito(campo))

        self.assertIsNone(_valor_explicito(None))

    def test_requer_revisao_sem_conferido_nao_aceita(self):
        campo = self.linhas['/document/data']
        campo.requer_revisao = True
        for valor, status in (
            (None, 'sugerido'),
            ('2020-01-10', 'sugerido'),
            ('2020-01-11', 'editado'),
        ):
            with self.subTest(valor=valor):
                campo.status_revisao = 'aceito'

                aplicar_linha(campo, incluir=True, valor=valor)

                self.assertEqual(campo.status_revisao, status)
        aplicar_linha(campo, incluir=True, conferido=True)
        self.assertEqual(campo.status_revisao, 'aceito')
        self.assertIsNone(campo.valor_final)

    def test_area_so_com_conversao_confirmada(self):
        campo = self.linhas['/acts/0/area']
        self.assertIn('unidade_area', campo.motivos_revisao)
        campo.motivos_revisao.append('baixa_confianca')

        aplicar_linha(campo, incluir=True, valor='0.0120', conferido=True)
        self.assertFalse(campo.area_convertida)
        self.assertIsNone(campo.valor_final)
        self.assertIn('unidade_area', campo.motivos_revisao)

        antes = versao_linha(campo)
        for ha_convertido, confirmo_conversao in (
            ('0.0120', False), (None, True), ('', True), ('', False),
        ):
            with self.subTest(ha=ha_convertido, confirmo=confirmo_conversao):
                with self.assertRaisesMessage(
                    valores.ValorInvalido, 'conversao_incompleta'
                ):
                    aplicar_linha(
                        campo, incluir=True, ha_convertido=ha_convertido,
                        confirmo_conversao=confirmo_conversao,
                    )
                self.assertEqual(versao_linha(campo), antes)

        for ha_convertido in ('invalido', '-1', '0.00001', '123456789.0000'):
            with self.subTest(ha=ha_convertido):
                with self.assertRaises(valores.ValorInvalido):
                    aplicar_linha(
                        campo, incluir=True, ha_convertido=ha_convertido,
                        confirmo_conversao=True,
                    )
                self.assertEqual(versao_linha(campo), antes)

        aplicar_linha(
            campo, incluir=True, ha_convertido='0,0120',
            confirmo_conversao=True, usuario=self.usuario, agora=self.agora,
        )
        self.assertTrue(campo.area_convertida)
        self.assertEqual(campo.valor_final, '0.0120')
        self.assertEqual(campo.normalized, '120.00')
        self.assertEqual(campo.status_revisao, 'editado')
        self.assertEqual(campo.motivos_revisao, ['baixa_confianca'])
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

        aplicar_linha(
            campo, incluir=True, ha_convertido='0.0120',
            confirmo_conversao=True, agora=self.agora + timedelta(seconds=1),
        )
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

        aplicar_linha(
            campo, incluir=True, ha_convertido='120,00',
            confirmo_conversao=True, conferido=True,
        )
        self.assertEqual(campo.status_revisao, 'aceito')
        self.assertEqual(campo.valor_final, '120.00')
        self.assertTrue(campo.area_convertida)

    def test_area_limpar_conversao(self):
        campo = self.linhas['/acts/0/area']
        aplicar_linha(
            campo, incluir=True, ha_convertido='0.0120',
            confirmo_conversao=True,
        )
        self.assertNotIn('unidade_area', campo.motivos_revisao)

        aplicar_linha(
            campo, incluir=True, ha_convertido=None,
            usuario=self.usuario, agora=self.agora,
        )

        self.assertFalse(campo.area_convertida)
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.status_revisao, 'sugerido')
        self.assertEqual(campo.motivos_revisao, ['unidade_area'])
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

        aplicar_linha(
            campo, incluir=True, agora=self.agora + timedelta(seconds=1)
        )
        self.assertEqual(campo.motivos_revisao, ['unidade_area'])
        self.assertIs(campo.revisado_por, self.usuario)
        self.assertEqual(campo.revisado_em, self.agora)

    def test_area_sem_destino_nao_converte(self):
        campo = self.linhas['/document/area']
        self.assertNotIn('unidade_area', campo.motivos_revisao)
        for tipo_valor in ('texto', 'area'):
            with self.subTest(tipo_valor=tipo_valor):
                # Mesmo uma linha antiga com motivo de unidade é SEM_DESTINO.
                campo.tipo_valor = tipo_valor
                campo.motivos_revisao = (
                    ['unidade_area'] if tipo_valor == 'area' else []
                )
                motivos = list(campo.motivos_revisao)
                for ha, confirmo in (('invalido', True), ('0.0120', False)):
                    aplicar_linha(
                        campo, incluir=True, ha_convertido=ha,
                        confirmo_conversao=confirmo, conferido=True,
                    )
                    self.assertFalse(campo.area_convertida)
                    self.assertIsNone(campo.valor_final)
                    self.assertEqual(campo.normalized, '120.00')
                    self.assertEqual(campo.status_revisao, 'aceito')
                    self.assertEqual(campo.motivos_revisao, motivos)

    def test_versao_linha_muda_com_cada_campo(self):
        campo = self.linhas['/document/data']
        antes = versao_linha(campo)
        alteracoes = {
            'status_revisao': 'aceito',
            'valor_final': '2020-01-11',
            # A escolha explícita no estado (P1 #322/PR #327): a confirmação
            # que só zera o valor_final muda a versão — e autora a linha.
            'escolha_explicita': True,
            'motivos_revisao': ['baixa_confianca'],
            'pessoa_escolhida_id': 1,
            'cartorio_escolhido_id': 2,
            'criar_novo': True,
            'area_convertida': True,
            'revisado_em': self.agora,
        }
        for nome, valor in alteracoes.items():
            with self.subTest(campo=nome):
                original = getattr(campo, nome)
                setattr(campo, nome, valor)
                self.assertNotEqual(versao_linha(campo), antes)
                setattr(campo, nome, original)
                self.assertEqual(versao_linha(campo), antes)

    def test_versao_linha_estavel_sem_mudanca(self):
        campo = self.linhas['/document/numero']
        campo.valor_final = 'Área conferida'
        esperado = sha256(
            '["sugerido","Área conferida",false,[],null,null,false,false,null]'
            .encode()
        ).hexdigest()[:16]

        self.assertEqual(versao_linha(campo), esperado)
        self.assertEqual(versao_linha(campo), esperado)
        self.assertRegex(versao_linha(campo), r'^[0-9a-f]{16}$')
