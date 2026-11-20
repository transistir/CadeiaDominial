"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from copy import deepcopy
from unittest.mock import patch
from django.core.exceptions import ValidationError
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from ia_ocr import importacao as modulo_importacao
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    CAMPOS_DA_ORIGEM, ParteRevisada, RevisaoInvalidada, dados_revisados,
    desnormalizar, descrever_aviso,
)
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)
from .test_importacao_base import ImportacaoBase


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


class CpfConcorrenteTest(ImportacaoBase):
    """P1 Greptile (#263 rodada 4): CPF gravado por outra importação.

    Duas importações em documentos diferentes resolvem o MESMO CPF: as duas
    não acham cadastro e chamam ``full_clean``/``save``. A trava do
    ``Documento`` não protege ``Pessoas`` — sem savepoint, o unique de CPF
    derruba a segunda importação com 500 e rollback total. Decisão D: a
    linha vencedora é relida e REUTILIZADA.
    """

    def test_cpf_gravado_na_janela_e_reutilizado_sem_erro(self):
        extracao = self._extracao(payload_registro(self.job.job_id))
        limpo = Pessoas.full_clean

        def full_clean_com_concorrente(alvo):
            limpo(alvo)  # a checagem de unicidade passa: ninguém commitou
            if getattr(alvo, 'cpf', None) == '12345678900':
                # ... e a importação do OUTRO documento commitou o MESMO
                # CPF entre a checagem e o INSERT deste ato.
                Pessoas.objects.create(
                    nome='JOÃO DE OUTRO DOCUMENTO', cpf='12345678900',
                )

        with patch.object(
            Pessoas, 'full_clean', autospec=True,
            side_effect=full_clean_com_concorrente,
        ):
            resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (lancamento,) = Lancamento.objects.all()
        joao = Pessoas.objects.get(cpf='12345678900')
        self.assertEqual(joao.nome, 'JOÃO DE OUTRO DOCUMENTO')
        self.assertEqual(
            LancamentoPessoa.objects.filter(
                lancamento=lancamento, pessoa=joao,
            ).count(),
            1,
        )
        # Uma única linha com o CPF: o INSERT perdedor morreu no savepoint
        # e a vencedora foi reutilizada, não duplicada.
        self.assertEqual(Pessoas.objects.filter(cpf='12345678900').count(), 1)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_cpf_commitado_na_janela_do_full_clean_e_reutilizado(self):
        # Rodada 6 (Codex): a importação do OUTRO documento commitou o MESMO
        # CPF entre o lookup de ``_resolver_pessoa`` e o ``full_clean`` — a
        # checagem de unicidade falha com ValidationError ANTES do INSERT,
        # o handler de IntegrityError nunca rodaria e o lote inteiro cairia.
        # Mesma decisão da rodada 4: reler a vencedora e REUTILIZAR.
        extracao = self._extracao(payload_registro(self.job.job_id))
        limpo = Pessoas.full_clean

        def full_clean_com_concorrente(alvo):
            if getattr(alvo, 'cpf', None) == '12345678900':
                # Commita o MESMO CPF antes da checagem de unicidade: ela
                # agora falha (ValidationError de unique), não o INSERT.
                Pessoas.objects.create(
                    nome='JOÃO DE OUTRO DOCUMENTO', cpf='12345678900',
                )
            limpo(alvo)

        with patch.object(
            Pessoas, 'full_clean', autospec=True,
            side_effect=full_clean_com_concorrente,
        ):
            resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        joao = Pessoas.objects.get(cpf='12345678900')
        self.assertEqual(joao.nome, 'JOÃO DE OUTRO DOCUMENTO')
        self.assertEqual(Pessoas.objects.filter(cpf='12345678900').count(), 1)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
