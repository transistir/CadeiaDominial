"""Testes da desnormalização do payload A3 em CampoSugerido (I-5, §18).

Um teste por comportamento: chaves JSON Pointer + tipo_valor, placeholders
dos obrigatórios ausentes, baixa confiança forçando revisão, closure sempre
em revisão e evidência (página inexistente / trecho ausente). As linhas
voltam sem pk e ``desnormalizar`` não toca o banco (assertNumQueries(0)).
"""

from datetime import timedelta
from hashlib import sha256

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from dominial.models import Cartorios, LancamentoTipo, Pessoas
from ia_ocr import valores
from ia_ocr.extracao_schema import validar_payload
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    aplicar_linha, avisos, desnormalizar, pendencias, versao_linha,
)

from .factories import criar_documento_digital
from .payloads_extracao import (
    SCHEMA_VERSION,
    TEXTO_PAGINA_1,
    payload_averbacao,
    payload_com_closure,
    payload_registro,
)


class AplicarLinhaTest(SimpleTestCase):
    def setUp(self):
        job = OcrJob()
        extracao = ExtracaoSugerida(ocr_job=job)
        pagina = PaginaOcr(
            ocr_job=job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1
        )
        payload = payload_registro(job.job_id)
        for area in (payload['acts'][0]['area'], payload['document']['area']):
            area.update(
                normalized='120.00', raw='120,00 m2', unidade='m2',
                evidencia={'pagina': 1, 'trecho': '120,00 m2'},
            )
        self.linhas = {
            linha.chave: linha
            for linha in desnormalizar(extracao, payload, [pagina])
        }
        self.usuario = get_user_model()(username='revisor')
        self.agora = timezone.now()

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
            '["sugerido","Área conferida",[],null,null,false,false,null]'
            .encode('utf-8')
        ).hexdigest()[:16]

        self.assertEqual(versao_linha(campo), esperado)
        self.assertEqual(versao_linha(campo), esperado)
        self.assertRegex(versao_linha(campo), r'^[0-9a-f]{16}$')


