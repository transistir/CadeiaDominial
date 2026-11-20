"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from copy import deepcopy
from unittest.mock import patch
from django.db import DatabaseError, connection, transaction
from django.test.utils import CaptureQueriesContext
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from ia_ocr import importacao as modulo_importacao
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)
from .test_importacao_base import ImportacaoBase, _DesfazImportacao


class TravaCartorioOrdemGlobalTest(ImportacaoBase):
    """P1 Greptile (#263 rodada 5): travas de cartório sem ABBA.

    Cada ato travava o nome no uso, na ordem do payload: a importação X
    travava ``A`` (transmissão) e depois ``B`` (origem); a Y, em outro
    documento, ``B`` e depois ``A`` — o Postgres detectava o ciclo e
    abortava uma delas com 500. Os nomes que a importação pode criar são
    travados de uma vez, antes do primeiro ato, na ordem global do id da
    trava. O ``_trava_nome_cartorio`` patchado registra a sequência (no
    sqlite a trava real é no-op).
    """

    def _payload_com_cartorios(self, nomes):
        """Um ato por par de nomes — transmissão e origem —, na ordem dada."""
        payload = self._payload_origem()
        modelo = payload['acts'].pop()
        for indice, (transmissao, origem) in enumerate(
            zip(nomes[::2], nomes[1::2]),
        ):
            ato = deepcopy(modelo)
            ato['ordem'] = indice + 1
            # Datas distintas: um ato não é duplicata do outro.
            ato['data'] = self._campo(
                f'2020-02-{15 + indice}', '15 de fevereiro de 2020',
            )
            ato['cartorio_transmissao'] = self._campo(
                transmissao, 'CRI de Guaíra',
            )
            ato['origem']['cartorio'] = self._campo(origem, 'CRI de Guaíra')
            payload['acts'].append(ato)
        return payload

    def _travas_da_importacao(self, payload):
        """Nomes que a importação do payload trava, em ordem; desfaz tudo."""
        travas = []
        with self.assertRaises(_DesfazImportacao):
            with transaction.atomic():
                extracao = self._extracao(payload)
                with patch.object(
                    modulo_importacao, '_trava_nome_cartorio', travas.append,
                ):
                    self.assertTrue(self._importar(extracao)['ok'])
                raise _DesfazImportacao
        return travas

    def test_ordens_opostas_travam_na_mesma_sequencia_crescente(self):
        nomes = ['CRI Delta', 'CRI Gama', 'CRI Beta', 'CRI Alfa']

        direta = self._travas_da_importacao(self._payload_com_cartorios(nomes))
        inversa = self._travas_da_importacao(
            self._payload_com_cartorios(nomes[::-1]),
        )

        # Uma importação com A→B e outra com B→A travam na MESMA sequência:
        # a segunda espera a primeira, nunca fecha ciclo.
        self.assertEqual(direta, inversa)
        # Cada nome uma vez só: o ato não trava de novo no uso.
        self.assertCountEqual(direta, [nome.casefold() for nome in nomes])
        # A ordem global é a do id que o Postgres de fato trava, crescente.
        chaves = [modulo_importacao._chave_da_trava(nome) for nome in direta]
        self.assertEqual(chaves, sorted(chaves))

    def test_todos_os_nomes_sao_travados_antes_da_primeira_gravacao(self):
        # O ato 1 repete o nome do ato 0 em outra caixa: trava uma vez só.
        extracao = self._extracao(self._payload_com_cartorios(
            ['CRI Alfa', 'CRI Beta', 'CRI Gama', 'cri alfa'],
        ))

        def contagens():
            return (
                Cartorios.objects.count(), Lancamento.objects.count(),
                Pessoas.objects.count(), ImportacaoIA.objects.count(),
            )

        antes = contagens()
        na_trava = []
        with patch.object(
            modulo_importacao, '_trava_nome_cartorio',
            lambda nome: na_trava.append(contagens()),
        ):
            resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        # Nada gravado enquanto trava: quem espera numa trava de nome não
        # segura linha nova que a outra importação possa disputar.
        self.assertEqual(na_trava, [antes] * 3)
        self.assertEqual(Cartorios.objects.count(), antes[0] + 3)

    def test_cartorio_escolhido_pelo_id_nao_trava(self):
        extracao = self._extracao(
            self._payload_com_cartorios(['CRI Alfa', 'CRI Beta']),
        )
        for indice, chave in enumerate(
            ('/acts/0/cartorio_transmissao', '/acts/0/origem/cartorio'),
        ):
            cartorio = Cartorios.objects.create(
                nome=f'CRI Cadastrado {indice}', cns=f'CNS-263-R5-{indice}',
            )
            extracao.campos.filter(chave=chave).update(
                cartorio_escolhido=cartorio, criar_novo=False,
            )
        travas = []

        with patch.object(
            modulo_importacao, '_trava_nome_cartorio', travas.append,
        ):
            resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(travas, [])

    def test_criar_novo_com_nome_ja_cadastrado_tambem_trava(self):
        # Escolha documentada: o conjunto travado vem do payload, não da
        # tabela — consultá-la antes de travar mandaria o nome que some na
        # janela para uma trava fora da ordem global. O cadastro existente
        # continua reaproveitado (decisão E).
        existente = Cartorios.objects.create(
            nome='CRI Alfa', cns='CNS-263-R5-ALFA',
        )
        extracao = self._extracao(
            self._payload_com_cartorios(['cri alfa', 'CRI Beta']),
        )
        travas = []

        with patch.object(
            modulo_importacao, '_trava_nome_cartorio', travas.append,
        ):
            self._importar(extracao)

        self.assertCountEqual(travas, ['cri alfa', 'cri beta'])
        self.assertEqual(
            Lancamento.objects.get().cartorio_transmissao, existente,
        )
        self.assertEqual(
            Cartorios.objects.filter(nome__iexact='cri alfa').count(), 1,
        )

    def test_nome_fora_do_conjunto_travado_trava_e_rebusca(self):
        # Ramo defensivo (pré-trava e resolução divergentes): trava e
        # re-busca como na rodada 4 — a linha que outro escritor commitou
        # enquanto esta esperava é reaproveitada, sem vínculo novo.
        vencedor = {}

        def trava_com_outro_escritor(nome):
            vencedor['cartorio'] = Cartorios.objects.create(
                nome='CRI Avulso', cns='CNS-263-R5-AVULSO',
            )

        criados = []
        with patch.object(
            modulo_importacao, '_trava_nome_cartorio',
            trava_com_outro_escritor,
        ):
            cartorio = modulo_importacao._resolver_cartorio(
                None, True, 'cri avulso', '/acts/0/cartorio_transmissao',
                criados, frozenset(),
            )

        self.assertEqual(cartorio, vencedor['cartorio'])
        self.assertEqual(criados, [])


