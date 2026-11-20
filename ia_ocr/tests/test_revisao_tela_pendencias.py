"""Descrição de pendências/avisos e tela sem atos (#262, #317) — migração
VERBATIM de ``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de
400 linhas): mesmas classes, mesmos nomes de teste; só mudam os imports.
"""

import re

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings

from ia_ocr import estados, revisao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)


class DescreverAvisoTest(SimpleTestCase):
    def test_motivo_da_origem_ganha_rotulo_proprio(self):
        for nome, rotulo in (
            ('livro', 'Livro da origem não consta no documento'),
            ('folha', 'Folha da origem não consta no documento'),
        ):
            with self.subTest(nome=nome):
                item = {
                    'chave': f'/acts/0/origem/{nome}',
                    'motivo': f'{nome}_origem_nao_consta', 'bloqueante': False,
                }
                descrito = revisao.descrever_aviso(item)
                self.assertEqual(descrito['rotulo'], rotulo)
                self.assertEqual(descrito['local'], f'Ato 1 — {nome}')
                for campo, valor in item.items():
                    self.assertEqual(descrito[campo], valor)

    def test_motivo_do_tipo_mantem_o_texto_de_sempre(self):
        descrito = revisao.descrever_aviso({
            'chave': '/acts/0/forma', 'motivo': 'requer_forma',
            'bloqueante': False,
        })
        self.assertEqual(descrito['rotulo'], 'Campo recomendado não preenchido')
        self.assertEqual(descrito['motivo'], 'requer_forma')




