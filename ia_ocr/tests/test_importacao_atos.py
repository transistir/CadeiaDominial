"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from datetime import date
from decimal import Decimal
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)
from .test_importacao_base import ImportacaoBase


class CaminhoFelizTest(ImportacaoBase):
    """Cenário 1: o registro inteiro vira lançamento com pessoas."""

    def test_transmissao_preenchida_grava_colunas_com_texto_sem_bordas(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        for nome, valor in (
            ('livro_transacao', ' 10-A '), ('folha_transacao', ' 25v '),
            ('data_transacao', '2019-12-20'),
        ):
            atualizado = extracao.campos.filter(chave=f'/acts/0/{nome}').update(
                valor_final=valor, status_revisao='editado',
            )
            self.assertEqual(atualizado, 1)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.livro_transacao, '10-A')
        self.assertEqual(lancamento.folha_transacao, '25v')
        self.assertEqual(lancamento.data_transacao, date(2019, 12, 20))
        self.assertEqual(lancamento.data, date(2020, 2, 15))

    def test_transmissao_do_payload_grava_sem_confundir_com_origem(self):
        payload = self._payload_origem()
        for nome, valor in (
            ('livro_transacao', '10-A'), ('folha_transacao', '25v'),
            ('data_transacao', '2019-12-20'),
        ):
            payload['acts'][0][nome] = self._campo(valor)
        payload['acts'][0]['origem']['data'] = self._campo('1990-01-02')
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.livro_transacao, '10-A')
        self.assertEqual(lancamento.folha_transacao, '25v')
        self.assertEqual(lancamento.data_transacao, date(2019, 12, 20))
        self.assertEqual(lancamento.livro_origem, '2')
        self.assertEqual(lancamento.folha_origem, '123')
        self.assertEqual(lancamento.data_origem, date(1990, 1, 2))

    def test_transmissao_vazia_grava_none_sem_bloquear(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        for nome in ('livro_transacao', 'folha_transacao', 'data_transacao'):
            atualizado = extracao.campos.filter(chave=f'/acts/0/{nome}').update(
                valor_final='', status_revisao='editado',
            )
            self.assertEqual(atualizado, 1)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertIsNone(lancamento.livro_transacao)
        self.assertIsNone(lancamento.folha_transacao)
        self.assertIsNone(lancamento.data_transacao)

    def test_transmissao_texto_so_com_espacos_grava_none(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        for nome in ('livro_transacao', 'folha_transacao'):
            atualizado = extracao.campos.filter(chave=f'/acts/0/{nome}').update(
                valor_final=' \t\n ', status_revisao='editado',
            )
            self.assertEqual(atualizado, 1)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertIsNone(lancamento.livro_transacao)
        self.assertIsNone(lancamento.folha_transacao)
        self.assertIsNone(lancamento.data_transacao)

    def test_transmissao_extracao_legada_grava_none(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        extracao.campos.filter(chave__in=[
            f'/acts/0/{nome}' for nome in (
                'livro_transacao', 'folha_transacao', 'data_transacao',
            )
        ]).delete()

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertIsNone(lancamento.livro_transacao)
        self.assertIsNone(lancamento.folha_transacao)
        self.assertIsNone(lancamento.data_transacao)

    def test_registro_vira_lancamento_com_partes_e_transicao(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (lancamento,) = Lancamento.objects.all()
        self.assertEqual(lancamento.documento, self.documento)
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(lancamento.data, date(2020, 2, 15))
        # Tarefa C #322: valor_transacao não existe no formulário de
        # lançamento — não é importado, mesmo vindo no payload do A3.
        self.assertIsNone(lancamento.valor_transacao)
        self.assertEqual(lancamento.area, Decimal('12.50'))
        # 2 transmitentes + 1 adquirente: a parte sem identificação é só
        # sugestão (requer_revisao falso) e ainda assim entra — a finalização
        # da revisão é o aceite humano (#263-I6-B).
        self.assertEqual(lancamento.pessoas.count(), 3)
        self.assertEqual(lancamento.pessoas.filter(tipo='transmitente').count(), 2)
        joao = Pessoas.objects.get(cpf='12345678900')
        self.assertEqual(joao.nome, 'JOÃO DA SILVA')
        pedro = LancamentoPessoa.objects.get(
            lancamento=lancamento, tipo='adquirente',
        )
        self.assertEqual(pedro.nome_digitado, 'PEDRO SANTOS')
        self.assertIsNone(pedro.pessoa.cpf)

        # Job transiciona com auditoria e as linhas do ato viram importadas.
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
        (transicao,) = self.job.transicoes.all()
        self.assertEqual(transicao.para_status, 'importado')
        self.assertEqual(transicao.motivo, 'importacao_ia')
        self.assertEqual(transicao.usuario, self.usuario)
        self.assertFalse(
            extracao.campos
            .filter(chave__startswith='/acts/0')
            .exclude(status_revisao='importado')
            .exists()
        )

        (linha,) = resultado['linhas']
        self.assertEqual(linha['chave'], '/acts/0')
        self.assertEqual(linha['rotulo'], 'R-1')
        self.assertEqual(linha['status'], 'criado')
        self.assertEqual(linha['lancamento_id'], lancamento.pk)
        self.assertEqual(linha['url'], self.url_lancamento(lancamento))

    def test_linha_antiga_de_valor_transacao_e_ignorada(self):
        """Tarefa C #322: extração antiga salva com a linha importa sem erro.

        SHOULD-FIX (revisão Opus): a linha antiga é uma que BLOQUEARIA sem o
        filtro — pendente com ``requer_revisao=True`` viraria
        ``revisao_pendente`` e ``dados_revisados`` recusaria a extração.
        """
        extracao = self._extracao(payload_registro(self.job.job_id))
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/valor_transacao',
            raw='R$ 150.000,00',
            normalized='150000.00',
            tipo_valor='decimal',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (lancamento,) = Lancamento.objects.all()
        self.assertIsNone(lancamento.valor_transacao)
        self.assertEqual(lancamento.area, Decimal('12.50'))

    def test_detalhes_do_payload_nao_e_importado(self):
        """#328: detalhes não existe no formulário de lançamento — não é
        importado, mesmo vindo no payload do A3."""
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['detalhes'] = self._campo(
            'Detalhes do ato', 'Escritura Pública de Compra e Venda',
        )
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (lancamento,) = Lancamento.objects.all()
        self.assertIsNone(lancamento.detalhes)

    def test_linha_antiga_de_detalhes_e_ignorada(self):
        """#328: extração antiga salva com a linha importa sem erro.

        Sem o filtro, a linha pendente com ``requer_revisao=True`` viraria
        ``revisao_pendente`` e ``dados_revisados`` recusaria a extração
        (mesmo caso do valor_transacao, Tarefa C #322).
        """
        extracao = self._extracao(payload_registro(self.job.job_id))
        CampoSugerido.objects.create(
            extracao=extracao,
            chave='/acts/0/detalhes',
            raw='Detalhes antigos',
            normalized='Detalhes antigos',
            tipo_valor='texto',
            status_revisao='sugerido',
            requer_revisao=True,
        )

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (lancamento,) = Lancamento.objects.all()
        self.assertIsNone(lancamento.detalhes)
        self.assertEqual(lancamento.area, Decimal('12.50'))


class VinculoOrigemTest(ImportacaoBase):
    """Cenário 2: origem estruturada + vínculo de auditoria com PDF."""

    def test_origem_estruturada_com_cartorio_proprio(self):
        extracao = self._extracao(self._payload_origem())

        self._importar(extracao)

        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.origem, 'T366')
        self.assertEqual(lancamento.livro_origem, '2')
        self.assertEqual(lancamento.folha_origem, '123')
        self.assertEqual(lancamento.cartorio_origem.nome, 'CRI de Origem')
        origem = LancamentoOrigem.objects.get()
        self.assertEqual(origem.lancamento, lancamento)
        self.assertEqual(origem.tipo_documento, 'transcricao')
        self.assertEqual(origem.numero, 'T366')
        self.assertEqual(origem.numero_normalizado, '366')
        self.assertEqual(origem.livro, '2')
        self.assertEqual(origem.folha, '123')
        self.assertEqual(origem.cartorio, lancamento.cartorio_origem)

        # Registro comum NÃO gera documento de origem: a regra anti-órfão do
        # fluxo manual só cria para início de matrícula (abaixo).
        self.assertEqual(Documento.objects.count(), 1)

        # Vínculo de auditoria: página e trecho saem da linha estrutural.
        vinculo = ImportacaoIA.objects.get(modelo='Lancamento')
        self.assertEqual(vinculo.campo.chave, '/acts/0')
        self.assertEqual(vinculo.pagina, 1)
        self.assertIn('R-1/42.718', vinculo.campo.evidencia_trecho)
        self.assertEqual(vinculo.documento_digital_id, self.arquivo.pk)
        self.assertEqual(vinculo.lancamento, lancamento)
        self.assertEqual(vinculo.criado_por, self.usuario)
        vinculo_origem = ImportacaoIA.objects.get(modelo='LancamentoOrigem')
        self.assertEqual(vinculo_origem.campo.chave, '/acts/0/origem/numero')
        self.assertTrue(
            ImportacaoIA.objects.filter(modelo='Cartorios').exists()
        )

    def test_inicio_de_matricula_cria_o_documento_de_origem(self):
        # A regra pétrea do anti-órfão: início de matrícula cria o documento
        # da origem quando ele não existe em lugar nenhum.
        DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        # Rótulo de MATRÍCULA: com o rótulo prevalecendo (#322 rodada 3),
        # o 'R-1' do payload-base faria o ato virar registro.
        payload['acts'][0]['rotulo'] = self._campo('M-1', 'R-1/42.718')
        extracao = self._extracao(payload)

        self._importar(extracao)

        self.assertEqual(Lancamento.objects.get().tipo.tipo, 'inicio_matricula')
        (documento_origem,) = Documento.objects.exclude(pk=self.documento.pk)
        self.assertEqual(documento_origem.numero, 'T366')
        self.assertEqual(documento_origem.imovel, self.imovel)
        self.assertEqual(LancamentoOrigem.objects.count(), 1)


class PrefixoIncompativelTest(ImportacaoBase):
    """Cenário 3: prefixo da origem briga com o tipo documental."""

    def test_prefixo_t_com_matricula_e_erro_na_linha_da_origem(self):
        payload = self._payload_origem()
        payload['acts'][0]['origem']['tipo_documento'] = self._campo(
            'matricula', 'MATRÍCULA Nº 42.718',
        )
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/origem/numero')
        self.assertEqual(erro['codigo'], 'valor_incompativel_destino')
        # Rollback total: nada gravado, job segue revisado.
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(Cartorios.objects.count(), 1)  # só o do factory
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')
        self.assertFalse(
            extracao.campos.filter(status_revisao='importado').exists()
        )


class ForaDoEscopoTest(ImportacaoBase):
    """Cenário 10: cabeçalho, cônjuge e closure não gravam nada."""

    def test_cabecalho_conjuge_e_closure_ficam_em_conferencia(self):
        payload = payload_com_closure(self.job.job_id)
        payload['acts'][0]['partes'].append({
            'papel': 'conjuge',
            'nome': self._campo('MARIA DE SOUZA', 'MARIA DA SILVA'),
            'documento_identificacao': None,
            'confianca': 0.9,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': 'MARIA DA SILVA'},
        })
        extracao = self._extracao(payload)
        # Closure é sempre decisão humana: as linhas precisam de um aceite
        # explícito antes de a revisão finalizar sem pendências.
        extracao.campos.filter(chave__startswith='/closure').update(
            status_revisao='aceito',
        )
        antes = Documento.objects.get(pk=self.documento.pk)

        self._importar(extracao)

        # Cabeçalho /document/* é só conferência: o Documento fica intacto.
        depois = Documento.objects.get(pk=self.documento.pk)
        self.assertEqual(antes.numero, depois.numero)
        self.assertEqual(antes.livro, depois.livro)
        self.assertEqual(antes.folha, depois.folha)
        self.assertEqual(antes.cartorio_id, depois.cartorio_id)
        self.assertEqual(Documento.objects.count(), 1)
        # Cônjuge é SEM_DESTINO: não vira LancamentoPessoa nem Pessoas.
        self.assertEqual(Lancamento.objects.get().pessoas.count(), 3)
        self.assertFalse(Pessoas.objects.filter(nome='MARIA DE SOUZA').exists())
        # Closure segue em conferência: nenhuma linha muda de status.
        self.assertFalse(
            extracao.campos
            .filter(chave__startswith='/closure')
            .filter(status_revisao='importado')
            .exists()
        )
