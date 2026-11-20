"""``dados_revisados`` (tipagem, recusas, ordenação e descartes) —
migração VERBATIM de ``ia_ocr/tests/test_revisao.py`` (Etapa 5,
grupo 3 do plano de 400 linhas). Corpos verbatim; só imports e a
linha de classe mudam.
"""

from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone

from dominial.models import Cartorios, Pessoas
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, OcrJob, PaginaOcr

from ia_ocr.revisao import (
    AtoRevisado, DadosRevisados, DocumentoRevisado, ParteRevisada,
    RevisaoInvalidada, dados_revisados, desnormalizar, pendencias,
)
from .factories import criar_documento_digital
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
)


class DadosRevisadosTest(TestCase):
    def setUp(self):
        self.job = OcrJob.objects.create(
            documento_digital=criar_documento_digital(), status='revisado',
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        self.cartorio = Cartorios.objects.create(
            nome='Cartório sintético revisado', cns='CNS-revisado', estado='SP',
        )
        self.pessoa = Pessoas.objects.create(nome='Pessoa sintética revisada')
        self.payload = payload_com_closure(self.job.job_id)
        ato = self.payload['acts'][0]
        for nome, valor in (
            ('numero_lancamento', 'R-1'),
            ('titulo', 'Compra e venda'),
            ('forma', 'Escritura pública'),
            ('descricao', 'Descrição revisada'),
            ('observacoes', 'Observações revisadas'),
            ('eh_inicio_matricula', True),
        ):
            ato[nome] = self._campo(valor)
        ato['cartorio_transmissao'] = self.payload['document']['cartorio'].copy()
        ato['origem'] = {
            nome: self._campo(valor) for nome, valor in (
                ('tipo_documento', 'transcricao'), ('numero', '99'),
                ('livro', '3-A'), ('folha', '12'), ('data', '1990-01-02'),
                ('cartorio', 'Cartório de origem'),
            )
        }
        ato['partes'][1]['documento_identificacao'] = {
            'tipo': self._campo('RG'), 'valor': self._campo('RG-123'),
        }
        self._finalizar(self.payload)

    @staticmethod
    def _campo(valor):
        return {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False, 'evidencia': None,
        }

    def _finalizar(self, payload):
        # Finalização direta: estes testes exercitam a leitura, não a UI.
        self.job.extracoes.update(finalizada_em=None)
        self.extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
            finalizada_em=timezone.now(),
        )
        linhas = desnormalizar(self.extracao, payload, [self.pagina])
        for linha in linhas:
            linha.status_revisao = 'aceito'
            if linha.tipo_valor == 'cartorio':
                linha.cartorio_escolhido = self.cartorio
            elif linha.tipo_valor == 'parte':
                if linha.chave == '/acts/0/partes/0':
                    linha.pessoa_escolhida = self.pessoa
                else:
                    linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)

    def test_transmissao_preenchida_tipadas_fora_da_conferencia(self):
        esperados = {
            'livro_transacao': '10-A',
            'folha_transacao': '25v',
            'data_transacao': date(2019, 12, 20),
        }
        for nome, valor in esperados.items():
            atualizado = self.extracao.campos.filter(
                chave=f'/acts/0/{nome}',
            ).update(valor_final=str(valor))
            self.assertEqual(atualizado, 1)

        dados = dados_revisados(self.extracao)

        for nome, esperado in esperados.items():
            with self.subTest(nome=nome):
                self.assertEqual(getattr(dados.atos[0], nome), esperado)
                self.assertIsInstance(getattr(dados.atos[0], nome), type(esperado))
                self.assertNotIn(f'/acts/0/{nome}', dados.conferencia)

    def test_transmissao_vazia_e_none(self):
        chaves = [
            f'/acts/0/{nome}' for nome in (
                'livro_transacao', 'folha_transacao', 'data_transacao',
            )
        ]
        self.assertEqual(self.extracao.campos.filter(chave__in=chaves).count(), 3)
        for vazio in (None, ''):
            with self.subTest(vazio=vazio):
                self.extracao.campos.filter(chave__in=chaves).update(valor_final=vazio)
                dados = dados_revisados(self.extracao)
                for chave in chaves:
                    self.assertIsNone(getattr(dados.atos[0], chave.rsplit('/', 1)[1]))
                    self.assertNotIn(chave, dados.conferencia)

    def test_transmissao_sem_linhas_e_none(self):
        nomes = ('livro_transacao', 'folha_transacao', 'data_transacao')
        self.extracao.campos.filter(
            chave__in=[f'/acts/0/{nome}' for nome in nomes],
        ).delete()

        dados = dados_revisados(self.extracao)

        for nome in nomes:
            with self.subTest(nome=nome):
                self.assertIsNone(getattr(dados.atos[0], nome))
                self.assertNotIn(f'/acts/0/{nome}', dados.conferencia)

    def test_dados_revisados_tipados(self):
        for chave, valor in (
            ('/document/data', '2020-01-11'),
            ('/document/livro', ''),
            ('/acts/0/data', '2020-02-16'),
            ('/acts/0/area', '0.0000'),
            ('/acts/0/eh_inicio_matricula', 'false'),
        ):
            self.extracao.campos.filter(chave=chave).update(valor_final=valor)

        dados = dados_revisados(self.extracao)

        self.assertIsInstance(dados, DadosRevisados)
        self.assertIsInstance(dados.documento, DocumentoRevisado)
        self.assertEqual(dados.documento.tipo, 'matricula')
        self.assertEqual(dados.documento.numero, '42.718')
        self.assertEqual(dados.documento.data, date(2020, 1, 11))
        self.assertIsInstance(dados.documento.data, date)
        self.assertEqual(dados.documento.cartorio_id, self.cartorio.pk)
        self.assertEqual(dados.documento.cri_atual_id, self.cartorio.pk)
        self.assertFalse(dados.documento.cartorio_criar_novo)
        self.assertFalse(dados.documento.cri_atual_criar_novo)
        self.assertIsNone(dados.documento.livro)
        self.assertEqual(dados.documento.folha, '087')
        self.assertIsInstance(dados.atos, tuple)
        self.assertEqual(len(dados.atos), 1)
        ato = dados.atos[0]
        self.assertIsInstance(ato, AtoRevisado)
        self.assertEqual(ato.ordem, 1)
        self.assertEqual(ato.tipo, 'registro')
        self.assertEqual(ato.numero_lancamento, 'R-1')
        self.assertEqual(ato.data, date(2020, 2, 16))
        self.assertIsInstance(ato.data, date)
        self.assertEqual(ato.area, Decimal('0.0000'))
        self.assertIsInstance(ato.area, Decimal)
        self.assertIs(ato.eh_inicio_matricula, False)
        self.assertEqual(ato.titulo, 'Compra e venda')
        self.assertEqual(ato.forma, 'Escritura pública')
        self.assertEqual(ato.descricao, 'Descrição revisada')
        self.assertEqual(ato.observacoes, 'Observações revisadas')
        self.assertEqual(ato.cartorio_origem_id, self.cartorio.pk)
        self.assertEqual(ato.cartorio_transmissao_id, self.cartorio.pk)
        self.assertFalse(ato.cartorio_origem_criar_novo)
        self.assertFalse(ato.cartorio_transmissao_criar_novo)
        self.assertEqual(ato.origem, {
            'tipo_documento': 'transcricao', 'numero': '99',
            'cartorio_id': self.cartorio.pk, 'livro': '3-A', 'folha': '12',
            'cartorio_criar_novo': False,
            'cartorio_nome': 'Cartório de origem',
            'data': date(1990, 1, 2),
        })
        self.assertIsInstance(ato.partes, tuple)
        self.assertEqual(ato.partes, (
            ParteRevisada(
                'transmitente', 'JOÃO DA SILVA', '12345678900', None,
                self.pessoa.pk, False, chave='/acts/0/partes/0',
            ),
            ParteRevisada(
                'transmitente', 'MARIA DA SILVA', None, 'RG-123', None, True,
                chave='/acts/0/partes/1',
            ),
            ParteRevisada(
                'adquirente', 'PEDRO SANTOS', None, None, None, True,
                chave='/acts/0/partes/2',
            ),
        ))

    def test_dados_revisados_recusa_job_nao_revisado(self):
        self.job.status = 'extraido'
        self.job.save(update_fields=['status'])
        with self.assertRaises(RevisaoInvalidada) as erro:
            dados_revisados(self.extracao)
        self.assertEqual(erro.exception.code, 'revisao_invalida')

    def test_dados_revisados_recusa_extracao_nao_vigente(self):
        ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload={}, payload_servico={}, provider='local-model',
        )
        with self.assertRaises(RevisaoInvalidada):
            dados_revisados(self.extracao)

    def test_dados_revisados_recusa_extracao_nao_finalizada(self):
        self.extracao.finalizada_em = None
        self.extracao.save(update_fields=['finalizada_em'])
        with self.assertRaises(RevisaoInvalidada):
            dados_revisados(self.extracao)

    def test_dados_revisados_recusa_pendencia(self):
        self.extracao.campos.filter(chave='/document/data').update(
            status_revisao='sugerido', requer_revisao=True,
        )
        with self.assertRaises(RevisaoInvalidada):
            dados_revisados(self.extracao)

    def test_dados_revisados_recusa_decisao_perdida_em_revisado(self):
        carregada = ExtracaoSugerida.objects.prefetch_related('campos').get(
            pk=self.extracao.pk,
        )
        self.assertEqual(pendencias(carregada), [])
        self.pessoa.delete()

        for extracao in (carregada, self.extracao):
            with self.subTest(cache=extracao is carregada):
                self.assertEqual(extracao.ocr_job.status, 'revisado')
                self.assertIsNotNone(extracao.finalizada_em)
                with self.assertRaises(RevisaoInvalidada):
                    dados_revisados(extracao)

    def test_conferencia_guarda_sem_destino(self):
        self.extracao.campos.filter(chave='/document/imovel_descricao').update(
            valor_final='Descrição conferida',
        )
        self.extracao.campos.filter(chave='/closure/origem_publica_sugerida').update(
            valor_final='',
        )
        self.extracao.campos.filter(chave='/closure/classificacao_sugerida').update(
            status_revisao='descartado',
        )
        self.extracao.campos.filter(
            chave='/acts/0/partes/0/documento_identificacao/valor',
        ).update(valor_final='***45678900')
        self.extracao.campos.filter(chave='/acts/0/partes/2').update(
            valor_final='conjuge',
        )

        dados = dados_revisados(self.extracao)

        self.assertEqual(dados.conferencia, {
            '/document/imovel_descricao': 'Descrição conferida',
            '/document/area': '12.5',
            '/acts/0/rotulo': 'R-1',
            '/acts/0/partes/0/documento_identificacao/tipo': 'CPF',
            '/acts/0/partes/0/documento_identificacao/valor': '***45678900',
            '/acts/0/partes/1/documento_identificacao/tipo': 'RG',
            '/acts/0/partes/2': 'conjuge',
            '/closure/indicio_fim_cadeia': 'true',
            '/closure/origem_publica_sugerida': '',
        })
        self.assertIsNone(dados.atos[0].partes[0].cpf)
        self.assertEqual(len(dados.atos[0].partes), 2)

    def test_linha_antiga_de_valor_transacao_e_ignorada(self):
        """Tarefa C #322: extração antiga salva com a linha não bloqueia.

        O formulário de lançamento não tem valor_transacao: a linha antiga,
        mesmo pendente, não vira pendência nem impede a leitura revisada.
        """
        self._finalizar(self.payload)
        self.extracao.campos.create(
            chave='/acts/0/valor_transacao',
            raw='R$ 999.999.999,99',
            normalized='999999999.99',
            tipo_valor='decimal',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        citadas = {item['chave'] for item in pendencias(self.extracao)}
        self.assertNotIn('/acts/0/valor_transacao', citadas)

        dados = dados_revisados(self.extracao)
        self.assertEqual(len(dados.atos), 1)

    def test_linha_antiga_de_detalhes_e_ignorada(self):
        """#328 (regra 11/11): extração antiga salva com a linha não bloqueia.

        O formulário de lançamento não tem detalhes: a linha antiga, mesmo
        pendente, não vira pendência nem impede a leitura revisada.
        """
        self._finalizar(self.payload)
        self.extracao.campos.create(
            chave='/acts/0/detalhes',
            raw='Detalhes antigos',
            normalized='Detalhes antigos',
            tipo_valor='texto',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        citadas = {item['chave'] for item in pendencias(self.extracao)}
        self.assertNotIn('/acts/0/detalhes', citadas)

        dados = dados_revisados(self.extracao)
        self.assertEqual(len(dados.atos), 1)

    def test_dados_revisados_ordena_atos_e_respeita_descartes(self):
        self.payload['acts'][0]['ordem'] = 2
        for numero, ordem in (('Av-2', 1), ('Av-3', 1), ('Av-4', 1)):
            ato = payload_averbacao(self.job.job_id)['acts'][0]
            ato['ordem'] = ordem
            ato['numero_lancamento'] = self._campo(numero)
            self.payload['acts'].append(ato)
        self._finalizar(self.payload)
        for chave in ('/acts/3', '/acts/0/partes/1'):
            self.extracao.campos.filter(chave=chave).update(
                status_revisao='descartado',
            )
        self.extracao.campos.filter(chave='/acts/0/partes/0').update(
            valor_final='adquirente',
        )

        dados = dados_revisados(self.extracao)

        self.assertEqual(
            [ato.numero_lancamento for ato in dados.atos], ['Av-2', 'Av-3', 'R-1'],
        )
        self.assertEqual([ato.ordem for ato in dados.atos], [1, 1, 2])
        self.assertIsNone(dados.atos[0].origem)
        registro = dados.atos[2]
        self.assertEqual([parte.papel for parte in registro.partes], [
            'adquirente', 'adquirente',
        ])
        self.assertFalse(any(
            chave.startswith(('/acts/3', '/acts/0/partes/1'))
            for chave in dados.conferencia
        ))

    def test_dados_revisados_cartorio_escolhido_precede_candidato_unico(self):
        outro = Cartorios.objects.create(
            nome='Outro cartório sintético', cns='CNS-outro', estado='SP',
        )
        self.extracao.campos.filter(chave='/document/cartorio').update(
            match_candidatos=[outro.pk],
        )
        self.extracao.campos.filter(chave='/document/cri_atual').update(
            cartorio_escolhido=None, match_candidatos=[outro.pk], criar_novo=True,
        )

        dados = dados_revisados(self.extracao)

        self.assertEqual(dados.documento.cartorio_id, self.cartorio.pk)
        self.assertIsNone(dados.documento.cri_atual_id)
        self.assertTrue(dados.documento.cri_atual_criar_novo)