class RevisaoSemAtosTelaTest(TelaTextoBase):
    """Issue #262: a saída sem atos só abre com a flag ligada.

    #341 fase 3: a oferta morou na tela de cards e agora é a página de
    confirmação da revisão (``revisao_sem_atos.html``); a entrada ``campos/``
    só encaminha. O comportamento novo por formulário tem cobertura integral
    em ``test_revisao_formulario_sem_atos.py``.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao_sem_atos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )
        # Sem atos, o cabeçalho ainda precisa das escolhas de cartório.
        extracao.campos.filter(tipo_valor='cartorio').update(criar_novo=True)
        return extracao

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_flag_ligada_mostra_aviso_e_mantem_pendencia(self):
        self._extracao_sem_atos()

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_sem_atos.html')
        self.assertIn('Concluir sem atos', html)

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=False)
    def test_flag_desligada_renderiza_como_hoje(self):
        self._extracao_sem_atos()

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('Concluir sem atos', html)
        self.assertIn(
            ('info', 'A extração não trouxe nenhum ato para revisar.'),
            self.mensagens(resposta),
        )

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_campo_obrigatorio_pendente_nao_mostra_confirmacao(self):
        # Issue #262: sem atos e com campo do documento pendente, a revisão
        # não pode oferecer a confirmação que destravaria a finalização.
        payload = payload_averbacao(self.job.job_id)
        payload['acts'] = []
        payload['document'].pop('data')
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        CampoSugerido.objects.bulk_create(
            revisao.desnormalizar(extracao, payload, list(self.job.paginas.all())),
        )

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('Concluir sem atos', html)
        self.assertIn(
            ('info', 'A extração não trouxe nenhum ato para revisar.'),
            self.mensagens(resposta),
        )

    @override_settings(OCR_PERMITIR_FINALIZAR_SEM_ATOS=True)
    def test_comentario_do_template_nao_vaza_no_html(self):
        # Issue #262: o bloco de aviso usa {% comment %}; o texto não pode
        # aparecer como conteúdo da página.
        self._extracao_sem_atos()

        resposta = self.client.get(self.url('campos_job_ocr'), follow=True)
        html = resposta.content.decode()

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('Concluir sem atos', html)
        self.assertNotIn('sem fabricar atos nem esconder a ausência', html)




class DescreverPendenciaMotivosDoMotorTest(SimpleTestCase):
    def test_motivos_do_motor_tem_rotulo_e_acao(self):
        for motivo in (
            'revisao_pendente', 'decisao_perdida', 'match_invalidado',
            'valor_incompativel_destino', 'valor_acima_do_limite_destino',
        ):
            with self.subTest(motivo=motivo):
                d = revisao.descrever_pendencia(
                    {'chave': '/document/x', 'motivo': motivo},
                )
                self.assertNotEqual(d['rotulo'], motivo)
                self.assertTrue(d['acao'])

    def test_motivo_desconhecido_nao_vaza_codigo_cru(self):
        d = revisao.descrever_pendencia(
            {'chave': '/document/x', 'motivo': 'foo_bar'},
        )
        self.assertEqual(d['rotulo'], 'Pendência a revisar')
        self.assertEqual(d['acao'], 'revise o campo')
        self.assertEqual(d['motivo'], 'foo_bar')


class DescreverPendenciaLocalTest(SimpleTestCase):
    """``local`` identifica o campo citado pela pendência (Greptile P2, #317)."""

    def test_regras_mapeadas(self):
        casos = (
            ('/document/tipo', 'Documento — tipo'),
            ('/document/data', 'Documento — data'),
            ('/document/cartorio', 'Documento — cartório'),
            ('/acts/0/data', 'Ato 1 — data'),
            ('/acts/1/tipo_sugerido', 'Ato 2 — tipo'),
            ('/acts/0/cartorio_transmissao', 'Ato 1 — cartório de transmissão'),
            ('/acts/0/valor_transacao', 'Ato 1 — valor'),
            ('/acts/0/origem/cartorio', 'Ato 1 — cartório de origem'),
            ('/acts/1/partes/2', 'Ato 2 — parte 3'),
        )
        for chave, local in casos:
            with self.subTest(chave=chave):
                d = revisao.descrever_pendencia(
                    {'chave': chave, 'motivo': 'revisao_pendente'},
                )
                self.assertEqual(d['local'], local)

    def test_fallback_usa_ultimo_segmento_com_espacos(self):
        casos = (
            ('/acts/0/origem/livro', 'Ato 1 — livro'),
            ('/document/cri_atual', 'Documento — cri atual'),
        )
        for chave, local in casos:
            with self.subTest(chave=chave):
                d = revisao.descrever_pendencia(
                    {'chave': chave, 'motivo': 'revisao_pendente'},
                )
                self.assertEqual(d['local'], local)

    def test_campo_de_parte_mantem_o_prefixo_da_parte(self):
        d = revisao.descrever_pendencia(
            {'chave': '/acts/1/partes/2/nome', 'motivo': 'revisao_pendente'},
        )
        self.assertEqual(d['local'], 'Ato 2 — parte 3 — nome')

    def test_nenhum_ato_aponta_para_os_atos_do_documento(self):
        d = revisao.descrever_pendencia(
            {'chave': '/acts', 'motivo': 'nenhum_ato'},
        )
        self.assertEqual(d['local'], 'Documento — atos')

    def test_chave_motivo_rotulo_e_acao_permanecem(self):
        d = revisao.descrever_pendencia(
            {'chave': '/acts/0/data', 'motivo': 'obrigatorio_ausente'},
        )
        self.assertEqual(d, {
            'chave': '/acts/0/data',
            'motivo': 'obrigatorio_ausente',
            'local': 'Ato 1 — data',
            'rotulo': 'Campo obrigatório não preenchido',
            'acao': 'informe a data',
            'alvo': 'campo-acts0data',
        })

    def test_chave_nao_string_nao_levanta_excecao(self):
        # MUST-FIX Opus (#317): payload cru/legado pode trazer chave None ou
        # não-string; a descrição da pendência não pode derrubar a tela.
        for chave in (None, '', 42):
            with self.subTest(chave=chave):
                self.assertEqual(revisao._local_da_chave(chave), '')
        d = revisao.descrever_pendencia(
            {'chave': None, 'motivo': 'revisao_pendente'},
        )
        self.assertEqual(d['local'], '')
        self.assertEqual(d['rotulo'], 'Confira este valor')
        self.assertEqual(d['acao'], 'confirme ou corrija')

    def test_resto_vazio_nao_deixa_travessao_pendurado(self):
        # ``/acts/0/`` não pode virar "Ato 1 — " nem '' virar "Documento — ".
        casos = (
            ('/acts/0/', 'Ato 1'),
            ('/acts/1/', 'Ato 2'),
            ('/document/', 'Documento'),
            ('/acts/1/partes/2/', 'Ato 2 — parte 3'),
        )
        for chave, local in casos:
            with self.subTest(chave=chave):
                self.assertEqual(revisao._local_da_chave(chave), local)




class PendenciaSemLocalNoTemplateTest(SimpleTestCase):
    """Item de pendência sem ``local`` (dict cru) não imprime ': ' órfão."""

    def _html(self, pendencias):
        # ``user`` só porque o ``default:`` do base.html resolve seu argumento
        # sem o tratamento silencioso de variável ausente.
        return render_to_string('ia_ocr/revisao_campos.html', {
            'user': AnonymousUser(),
            'pendencias': pendencias,
        })

    def test_item_sem_local_nao_comeca_com_dois_pontos(self):
        html = self._html([{
                'chave': '/acts/0/data',
                'motivo': 'obrigatorio_ausente',
                'rotulo': 'Campo obrigatório não preenchido',
                'acao': 'informe a data',
                # sem ``local``: outro produtor de dict / payload legado
            }],
        )
        linha = re.search(
            r'<li class="pendencia"[^>]*>\s*(.*?)\s*<details>', html, re.S,
        ).group(1)
        self.assertIn(
            'Campo obrigatório não preenchido — informe a data', linha,
        )
        self.assertFalse(
            linha.startswith(': '), f'linha começa com ": ": {linha!r}',
        )

    def test_item_com_local_mantem_o_prefixo(self):
        html = self._html([{
            'chave': '/acts/0/data',
            'motivo': 'obrigatorio_ausente',
            'local': 'Ato 1 — data',
            'rotulo': 'Campo obrigatório não preenchido',
            'acao': 'informe a data',
        }])
        self.assertIn(
            'Ato 1 — data: Campo obrigatório não preenchido — informe a data',
            html,
        )
