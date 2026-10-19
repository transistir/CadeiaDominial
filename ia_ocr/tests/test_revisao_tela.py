"""Tela de revisão de campos (I-5): render, escape, pendências e somente leitura."""

import json
import re

from django.conf import settings
from django.shortcuts import resolve_url
from django.test.html import Element
from django.utils import timezone

from dominial.models import Cartorios, LancamentoTipo, Pessoas
from ia_ocr import estados, revisao, views
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob
from ia_ocr.revisao import IndiceCartorios, IndicePessoas, enriquecer_payload

from .base_texto import TelaTextoBase
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
    payload_registro,
)
from .test_ui_card_ocr import _atributos, _elementos

RAW_MALICIOSO = '<script>alert(1)</script>"><img onerror=1>'


class RevisaoTelaTest(TelaTextoBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.dono)
        self.documento.tipo.tipo = 'matricula'
        self.documento.tipo.save(update_fields=['tipo'])
        self.job.paginas.filter(numero_pagina=1).update(texto_ocr=TEXTO_PAGINA_1)
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.EXTRAIDO)
        self.job.refresh_from_db()

    def _extracao(self, payload=None, resolver=False):
        payload = payload or payload_averbacao(self.job.job_id)
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
        )
        linhas = revisao.desnormalizar(extracao, payload, list(self.job.paginas.all()))
        if resolver:
            for linha in linhas:
                linha.status_revisao = 'aceito'
                if linha.tipo_valor in ('parte', 'cartorio'):
                    linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        return extracao

    def _tela(self):
        return self.client.get(self.url('campos_job_ocr'))

    def _botao_finalizar(self, resposta):
        html = resposta.content.decode()
        botao = re.search(r'<button[^>]*data-ocr-finalizar[^>]*>', html)
        self.assertIsNotNone(botao)
        return botao.group(0)

    @staticmethod
    def _valor_do_card(html, chave):
        card = next(
            card for card in _elementos(
                html, 'article', presentes=('data-campo',),
            )
            if _atributos(card)['data-chave'] == chave
        )
        for tag in ('input', 'textarea'):
            elementos = _descendentes(card, tag, 'data-campo-valor')
            if not elementos:
                continue
            elemento = elementos[0]
            if tag == 'input':
                return _atributos(elemento).get('value', '')
            return ''.join(
                filho for filho in elemento.children if isinstance(filho, str)
            )
        return None

    def test_tela_exige_extraido(self):
        self._extracao()
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.CONCLUIDO)

        resposta = self._tela()

        self.assertRedirects(resposta, self.url_tela(), fetch_redirect_response=False)
        self.assertTrue(self.mensagens(resposta))

    def test_tela_renderiza_campos_e_versao(self):
        extracao = self._extracao()

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'ia_ocr/revisao_campos.html')
        self.assertContains(resposta, 'data-ocr-revisao')
        self.assertContains(resposta, f'data-versao="{resposta.context["versao"]}"')
        self.assertContains(resposta, ' data-campo\n', count=extracao.campos.count())
        self.assertContains(resposta, '← Voltar ao processamento')

    def test_tela_escapa_texto_do_ocr(self):
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['raw'] = RAW_MALICIOSO
        self._extracao(payload)

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, '<script>alert(1)</script>')
        self.assertNotContains(resposta, '"><img onerror=1>')
        self.assertContains(resposta, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertContains(resposta, '&quot;&gt;&lt;img onerror=1&gt;')

    def test_tela_mostra_pendencias_e_desabilita_finalizar(self):
        extracao = self._extracao()
        self.assertTrue(revisao.pendencias(extracao))

        resposta = self._tela()

        self.assertContains(resposta, 'data-ocr-pendencias')
        self.assertIn('disabled', self._botao_finalizar(resposta))

    def test_tela_sem_pendencia_habilita_finalizar(self):
        extracao = self._extracao(resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])

        resposta = self._tela()

        self.assertNotContains(resposta, 'data-ocr-pendencias')
        self.assertNotIn('disabled', self._botao_finalizar(resposta))
        self.assertNotContains(resposta, 'data-ocr-somente-leitura')

    def test_tela_mostra_rotulos_dos_candidatos(self):
        candidatos = [
            Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='11111111111'),
            Pessoas.objects.create(nome='JOÃO PEREIRA', cpf='22222222222'),
        ]
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][0]['match_pessoa_candidatos'] = [
            candidato.pk for candidato in candidatos
        ]
        self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'CPF ***.***.***-11')
        self.assertContains(resposta, 'CPF ***.***.***-22')
        self.assertContains(
            resposta, f'<option value="{candidatos[0].pk}"',
        )
        self.assertContains(
            resposta, f'<option value="{candidatos[1].pk}"',
        )
        self.assertNotContains(resposta, 'Registro #11')
        self.assertNotContains(resposta, '11111111111')
        self.assertNotContains(resposta, '22222222222')

    def test_tela_mostra_evidencia_e_link_da_pagina(self):
        self.job.paginas.filter(numero_pagina=2).update(
            texto_ocr='Página dois Nº 42.718',
        )
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 2, 'trecho': 'Nº 42.718',
        }
        self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'Página 2')
        self.assertContains(resposta, 'Nº 42.718')
        self.assertContains(resposta, f'{self.url_pdf()}#page=2')

    def test_tela_somente_leitura_apos_revisado(self):
        extracao = self._extracao(resolver=True)
        ExtracaoSugerida.objects.filter(pk=extracao.pk).update(
            finalizada_em=timezone.now(), finalizada_por=self.dono,
        )
        OcrJob.objects.filter(pk=self.job.pk).update(status=estados.REVISADO)

        resposta = self._tela()

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'data-ocr-somente-leitura')
        self.assertIn('disabled', self._botao_finalizar(resposta))
        html = resposta.content.decode()
        valores = re.findall(r'<(?:input|textarea)[^>]*data-campo-valor[^>]*>', html)
        self.assertEqual(len(valores), extracao.campos.count())
        for tag in valores:
            self.assertIn(' disabled', tag)

    def test_campo_limpo_nao_ressuscita_ao_recarregar_nem_conferir(self):
        self._extracao()
        chave = '/document/numero'
        versao = self._tela().context['versao']

        # Limpar o texto opcional grava '' (vazio intencional, não None).
        for conferido in (False, True):
            with self.subTest(conferido=conferido):
                resposta = self.client.post(
                    self.url('salvar_bloco_ocr'),
                    data=json.dumps({'versao': versao, 'decisoes': [{
                        'chave': chave, 'incluir': True,
                        'conferido': conferido, 'valor': '',
                    }]}),
                    content_type='application/json',
                )
                self.assertEqual(resposta.status_code, 200, resposta.content)
                versao = resposta.json()['versao']

                html = self._tela().content.decode()
                self.assertEqual(self._valor_do_card(html, chave), '')

    def test_tela_exige_login_e_permissao(self):
        self._extracao()
        url = self.url('campos_job_ocr')

        self.client.logout()
        resposta = self.client.get(url)
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.url.startswith(
            f'{resolve_url(settings.LOGIN_URL)}?next=',
        ))

        self.client.force_login(self.sem_acesso)
        self.assertEqual(self.client.get(url).status_code, 404)

    def _extracao_com_cartorio_nulo(self, payload=None):
        """Payload com cartório obrigatório sem nome; demais linhas resolvidas."""
        payload = payload or payload_registro(self.job.job_id)
        payload['document']['cartorio']['normalized'] = None
        extracao = self._extracao(payload)
        for campo in extracao.campos.all():
            if campo.chave == '/document/cartorio':
                continue
            campo.status_revisao = 'aceito'
            if campo.tipo_valor in ('parte', 'cartorio'):
                campo.criar_novo = True
            campo.save()
        return extracao

    def _salvar_cartorio(self, decisao):
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/document/cartorio', 'incluir': True, **decisao,
                }],
            }),
            content_type='application/json',
        )
        return salvar

    def test_salvar_cartorio_digitado_satisfaz_obrigatorio(self):
        extracao = self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'Cartório Novo', 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.valor_final, 'Cartório Novo')
        self.assertEqual(campo.status_revisao, 'editado')
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            and pendencia['motivo'] == 'obrigatorio_ausente'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_finalizar_com_cartorio_digitado(self):
        extracao = self._extracao_com_cartorio_nulo()
        salvar = self._salvar_cartorio({
            'valor': 'Cartório Novo', 'escolha': {'criar_novo': True},
        })
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        extracao.refresh_from_db()
        dados = revisao.dados_revisados(extracao)
        self.assertEqual(dados.documento.cartorio_nome, 'Cartório Novo')
        self.assertTrue(dados.documento.cartorio_criar_novo)

    def test_criar_novo_cartorio_opcional_sem_nome_gera_pendencia(self):
        extracao = self._extracao(resolver=True)
        self.assertEqual(revisao.pendencias(extracao), [])
        chave = '/document/cri_atual'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                    'escolha': {'criar_novo': True},
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertIn(
            {'chave': chave, 'motivo': 'criar_novo_sem_nome',
             'bloqueante': True},
            revisao.pendencias(extracao),
        )

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': salvar.json()['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': 'Cartório Novo',
                    'escolha': {'criar_novo': True},
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertFalse(any(
            pendencia['motivo'] == 'criar_novo_sem_nome'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_escolher_cartorio_existente_zera_nome(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-novo', estado='PR',
        )
        extracao = self._extracao_com_cartorio_nulo()
        # A tela só oferece match_candidatos: o cartório foi criado depois da
        # extração, então simula a lista recomputada que o select exibiria.
        extracao.campos.filter(chave='/document/cartorio').update(
            match_candidatos=[cartorio.pk],
        )

        salvar = self._salvar_cartorio({
            'valor': 'Cartório Digitado',
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertIsNone(campo.valor_final)
        self.assertEqual(campo.cartorio_escolhido_id, cartorio.pk)
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            and pendencia['motivo'] == 'obrigatorio_ausente'
            for pendencia in revisao.pendencias(extracao)
        ))

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        extracao.refresh_from_db()
        dados = revisao.dados_revisados(extracao)
        self.assertEqual(dados.documento.cartorio_id, cartorio.pk)

    def test_cartorio_digitado_acima_do_limite_e_422(self):
        self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 10001, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_cartorio_nome_no_limite_de_200_e_aceito(self):
        extracao = self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 200, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.valor_final, 'x' * 200)

    def test_cartorio_nome_acima_de_200_e_422(self):
        self._extracao_com_cartorio_nulo()

        salvar = self._salvar_cartorio({
            'valor': 'x' * 201, 'escolha': {'criar_novo': True},
        })

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_cartorio_nome_acima_de_200_bloqueia_finalizacao(self):
        extracao = self._extracao_com_cartorio_nulo()
        extracao.campos.filter(chave='/document/cartorio').update(
            normalized='x' * 201, status_revisao='editado', criar_novo=True,
        )
        versao = self._tela().context['versao']

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': versao}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': '/document/cartorio',
                'motivo': 'valor_acima_do_limite_destino',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )

    def _extracao_com_cartorio_ocr_longo(self, cartorio_pk=None):
        """OCR traz nome acima de 200; opcionalmente com candidato existente."""
        extracao = self._extracao(resolver=True)
        extracao.campos.filter(chave='/document/cartorio').update(
            normalized='x' * 250,
            match_candidatos=[cartorio_pk] if cartorio_pk else [],
            status_revisao='sugerido',
            criar_novo=False,
        )
        return extracao

    def test_cartorio_existente_escolhido_aceita_nome_longo_do_ocr(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-longo', estado='PR',
        )
        extracao = self._extracao_com_cartorio_ocr_longo(cartorio.pk)

        salvar = self._salvar_cartorio({
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/document/cartorio')
        self.assertEqual(campo.cartorio_escolhido_id, cartorio.pk)
        self.assertFalse(any(
            pendencia['chave'] == '/document/cartorio'
            for pendencia in revisao.pendencias(extracao)
        ))

    def test_cartorio_existente_escolhido_finaliza_com_nome_longo_do_ocr(self):
        cartorio = Cartorios.objects.create(
            nome='Cartório Existente', cns='E2E-longo', estado='PR',
        )
        self._extracao_com_cartorio_ocr_longo(cartorio.pk)

        salvar = self._salvar_cartorio({
            'escolha': {'cartorio_id': cartorio.pk, 'criar_novo': False},
        })
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_cartorio_nome_longo_do_ocr_sem_escolha_e_422(self):
        self._extracao_com_cartorio_ocr_longo()

        salvar = self._salvar_cartorio({'escolha': {'criar_novo': False}})

        self.assertEqual(salvar.status_code, 422, salvar.content)
        self.assertEqual(salvar.json()['erro'], 'valor_invalido')
        self.assertEqual(salvar.json()['chave'], '/document/cartorio')

    def test_evidencia_mascara_documentos_com_7_ou_mais_digitos(self):
        payload = payload_averbacao(self.job.job_id)
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'trecho': 'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
        }
        extracao = self._extracao(payload)

        resposta = self._tela()

        self.assertContains(resposta, 'CPF ***')
        self.assertNotContains(resposta, '123.456.789-00')
        self.assertEqual(
            extracao.campos.get(chave='/document/numero').evidencia_trecho,
            'Transmitente: JOÃO DA SILVA (CPF 123.456.789-00).',
        )

    def test_mascara_sequencias_longas_e_preserva_texto_sem_documento(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123.456.789-00 e RG 12.345.678-9'),
            'CPF *** e RG ***',
        )
        self.assertEqual(
            mascarar('Trecho sem documento, com 123456 apenas.'),
            'Trecho sem documento, com *** apenas.',
        )

    def test_mascara_preserva_data_iso_valor_cns_e_processo(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Data 10/01/2020, ISO 2020-01-10, valor R$ 1.500.000,00, '
            'CNS 123456789012345, processo 0001234-56.2020.8.16.0001.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_e_rg_com_pontuacao_final(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 12345678900 e RG 1234567-X, matrícula 123456.'),
            'CPF *** e RG ***, matrícula ***.',
        )

    def test_mascara_rg_seguido_de_pontuacao(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(mascarar('RG 123456.'), 'RG ***.')
        self.assertEqual(
            mascarar('RG 123456, emitido pelo oficial'),
            'RG ***, emitido pelo oficial',
        )

    def test_mascara_preserva_pontuacao_de_numero_maior(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Valor 1.500.000,00 e 1500000,00, datas 10/01/2020 e '
            '2020-01-10, CNS 123456789012345'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_mascara_cpf_com_espacos_contiguo_e_rg_curto(self):
        mascarar = views._mascarar_evidencia
        self.assertEqual(
            mascarar('CPF 123 456 789 00 e CPF 12345678900.'),
            'CPF *** e CPF ***.',
        )
        self.assertEqual(
            mascarar('RG 123456 e RG 123456789.'),
            'RG *** e RG ***.',
        )

    def test_mascara_preserva_valor_sem_milhar_e_processo_longo(self):
        mascarar = views._mascarar_evidencia
        trecho = (
            'Valor 1500000,00, processo 000123456789, '
            'CNS 123456789012345.'
        )
        self.assertEqual(mascarar(trecho), trecho)

    def test_valor_transacao_opcional_vazio_salva_e_finaliza(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        self.assertEqual(revisao.pendencias(extracao), [])
        chave = '/acts/0/valor_transacao'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertEqual(
            extracao.campos.get(chave=chave).valor_final, '',
        )
        self.assertFalse(any(
            pendencia['chave'] == chave
            for pendencia in revisao.pendencias(extracao)
        ))

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 200, finalizar.content)

    def test_obrigatorio_vazio_continua_bloqueando_finalizacao(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        chave = '/document/data'

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': chave,
                'motivo': 'obrigatorio_ausente',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )
        self.assertFalse(any(
            pendencia['chave'] == chave
            and pendencia['motivo'] == 'valor_incompativel_destino'
            for pendencia in finalizar.json()['pendencias']
        ))

    def test_enum_obrigatorio_vazio_bloqueia_finalizacao(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': dict(payload['document']['tipo']),
        }
        extracao = self._extracao(payload, resolver=True)
        chave = '/acts/0/origem/tipo_documento'
        self.assertFalse(any(
            pendencia['chave'] == chave
            for pendencia in revisao.pendencias(extracao)
        ))

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': chave, 'incluir': True, 'valor': '',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        self.assertEqual(
            extracao.campos.get(chave=chave).valor_final, '',
        )

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )

        self.assertEqual(finalizar.status_code, 422, finalizar.content)
        self.assertIn(
            {
                'chave': chave,
                'motivo': 'valor_incompativel_destino',
                'bloqueante': True,
            },
            finalizar.json()['pendencias'],
        )

    def test_decimal_so_espacos_salva_como_vazio(self):
        extracao = self._extracao(
            payload_registro(self.job.job_id), resolver=True,
        )
        for chave in ('/acts/0/valor_transacao', '/acts/0/area'):
            with self.subTest(chave=chave):
                salvar = self.client.post(
                    self.url('salvar_bloco_ocr'),
                    data=json.dumps({
                        'versao': self._tela().context['versao'],
                        'decisoes': [{
                            'chave': chave, 'incluir': True, 'valor': '   ',
                        }],
                    }),
                    content_type='application/json',
                )

                self.assertEqual(salvar.status_code, 200, salvar.content)
                self.assertEqual(
                    extracao.campos.get(chave=chave).valor_final, '',
                )

    def test_descartar_campo_exigido_pelo_tipo_nao_estoura(self):
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        extracao = self._extracao()

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{'chave': '/acts/0/descricao', 'incluir': False}],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/descricao')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_mudar_tipo_com_titulo_descartado_nao_estoura(self):
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=False, requer_observacao=False,
        )
        extracao = self._extracao()
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/titulo',
            raw='Título antigo',
            normalized='Título antigo',
            tipo_valor='texto',
            status_revisao='descartado',
        )

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': self._tela().context['versao'],
                'decisoes': [{
                    'chave': '/acts/0/tipo_sugerido',
                    'incluir': True, 'valor': 'registro',
                }],
            }),
            content_type='application/json',
        )

        self.assertEqual(salvar.status_code, 200, salvar.content)
        campo = extracao.campos.get(chave='/acts/0/titulo')
        self.assertEqual(campo.status_revisao, 'descartado')

    def test_finaliza_usando_apenas_os_controles_renderizados(self):
        # Cartório do documento: match único; cri_atual: dois homônimos;
        # JOÃO por CPF; MARIA e PEDRO sem cadastro (único caminho: criar).
        Cartorios.objects.create(nome='CRI de Guaíra', cns='E2E-1', estado='PR')
        homonimos = [
            Cartorios.objects.create(
                nome='Cartório de Registro de Imóveis de Guaíra',
                cns=f'E2E-{indice}', estado='PR',
            )
            for indice in (2, 3)
        ]
        Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='12345678900')
        payload = enriquecer_payload(
            payload_registro(self.job.job_id), IndicePessoas(), IndiceCartorios(),
        )
        self._extracao(payload)

        html = self._tela().content.decode()
        toolbar = _elementos(html, 'div', presentes=('data-ocr-toolbar',))[0]
        versao = _atributos(toolbar)['data-versao']
        decisoes = [
            decisao for card in _elementos(html, 'article', presentes=('data-campo',))
            if (decisao := _decisao_do_card(card)) is not None
        ]
        escolhas = {d['chave']: d['escolha'] for d in decisoes if 'escolha' in d}
        self.assertEqual(
            escolhas['/document/cri_atual']['cartorio_id'], homonimos[0].pk,
        )
        self.assertTrue(escolhas['/acts/0/partes/2']['criar_novo'])

        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({'versao': versao, 'decisoes': decisoes}),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)

        finalizar = self.client.post(
            self.url('finalizar_revisao_ocr'),
            data=json.dumps({'versao': salvar.json()['versao']}),
            content_type='application/json',
        )
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        self.assertIn('redirect', finalizar.json())