class TravaCpfOrdemGlobalTest(ImportacaoBase):
    """P1 Codex (#263 rodada 6): travas de CPF sem ABBA.

    Duas importações em documentos distintos que criam CPFs ainda
    inexistentes disputam o índice unique de ``Pessoas.cpf`` na ordem dos
    atos: X insere A e depois B; Y insere B e depois A — o Postgres detecta
    o ciclo e aborta uma com ``deadlock_detected``, que o handler de
    ``IntegrityError`` não cobre. Espelho da rodada 5 do cartório: os CPFs
    que a importação pode criar são travados de uma vez, antes do primeiro
    ato, na ordem global do id da trava. O ``_trava_cpf`` patchado registra
    a sequência (no sqlite a trava real é no-op).
    """

    def _payload_com_cpfs(self, atos_de_cpfs):
        """Um ato por lista de ``(nome, cpf)`` das partes, na ordem dada.

        ``cpf`` com máscara exercita o normalizador; ``None`` é a parte sem
        identificação (PEDRO do modelo), que nunca trava. Só o VALOR muda:
        os trechos de evidência ficam os do modelo — substring do texto OCR
        sintético; trecho estranho viraria pendência de revisão.
        """
        payload = payload_registro(self.job.job_id)
        modelo = payload['acts'].pop()
        nomes_modelo = [parte['nome']['normalized'] for parte in modelo['partes']]
        cpfs_modelo = [
            (parte['documento_identificacao'] or {}).get('valor', {}).get('raw')
            for parte in modelo['partes']
        ]
        for indice, partes in enumerate(atos_de_cpfs):
            ato = deepcopy(modelo)
            ato['ordem'] = indice + 1
            # Datas distintas: um ato não é duplicata do outro.
            ato['data'] = self._campo(
                f'2020-02-{15 + indice}', '15 de fevereiro de 2020',
            )
            for indice_parte, (parte, (nome, cpf)) in enumerate(
                zip(ato['partes'], partes),
            ):
                parte['nome'] = self._campo(nome, nomes_modelo[indice_parte])
                if cpf is None:
                    parte['documento_identificacao'] = None
                else:
                    parte['documento_identificacao'] = {
                        'tipo': self._campo('CPF', cpfs_modelo[indice_parte]),
                        'valor': self._campo(cpf, cpfs_modelo[indice_parte]),
                    }
            payload['acts'].append(ato)
        return payload

    def _travas_cpf_da_importacao(self, payload):
        """CPFs que a importação do payload trava, em ordem; desfaz tudo."""
        travas = []
        with self.assertRaises(_DesfazImportacao):
            with transaction.atomic():
                extracao = self._extracao(payload)
                with patch.object(
                    modulo_importacao, '_trava_cpf', travas.append,
                ):
                    self.assertTrue(self._importar(extracao)['ok'])
                raise _DesfazImportacao
        return travas

    def test_cpfs_de_atos_distintos_travam_na_mesma_sequencia_crescente(self):
        # Um CPF com máscara: a trava é pelos DÍGITOS, o mesmo material do
        # lookup e do INSERT de ``_resolver_pessoa``. Todos com dígito
        # verificador válido — inválido virava pendência de revisão.
        direto = [[
            ('JOÃO A', '11122233396'),
            ('MARIA B', '44455566619'),
            ('PEDRO SANTOS', None),
        ], [
            ('ANA C', '777.888.999-41'),
            ('BRUNO D', '22233344405'),
            ('CARLOS', None),
        ]]
        inverso = [direto[1], direto[0]]

        travas_direto = self._travas_cpf_da_importacao(
            self._payload_com_cpfs(direto),
        )
        travas_inverso = self._travas_cpf_da_importacao(
            self._payload_com_cpfs(inverso),
        )

        # Uma importação com A→B e outra com B→A travam na MESMA sequência:
        # a segunda espera a primeira, nunca fecha ciclo.
        self.assertEqual(travas_direto, travas_inverso)
        self.assertCountEqual(travas_direto, [
            '11122233396', '44455566619', '77788899941', '22233344405',
        ])
        # A ordem global é a do id que o Postgres de fato trava, crescente.
        chaves = [
            modulo_importacao._chave_cpf_da_trava(cpf)
            for cpf in travas_direto
        ]
        self.assertEqual(chaves, sorted(chaves))

    def test_cpf_de_parte_fora_de_criacao_nao_trava(self):
        # JOÃO escolhido do cadastro (criar_novo=False): decisão D sem
        # criação, nada a serializar. PEDRO não tem CPF: nem há o que travar.
        # Só o CPF da parte a criar entra no conjunto.
        cadastrado = Pessoas.objects.create(
            nome='JOÃO CADASTRADO', cpf='12345678900',
        )
        extracao = self._extracao(self._payload_com_cpfs([[
            ('JOÃO DA SILVA', '12345678900'),
            ('MARIA DA SILVA', '98765432100'),
            ('PEDRO SANTOS', None),
        ]]))
        extracao.campos.filter(chave='/acts/0/partes/0').update(
            pessoa_escolhida=cadastrado, criar_novo=False,
        )
        travas = []

        with patch.object(
            modulo_importacao, '_trava_cpf', travas.append,
        ):
            resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(travas, ['98765432100'])

    def test_espaco_de_chave_do_cpf_e_separado_do_do_cartorio(self):
        # Mesmo material nos dois tipos de trava, ids distintos: o CPF é
        # hasheado com o prefixo 'cpf:' — sem ele, o id colidiria com o da
        # trava de cartório de mesmo material e uma trava esperaria a outra
        # sem disputar nada.
        self.assertNotEqual(
            modulo_importacao._chave_cpf_da_trava('12345678900'),
            modulo_importacao._chave_da_trava('12345678900'),
        )

    def test_trava_cpf_e_no_op_fora_do_postgresql(self):
        # Contrato do guard: fora do Postgres (um escritor por vez) a trava
        # não consulta o banco — a suíte padrão inteira roda sobre o no-op.
        # O ``vendor`` é forçado para 'sqlite': sem isso o teste rodaria o
        # caminho real no PostgreSQL (consulta de advisory lock) e falharia
        # lá com a trava funcionando (Greptile P1 no PR #310).
        with patch.object(connection, 'vendor', 'sqlite'):
            with CaptureQueriesContext(connection) as consultas:
                modulo_importacao._trava_cpf('12345678900')
        self.assertEqual(len(consultas), 0)
