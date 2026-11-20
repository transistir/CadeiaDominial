"""Parte 1 de 2 do corpo de ``RevisaoServicesTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_revisao_services.py``.
"""

"""Persistência transacional e finalização da revisão com dados sintéticos."""

from collections import Counter
from hashlib import sha256

from django.utils import timezone

from dominial.models import LancamentoTipo
from ia_ocr import estados, services, valores
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    CAMPOS_DA_ORIGEM, desnormalizar, pendencias, versao_linha,
)

from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao,
)


class RevisaoServicesTestParte1:
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

    def test_transmissao_vazia_salva_bloco_sem_campos_novos(self):
        self._resolver_pendencias()
        decisoes = {
            campo.chave: {'incluir': True, 'conferido': True}
            for campo in self.extracao.campos.filter(chave__startswith='/acts/0')
        }
        chaves = [
            f'/acts/0/{nome}' for nome in (
                'livro_transacao', 'folha_transacao', 'data_transacao',
            )
        ]
        for chave in chaves:
            decisoes[chave] = {'incluir': True, 'conferido': True, 'valor': ''}

        salva, _versao, _partes, campos_novos = services.salvar_bloco(
            self.extracao, decisoes, self.usuario,
            services.versao_bloco(self.extracao),
        )

        self.assertEqual(salva.pk, self.extracao.pk)
        self.assertEqual(campos_novos, [])
        self.assertEqual(pendencias(salva), [])
        for chave in chaves:
            self.assertEqual(salva.campos.get(chave=chave).valor_final, '')

    def test_transmissao_data_preenchida_persiste_sem_campos_novos(self):
        chave = '/acts/0/data_transacao'

        salva, _versao, _partes, campos_novos = services.salvar_bloco(
            self.extracao, {
                chave: {'incluir': True, 'conferido': True, 'valor': '2019-12-20'},
            }, self.usuario, services.versao_bloco(self.extracao),
        )

        self.assertEqual(campos_novos, [])
        campo = salva.campos.get(chave=chave)
        self.assertEqual(campo.valor_final, '2019-12-20')
        self.assertEqual(campo.tipo_valor, 'data')
        self.assertEqual(campo.status_revisao, 'editado')

    def test_salvar_bloco_recusa_livro_transacao_com_51_caracteres(self):
        self._resolver_pendencias()
        chave = '/acts/0/livro_transacao'
        versao = services.versao_bloco(self.extracao)

        with self.assertRaisesMessage(
            valores.ValorInvalido,
            'texto acima do limite de 50 caracteres do destino',
        ):
            services.salvar_bloco(
                self.extracao, {
                    chave: {'incluir': True, 'conferido': True, 'valor': 'X' * 51},
                }, self.usuario, versao,
            )

        self.assertEqual(services.versao_bloco(self.extracao), versao)
        self.assertIsNone(self.extracao.campos.get(chave=chave).valor_final)

    def test_salvar_bloco_aplica_e_persiste(self):
        carregada = ExtracaoSugerida.objects.prefetch_related('campos').get(
            pk=self.extracao.pk,
        )
        versao = services.versao_bloco(carregada)
        antes = timezone.now()

        resultado, versao_devolvida, _invalidou_partes, _campos_novos = services.salvar_bloco(
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
        salva, versao_salva, _invalidou_partes, _campos_novos = services.salvar_bloco(
            self.extracao,
            {'/document/data': {'incluir': True, 'valor': '2020-01-11'}},
            self.usuario, services.versao_bloco(self.extracao),
        )

        self.assertEqual(salva.pk, self.extracao.pk)
        self.assertEqual(versao_salva, services.versao_bloco(self.extracao))

        # Outro revisor grava logo depois: o token já devolvido segue sendo o
        # do estado que o primeiro save deixou e não serve mais para gravar.
        _, versao_do_outro, _invalidou_outra, _campos_novos = services.salvar_bloco(
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

    def test_decisao_de_linha_ignorada_recusa_sem_gravar(self):
        # Tarefa C #322 (revisão Opus): a chave EXISTE numa extração antiga,
        # mas a folha não tem mais destino — aplicar a decisão levantaria
        # ChaveDesconhecida (500). Recusa 4xx antes de gravar qualquer linha.
        # #328 rodada 2 (Opus N-2): vale para as duas folhas sem destino.
        for chave, raw, valor, tipo_valor in (
            ('/acts/0/valor_transacao', 'R$ 150.000,00', '150000.00', 'decimal'),
            ('/acts/0/detalhes', 'Detalhes antigos', 'Detalhes antigos', 'texto'),
        ):
            with self.subTest(chave=chave):
                CampoSugerido.objects.create(
                    extracao=self.extracao,
                    chave=chave,
                    raw=raw,
                    normalized=valor,
                    tipo_valor=tipo_valor,
                    status_revisao='aceito',
                )
                versao = services.versao_bloco(self.extracao)

                with self.assertRaises(services.ExtracaoRecusada) as contexto:
                    services.salvar_bloco(
                        self.extracao, {
                            chave: {
                                'incluir': True, 'conferido': True,
                                'valor': valor,
                            },
                        }, self.usuario, versao,
                    )

                self.assertEqual(contexto.exception.code, 'linha_inexistente')
                self.assertEqual(services.versao_bloco(self.extracao), versao)
                campo = self.extracao.campos.get(chave=chave)
                self.assertIsNone(campo.valor_final)

    def test_mudar_tipo_cria_linhas_exigidas_e_salva_nelas(self):
        LancamentoTipo.objects.create(
            tipo='averbacao', requer_descricao=True, requer_observacao=False,
        )
        LancamentoTipo.objects.create(
            tipo='registro', requer_titulo=True,
            requer_cartorio_origem=True, requer_observacao=False,
        )
        self.assertFalse(
            self.extracao.campos.filter(
                chave__in=['/acts/0/titulo', '/acts/0/origem/cartorio'],
            ).exists()
        )
        versao = services.versao_bloco(self.extracao)

        _salva, _versao, _partes, campos_novos = services.salvar_bloco(
            self.extracao,
            {'/acts/0/tipo_sugerido': {'incluir': True, 'valor': 'registro'}},
            self.usuario, versao,
        )
        # #324 rodada 2: título + cartório de origem + as 5 linhas da origem.
        self.assertEqual(
            sorted(campos_novos),
            [
                '/acts/0/origem/cartorio', '/acts/0/origem/data',
                '/acts/0/origem/folha', '/acts/0/origem/livro',
                '/acts/0/origem/numero', '/acts/0/origem/tipo_documento',
                '/acts/0/titulo',
            ],
        )
        for nome in ('livro_transacao', 'folha_transacao', 'data_transacao'):
            chave = f'/acts/0/{nome}'
            with self.subTest(chave=chave):
                self.assertNotIn(chave, campos_novos)
                self.assertEqual(self.extracao.campos.filter(chave=chave).count(), 1)

        campos = {campo.chave: campo for campo in self.extracao.campos.all()}
        for chave in ('/acts/0/titulo', '/acts/0/origem/cartorio'):
            with self.subTest(chave=chave):
                self.assertIn(chave, campos)
                self.assertIsNone(campos[chave].normalized)
                self.assertFalse(campos[chave].requer_revisao)

        # As chaves novas existem: salvar nelas não devolve linha_inexistente.
        versao = services.versao_bloco(self.extracao)
        services.salvar_bloco(
            self.extracao, {
                '/acts/0/titulo': {
                    'incluir': True, 'valor': 'Escritura Pública',
                },
                '/acts/0/origem/cartorio': {
                    'incluir': True, 'conferido': True,
                    'escolha': {'criar_novo': True},
                },
            }, self.usuario, versao,
        )
        campos = {campo.chave: campo for campo in self.extracao.campos.all()}
        self.assertEqual(campos['/acts/0/titulo'].valor_final, 'Escritura Pública')
        self.assertTrue(campos['/acts/0/origem/cartorio'].criar_novo)

    # --- #324 rodada 2 (P1): trocar o tipo cria a origem INTEIRA ---------------

    CHAVES_DA_ORIGEM = [
        f'/acts/0/origem/{nome}' for nome in ('cartorio', *CAMPOS_DA_ORIGEM)
    ]

    def _trocar_tipo(self, tipo):
        return services.salvar_bloco(
            self.extracao,
            {'/acts/0/tipo_sugerido': {'incluir': True, 'valor': tipo}},
            self.usuario, services.versao_bloco(self.extracao),
        )

    def _chaves_da_origem_no_banco(self):
        return Counter(
            self.extracao.campos.filter(chave__startswith='/acts/0/origem/')
            .values_list('chave', flat=True)
        )

    def _confere_origem_completa_uma_vez(self, tipo):
        """A IA sugeriu averbação SEM origem; o revisor troca para ``tipo``.

        Antes da correção só nascia ``origem/cartorio``: o formulário não tinha
        onde declarar número/tipo/livro/folha/data e a importação gravava sem
        ``LancamentoOrigem``, sem Documento de origem e sem a FK.
        """
        self.assertEqual(self._chaves_da_origem_no_banco(), Counter())

        _salva, _versao, _partes, campos_novos = self._trocar_tipo(tipo)

        # As seis chaves, exatamente, cada uma UMA vez — no retorno e no banco.
        origem_nova = [c for c in campos_novos if '/origem/' in c]
        self.assertEqual(
            Counter(origem_nova), Counter(self.CHAVES_DA_ORIGEM),
        )
        self.assertEqual(
            self._chaves_da_origem_no_banco(), Counter(self.CHAVES_DA_ORIGEM),
        )
        for campo in self.extracao.campos.filter(
            chave__in=self.CHAVES_DA_ORIGEM,
        ):
            with self.subTest(chave=campo.chave):
                self.assertFalse(campo.requer_revisao)
                self.assertIsNone(campo.raw)
                self.assertIsNone(campo.normalized)
        # Só o cartório (exigido pelo tipo) gera pendência; as outras cinco são
        # linhas vazias editáveis, sem bloquear nem poluir a tela.
        da_origem = [
            p for p in pendencias(self.extracao) if '/origem/' in p['chave']
        ]
        self.assertEqual(
            {p['chave'] for p in da_origem}, {'/acts/0/origem/cartorio'},
        )
        self.assertIn({
            'chave': '/acts/0/origem/cartorio',
            'motivo': 'obrigatorio_ausente', 'bloqueante': True,
        }, da_origem)

        # Repetir o save com o mesmo tipo não recria nem duplica nada.
        _salva, _versao, _partes, repetidos = self._trocar_tipo(tipo)
        self.assertEqual(repetidos, [])
        self.assertEqual(
            self._chaves_da_origem_no_banco(), Counter(self.CHAVES_DA_ORIGEM),
        )