def _descendentes(no, nome_tag, atributo):
    """Elementos `nome_tag` com `atributo` na subárvore de `no`."""
    achados = []
    for filho in no.children:
        if not isinstance(filho, Element):
            continue
        if filho.name == nome_tag and atributo in _atributos(filho):
            achados.append(filho)
        achados += _descendentes(filho, nome_tag, atributo)
    return achados


def _decisao_do_card(card):
    """A decisão que o ocr_revisao.js mandaria com o card conferido.

    Card sem valor fica de fora (nada a conferir); cards de parte/cartório
    levam ``escolha`` com a opção selecionada, a primeira candidata quando
    nenhuma vem selecionada, ou criar novo quando não há candidata.
    """
    valor = None
    for tag in ('input', 'textarea'):
        for elemento in _descendentes(card, tag, 'data-campo-valor'):
            atributos = _atributos(elemento)
            valor = atributos.get('value') if tag == 'input' else ''.join(
                filho for filho in elemento.children if isinstance(filho, str)
            )
            tipo = atributos['data-tipo']
    if not valor:
        return None
    decisao = {
        'chave': _atributos(card)['data-chave'],
        'incluir': True,
        'conferido': True,
    }
    # Espelha TIPOS_SEM_VALOR do ocr_revisao.js: sem conversor de formulário.
    if tipo not in ('parte', 'ato'):
        decisao['valor'] = valor
    selects = _descendentes(card, 'select', 'data-ocr-escolha')
    criar = _descendentes(card, 'input', 'data-ocr-criar-novo')
    if selects or criar:
        escolhido = None
        alvo = None
        if selects:
            alvo = _atributos(selects[0])['data-ocr-escolha']
            opcoes = [
                opcao for opcao in _descendentes(selects[0], 'option', 'value')
                if _atributos(opcao)['value']
            ]
            selecionadas = [o for o in opcoes if 'selected' in _atributos(o)]
            escolhida = (selecionadas or opcoes or [None])[0]
            if escolhida is not None:
                escolhido = int(_atributos(escolhida)['value'])
        decisao['escolha'] = {
            'pessoa_id': escolhido if alvo == 'pessoa_id' else None,
            'cartorio_id': escolhido if alvo == 'cartorio_id' else None,
            'criar_novo': escolhido is None and bool(criar),
        }
    return decisao
