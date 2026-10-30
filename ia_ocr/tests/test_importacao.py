"""Testes da importação assistida da revisão finalizada (I-6 / #263).

O serviço grava os atos marcados de uma extração finalizada em lançamentos
do dominial, com savepoint por ato e rollback total ao primeiro erro. Os
payloads são os mesmos sintéticos da revisão (nada de documento real), e a
decisão B (#263-I6-B) está em jogo no caminho feliz: linha ``sugerido`` sem
``requer_revisao`` entra na importação porque a finalização da revisão já é
o aceite humano.
"""

import io
import threading
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import (
    RequestFactory, TestCase, TransactionTestCase, skipUnlessDBFeature,
)
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, UserTI,
)
from dominial.services.lancamento_criacao_service import LancamentoCriacaoService
from dominial.services.lancamento_origem_service import LancamentoOrigemService
from dominial.tests.test_issue_263_concorrencia_importacao import (
    travas_executadas,
)
from ia_ocr import importacao as modulo_importacao
from ia_ocr import services
from ia_ocr.estados import TransicaoConcorrente
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    ParteRevisada, RevisaoInvalidada, dados_revisados, desnormalizar,
)

from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)
from .test_texto_concorrencia_pg import _rodar

ESPERA_S = 10
BLOQUEIO_S = 1.0


