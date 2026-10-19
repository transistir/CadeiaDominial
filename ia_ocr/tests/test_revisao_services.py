"""Persistência transacional e finalização da revisão com dados sintéticos."""

from hashlib import sha256

from django.test import TestCase
from django.utils import timezone

from ia_ocr import estados, services
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import desnormalizar, pendencias, versao_linha

from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)


class RevisaoServicesTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(upload_por=self.usuario),
            status=estados.EXTRAIDO, criado_por=self.usuario,
        )
        pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        payload = payload_averbacao(self.job.job_id)
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider=PROVIDER,
            solicitada_por=self.usuario,
        )
        CampoSugerido.objects.bulk_create(
            desnormalizar(self.extracao, payload, [pagina]),
        )

    def _resolver_pendencias(self):
        decisoes = {}
        for campo in self.extracao.campos.all():
            decisao = {'incluir': True, 'conferido': True}
            if campo.tipo_valor in ('cartorio', 'parte'):
                decisao['escolha'] = {'criar_novo': True}
            decisoes[campo.chave] = decisao
        services.salvar_bloco(
            self.extracao, decisoes, self.usuario,
            services.versao_bloco(self.extracao),
        )
        self.assertEqual(pendencias(self.extracao), [])

    def test_salvar_bloco_aplica_e_persiste(self):
        carregada = ExtracaoSugerida.objects.prefetch_related('campos').get(
            pk=self.extracao.pk,
        )
        versao = services.versao_bloco(carregada)
        antes = timezone.now()

        resultado, versao_devolvida = services.salvar_bloco(
            carregada, {
                '/document/data': {'incluir': True, 'valor': '2020-01-11'},
                '/document/numero': {'incluir': True, 'conferido': True},
                '/document/livro': {'incluir': False},
                '/document/cartorio': {
                    'incluir': True, 'conferido': True,
                    'escolha': {'criar_novo': True},
                },
            }, self.usuario, versao,
        )

        self.assertEqual(resultado.pk, self.extracao.pk)
        campos = {campo.chave: campo for campo in resultado.campos.all()}
        data = campos['/document/data']
        self.assertEqual(data.valor_final, '2020-01-11')
        self.assertEqual(data.normalized, '2020-01-10')
        self.assertEqual(data.status_revisao, 'editado')
        self.assertEqual(campos['/document/numero'].status_revisao, 'aceito')
        self.assertEqual(campos['/document/livro'].status_revisao, 'descartado')
        self.assertTrue(campos['/document/cartorio'].criar_novo)
        for chave in ('data', 'numero', 'livro', 'cartorio'):
            campo = campos[f'/document/{chave}']
            self.assertEqual(campo.revisado_por, self.usuario)
            self.assertGreaterEqual(campo.revisado_em, antes)
            self.assertLessEqual(campo.revisado_em, timezone.now())
        versao_atual = services.versao_bloco(carregada)
        self.assertNotEqual(versao_atual, versao)
        self.assertEqual(versao_devolvida, versao_atual)
        versoes = ''.join(versao_linha(campos[chave]) for chave in sorted(campos))
        self.assertEqual(versao_atual, sha256(
            f'{self.extracao.pk}:{versoes}'.encode('utf-8'),
        ).hexdigest())
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.exists())

    def test_versao_cliente_velha_409_com_chaves(self):
        versao = services.versao_bloco(self.extracao)
        decisoes = {
            campo.chave: {
                'incluir': True, 'conferido': True,
                'versao': versao_linha(campo),
            }
            for campo in self.extracao.campos.filter(
                chave__in=['/document/data', '/document/livro'],
            ).order_by('chave')
        }
        services.salvar_bloco(
            self.extracao,
            {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
            self.usuario, versao,
        )
        versao_atual = services.versao_bloco(self.extracao)

        for sem_versao in ((), ('/document/livro',), tuple(decisoes)):
            with self.subTest(sem_versao=sem_versao):
                enviadas = {chave: dict(decisao) for chave, decisao in decisoes.items()}
                for chave in sem_versao:
                    enviadas[chave].pop('versao')
                with self.assertRaises(services.ConflitoVersao) as contexto:
                    services.salvar_bloco(
                        self.extracao, enviadas, self.usuario, versao,
                    )
                self.assertEqual(contexto.exception.code, 'conflito_versao')
                self.assertEqual(
                    contexto.exception.chaves_afetadas,
                    list(decisoes) if sem_versao else ['/document/data'],
                )
                self.assertEqual(services.versao_bloco(self.extracao), versao_atual)

    def test_versao_devolvida_pelo_save_e_a_da_transacao(self):
        salva, versao_salva = services.salvar_bloco(
            self.extracao,
            {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
            self.usuario, services.versao_bloco(self.extracao),
        )

        self.assertEqual(salva.pk, self.extracao.pk)
        self.assertEqual(versao_salva, services.versao_bloco(self.extracao))

        # Outro revisor grava logo depois: o token já devolvido segue sendo o
        # do estado que o primeiro save deixou e não serve mais para gravar.
        _, versao_do_outro = services.salvar_bloco(
            self.extracao,
            {'/document/numero': {'incluir': True, 'conferido': True}},
            criar_usuario(), versao_salva,
        )

        self.assertNotEqual(versao_salva, versao_do_outro)
        self.assertEqual(services.versao_bloco(self.extracao), versao_do_outro)
        with self.assertRaises(services.ConflitoVersao):
            services.salvar_bloco(
                self.extracao, {'/document/livro': {'incluir': False}},
                self.usuario, versao_salva,
            )

    def test_decisao_de_linha_inexistente_recusa(self):
        versao = services.versao_bloco(self.extracao)
        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            services.salvar_bloco(
                self.extracao, {
                    '/document/data': {'incluir': True, 'valor': '2020-01-11'},
                    '/document/inexistente': {'incluir': True},
                }, self.usuario, versao,
            )
        self.assertEqual(contexto.exception.code, 'linha_inexistente')
        self.assertEqual(services.versao_bloco(self.extracao), versao)

    def test_salvar_depois_de_finalizada_recusa(self):
        self._resolver_pendencias()
        services.finalizar_revisao(self.extracao, self.usuario)
        versao = services.versao_bloco(self.extracao)

        for status in (estados.REVISADO, estados.EXTRAIDO, estados.IMPORTADO):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)
                with self.assertRaises(services.ExtracaoRecusada):
                    services.salvar_bloco(
                        self.extracao,
                        {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
                        self.usuario, versao,
                    )
                self.assertEqual(services.versao_bloco(self.extracao), versao)
                self.assertEqual(self.job.transicoes.count(), 1)

    def test_finalizar_com_pendencia_422_lista_pendencias(self):
        self._resolver_pendencias()
        carregada = ExtracaoSugerida.objects.prefetch_related('campos').get(
            pk=self.extracao.pk,
        )
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='sugerido', requer_revisao=True,
        )

        with self.assertRaises(services.RevisaoIncompleta) as contexto:
            services.finalizar_revisao(carregada, self.usuario)

        self.assertEqual(contexto.exception.code, 'revisao_incompleta')
        self.assertEqual(contexto.exception.pendencias, [{
            'chave': '/document/data', 'motivo': 'revisao_pendente',
            'bloqueante': True,
        }])
        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertIsNone(self.extracao.finalizada_em)
        self.assertIsNone(self.extracao.finalizada_por)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertFalse(self.job.transicoes.exists())

    def test_finalizar_sem_pendencia_transiciona_e_audita(self):
        self._resolver_pendencias()
        antes = timezone.now()

        resultado = services.finalizar_revisao(self.extracao, self.usuario)

        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(resultado.pk, self.extracao.pk)
        self.assertEqual(resultado.finalizada_em, self.extracao.finalizada_em)
        self.assertGreaterEqual(self.extracao.finalizada_em, antes)
        self.assertLessEqual(self.extracao.finalizada_em, timezone.now())
        self.assertEqual(self.extracao.finalizada_por, self.usuario)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(resultado.ocr_job.status, estados.REVISADO)
        transicao = self.job.transicoes.get()
        self.assertEqual(transicao.de_status, estados.EXTRAIDO)
        self.assertEqual(transicao.para_status, estados.REVISADO)
        self.assertEqual(transicao.usuario, self.usuario)
        self.assertEqual(transicao.motivo, 'revisao_finalizada')

    def test_finalizar_duas_vezes_e_idempotente(self):
        self._resolver_pendencias()
        primeira = services.finalizar_revisao(self.extracao, self.usuario)
        transicao = self.job.transicoes.get()
        # O chamador retém a instância antiga, ainda sem finalizada_em.
        self.assertIsNone(self.extracao.finalizada_em)
        outro_usuario = criar_usuario()

        segunda = services.finalizar_revisao(self.extracao, outro_usuario)

        self.extracao.refresh_from_db()
        self.job.refresh_from_db()
        self.assertEqual(segunda.pk, primeira.pk)
        self.assertEqual(segunda.finalizada_em, primeira.finalizada_em)
        self.assertEqual(self.extracao.finalizada_em, primeira.finalizada_em)
        self.assertEqual(self.extracao.finalizada_por, self.usuario)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(self.job.transicoes.get().pk, transicao.pk)

    def test_finalizar_com_versao_atual_funciona(self):
        self._resolver_pendencias()
        versao = services.versao_bloco(self.extracao)

        finalizada = services.finalizar_revisao(
            self.extracao, self.usuario, versao_cliente=versao,
        )
        # Duplo clique: finalizar não muda o bloco, e o reenvio é idempotente.
        repetida = services.finalizar_revisao(
            self.extracao, self.usuario, versao_cliente=versao,
        )

        self.job.refresh_from_db()
        self.assertIsNotNone(finalizada.finalizada_em)
        self.assertEqual(finalizada.finalizada_por, self.usuario)
        self.assertEqual(repetida.finalizada_em, finalizada.finalizada_em)
        self.assertEqual(self.job.status, estados.REVISADO)
        self.assertEqual(self.job.transicoes.count(), 1)
