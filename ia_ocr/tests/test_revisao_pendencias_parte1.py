"""Pendências e avisos da revisão — parte 1 de 3 do corpo de
``PendenciasEAvisosTest`` (``ia_ocr/tests/test_revisao.py``,
Etapa 5, grupo 3 do plano de 400 linhas). Classe SIMPLES (sem
``TestCase``): o discovery do Django não a coleta; quem coleta é a
fachada em ``test_revisao_pendencias.py``. Corpos verbatim.
"""

from collections import Counter
from dominial.models import LancamentoTipo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from ia_ocr.revisao import (
    CAMPOS_DA_ORIGEM, aplicar_linha, avisos, campo_obrigatorio, desnormalizar,
    garantir_placeholders_obrigatorios, pendencias,
)
from .factories import criar_documento_digital
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_registro,
)


class PendenciasEAvisosTestParte1:
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

    def _sem_rotulo(self):
        """Rótulo inerte: o ``tipo_sugerido`` volta a decidir (#322 r7).

        Com o rótulo R/Av resolvendo o tipo, o ``tipo_sugerido`` deixa de
        decidi-lo — estes testes exercitam obrigações de tipos que só o
        ``tipo_sugerido`` expressa (início de matrícula) ou edições nele.
        """
        CampoSugerido.objects.filter(
            chave__in=('/acts/0', '/acts/0/rotulo'),
        ).update(normalized=None, raw=None, valor_final=None)

    @staticmethod
    def _criar_novo_sem_nome(chave):
        return {
            'chave': chave, 'motivo': 'criar_novo_sem_nome', 'bloqueante': True,
        }

    def test_transmissao_opcional_nao_altera_pendencias_nem_avisos(self):
        self.registro.requer_forma = True
        self.registro.save(update_fields=['requer_forma'])
        linhas = self._persistir(self._registro_completo())
        chaves = [
            f'/acts/0/{nome}' for nome in (
                'livro_transacao', 'folha_transacao', 'data_transacao',
            )
        ]
        for chave in chaves:
            with self.subTest(chave=chave):
                self.assertIn(chave, linhas)
                self.assertFalse(campo_obrigatorio(chave))
        self.assertEqual(pendencias(self.extracao), [])
        avisos_com_transmissao = avisos(self.extracao)
        self.assertIn({
            'chave': '/acts/0/forma', 'motivo': 'requer_forma',
            'bloqueante': False,
        }, avisos_com_transmissao)

        self.extracao.campos.filter(chave__in=chaves).delete()

        self.assertEqual(pendencias(self.extracao), [])
        self.assertEqual(avisos(self.extracao), avisos_com_transmissao)

    def test_origem_vazia_nao_altera_pendencias_nem_avisos(self):
        # #324: o ato tem origem (só o cartório); os demais campos viram
        # linhas vazias editáveis e NÃO criam pendência nem aviso.
        linhas = self._persistir(self._registro_completo())
        chaves = [
            f'/acts/0/origem/{nome}' for nome in (
                'tipo_documento', 'numero', 'livro', 'folha', 'data',
            )
        ]
        for chave in chaves:
            with self.subTest(chave=chave):
                self.assertIn(chave, linhas)
                self.assertFalse(campo_obrigatorio(chave))
        self.assertEqual(pendencias(self.extracao), [])
        avisos_com_origem = avisos(self.extracao)

        self.extracao.campos.filter(chave__in=chaves).delete()

        self.assertEqual(pendencias(self.extracao), [])
        self.assertEqual(avisos(self.extracao), avisos_com_origem)

    def test_tipo_documento_da_origem_nunca_lido_nao_bloqueia(self):
        linhas = self._persistir(self._registro_completo())
        chave = '/acts/0/origem/tipo_documento'
        tipo = linhas[chave]
        self.assertIsNone(tipo.normalized)

        # Revisor passou pelo card sem escolher tipo: a importação infere o
        # tipo pelo prefixo M/T, então o vazio não é valor incompatível.
        aplicar_linha(tipo, incluir=True, valor='', conferido=True)
        tipo.save()

        self.assertEqual(tipo.valor_final, '')
        self.assertEqual(pendencias(self.extracao), [])

    def test_tipo_documento_da_origem_lido_e_limpo_continua_bloqueando(self):
        payload = self._registro_completo()
        payload['acts'][0]['origem']['tipo_documento'] = {
            'raw': 'Matrícula', 'normalized': 'matricula', 'confianca': 0.95,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': 'MATRÍCULA Nº 42.718'},
        }
        chave = '/acts/0/origem/tipo_documento'
        tipo = self._persistir(payload)[chave]
        self.assertEqual(pendencias(self.extracao), [])

        aplicar_linha(tipo, incluir=True, valor='')
        tipo.save()

        self.assertIn({
            'chave': chave, 'motivo': 'valor_incompativel_destino',
            'bloqueante': True,
        }, pendencias(self.extracao))

    def test_tipo_documento_da_origem_lido_sem_normalizar_nao_e_isento(self):
        # #324 rodada 2: a isenção é para o tipo que a leitura NUNCA trouxe
        # (``raw`` E ``normalized`` ausentes). Um tipo que a IA LEU
        # ('Matrícula') mas não soube normalizar não é isento: esvaziá-lo cai
        # na regra normal, em vez de virar um placeholder vazio silencioso.
        payload = self._registro_completo()
        payload['acts'][0]['origem']['tipo_documento'] = {
            'raw': 'Matrícula', 'normalized': None, 'confianca': 0.95,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': 'MATRÍCULA Nº 42.718'},
        }
        chave = '/acts/0/origem/tipo_documento'
        tipo = self._persistir(payload)[chave]
        self.assertEqual(tipo.raw, 'Matrícula')
        self.assertIsNone(tipo.normalized)

        aplicar_linha(tipo, incluir=True, valor='', conferido=True)
        tipo.save()

        self.assertIn({
            'chave': chave, 'motivo': 'valor_incompativel_destino',
            'bloqueante': True,
        }, pendencias(self.extracao))

    def test_garantir_placeholders_nao_duplica_a_origem_que_ja_veio(self):
        # #324 rodada 2 (P1): o número da origem veio no payload (as outras
        # quatro linhas nasceram vazias no desmonte) e o revisor descartou o
        # livro. Trocar para um tipo que exige o cartório de origem cria só
        # o que falta: nunca repete uma chave — nem a descartada, que segue
        # ocupando a chave única.
        payload = self._com_origem_numerada(payload_averbacao(self.job.job_id))
        linhas = self._persistir(payload)
        chaves = [f'/acts/0/origem/{nome}' for nome in CAMPOS_DA_ORIGEM]
        for chave in chaves:
            self.assertIn(chave, linhas)
        self.assertNotIn('/acts/0/origem/cartorio', linhas)
        livro = linhas['/acts/0/origem/livro']
        aplicar_linha(livro, incluir=False)
        livro.save()
        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='registro')
        tipo.save()

        novas = garantir_placeholders_obrigatorios(self.extracao)

        self.assertCountEqual(
            [campo.chave for campo in novas],
            ['/acts/0/titulo', '/acts/0/origem/cartorio'],
        )
        self.assertEqual(
            Counter(self.extracao.campos.filter(
                chave__startswith='/acts/0/origem/',
            ).values_list('chave', flat=True)),
            Counter([*chaves, '/acts/0/origem/cartorio']),
        )
        self.assertEqual(
            self.extracao.campos.get(chave='/acts/0/origem/numero').normalized,
            'M42.718',
        )
        self.assertEqual(
            self.extracao.campos.get(chave='/acts/0/origem/livro')
            .status_revisao,
            'descartado',
        )
        # Idempotente: a segunda chamada não encontra mais nada a criar.
        self.assertEqual(garantir_placeholders_obrigatorios(self.extracao), [])

    # --- #324: livro/folha da origem que o documento não traz ---------------