class ImportacaoFixture:
    """Job ``revisado`` com extração finalizada, pronto para importar.

    Mixin (sem ``TestCase``) para a mesma montagem servir à classe de
    concorrência real em PostgreSQL (``TransactionTestCase``).
    """

    def setUp(self):
        self.usuario = criar_usuario()
        self.arquivo = criar_documento_digital(upload_por=self.usuario)
        UserTI.objects.create(
            user=self.usuario,
            tis=self.arquivo.documento.imovel.terra_indigena_id,
        )
        self.documento = self.arquivo.documento
        self.imovel = self.documento.imovel
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        self.pagina = PaginaOcr.objects.create(
            ocr_job=self.job, numero_pagina=1, texto_ocr=TEXTO_PAGINA_1,
        )
        self.tipo_registro = LancamentoTipo.objects.create(tipo='registro')

    @staticmethod
    def _campo(valor, trecho=None):
        campo = {
            'raw': valor, 'normalized': valor, 'confianca': 0.95,
            'requer_revisao': False,
        }
        if trecho:
            campo['evidencia'] = {'pagina': 1, 'trecho': trecho}
        return campo

    def _extracao(self, payload):
        extracao = ExtracaoSugerida.objects.create(
            ocr_job=self.job, schema_version=SCHEMA_VERSION,
            payload=payload, payload_servico=payload, provider='local-model',
        )
        linhas = desnormalizar(extracao, payload, [self.pagina])
        for linha in linhas:
            if linha.tipo_valor in ('parte', 'cartorio'):
                linha.criar_novo = True
        CampoSugerido.objects.bulk_create(linhas)
        extracao.finalizada_em = timezone.now()
        extracao.save(update_fields=['finalizada_em'])
        return extracao

    def _todos_os_atos(self, extracao):
        return [
            f'/acts/{indice}' for indice in range(len(extracao.payload['acts']))
        ]

    def _importar(self, extracao, atos=None, versao=None):
        return importar(
            extracao, self.usuario,
            versao if versao is not None else services.versao_bloco(extracao),
            atos if atos is not None else self._todos_os_atos(extracao),
        )

    def _payload_origem(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('transcricao', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('T366', '42.718'),
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        return payload

    def _payload_com_numero(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['numero_lancamento'] = self._campo('R-1', 'R-1/42.718')
        return payload

    def url_lancamento(self, lancamento):
        return reverse('editar_lancamento', kwargs={
            'tis_id': self.imovel.terra_indigena_id_id,
            'imovel_id': self.imovel.pk,
            'lancamento_id': lancamento.pk,
        })


class ImportacaoBase(ImportacaoFixture, TestCase):
    """Job ``revisado`` com extração finalizada, pronto para importar."""


class CaminhoFelizTest(ImportacaoBase):
    """Cenário 1: o registro inteiro vira lançamento com pessoas."""

    def test_registro_vira_lancamento_com_partes_e_transicao(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (lancamento,) = Lancamento.objects.all()
        self.assertEqual(lancamento.documento, self.documento)
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(lancamento.data, date(2020, 2, 15))
        self.assertEqual(lancamento.valor_transacao, Decimal('150000.00'))
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


class DuplicidadeTest(ImportacaoBase):
    """Cenário 4: as três formas de cair no lançamento já existente."""

    def setUp(self):
        super().setUp()
        self.extracao = self._extracao(self._payload_com_numero())

    def _existente(self, numero, tipo=None, data=None):
        return Lancamento.objects.create(
            documento=self.documento,
            tipo=tipo or self.tipo_registro,
            numero_lancamento=numero,
            data=data or date(2020, 2, 15),
        )

    def _erros(self):
        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(self.extracao)
        return contexto.exception.linhas[0]['erros']

    def test_mesma_tupla_documento_tipo_data_numero(self):
        existente = self._existente('R-1')

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['chave'], '/acts/0')
        self.assertEqual(erro['existente']['id'], existente.pk)
        self.assertEqual(
            erro['existente']['url'], self.url_lancamento(existente),
        )
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_mesmo_numero_com_tipo_e_data_diferentes(self):
        tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')
        existente = self._existente(
            'R-1', tipo=tipo_averbacao, data=date(2021, 1, 1),
        )

        (erro,) = self._erros()

        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)

    def test_numero_nulo_casa_com_existente_sem_numero(self):
        # Uma extração finalizada por job (constraint): o mesmo documento
        # ganha um SEGUNDO job revisado para o payload sem número.
        self.job.status = 'importado'
        self.job.save(update_fields=['status'])
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        extracao = self._extracao(payload_registro(self.job.job_id))
        self._existente(None)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')


class PessoaReutilizadaTest(ImportacaoBase):
    """Cenário 5: decisão D — CPF existente reutiliza, homônimo cria."""

    def _extracao_pronta(self):
        return self._extracao(payload_registro(self.job.job_id))

    def test_pessoa_escolhida_nao_cria_nova(self):
        extracao = self._extracao_pronta()
        maria = Pessoas.objects.create(nome='MARIA EXISTENTE', cpf='98765432100')
        CampoSugerido.objects.filter(chave='/acts/0/partes/1').update(
            pessoa_escolhida=maria, criar_novo=False,
        )
        antes = Pessoas.objects.count()

        self._importar(extracao)

        # JOÃO e PEDRO são criados; MARIA é a escolhida reutilizada.
        self.assertEqual(Pessoas.objects.count(), antes + 2)
        self.assertEqual(
            LancamentoPessoa.objects.filter(pessoa=maria).count(), 1,
        )

    def test_criar_novo_com_cpf_ja_existente_reutiliza(self):
        extracao = self._extracao_pronta()
        joao = Pessoas.objects.create(nome='JOÃO CADASTRADO', cpf='12345678900')
        antes = Pessoas.objects.count()

        self._importar(extracao)

        self.assertEqual(Pessoas.objects.count(), antes + 2)
        joao.refresh_from_db()
        self.assertEqual(joao.nome, 'JOÃO CADASTRADO')
        self.assertEqual(
            LancamentoPessoa.objects.filter(pessoa=joao).count(), 1,
        )

    def test_mesma_pessoa_em_dois_atos_e_criada_uma_vez(self):
        payload = payload_registro(self.job.job_id)
        segundo = deepcopy(payload['acts'][0])
        segundo['ordem'] = 2
        segundo['data'] = self._campo('2021-03-20', '20 de março de 2021')
        payload['acts'].append(segundo)
        extracao = self._extracao(payload)

        self._importar(extracao)

        self.assertEqual(
            Pessoas.objects.filter(cpf='12345678900').count(), 1,
        )
        self.assertEqual(Lancamento.objects.count(), 2)
        self.assertEqual(
            LancamentoPessoa.objects.filter(
                pessoa__cpf='12345678900', tipo='transmitente',
            ).count(),
            2,
        )


class RollbackTardioTest(ImportacaoBase):
    """Cenário 6: falha na transição final desfaz tudo que foi gravado."""

    def test_transicao_concorrente_desfaz_a_importacao(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        antes = (
            Lancamento.objects.count(),
            LancamentoPessoa.objects.count(),
            Pessoas.objects.count(),
            Cartorios.objects.count(),
            ImportacaoIA.objects.count(),
        )

        with patch.object(
            OcrJob, 'transicionar',
            side_effect=TransicaoConcorrente('CAS perdido'),
        ):
            with self.assertRaises(TransicaoConcorrente):
                self._importar(extracao)

        self.assertEqual(
            (
                Lancamento.objects.count(),
                LancamentoPessoa.objects.count(),
                Pessoas.objects.count(),
                Cartorios.objects.count(),
                ImportacaoIA.objects.count(),
            ),
            antes,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')
        self.assertFalse(
            extracao.campos.filter(status_revisao='importado').exists()
        )


class ErroPorCampoTest(ImportacaoBase):
    """Cenário 7: message_dict do full_clean vira erro na linha do ato."""

    def test_erro_de_campo_mapeia_para_a_chave_do_titulo(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        # Defesa em profundidade: a revisão já teria bloqueado um título
        # fora do limite; o patch isola o MAPEAMENTO do message_dict do
        # modelo para a chave de linha que a tela conhece.
        with patch.object(
            Lancamento, 'full_clean',
            side_effect=ValidationError({'titulo': ['Fora do limite.']}),
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/titulo')
        self.assertEqual(erro['codigo'], 'campo_invalido')
        self.assertEqual(erro['mensagem'], 'Fora do limite.')
        self.assertEqual(Lancamento.objects.count(), 0)


class EstadoEVersaoTest(ImportacaoBase):
    """Cenários 8 e 9: estado do job, idempotência, versão e atos marcados."""

    def test_job_extraido_recusa_com_estado_invalido(self):
        self.job.status = 'extraido'
        self.job.save(update_fields=['status'])
        extracao = self._extracao(payload_registro(self.job.job_id))

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            self._importar(extracao)

        self.assertEqual(contexto.exception.code, 'estado_invalido')

    def test_importado_e_idempotente_com_a_mesma_versao_da_tela(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        versao_tela = services.versao_bloco(extracao)

        primeiro = importar(extracao, self.usuario, versao_tela, ['/acts/0'])
        # A tela não recarregou: manda a mesma versão (agora velha — as
        # linhas viraram importado). O job importado responde o resultado
        # gravado em vez de conflitar.
        segundo = importar(extracao, self.usuario, versao_tela, ['/acts/0'])

        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertTrue(segundo['ok'])
        self.assertEqual(segundo['linhas'][0]['status'], 'criado')
        self.assertEqual(
            segundo['linhas'][0]['lancamento_id'],
            primeiro['linhas'][0]['lancamento_id'],
        )
        self.assertEqual(
            self.job.transicoes.filter(para_status='importado').count(), 1,
        )

    def test_versao_velha_e_conflito(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        versao_tela = services.versao_bloco(extracao)
        # A revisão mudou depois que a tela leu o token.
        CampoSugerido.objects.filter(chave='/acts/0/area').update(
            valor_final='9.99',
        )

        with self.assertRaises(services.ConflitoVersao):
            importar(extracao, self.usuario, versao_tela, ['/acts/0'])

        self.assertEqual(Lancamento.objects.count(), 0)

    def test_ato_desmarcado_aparece_ignorado(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'].append(
            deepcopy(payload['acts'][0]) | {'ordem': 2}
        )
        payload['acts'][1]['data'] = self._campo(
            '2021-03-20', '20 de março de 2021',
        )
        extracao = self._extracao(payload)

        resultado = self._importar(extracao, atos=['/acts/0'])

        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(len(resultado['linhas']), 2)
        ignorado = resultado['linhas'][1]
        self.assertEqual(ignorado['chave'], '/acts/1')
        self.assertEqual(ignorado['status'], 'ignorado')
        self.assertIsNone(ignorado['lancamento_id'])
        self.assertFalse(
            extracao.campos
            .filter(chave__startswith='/acts/1')
            .filter(status_revisao='importado')
            .exists()
        )

    def test_ato_inexistente_recusa(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            self._importar(extracao, atos=['/acts/9'])

        self.assertEqual(contexto.exception.code, 'ato_invalido')

    def test_lista_vazia_recusa(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with self.assertRaises(services.ExtracaoRecusada) as contexto:
            self._importar(extracao, atos=[])

        self.assertEqual(contexto.exception.code, 'nenhum_ato')


class DecisaoPerdidaTest(ImportacaoBase):
    """Cadastro escolhido (pessoa/cartório) deletado após a finalização."""

    def test_pessoa_deletada_deixa_a_revisao_invalida(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        maria = Pessoas.objects.create(nome='MARIA EXISTENTE', cpf='11122233344')
        extracao.campos.filter(chave='/acts/0/partes/1').update(
            pessoa_escolhida=maria, criar_novo=False,
        )
        # A tela leu o token ANTES da exclusão (#263 rodada 3): o SET_NULL
        # muda a linha e envelhece o token, mas a resposta tem de dizer
        # ONDE a decisão se perdeu — não um conflito de versão genérico.
        versao_tela = services.versao_bloco(extracao)
        # A escolha morre com a pessoa (FK SET_NULL): a linha volta a ser
        # pendência de escolha e o motor de revisão recusa antes da gravação.
        maria.delete()

        with self.assertRaises(RevisaoInvalidada):
            self._importar(extracao, versao=versao_tela)

        # Aceite da rodada 2 (#263): a recusa preserva as pendências
        # estruturadas para a tela identificar a parte — uma escolha que
        # virou nada depois da finalização é decisão perdida, não uma
        # pendência genérica de escolha.
        pendencias = modulo_importacao.pendencias_para_resposta(extracao)
        self.assertIn(
            {'chave': '/acts/0/partes/1', 'motivo': 'decisao_perdida'},
            pendencias,
        )

        self.assertEqual(Lancamento.objects.count(), 0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')

    def test_cartorio_da_origem_deletado_vira_decisao_perdida(self):
        # P3 (#263 rodada 3): ``cartorio_escolhido`` também é SET_NULL — a
        # pendência genérica de escolha vira decisão perdida na linha da
        # origem, como na parte.
        extracao = self._extracao(self._payload_origem())
        escolhido = Cartorios.objects.create(
            nome='CRI Escolhido', cns='CNS-263-ESC',
        )
        extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=escolhido, criar_novo=False,
        )
        versao_tela = services.versao_bloco(extracao)
        escolhido.delete()

        with self.assertRaises(RevisaoInvalidada):
            self._importar(extracao, versao=versao_tela)

        self.assertIn(
            {'chave': '/acts/0/origem/cartorio', 'motivo': 'decisao_perdida'},
            modulo_importacao.pendencias_para_resposta(extracao),
        )
        self.assertEqual(Lancamento.objects.count(), 0)


class CartorioSumiuNaGravacaoTest(ImportacaoBase):
    """P3 (#263 rodada 3): cartório escolhido que some DURANTE a gravação.

    A revisão foi lida com o cartório de pé; ele é excluído antes de o ato
    gravar (o ``Cartorios`` não é travado). Origem e transmissão viram
    ``decisao_perdida`` na linha do cartório — nunca o lançamento gravado
    sem ele.
    """

    def _escolher(self, extracao, chave):
        cartorio = Cartorios.objects.create(
            nome='CRI Escolhido', cns='CNS-263-SUM',
        )
        extracao.campos.filter(chave=chave).update(
            cartorio_escolhido=cartorio, criar_novo=False,
        )
        return cartorio

    def _importar_excluindo_no_meio(self, extracao, cartorio):
        marcar = modulo_importacao._atos_marcados

        def marcar_e_excluir(*args, **kwargs):
            # Já passou da leitura da revisão e do token: outro usuário
            # exclui o cartório agora.
            marcados = marcar(*args, **kwargs)
            cartorio.delete()
            return marcados

        with patch.object(
            modulo_importacao, '_atos_marcados', side_effect=marcar_e_excluir,
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)
        return contexto.exception.linhas[0]['erros']

    def test_cartorio_da_transmissao_excluido_e_decisao_perdida(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['cartorio_transmissao'] = self._campo(
            'CRI de Transmissão', 'CRI de Guaíra',
        )
        extracao = self._extracao(payload)
        cartorio = self._escolher(extracao, '/acts/0/cartorio_transmissao')

        (erro,) = self._importar_excluindo_no_meio(extracao, cartorio)

        self.assertEqual(erro['chave'], '/acts/0/cartorio_transmissao')
        self.assertEqual(erro['codigo'], 'decisao_perdida')
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_cartorio_da_origem_excluido_e_decisao_perdida(self):
        extracao = self._extracao(self._payload_origem())
        cartorio = self._escolher(extracao, '/acts/0/origem/cartorio')

        (erro,) = self._importar_excluindo_no_meio(extracao, cartorio)

        self.assertEqual(erro['chave'], '/acts/0/origem/cartorio')
        self.assertEqual(erro['codigo'], 'decisao_perdida')
        self.assertEqual(Lancamento.objects.count(), 0)


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


class ResumoTest(ImportacaoBase):
    def test_resumo_aponta_duplicado_sem_gravar(self):
        extracao = self._extracao(self._payload_com_numero())
        existente = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R-1', data=date(2020, 2, 15),
        )

        dados = resumo(extracao)

        (ato,) = dados['atos']
        self.assertEqual(ato['chave'], '/acts/0')
        self.assertEqual(ato['rotulo'], 'R-1')
        self.assertTrue(ato['duplicado'])
        self.assertEqual(ato['existente']['id'], existente.pk)
        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(self.job.status, 'revisado')

    def test_resumo_sem_duplicado(self):
        extracao = self._extracao(self._payload_com_numero())

        dados = resumo(extracao)

        (ato,) = dados['atos']
        self.assertFalse(ato['duplicado'])
        self.assertIsNone(ato['existente'])


# ---------------------------------------------------------------------------
# Rodada 2 (review Codex #263): corrida IA × manual, cache de pessoas,
# savepoint por ato, origem longa, linhas descartadas, auditoria do
# documento de origem, erro de pessoa ancorado na parte e stdout sem
# valor documental.
# ---------------------------------------------------------------------------


class PessoaCacheTest(ImportacaoBase):
    """P1-2 (#263 rodada 2): homônimos não podem fundir cadastros.

    A decisão D reaproveita por identificação (CPF; RG+nome dentro da
    mesma importação) — nunca por nome puro: homônimo existe.
    """

    @staticmethod
    def _parte_rg(papel, nome, rg):
        return {
            'papel': papel,
            'nome': {
                'raw': nome, 'normalized': nome, 'confianca': 0.92,
                'requer_revisao': False,
                'evidencia': {'pagina': 1, 'trecho': nome},
            },
            'documento_identificacao': {
                'tipo': {
                    'raw': 'RG', 'normalized': 'RG', 'confianca': 0.92,
                    'requer_revisao': False,
                    'evidencia': {'pagina': 1, 'trecho': nome},
                },
                'valor': {
                    'raw': rg, 'normalized': rg, 'confianca': 0.92,
                    'requer_revisao': False,
                    'evidencia': {'pagina': 1, 'trecho': nome},
                },
            },
            'confianca': 0.92,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': nome},
        }

    @staticmethod
    def _parte_sem_doc(papel, nome):
        return {
            'papel': papel,
            'nome': {
                'raw': nome, 'normalized': nome, 'confianca': 0.92,
                'requer_revisao': False,
                'evidencia': {'pagina': 1, 'trecho': nome},
            },
            'documento_identificacao': None,
            'confianca': 0.92,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': nome},
        }

    def _dois_atos(self, partes):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'] = deepcopy(partes)
        segundo = deepcopy(payload['acts'][0]) | {'ordem': 2}
        segundo['data'] = self._campo('2021-03-20', '20 de março de 2021')
        payload['acts'].append(segundo)
        return payload

    def test_rgs_distintos_com_o_mesmo_nome_criam_duas_pessoas(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'] = [
            self._parte_rg('transmitente', 'JOÃO DA SILVA', '12.345.678-9'),
            self._parte_rg('transmitente', 'JOÃO DA SILVA', '98.765.432-1'),
        ]
        extracao = self._extracao(payload)

        self._importar(extracao)

        homonimos = Pessoas.objects.filter(nome='JOÃO DA SILVA')
        self.assertEqual(homonimos.count(), 2)
        self.assertEqual(
            set(homonimos.values_list('rg', flat=True)),
            {'12.345.678-9', '98.765.432-1'},
        )

    def test_mesmo_nome_e_rg_em_dois_atos_cria_uma_pessoa(self):
        # O ato 2 repete o PEDRO do ato 1 (mesmo RG) e traz um homônimo com
        # OUTRO RG: só a chave nome+RG separa os dois. Cache por nome
        # fundiria o homônimo no PEDRO do ato 1; sem cache, o PEDRO do
        # ato 1 viraria dois cadastros (#263 rodada 3).
        payload = self._dois_atos(
            [self._parte_rg('adquirente', 'PEDRO SANTOS', '12.345.678-9')],
        )
        payload['acts'][1]['partes'].append(
            self._parte_rg('transmitente', 'PEDRO SANTOS', '98.765.432-1'),
        )
        extracao = self._extracao(payload)

        self._importar(extracao)

        pedros = Pessoas.objects.filter(nome='PEDRO SANTOS')
        self.assertEqual(
            sorted(pedros.values_list('rg', flat=True)),
            ['12.345.678-9', '98.765.432-1'],
        )
        self.assertEqual(
            LancamentoPessoa.objects.filter(
                pessoa=pedros.get(rg='12.345.678-9'),
            ).count(),
            2,
        )
        self.assertEqual(Lancamento.objects.count(), 2)

    def test_sem_identificacao_cria_uma_pessoa_por_ato(self):
        # Homônimo sem CPF/RG não é evidência de mesma pessoa (decisão D):
        # cada ato grava o seu cadastro.
        partes = [self._parte_sem_doc('adquirente', 'PEDRO SANTOS')]
        extracao = self._extracao(self._dois_atos(partes))

        self._importar(extracao)

        self.assertEqual(
            Pessoas.objects.filter(nome='PEDRO SANTOS').count(), 2,
        )


class PessoaConflitanteTest(ImportacaoBase):
    """P1-2 (#263 rodada 2): CPF e RG apontando para cadastros distintos.

    Checagem DEFENSIVA (#263 rodada 3): ``dados_revisados`` entrega CPF
    **ou** RG por parte — a linha ``documento_identificacao/valor`` tem um
    destino só, decidido pelo tipo. O primeiro teste prova isso no fluxo
    real; o segundo monta a ``ParteRevisada`` à mão para exercitar a
    checagem que fica de guarda caso o contrato da parte mude.
    """

    def test_fluxo_real_entrega_cpf_ou_rg_nunca_os_dois(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'][2] = PessoaCacheTest._parte_rg(
            'adquirente', 'PEDRO SANTOS', '12.345.678-9',
        )
        extracao = self._extracao(payload)

        (ato,) = dados_revisados(extracao).atos

        identificacoes = {
            parte.nome: (parte.cpf, parte.rg) for parte in ato.partes
        }
        self.assertEqual(
            identificacoes['JOÃO DA SILVA'], ('12345678900', None),
        )
        self.assertEqual(
            identificacoes['PEDRO SANTOS'], (None, '12.345.678-9'),
        )
        for cpf, rg in identificacoes.values():
            self.assertFalse(cpf and rg)

    def test_cpf_de_um_e_rg_de_outro_devolvem_decisao_conflitante(self):
        Pessoas.objects.create(nome='PEDRO CADASTRADO', cpf='11122233344')
        cache = {}
        erros = modulo_importacao._Erros('/acts/9')
        so_rg = ParteRevisada(
            papel='transmitente', nome='PEDRO DA SILVA', cpf=None,
            rg='12.345.678-9', pessoa_id=None, criar_novo=True,
            chave='/acts/9/partes/0',
        )
        pessoa_rg, criada = modulo_importacao._resolver_pessoa(
            so_rg, cache, erros,
        )
        self.assertIsNotNone(pessoa_rg)
        self.assertTrue(criada)

        com_conflito = ParteRevisada(
            papel='transmitente', nome='PEDRO DA SILVA',
            cpf='111.222.333-44', rg='12.345.678-9',
            pessoa_id=None, criar_novo=True,
            chave='/acts/9/partes/1',
        )
        pessoa, _ = modulo_importacao._resolver_pessoa(
            com_conflito, cache, erros,
        )

        # Fusão silenciosa não: o conflito é erro na linha da parte.
        self.assertIsNone(pessoa)
        (erro,) = erros.itens
        self.assertEqual(erro['codigo'], 'decisao_conflitante')
        self.assertEqual(
            erro['chave'], '/acts/9/partes/1/documento_identificacao/valor',
        )


class SavepointPorAtoTest(ImportacaoBase):
    """P2-3 (#263 rodada 2): o erro de um ato desfaz o savepoint DELE.

    Sem o rollback imediato, o que o ato inválido gravou fica de pé para
    os atos seguintes — que veem duplicata com um ``existente`` apontando
    para um registro que o rollback global vai desfazer.
    """

    def setUp(self):
        super().setUp()
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')

    def test_ato_invalido_desfaz_o_proprio_savepoint(self):
        payload = self._payload_com_numero()  # registro R-1 com partes
        averbacao = payload_averbacao(self.job.job_id)['acts'][0] | {'ordem': 2}
        averbacao['numero_lancamento'] = self._campo('R-1', 'Av-1/42.718')
        averbacao['partes'] = [{
            'papel': 'adquirente',
            'nome': {
                'raw': 'JOÃO DA SILVA', 'normalized': 'JOÃO DA SILVA',
                'confianca': 0.92, 'requer_revisao': False,
                'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
            },
            'documento_identificacao': {
                'tipo': {
                    'raw': 'CPF', 'normalized': 'CPF', 'confianca': 0.92,
                    'requer_revisao': False,
                    'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
                },
                'valor': {
                    'raw': '123.456.789-00', 'normalized': '12345678900',
                    'confianca': 0.92, 'requer_revisao': False,
                    'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
                },
            },
            'confianca': 0.92,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': 'JOÃO DA SILVA'},
        }]
        payload['acts'].append(averbacao)
        extracao = self._extracao(payload)
        pessoas_antes = Pessoas.objects.count()  # o factory já cria 1

        # Ato 1: grava o R-1 e a pessoa da 1ª parte (cacheada), e morre na
        # pessoa da 2ª. O savepoint tem que desfazer lançamento E cache —
        # senão o ato 2 vê duplicata (e reutilizaria pessoa desfeita).
        chamadas = iter(['ok', 'falha', 'ok'])

        def full_clean_pessoas():
            if next(chamadas) == 'falha':
                raise ValidationError({'cpf': ['Fora do limite.']})

        with patch.object(
            Pessoas, 'full_clean', side_effect=full_clean_pessoas,
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        linhas = contexto.exception.linhas
        self.assertEqual(linhas[0]['chave'], '/acts/0')
        self.assertEqual(linhas[0]['status'], 'erro')
        self.assertEqual(linhas[1]['chave'], '/acts/1')
        # O ato 2 GRAVOU de verdade (o R-1 do ato 1 voltou ao nada com o
        # savepoint) e só foi desfeito pelo rollback global da recusa.
        self.assertEqual(linhas[1]['status'], 'nao_gravado')
        self.assertNotIn('erros', linhas[1])
        # Nenhum `existente` aponta para registro desfeito pelo rollback.
        for linha in linhas:
            for erro in linha.get('erros', []):
                if 'existente' in erro:
                    self.assertTrue(
                        Lancamento.objects
                        .filter(pk=erro['existente']['id']).exists(),
                    )
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(Pessoas.objects.count(), pessoas_antes)
        # O ato 2 recriou o JOÃO: a entrada de cache do ato desfeito foi
        # descartada. Reaproveitada, ``full_clean`` rodaria só 2 vezes.
        self.assertIsNone(next(chamadas, None))


class OrigemLongaTest(ImportacaoBase):
    """P2-4 (#263 rodada 2): origem acima do limite vira 422, não 500."""

    def test_origem_com_50_digitos_e_erro_na_linha_da_origem(self):
        payload = self._payload_origem()
        payload['acts'][0]['origem']['numero'] = self._campo(
            '1' * 50, '42.718',
        )
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/origem/numero')
        self.assertEqual(erro['codigo'], 'valor_acima_do_limite_destino')
        self.assertEqual(Lancamento.objects.count(), 0)


class LinhasDescartadasTest(ImportacaoBase):
    """P2-5 (#263 rodada 2): linha descartada não vira importada."""

    def test_parte_descartada_mantem_status_e_autoria_da_revisao(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        outro = criar_usuario()
        # A revisão aceitou o nome do PEDRO e depois descartou SÓ a parte
        # (a linha-pai): a filha fica fora pelo ancestral, não por status
        # próprio (#263 rodada 3 — descartar pai e filhos não provava isso).
        CampoSugerido.objects.filter(chave='/acts/0/partes/2/nome').update(
            status_revisao='aceito',
            revisado_por=outro,
            revisado_em=timezone.now(),
        )
        CampoSugerido.objects.filter(chave='/acts/0/partes/2').update(
            status_revisao='descartado',
            revisado_por=outro,
            revisado_em=timezone.now(),
        )

        self._importar(extracao)

        # A parte descartada e a linha filha continuam como a revisão
        # deixou: a importação não reescreve decisão de descarte.
        pai = extracao.campos.get(chave='/acts/0/partes/2')
        self.assertEqual(pai.status_revisao, 'descartado')
        self.assertEqual(pai.revisado_por, outro)
        filha = extracao.campos.get(chave='/acts/0/partes/2/nome')
        self.assertEqual(filha.status_revisao, 'aceito')
        self.assertEqual(filha.revisado_por, outro)
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.pessoas.count(), 2)  # sem o PEDRO
        # As linhas incluídas do ato foram marcadas com o autor da importação.
        # Todas as demais linhas do ato foram marcadas com o autor da
        # importação.
        demais = (
            extracao.campos.filter(chave__startswith='/acts/0')
            .exclude(chave__startswith='/acts/0/partes/2')
        )
        self.assertTrue(demais.exists())
        self.assertFalse(
            demais.exclude(
                status_revisao='importado', revisado_por=self.usuario,
            ).exists()
        )


class DocumentoOrigemAuditadoTest(ImportacaoBase):
    """P2-6 (#263 rodada 2): documento de origem também gera ImportacaoIA."""

    def test_inicio_de_matricula_gera_vinculo_do_documento_criado(self):
        DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        extracao = self._extracao(payload)

        self._importar(extracao)

        lancamento = Lancamento.objects.get()
        (documento_origem,) = Documento.objects.exclude(pk=self.documento.pk)
        vinculo = ImportacaoIA.objects.get(modelo='Documento')
        self.assertEqual(vinculo.objeto_id, documento_origem.pk)
        self.assertEqual(vinculo.campo.chave, '/acts/0/origem/numero')
        self.assertEqual(vinculo.pagina, 1)
        self.assertEqual(vinculo.lancamento, lancamento)
        self.assertEqual(vinculo.criado_por, self.usuario)

    def test_documento_alheio_do_mesmo_imovel_nao_e_vinculado(self):
        # B2 (#263 rodada 3): o Imovel não é travado — outro escritor pode
        # criar documento no mesmo imóvel durante a importação. O vínculo
        # sai dos IDs que o caminho de criação devolve, nunca do diff dos
        # documentos do imóvel.
        DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        extracao = self._extracao(payload)
        processar = LancamentoOrigemService.processar_origens_automaticas
        alheios = []

        def com_escritor_concorrente(*args, **kwargs):
            alheios.append(Documento.objects.create(
                imovel=self.imovel, tipo=self.documento.tipo,
                numero=f'M909{len(alheios)}', data=date(2024, 1, 1),
                cartorio=self.documento.cartorio, livro='1', folha='1',
            ))
            return processar(*args, **kwargs)

        with patch.object(
            LancamentoOrigemService, 'processar_origens_automaticas',
            side_effect=com_escritor_concorrente,
        ):
            self._importar(extracao)

        self.assertTrue(alheios)
        (documento_origem,) = Documento.objects.filter(
            imovel=self.imovel, numero='T366',
        )
        self.assertEqual(
            list(
                ImportacaoIA.objects.filter(modelo='Documento')
                .values_list('objeto_id', flat=True)
            ),
            [documento_origem.pk],
        )


class DuplicataInternaTest(ImportacaoBase):
    """B3 (#263 rodada 3): dois atos do payload com o mesmo lançamento.

    O ato 1 grava no savepoint dele; o ato 2 colide com ELE, que o
    rollback global vai desfazer. ``existente`` só aponta registro anterior
    à importação — a colisão interna é erro na chave do ato conflitante.
    """

    def test_dois_atos_iguais_recusam_sem_existente(self):
        payload = self._payload_com_numero()
        payload['acts'].append(deepcopy(payload['acts'][0]) | {'ordem': 2})
        extracao = self._extracao(payload)
        antes = (
            Pessoas.objects.count(), Cartorios.objects.count(),
            ImportacaoIA.objects.count(),
        )

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        primeiro, segundo = contexto.exception.linhas
        self.assertEqual(primeiro['chave'], '/acts/0')
        self.assertEqual(primeiro['status'], 'nao_gravado')
        self.assertIsNone(primeiro['lancamento_id'])
        self.assertEqual(segundo['chave'], '/acts/1')
        self.assertEqual(segundo['status'], 'erro')
        (erro,) = segundo['erros']
        self.assertEqual(erro['chave'], '/acts/1')
        self.assertEqual(erro['codigo'], 'ato_duplicado_na_importacao')
        self.assertNotIn('existente', erro)
        # Nada gravado: nem o ato 1, nem pessoas/cartórios/vínculos.
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(
            (
                Pessoas.objects.count(), Cartorios.objects.count(),
                ImportacaoIA.objects.count(),
            ),
            antes,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')

    def test_registro_anterior_continua_com_existente(self):
        # A colisão com o que já existia antes da importação segue com o
        # ``existente`` — mesmo quando um ato anterior também gravou.
        existente = Lancamento.objects.create(
            documento=self.documento, tipo=self.tipo_registro,
            numero_lancamento='R-2', data=date(2021, 3, 20),
        )
        payload = self._payload_com_numero()
        segundo = deepcopy(payload['acts'][0]) | {'ordem': 2}
        segundo['numero_lancamento'] = self._campo('R-2', 'R-1/42.718')
        payload['acts'].append(segundo)
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (erro,) = contexto.exception.linhas[1]['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(erro['existente']['id'], existente.pk)


class RedeDeSegurancaOrigemTest(ImportacaoBase):
    """``ValidationError`` do serviço da origem vira erro da linha, não 500."""

    def test_recusa_do_servico_da_origem_e_erro_com_mensagem_fixa(self):
        extracao = self._extracao(self._payload_origem())
        processar = LancamentoOrigemService.processar_origens_automaticas

        def recusa_na_chamada_explicita(*args, **kwargs):
            # O sinal post_save chama sem queryset e engole exceções; a
            # chamada explícita da importação (com queryset) é a que conta.
            if 'documentos_queryset' in kwargs:
                raise ValidationError('Origem T366 duplicada no cartório.')
            return processar(*args, **kwargs)

        with patch.object(
            LancamentoOrigemService, 'processar_origens_automaticas',
            side_effect=recusa_na_chamada_explicita,
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        (erro,) = contexto.exception.linhas[0]['erros']
        self.assertEqual(erro['chave'], '/acts/0/origem/numero')
        self.assertEqual(erro['codigo'], 'valor_incompativel_destino')
        # Mensagem fixa: o texto da exceção (com o número) não vaza.
        self.assertEqual(
            erro['mensagem'],
            'O número da origem não pôde ser gravado no lançamento.',
        )
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(LancamentoOrigem.objects.count(), 0)


class ErroPessoaPorCampoTest(ImportacaoBase):
    """P2-7 (#263 rodada 2): erro de Pessoas ancora na linha da parte."""

    def test_erro_de_nome_e_cpf_ancoram_nas_linhas_da_parte(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        # Defesa em profundidade (a revisão já limitaria os valores): o
        # patch isola o MAPEAMENTO do message_dict de Pessoas para as
        # chaves de linha que a tela conhece.
        with patch.object(
            Pessoas, 'full_clean',
            side_effect=ValidationError({
                'nome': ['Nome fora do limite.'],
                'cpf': ['CPF fora do limite.'],
            }),
        ):
            with self.assertRaises(ImportacaoInvalida) as contexto:
                self._importar(extracao)

        chaves = {
            (erro['chave'], erro['codigo'])
            for erro in contexto.exception.linhas[0]['erros']
        }
        self.assertIn(
            ('/acts/0/partes/0/nome', 'campo_invalido'), chaves,
        )
        self.assertIn(
            (
                '/acts/0/partes/0/documento_identificacao/valor',
                'campo_invalido',
            ),
            chaves,
        )


def _post_cadastro_manual(tipo_registro):
    """POST mínimo do cadastro manual: gera o número ``R1 M42``."""
    return {
        'tipo_lancamento': str(tipo_registro.pk),
        'sigla_matricula': 'M42',
        'numero_lancamento_simples': '1',
        'data': '2020-02-15',
        'observacoes': '',
    }


class TravaDocumentoTest(ImportacaoBase):
    """P1-1 (#263 rodadas 2 e 3): importação e cadastro manual disputam o Documento.

    Os dois fluxos gravam lançamento no mesmo documento: ambos EXECUTAM a
    trava do ``Documento`` dentro da transação — a importação por último na
    ordem da exclusão do PDF (``DocumentoDigital`` → job → extração →
    ``Documento``); o cadastro manual só ela, antes de gravar. A trava da
    importação é só do Documento (``of=('self',)``): o JOIN do
    ``select_related('imovel')`` travaria também o Imovel (rodada 3).
    """

    ORDEM = (DocumentoDigital, OcrJob, ExtracaoSugerida, Documento)

    def test_importacao_trava_por_ultimo_so_o_documento(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with travas_executadas() as travas:
            self._importar(extracao)

        self.assertEqual(
            [trava for trava in travas if trava[0] in self.ORDEM],
            [
                (DocumentoDigital, ()),
                (OcrJob, ()),
                (ExtracaoSugerida, ()),
                (Documento, ('self',)),
            ],
        )

    def test_criacao_manual_trava_o_documento_na_mesma_ordem(self):
        request = RequestFactory().post(
            '/lancamento/criar/', _post_cadastro_manual(self.tipo_registro),
        )
        request.user = self.usuario
        gravados_na_trava = []

        def contar(modelo):
            if modelo is Documento:
                gravados_na_trava.append(
                    Lancamento.objects.filter(documento=self.documento).count()
                )

        with travas_executadas(contar) as travas:
            lancamento, _ = LancamentoCriacaoService.criar_lancamento_completo(
                request, self.imovel.terra_indigena_id, self.imovel,
                self.documento,
            )

        # Só a última trava da ordem, executada antes do INSERT.
        self.assertEqual(
            [trava for trava in travas if trava[0] in self.ORDEM],
            [(Documento, ())],
        )
        self.assertEqual(gravados_na_trava, [0])
        self.assertIsNotNone(lancamento)


@skipUnlessDBFeature('has_select_for_update_of')
class TravaDocumentoSqlTest(ImportacaoBase):
    """SQL real da trava (PostgreSQL; o sqlite não emite ``FOR UPDATE``)."""

    def test_sql_da_trava_cobre_so_a_tabela_do_documento(self):
        extracao = self._extracao(payload_registro(self.job.job_id))

        with CaptureQueriesContext(connection) as capturadas:
            self._importar(extracao)

        (sql,) = [
            consulta['sql'] for consulta in capturadas.captured_queries
            if 'FOR UPDATE' in consulta['sql']
            and 'FROM "dominial_documento"' in consulta['sql']
        ]
        # O select_related continua (JOIN no imóvel); a trava, não.
        self.assertIn('JOIN "dominial_imovel"', sql)
        self.assertTrue(
            sql.endswith('FOR UPDATE OF "dominial_documento"'), sql,
        )


@skipUnlessDBFeature('has_select_for_update', 'has_select_for_update_of')
class ImportacaoXCadastroManualPostgresTest(
    ImportacaoFixture, TransactionTestCase,
):
    """Concorrência real (2 conexões): a trava do Documento serializa os fluxos.

    ``TransactionTestCase`` + threads com conexões próprias (mesmo padrão
    de ``test_texto_concorrencia_pg``). Na suíte sqlite esta classe é
    PULADA (comportamento esperado); rodar contra um Postgres para valer.
    """

    def setUp(self):
        super().setUp()
        self.dentro = threading.Event()
        self.liberar = threading.Event()
        vincular = modulo_importacao._vincular

        def vincular_devagar(*args, **kwargs):
            # Depois de travar o Documento e gravar o lançamento do ato,
            # antes do commit: a importação segura as travas aqui.
            self.dentro.set()
            self.liberar.wait(timeout=ESPERA_S)
            return vincular(*args, **kwargs)

        patcher = patch.object(modulo_importacao, '_vincular', vincular_devagar)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.liberar.set)

    def _importacao_segurando_a_trava(self, extracao, resultado):
        importacao = _rodar(
            lambda: self._importar(extracao), resultado, 'importacao',
        )
        self.assertTrue(
            self.dentro.wait(timeout=ESPERA_S),
            'a importação não chegou a travar o Documento',
        )
        return importacao

    def test_importacao_trava_o_documento_e_nao_o_imovel(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        resultado = {}
        importacao = self._importacao_segurando_a_trava(extracao, resultado)

        # NOWAIT falha na hora se a linha estiver travada por outra conexão.
        with transaction.atomic():
            Imovel.objects.select_for_update(nowait=True).get(pk=self.imovel.pk)
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                Documento.objects.select_for_update(nowait=True).get(
                    pk=self.documento.pk,
                )

        self.liberar.set()
        importacao.join(timeout=ESPERA_S)
        self.assertEqual(resultado['importacao'][0], 'ok', resultado['importacao'])

    def test_cadastro_manual_espera_a_importacao_e_recusa_o_mesmo_numero(self):
        payload = payload_registro(self.job.job_id)
        # Mesmo texto do número que o cadastro manual gera (a normalização
        # entre ``R-1`` e ``R1 M42`` é assunto de outra issue).
        payload['acts'][0]['numero_lancamento'] = self._campo(
            'R1 M42', 'R-1/42.718',
        )
        extracao = self._extracao(payload)
        request = RequestFactory().post(
            '/lancamento/criar/', _post_cadastro_manual(self.tipo_registro),
        )
        request.user = self.usuario
        resultado = {}
        importacao = self._importacao_segurando_a_trava(extracao, resultado)

        manual = _rodar(
            lambda: LancamentoCriacaoService.criar_lancamento_completo(
                request, self.imovel.terra_indigena_id, self.imovel,
                self.documento,
            ),
            resultado, 'manual',
        )
        manual.join(timeout=BLOQUEIO_S)
        self.assertTrue(
            manual.is_alive(),
            'o cadastro manual não esperou a trava do Documento',
        )

        self.liberar.set()
        importacao.join(timeout=ESPERA_S)
        manual.join(timeout=ESPERA_S)

        self.assertEqual(resultado['importacao'][0], 'ok', resultado['importacao'])
        self.assertEqual(resultado['manual'][0], 'ok', resultado['manual'])
        lancamento, mensagem = resultado['manual'][1]
        self.assertIsNone(lancamento)
        self.assertIn('Já existe um lançamento com o número "R1 M42"', mensagem)
        self.assertEqual(
            Lancamento.objects.filter(documento=self.documento).count(), 1,
        )


class StdoutSemValorDocumentalTest(ImportacaoBase):
    """P2-9 (#263 rodada 2): stdout da importação sem número/tipo documental."""

    def test_importacao_nao_imprime_o_numero_da_origem(self):
        extracao = self._extracao(self._payload_origem())

        saida = io.StringIO()
        with redirect_stdout(saida):
            self._importar(extracao)

        self.assertNotIn('366', saida.getvalue())
