"""Testes da importação assistida da revisão finalizada (I-6 / #263).

O serviço grava os atos marcados de uma extração finalizada em lançamentos
do dominial, com savepoint por ato e rollback total ao primeiro erro. Os
payloads são os mesmos sintéticos da revisão (nada de documento real), e a
decisão B (#263-I6-B) está em jogo no caminho feliz: linha ``sugerido`` sem
``requer_revisao`` entra na importação porque a finalização da revisão já é
o aceite humano.
"""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dominial.models import (
    Cartorios, Documento, DocumentoTipo, Lancamento, LancamentoOrigem,
    LancamentoPessoa, LancamentoTipo, Pessoas, UserTI,
)
from ia_ocr import services
from ia_ocr.estados import TransicaoConcorrente
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from ia_ocr.revisao import RevisaoInvalidada, desnormalizar

from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_com_closure, payload_registro,
)


class ImportacaoBase(TestCase):
    """Job ``revisado`` com extração finalizada, pronto para importar."""

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
    """Pessoa escolhida deletada após a finalização da revisão."""

    def test_pessoa_deletada_deixa_a_revisao_invalida(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        maria = Pessoas.objects.create(nome='MARIA EXISTENTE', cpf='11122233344')
        extracao.campos.filter(chave='/acts/0/partes/1').update(
            pessoa_escolhida=maria, criar_novo=False,
        )
        # A escolha morre com a pessoa (FK SET_NULL): a linha volta a ser
        # pendência de escolha e o motor de revisão recusa antes da gravação.
        maria.delete()

        with self.assertRaises(RevisaoInvalidada):
            self._importar(extracao)

        self.assertEqual(Lancamento.objects.count(), 0)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'revisado')


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
