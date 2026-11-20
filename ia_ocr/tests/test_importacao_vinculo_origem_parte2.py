"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.

Parte 2 de 3 da classe ``VinculoDocumentoOrigemTest`` — 816 linhas
não cabem em um arquivo de 400. Classe SIMPLES (sem ``TestCase``):
o discovery do Django não a coleta; quem coleta é a fachada em
``test_importacao_vinculo_origem.py``. Corpos verbatim.
"""

import json
from copy import deepcopy
from datetime import date
from unittest.mock import patch
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse
from django.test import (
    RequestFactory, TestCase, TransactionTestCase, skipUnlessDBFeature,
)
from dominial.managers import documentos_for_user
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.views.documento_views import excluir_documento
from ia_ocr import importacao as modulo_importacao
from ia_ocr import services
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr


class VinculoDocumentoOrigemParte2:
    """Continuação verbatim da parte 1 (ver lá)."""



    def test_view_de_exclusao_mostra_a_mensagem_em_vez_de_500(self):
        lancamento, documento_origem = (
            self._importar_inicio_e_pegar_o_documento_de_origem()
        )
        request = RequestFactory().post('/exclusao-protegida/')
        request.user = self.usuario
        request.session = {}
        request._messages = FallbackStorage(request)

        # ``excluir_documento`` não tem rota em urls.py: chamada direta da
        # view (mesmo padrão de dominial/tests/test_issue_258_protected_error).
        with patch(
            'dominial.views.documento_views.render',
            return_value=HttpResponse('confirmação sintética'),
        ), self.assertLogs(
            'dominial.views.documento_views', level='WARNING',
        ) as logs:
            resposta = excluir_documento(
                request,
                tis_id=self.imovel.terra_indigena_id_id,
                imovel_id=self.imovel.pk,
                documento_id=documento_origem.pk,
            )

        # Volta à tela de confirmação com a mensagem — nenhuma exceção sobe.
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            [str(mensagem) for mensagem in get_messages(request)],
            [
                'Documento possui vínculos que impedem a exclusão '
                '(lançamentos). Remova esses vínculos antes de excluir.'
            ],
        )
        self.assertIn(f'documento id={documento_origem.pk}', logs.output[0])
        self.assertTrue(
            Documento.objects.filter(pk=documento_origem.pk).exists()
        )
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.documento_origem, documento_origem)


    def test_ato_com_erro_desfaz_documento_e_vinculo(self):
        payload = self._payload_inicio()
        segundo = deepcopy(payload['acts'][0])
        segundo['ordem'] = 2
        segundo['rotulo'] = self._campo('R-2', 'R-1/42.718')
        segundo['tipo_sugerido'] = self._campo('registro', 'R-1/42.718')
        # Número da origem sem cartório: o ato 2 recusa e leva o bloco junto.
        del segundo['origem']['cartorio']
        payload['acts'].append(segundo)
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        status = {linha['chave']: linha['status'] for linha in contexto.exception.linhas}
        self.assertEqual(status['/acts/1'], 'erro')
        self.assertEqual(status['/acts/0'], 'nao_gravado')
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertFalse(self._outros_documentos().exists())
        self.assertFalse(LancamentoOrigem.objects.exists())

    # --- #267 (parte IA): homônimo de outro tipo no cartório da origem -------


    def _matricula_homonima_em(self, imovel):
        tipo, _ = DocumentoTipo.objects.get_or_create(tipo='matricula')
        return Documento.objects.create(
            imovel=imovel, tipo=tipo, numero='M366', data=date(1990, 1, 1),
            cartorio=self.cartorio_origem, livro='1', folha='1',
        )


    @staticmethod
    def _avisos_do_ato(resultado):
        (linha,) = resultado['linhas']
        return linha['avisos']


    def test_homonimo_de_outro_tipo_avisa_e_nunca_vincula(self):
        irmao = self._imovel_em(self.imovel.terra_indigena_id, 'Irmão')
        matricula = self._matricula_homonima_em(irmao)
        # A origem declara TRANSCRIÇÃO T366; no cartório só existe M366.
        extracao = self._extracao(self._payload_origem())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertIsNone(Lancamento.objects.get().documento_origem)
        self.assertEqual(list(self._outros_documentos()), [matricula])
        avisos = self._avisos_do_ato(resultado)
        (aviso,) = [texto for texto in avisos if 'outro tipo' in texto]
        self.assertIn('matrícula', aviso)
        self.assertIn('transcrição', aviso)
        # O aviso fala do tipo, nunca do número nem de ids.
        self.assertNotIn('366', aviso)


    def test_inicio_de_matricula_cria_como_declarado_e_avisa_o_homonimo(self):
        irmao = self._imovel_em(self.imovel.terra_indigena_id, 'Irmão')
        matricula = self._matricula_homonima_em(irmao)
        extracao = self._extracao(self._payload_inicio())

        resultado = self._importar(extracao)

        criado = Documento.objects.get(numero=self.NUMERO)
        self.assertEqual(criado.tipo, self.tipo_transcricao)
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.documento_origem, criado)
        self.assertNotEqual(lancamento.documento_origem, matricula)
        self.assertEqual(
            len([a for a in self._avisos_do_ato(resultado) if 'outro tipo' in a]),
            1,
        )


    def test_sem_homonimo_nao_ha_aviso_de_outro_tipo(self):
        resultado = self._importar(self._extracao(self._payload_origem()))

        self.assertFalse([
            a for a in self._avisos_do_ato(resultado) if 'outro tipo' in a
        ])


    def test_homonimo_em_ti_de_outro_usuario_nao_avisa_nem_vaza(self):
        ti_alheia = TIs.objects.create(
            nome='TI Alheia H267', codigo='TI-H267', etnia='Teste',
        )
        alheio = self._imovel_em(ti_alheia, 'ImovelAlheioH267')
        self._matricula_homonima_em(alheio)
        extracao = self._extracao(self._payload_origem())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertFalse([
            a for a in self._avisos_do_ato(resultado) if 'outro tipo' in a
        ])
        visivel = repr(resultado) + repr(list(ImportacaoIA.objects.values()))
        for segredo in ('M366', 'ImovelAlheioH267', 'TI Alheia H267'):
            with self.subTest(segredo=segredo):
                self.assertNotIn(segredo, visivel)

    # --- #267 no replay: o aviso de homônimo é GRAVADO, não recalculado -----
    # (#324 rodada 4, P2 do Codex). Depois da importação o documento declarado
    # (T366) existe, e ``homonimo_outro_tipo`` devolve ``None``: a única fonte
    # do aviso do replay é o registro que a primeira resposta gravou.


    def _payload_inicio_sem_rotulo(self):
        """Início de matrícula sem rótulo: o rótulo 'M-1' do ``_payload_inicio``
        gera um aviso próprio que o replay nunca devolveu (os avisos de rótulo
        não são gravados) e sujaria a comparação dos avisos da ORIGEM."""
        payload = self._payload_inicio()
        del payload['acts'][0]['rotulo']
        return payload


    def _importar_inicio_com_homonimo(self, sem_livro_e_folha=False):
        irmao = self._imovel_em(self.imovel.terra_indigena_id, 'Irmão')
        self._matricula_homonima_em(irmao)
        payload = self._payload_inicio_sem_rotulo()
        if sem_livro_e_folha:
            for nome in ('livro', 'folha'):
                del payload['acts'][0]['origem'][nome]
        extracao = self._extracao(payload)
        return extracao, self._importar(extracao)


    def _repetir_a_importacao(self, extracao):
        return importar(
            extracao, self.usuario, services.versao_bloco(extracao),
            ['/acts/0'],
        )


    @staticmethod
    def _so_os_de_homonimo(avisos):
        return [aviso for aviso in avisos if 'outro tipo' in aviso]


    def test_replay_devolve_o_mesmo_aviso_de_homonimo_uma_vez(self):
        # Sem livro/folha: a primeira resposta traz os TRÊS avisos, e o replay
        # tem de devolver a mesma lista, na mesma ordem.
        extracao, primeira = self._importar_inicio_com_homonimo(
            sem_livro_e_folha=True,
        )
        avisos_da_primeira = self._avisos_do_ato(primeira)
        self.assertEqual(
            len(self._so_os_de_homonimo(avisos_da_primeira)), 1,
        )
        self.assertEqual(len(avisos_da_primeira), 3)
        # A premissa que obriga a gravar: o documento declarado já existe,
        # então o aviso não sai mais da checagem.
        self.assertIsNone(LancamentoOrigemService.homonimo_outro_tipo(
            'transcricao', self.NUMERO, self.cartorio_origem,
            documentos_queryset=documentos_for_user(self.usuario),
        ))

        for repeticao in (1, 2):
            with self.subTest(repeticao=repeticao):
                repetida = self._repetir_a_importacao(extracao)

                self.assertEqual(
                    self._avisos_do_ato(repetida), avisos_da_primeira,
                )
                self.assertEqual(
                    len(self._so_os_de_homonimo(self._avisos_do_ato(repetida))),
                    1,
                )
        self.assertEqual(Lancamento.objects.count(), 1)


    def test_replays_nao_aumentam_o_que_esta_gravado(self):
        extracao, _ = self._importar_inicio_com_homonimo()
        chave = modulo_importacao.CHAVE_PAYLOAD_IMPORTACAO
        extracao.refresh_from_db()
        gravado = deepcopy(extracao.payload[chave])

        self._repetir_a_importacao(extracao)
        self._repetir_a_importacao(extracao)

        extracao.refresh_from_db()
        self.assertEqual(extracao.payload[chave], gravado)
        self.assertEqual(len(gravado['avisos']['/acts/0']), 1)


    def test_aviso_gravado_so_tem_codigo_e_tipos(self):
        extracao, _ = self._importar_inicio_com_homonimo()

        extracao.refresh_from_db()
        self.assertEqual(
            extracao.payload['_importacao'],
            {
                'versao': 1,
                'avisos': {'/acts/0': [{
                    'codigo': 'homonimo_outro_tipo',
                    'tipo_declarado': 'transcricao',
                    'tipo_existente': 'matricula',
                }]},
            },
        )
        # Nada que identifique pessoa, cartório, imóvel ou documento.
        gravado = json.dumps(extracao.payload['_importacao'])
        for segredo in (
            '366', 'CRI de Origem', 'CNS-324', 'Irmão', self.usuario.username,
        ):
            with self.subTest(segredo=segredo):
                self.assertNotIn(segredo, gravado)
        # O contrato do serviço (de onde a revisão lê) não é tocado.
        self.assertNotIn('_importacao', extracao.payload_servico)


    def test_importacao_desfeita_nao_grava_aviso_e_a_proxima_grava_uma_vez(self):
        irmao = self._imovel_em(self.imovel.terra_indigena_id, 'Irmão')
        self._matricula_homonima_em(irmao)
        payload = self._payload_inicio_sem_rotulo()
        segundo = deepcopy(payload['acts'][0])
        segundo['ordem'] = 2
        segundo['rotulo'] = self._campo('R-2', 'R-1/42.718')
        segundo['tipo_sugerido'] = self._campo('registro', 'R-1/42.718')
        # Ato 2 sem cartório da origem: recusa e leva o bloco inteiro junto.
        del segundo['origem']['cartorio']
        payload['acts'].append(segundo)
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida):
            self._importar(extracao)

        extracao.refresh_from_db()
        self.assertNotIn('_importacao', extracao.payload)
        self.assertEqual(OcrJob.objects.get(pk=self.job.pk).status, 'revisado')

        # Nova tentativa só com o ato bom: o aviso nasce uma vez.
        resultado = self._repetir_a_importacao(extracao)

        status = {linha['chave']: linha['status'] for linha in resultado['linhas']}
        self.assertEqual(status, {'/acts/0': 'criado', '/acts/1': 'ignorado'})
        (primeiro,) = [
            linha for linha in resultado['linhas'] if linha['chave'] == '/acts/0'
        ]
        self.assertEqual(len(self._so_os_de_homonimo(primeiro['avisos'])), 1)
        extracao.refresh_from_db()
        self.assertEqual(
            list(extracao.payload['_importacao']['avisos']), ['/acts/0'],
        )
        self.assertEqual(
            len(extracao.payload['_importacao']['avisos']['/acts/0']), 1,
        )
        replay = self._repetir_a_importacao(extracao)
        (primeiro_do_replay,) = [
            linha for linha in replay['linhas'] if linha['chave'] == '/acts/0'
        ]
        self.assertEqual(primeiro_do_replay['avisos'], primeiro['avisos'])


    def test_sem_homonimo_o_payload_da_extracao_nao_e_tocado(self):
        extracao = self._extracao(self._payload_origem())
        antes = ExtracaoSugerida.objects.values_list(
            'payload', flat=True,
        ).get(pk=extracao.pk)

        primeira = self._importar(extracao)
        repetida = self._repetir_a_importacao(extracao)

        depois = ExtracaoSugerida.objects.values_list(
            'payload', flat=True,
        ).get(pk=extracao.pk)
        self.assertEqual(depois, antes)
        self.assertNotIn('_importacao', depois)
        self.assertFalse(self._so_os_de_homonimo(self._avisos_do_ato(repetida)))
        self.assertEqual(
            self._avisos_do_ato(repetida), self._avisos_do_ato(primeira),
        )


    def test_registro_gravado_desconhecido_ou_malformado_nao_vira_aviso(self):
        extracao, primeira = self._importar_inicio_com_homonimo()
        self.assertEqual(
            len(self._so_os_de_homonimo(self._avisos_do_ato(primeira))), 1,
        )
        for registros in (
            [{'codigo': 'inventado', 'tipo_declarado': 'transcricao',
              'tipo_existente': 'matricula'}],
            [{'codigo': 'homonimo_outro_tipo', 'tipo_declarado': None,
              'tipo_existente': 'matricula'}],
            ['texto solto'],
            'nao-e-lista',
        ):
            with self.subTest(registros=registros):
                carimbado = ExtracaoSugerida.objects.get(pk=extracao.pk)
                carimbado.payload['_importacao']['avisos']['/acts/0'] = registros
                carimbado.save(update_fields=['payload'])

                repetida = self._repetir_a_importacao(extracao)

                self.assertFalse(
                    self._so_os_de_homonimo(self._avisos_do_ato(repetida)),
                )