class PendenciasEAvisosTest(TestCase):
    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital()
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1
        )
        self.registro = LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True, requer_cartorio_origem=True,
            requer_observacao=False,
        )
        self.averbacao = LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        self.inicio = LancamentoTipo.objects.create(
            tipo='inicio_matricula', requer_cartorio_origem=False,
            requer_observacao=False,
        )

    def _persistir(self, payload):
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        linhas = desnormalizar(self.extracao, payload, [self.pagina])
        for linha in linhas:
            if linha.tipo_valor in ('parte', 'cartorio'):
                linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        return {linha.chave: linha for linha in linhas}

    def _registro_completo(self):
        payload = payload_registro(self.job.job_id)
        titulo = 'Escritura Pública de Compra e Venda'
        payload['acts'][0]['titulo'] = {
            'raw': titulo, 'normalized': titulo, 'confianca': 0.95,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': titulo},
        }
        payload['acts'][0]['origem'] = {
            'cartorio': payload['document']['cartorio'].copy(),
        }
        return payload

    @staticmethod
    def _obrigatorio(chave):
        return {
            'chave': chave, 'motivo': 'obrigatorio_ausente', 'bloqueante': True,
        }

    def test_obrigatorio_descartado_bloqueia(self):
        linhas = self._persistir(self._registro_completo())
        self.assertEqual(pendencias(self.extracao), [])
        for chave in (
            '/document/tipo', '/document/data', '/document/cartorio',
            '/acts/0/tipo_sugerido', '/acts/0/data', '/acts/0/titulo',
            '/acts/0/origem/cartorio',
        ):
            with self.subTest(chave=chave):
                linha = linhas[chave]
                linha.status_revisao = 'descartado'
                linha.save()
                self.assertEqual(
                    pendencias(self.extracao), [self._obrigatorio(chave)]
                )
                linha.status_revisao = 'sugerido'
                linha.save()

    def test_data_nula_bloqueia(self):
        for chave in ('/document/data', '/acts/0/data'):
            with self.subTest(chave=chave):
                payload = self._registro_completo()
                ramo = payload['document'] if chave.startswith('/document') else (
                    payload['acts'][0]
                )
                ramo['data']['normalized'] = None
                linha = self._persistir(payload)[chave]
                linha.status_revisao = 'aceito'
                linha.save()
                self.assertEqual(
                    pendencias(self.extracao), [self._obrigatorio(chave)]
                )

                aplicar_linha(linha, incluir=True, valor='2020-01-11')
                linha.save()
                self.assertEqual(pendencias(self.extracao), [])

                linha.valor_final = ''
                linha.save()
                self.assertIn(self._obrigatorio(chave), pendencias(self.extracao))

                linha.normalized = '2020-01-11'
                linha.valor_final = 'data inválida'
                linha.save()
                self.assertEqual(pendencias(self.extracao), [{
                    'chave': chave, 'motivo': 'valor_incompativel_destino',
                    'bloqueante': True,
                }])

    def test_registro_exige_titulo_e_cartorio_origem(self):
        self._persistir(payload_registro(self.job.job_id))
        self.assertCountEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/titulo'),
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])
        self._persistir(self._registro_completo())
        self.assertEqual(pendencias(self.extracao), [])

    def test_averbacao_exige_descricao(self):
        for estado in ('ausente', 'vazio', 'descartado'):
            with self.subTest(estado=estado):
                payload = payload_averbacao(self.job.job_id)
                if estado == 'ausente':
                    del payload['acts'][0]['descricao']
                elif estado == 'vazio':
                    payload['acts'][0]['descricao']['normalized'] = ''
                linhas = self._persistir(payload)
                if estado == 'descartado':
                    linha = linhas['/acts/0/descricao']
                    linha.status_revisao = 'descartado'
                    linha.save()
                self.assertEqual(pendencias(self.extracao), [
                    self._obrigatorio('/acts/0/descricao'),
                ])

    def test_inicio_matricula_exige_cartorio_origem(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['tipo_sugerido']['normalized'] = 'inicio_matricula'
        self._persistir(payload)
        for flag in (False, True):
            with self.subTest(requer_cartorio_origem=flag):
                self.inicio.requer_cartorio_origem = flag
                self.inicio.save()
                self.assertEqual(pendencias(self.extracao), [
                    self._obrigatorio('/acts/0/origem/cartorio'),
                ])
        payload['acts'][0]['origem'] = {
            'cartorio': payload['document']['cartorio'].copy(),
        }
        self._persistir(payload)
        self.assertEqual(pendencias(self.extracao), [])

    def test_tipo_editado_recalcula_obrigacoes(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['descricao'] = payload_averbacao(
            self.job.job_id
        )['acts'][0]['descricao']
        linhas = self._persistir(payload)
        self.assertCountEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/titulo'),
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])
        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='averbacao')
        tipo.save()
        self.assertEqual(tipo.normalized, 'registro')
        self.assertEqual(pendencias(self.extracao), [])

        descricao = linhas['/acts/0/descricao']
        aplicar_linha(descricao, incluir=True, valor='')
        descricao.save()
        self.assertEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/descricao'),
        ])

        aplicar_linha(tipo, incluir=True, valor='inicio_matricula')
        tipo.save()
        self.assertEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])

    def test_requer_forma_e_observacao_sao_aviso_nao_bloqueio(self):
        self.averbacao.requer_forma = True
        self.averbacao.requer_observacao = True
        self.averbacao.save()
        payload = payload_averbacao(self.job.job_id)
        self._persistir(payload)
        esperados = [
            {'chave': '/acts/0/forma', 'motivo': 'requer_forma',
             'bloqueante': False},
            {'chave': '/acts/0/observacoes', 'motivo': 'requer_observacao',
             'bloqueante': False},
        ]
        self.assertCountEqual(avisos(self.extracao), esperados)
        self.assertEqual(pendencias(self.extracao), [])

        for flag, caminho in (
            ('requer_detalhes', 'detalhes'),
            ('requer_transmissao', 'partes'),
            ('requer_livro_origem', 'origem/livro'),
            ('requer_folha_origem', 'origem/folha'),
            ('requer_data_origem', 'origem/data'),
        ):
            setattr(self.averbacao, flag, True)
            esperados.append({
                'chave': f'/acts/0/{caminho}', 'motivo': flag,
                'bloqueante': False,
            })
        self.averbacao.save()
        self.assertCountEqual(avisos(self.extracao), esperados)
        self.assertEqual(pendencias(self.extracao), [])

        ato = payload['acts'][0]
        for campo in ('forma', 'detalhes', 'observacoes'):
            ato[campo] = ato['descricao'].copy()
        ato['origem'] = {
            campo: payload['document'][campo].copy()
            for campo in ('livro', 'folha', 'data')
        }
        ato['partes'] = payload_registro(self.job.job_id)['acts'][0]['partes']
        linhas = self._persistir(payload)
        self.assertEqual(avisos(self.extracao), [])
        self.assertEqual(pendencias(self.extracao), [])

        for papel in ('transmitente', 'adquirente'):
            with self.subTest(papel=papel):
                partes = self.extracao.campos.filter(
                    tipo_valor='parte', normalized=papel,
                )
                partes.update(status_revisao='descartado')
                self.assertEqual(avisos(self.extracao), [{
                    'chave': '/acts/0/partes', 'motivo': 'requer_transmissao',
                    'bloqueante': False,
                }])
                self.assertEqual(pendencias(self.extracao), [])
                partes.update(status_revisao='sugerido')

        forma = linhas['/acts/0/forma']
        forma.status_revisao = 'descartado'
        forma.save()
        self.assertEqual(avisos(self.extracao), [esperados[0]])
        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='registro')
        tipo.save()
        self.assertEqual(avisos(self.extracao), [])

    def test_ato_descartado_nao_gera_pendencias_filhas(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['data']['normalized'] = None
        payload['acts'][0]['area']['unidade'] = 'm2'
        payload['acts'].append(payload_averbacao(self.job.job_id)['acts'][0])
        linhas = self._persistir(payload)
        parte = linhas['/acts/0/partes/0']
        parte.criar_novo = False
        parte.requer_revisao = True
        parte.motivos_revisao = ['match_invalidado']
        parte.save()
        nome = linhas['/acts/0/partes/0/nome']
        nome.requer_revisao = True
        nome.save()
        for motivo in ('revisao_pendente', 'escolha_pendente', 'match_invalidado'):
            self.assertIn({
                'chave': parte.chave, 'motivo': motivo, 'bloqueante': True,
            }, pendencias(self.extracao))
        self.assertIn({
            'chave': '/acts/0/area', 'motivo': 'unidade_area', 'bloqueante': True,
        }, pendencias(self.extracao))

        parte.status_revisao = 'descartado'
        parte.save()
        self.assertFalse(any(
            item['chave'].startswith('/acts/0/partes/0')
            for item in pendencias(self.extracao)
        ))
        ato = linhas['/acts/0']
        ato.status_revisao = 'descartado'
        ato.save()
        self.registro.requer_forma = True
        self.registro.save()
        self.assertEqual(pendencias(self.extracao), [])
        self.assertEqual(avisos(self.extracao), [])

    def test_decisao_perdida_vira_pendencia(self):
        for chave, atributo, registro in (
            ('/acts/0/partes/0', 'pessoa_escolhida',
             Pessoas.objects.create(nome='Pessoa sintética escolhida')),
            ('/document/cartorio', 'cartorio_escolhido',
             Cartorios.objects.create(
                 nome='Cartório sintético escolhido', cns='CNS-escolhido',
                 estado='SP',
             )),
        ):
            with self.subTest(chave=chave):
                linha = self._persistir(self._registro_completo())[chave]
                linha.criar_novo = False
                linha.save()
                self.assertEqual(pendencias(self.extracao), [{
                    'chave': chave, 'motivo': 'escolha_pendente',
                    'bloqueante': True,
                }])
                setattr(linha, atributo, registro)
                linha.status_revisao = 'aceito'
                linha.save()
                # Simula remoção concorrente após as linhas serem carregadas.
                extracao = ExtracaoSugerida.objects.prefetch_related('campos').get(
                    pk=self.extracao.pk
                )
                self.assertEqual(pendencias(extracao), [])
                registro.delete()
                self.assertEqual(pendencias(extracao), [{
                    'chave': chave, 'motivo': 'decisao_perdida',
                    'bloqueante': True,
                }])

    def test_nenhum_ato_incluido_bloqueia(self):
        for sem_atos in (False, True):
            with self.subTest(sem_atos=sem_atos):
                payload = payload_registro(self.job.job_id)
                if sem_atos:
                    payload['acts'] = []
                    payload['document'] = {}
                self._persistir(payload)
                self.extracao.campos.filter(tipo_valor='ato').update(
                    status_revisao='descartado'
                )
                self.assertEqual(pendencias(self.extracao), [{
                    'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
                }])
                self.assertEqual(avisos(self.extracao), [])


class DesnormalizarTest(TestCase):
    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital()
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1
        )
        self.paginas = [self.pagina]
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job,
            schema_version=SCHEMA_VERSION,
            payload={},
            payload_servico={},
            provider='local-model',
        )

    def _linhas(self, payload, validar=True):
        if validar:
            # As fixtures nascem válidas no A3 contra as páginas do job.
            validar_payload(payload, self.job.job_id, [1])
        return desnormalizar(self.extracao, payload, self.paginas)

    @staticmethod
    def _por_chave(linhas):
        return {linha.chave: linha for linha in linhas}

    def test_chaves_json_pointer_e_tipo_valor(self):
        registro = payload_registro(self.job.job_id)
        averbacao = payload_averbacao(self.job.job_id)
        validar_payload(registro, self.job.job_id, [1])
        validar_payload(averbacao, self.job.job_id, [1])

        with self.assertNumQueries(0):
            linhas = desnormalizar(self.extracao, registro, self.paginas)
            linhas_averbacao = desnormalizar(
                self.extracao, averbacao, self.paginas
            )

        por_chave = self._por_chave(linhas)
        self.assertEqual(len(por_chave), len(linhas))  # chaves únicas
        for linha in linhas:
            self.assertIsInstance(linha, CampoSugerido)
            self.assertIsNone(linha.pk)  # nada salvo
            self.assertEqual(linha.extracao, self.extracao)

        data = por_chave['/document/data']
        self.assertEqual(data.tipo_valor, 'data')
        self.assertEqual(data.raw, '10 de janeiro de 2020')
        self.assertEqual(data.normalized, '2020-01-10')
        self.assertEqual(data.confianca, 0.95)
        # Payload limpo: sem motivos, sem revisão, evidência íntegra.
        self.assertEqual(data.motivos_revisao, [])
        self.assertFalse(data.requer_revisao)
        self.assertEqual(data.evidencia_pagina, 1)
        self.assertEqual(data.evidencia_trecho, '10 de janeiro de 2020')

        nome = por_chave['/acts/0/partes/1/nome']
        self.assertEqual(nome.tipo_valor, 'texto')
        self.assertEqual(nome.normalized, 'MARIA DA SILVA')

        self.assertEqual(por_chave['/document/tipo'].tipo_valor, 'enum')
        self.assertEqual(por_chave['/document/cartorio'].tipo_valor, 'cartorio')
        self.assertEqual(
            por_chave['/acts/0/valor_transacao'].tipo_valor, 'decimal'
        )
        self.assertEqual(por_chave['/acts/0/area'].tipo_valor, 'area')
        self.assertEqual(
            por_chave['/acts/0/partes/0/documento_identificacao/valor']
            .normalized,
            '12345678900',
        )

        ato = por_chave['/acts/0']
        self.assertEqual(ato.tipo_valor, 'ato')
        self.assertEqual(ato.normalized, 'R-1')

        parte = por_chave['/acts/0/partes/2']
        self.assertEqual(parte.tipo_valor, 'parte')
        self.assertEqual(parte.normalized, 'adquirente')

        # closure=None → nenhuma linha /closure no registro.
        self.assertFalse(
            [chave for chave in por_chave if chave.startswith('/closure')]
        )

        # Averbação: descrição presente, sem origem e sem partes.
        por_chave_av = self._por_chave(linhas_averbacao)
        self.assertEqual(por_chave_av['/acts/0'].normalized, 'Av-1')
        self.assertEqual(por_chave_av['/acts/0/descricao'].tipo_valor, 'texto')
        self.assertFalse(
            [chave for chave in por_chave_av if '/origem' in chave]
        )
        self.assertFalse(
            [chave for chave in por_chave_av if '/partes' in chave]
        )

    def test_placeholders_dos_obrigatorios(self):
        completo = self._por_chave(self._linhas(payload_registro(self.job.job_id)))
        obrigatorios = (
            ('/document/tipo', 'enum'),
            ('/document/data', 'data'),
            ('/document/cartorio', 'cartorio'),
            ('/acts/0/tipo_sugerido', 'enum'),
            ('/acts/0/data', 'data'),
        )
        for chave, _tipo in obrigatorios:
            # Presentes no payload: folhas reais (com confiança), não placeholder.
            self.assertIsNotNone(completo[chave].confianca, chave)

        payload = payload_registro(self.job.job_id)
        del payload['document']['tipo']
        del payload['document']['data']
        del payload['document']['cartorio']
        del payload['acts'][0]['tipo_sugerido']
        del payload['acts'][0]['data']

        linhas = self._linhas(payload, validar=False)
        por_chave = self._por_chave(linhas)
        self.assertEqual(len(por_chave), len(linhas))  # sem chave duplicada

        for chave, tipo in obrigatorios:
            with self.subTest(chave=chave):
                linha = por_chave[chave]
                self.assertIsNone(linha.raw)
                self.assertIsNone(linha.normalized)
                self.assertIsNone(linha.confianca)
                self.assertTrue(linha.requer_revisao)
                self.assertEqual(linha.tipo_valor, tipo)
                self.assertIsNone(linha.evidencia_pagina)

    def test_baixa_confianca_forca_revisao(self):
        payload = payload_registro(self.job.job_id)
        numero = payload['document']['numero']
        numero['confianca'] = 0.42
        numero['requer_revisao'] = False  # payload diz que não precisa
        payload['document']['livro']['confianca'] = 0.70  # fronteira: não é baixa
        payload['acts'][0]['partes'][0]['confianca'] = 0.5  # linha de parte

        por_chave = self._por_chave(self._linhas(payload))

        baixa = por_chave['/document/numero']
        self.assertEqual(baixa.confianca, 0.42)
        self.assertIn('baixa_confianca', baixa.motivos_revisao)
        self.assertTrue(baixa.requer_revisao)  # forçada apesar do False

        fronteira = por_chave['/document/livro']
        self.assertNotIn('baixa_confianca', fronteira.motivos_revisao)
        self.assertFalse(fronteira.requer_revisao)

        parte = por_chave['/acts/0/partes/0']
        self.assertIn('baixa_confianca', parte.motivos_revisao)
        self.assertTrue(parte.requer_revisao)

    def test_closure_sempre_requer_revisao(self):
        payload = payload_com_closure(self.job.job_id)
        for campo in payload['closure'].values():
            campo['requer_revisao'] = False  # mesmo negando, closure revisa
            campo['confianca'] = 0.99

        linhas = self._linhas(payload)
        closure = [l for l in linhas if l.chave.startswith('/closure')]
        self.assertEqual(
            {l.chave for l in closure},
            {
                '/closure/indicio_fim_cadeia',
                '/closure/origem_publica_sugerida',
                '/closure/classificacao_sugerida',
            },
        )
        for linha in closure:
            with self.subTest(chave=linha.chave):
                self.assertIn('closure', linha.motivos_revisao)
                self.assertTrue(linha.requer_revisao)

        indicio = self._por_chave(linhas)['/closure/indicio_fim_cadeia']
        self.assertEqual(indicio.normalized, 'true')  # booleano canônico

    def test_evidencia_pagina_inexistente_e_trecho_ausente(self):
        payload = payload_registro(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 99,  # fora das páginas do job
            'trecho': 'Nº 42.718',
        }
        payload['document']['livro']['evidencia'] = {
            'pagina': 1,
            'trecho': 'trecho que não está no OCR',
        }
        payload['document']['folha']['evidencia'] = None  # A3 admite nula

        por_chave = self._por_chave(self._linhas(payload))

        inexistente = por_chave['/document/numero']
        self.assertIsNone(inexistente.evidencia_pagina)
        self.assertEqual(inexistente.evidencia_trecho, '')
        self.assertIn('evidencia_invalida', inexistente.motivos_revisao)
        self.assertTrue(inexistente.requer_revisao)

        ausente = por_chave['/document/livro']
        self.assertEqual(ausente.evidencia_pagina, 1)
        self.assertEqual(ausente.evidencia_trecho, '')
        self.assertIn('trecho_ausente', ausente.motivos_revisao)
        self.assertTrue(ausente.requer_revisao)

        nula = por_chave['/document/folha']
        self.assertIsNone(nula.evidencia_pagina)
        self.assertEqual(nula.evidencia_trecho, '')
        self.assertNotIn('evidencia_invalida', nula.motivos_revisao)
        self.assertNotIn('trecho_ausente', nula.motivos_revisao)

    def test_normalized_null_permanece_null(self):
        payload = payload_registro(self.job.job_id)
        payload['document']['data']['normalized'] = None

        data = self._por_chave(self._linhas(payload))['/document/data']

        # null ≠ vazio: o campo fica None, não '', e a pendência é explícita.
        self.assertIsNone(data.normalized)
        self.assertTrue(data.requer_revisao)
        self.assertIn('normalizacao_invalida', data.motivos_revisao)
        self.assertEqual(data.raw, '10 de janeiro de 2020')  # raw preservado

    def test_unidade_area(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['area']['unidade'] = 'm2'

        area = self._por_chave(self._linhas(payload))['/acts/0/area']

        self.assertIn('unidade_area', area.motivos_revisao)
        self.assertTrue(area.requer_revisao)
        # O valor canônico permanece: converter unidade é decisão humana.
        self.assertEqual(area.normalized, '12.50')

    def test_normalizacao_invalida_em_decimal(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['valor_transacao']['normalized'] = 'abc'

        valor = self._por_chave(self._linhas(payload))['/acts/0/valor_transacao']

        self.assertIsNone(valor.normalized)
        self.assertTrue(valor.requer_revisao)
        self.assertIn('normalizacao_invalida', valor.motivos_revisao)
        self.assertEqual(valor.raw, 'R$ 150.000,00')  # raw preservado

    def test_evidencia_usa_texto_corrigido(self):
        """Trecho é conferido contra o texto vigente: o corrigido (#290).

        O OCR puro é só fallback (página sem ``texto_corrigido`` — coberto
        pelos demais testes): com correção aplicada, trecho que só existe
        no OCR original é ``trecho_ausente``.
        """
        self.pagina.texto_corrigido = (
            'Texto revisado pelo serviço. MATRÍCULA Nº 42.718.'
        )
        self.pagina.save(update_fields=['texto_corrigido'])

        payload = payload_registro(self.job.job_id)
        # Só existe no texto corrigido → evidência íntegra.
        payload['document']['tipo']['evidencia'] = {
            'pagina': 1, 'trecho': 'Texto revisado pelo serviço.',
        }
        # Só existe no OCR puro → não vale mais contra o texto corrigido.
        payload['document']['data']['evidencia'] = {
            'pagina': 1, 'trecho': '10 de janeiro de 2020',
        }

        por_chave = self._por_chave(self._linhas(payload))

        do_corrigido = por_chave['/document/tipo']
        self.assertEqual(
            do_corrigido.evidencia_trecho, 'Texto revisado pelo serviço.'
        )
        self.assertNotIn('trecho_ausente', do_corrigido.motivos_revisao)

        so_do_ocr = por_chave['/document/data']
        self.assertEqual(so_do_ocr.evidencia_trecho, '')
        self.assertIn('trecho_ausente', so_do_ocr.motivos_revisao)
        self.assertTrue(so_do_ocr.requer_revisao)

    def test_bbox_guardado(self):
        # bbox ainda não está no schema A3 vendorizado (o evidence tem
        # additionalProperties: false) e desnormalizar não valida: os
        # payloads aqui pulam o validar_payload.
        payload = payload_registro(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 1, 'trecho': 'Nº 42.718', 'bbox': [10, 20, 300, 40],
        }
        payload['acts'][0]['evidencia'] = {
            'pagina': 1, 'trecho': 'R-1/42.718', 'bbox': [1.5, 2, 3, 4.5],
        }
        payload['acts'][0]['partes'][0]['evidencia'] = {
            'pagina': 1, 'trecho': 'JOÃO DA SILVA', 'bbox': [0, 0, 100, 20],
        }

        por_chave = self._por_chave(self._linhas(payload, validar=False))

        campo = por_chave['/document/numero']
        self.assertEqual(campo.evidencia_bbox, [10, 20, 300, 40])
        self.assertEqual(campo.evidencia_trecho, 'Nº 42.718')
        # bbox íntegro não é pendência: linha segue limpa.
        self.assertEqual(campo.motivos_revisao, [])
        self.assertFalse(campo.requer_revisao)

        # Linhas estruturais (ato e parte) também carregam o bbox.
        self.assertEqual(por_chave['/acts/0'].evidencia_bbox, [1.5, 2, 3, 4.5])
        self.assertEqual(
            por_chave['/acts/0/partes/0'].evidencia_bbox, [0, 0, 100, 20]
        )

        # Evidência sem bbox (e placeholder) → None, sem pendência.
        self.assertIsNone(por_chave['/document/data'].evidencia_bbox)
        self.assertNotIn(
            'trecho_ausente', por_chave['/document/data'].motivos_revisao
        )

    def test_bbox_invalido_vira_none(self):
        invalidos = (
            [10, 20, 30],            # 3 números
            [10, 20, 30, 40, 50],    # 5 números
            [10, 20, '30', 40],      # string no meio
            [True, 20, 30, 40],      # bool não é número
            '10,20,30,40',           # não é lista
            {'x0': 10},              # não é lista
            None,                    # null explícito
        )
        for bbox in invalidos:
            with self.subTest(bbox=bbox):
                payload = payload_registro(self.job.job_id)
                payload['document']['numero']['evidencia'] = {
                    'pagina': 1, 'trecho': 'Nº 42.718', 'bbox': bbox,
                }

                numero = self._por_chave(
                    self._linhas(payload, validar=False)
                )['/document/numero']

                self.assertIsNone(numero.evidencia_bbox)
                # bbox malformado NÃO é pendência: página e trecho seguem
                # íntegros e a linha não vai para revisão por causa dele.
                self.assertEqual(numero.evidencia_pagina, 1)
                self.assertEqual(numero.evidencia_trecho, 'Nº 42.718')
                self.assertEqual(numero.motivos_revisao, [])
                self.assertFalse(numero.requer_revisao)
