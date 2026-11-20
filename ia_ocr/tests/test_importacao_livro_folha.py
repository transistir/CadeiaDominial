"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.
"""

from datetime import date
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from ia_ocr import importacao as modulo_importacao
from ia_ocr import services
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


class OrigemPontuadaTest(ImportacaoBase):
    """P1 Codex (#263 rodada 4): 'T42.718' não vira 'M42' + 'M718'.

    O normalizador preserva a pontuação do número (decisão dele); o
    fallback de texto livre do ``processar_origens_para_documentos``
    repartia 'T42.718' em dois números e criava dois documentos errados —
    com o ``LancamentoOrigem`` apontando 'T42.718' e sucesso na resposta.
    O tipo estruturado revisado viaja até a criação do documento.
    """

    def _extracao_inicio_matricula(self, numero):
        DocumentoTipo.objects.create(tipo='transcricao')
        # O fallback de texto livre cria 'M42'/'M718' como MATRÍCULA: sem o
        # tipo cadastrado a falha engolida escondia o bug (0 documentos).
        DocumentoTipo.objects.create(tipo='matricula')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        # Rótulo de MATRÍCULA: com o rótulo prevalecendo (#322 rodada 3),
        # o 'R-1' do payload-base faria o ato virar registro.
        payload['acts'][0]['rotulo'] = self._campo('M-1', 'R-1/42.718')
        payload['acts'][0]['origem']['numero'] = self._campo(
            numero, '42.718',
        )
        return self._extracao(payload)

    def test_inicio_de_matricula_com_pontuacao_cria_um_documento_sozinho(self):
        extracao = self._extracao_inicio_matricula('T42.718')

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        # O fallback de texto livre não rodou: nenhum M42/M718 nasceu.
        self.assertFalse(
            Documento.objects.filter(numero__in=['M42', 'M718']).exists(),
        )
        (documento_origem,) = Documento.objects.exclude(pk=self.documento.pk)
        self.assertEqual(documento_origem.numero, 'T42.718')
        self.assertEqual(documento_origem.tipo.tipo, 'transcricao')
        self.assertEqual(documento_origem.imovel, self.imovel)
        # O documento de origem criado entra na auditoria, como o T366.
        vinculo = ImportacaoIA.objects.get(modelo='Documento')
        self.assertEqual(vinculo.objeto_id, documento_origem.pk)
        self.assertEqual(vinculo.campo.chave, '/acts/0/origem/numero')
        # O texto revisado é preservado e a origem estruturada é uma só.
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.origem, 'T42.718')
        origem = LancamentoOrigem.objects.get()
        self.assertEqual(origem.tipo_documento, 'transcricao')
        self.assertEqual(origem.numero_normalizado, '42.718')


class OrigemSoCartorioTest(ImportacaoBase):
    """Major CodeRabbit (#263 rodada 4): origem sem número, só cartório.

    ``_resolver_cartorio`` só rodava no ramo que monta o ``texto_origem``:
    origem com apenas o cartório ficava sem ``cartorio_origem`` e a
    validação de ``requer_cartorio_origem`` do lançamento recusava. O
    cartório é resolvido sempre que há origem; o número só entra na
    montagem do texto/mapeamento.
    """

    def _tornar_exigente(self):
        self.tipo_registro.requer_cartorio_origem = True
        self.tipo_registro.save(update_fields=['requer_cartorio_origem'])

    def _payload_so_cartorio(self):
        payload = self._payload_origem()
        payload['acts'][0]['origem'] = {
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
        }
        return payload

    def test_origem_so_com_cartorio_grava_o_cartorio_de_origem(self):
        self._tornar_exigente()
        extracao = self._extracao(self._payload_so_cartorio())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.cartorio_origem.nome, 'CRI de Origem')
        # Sem número não há texto de origem nem linha estruturada.
        self.assertIsNone(lancamento.origem)
        self.assertEqual(LancamentoOrigem.objects.count(), 0)
        self.assertEqual(Documento.objects.count(), 1)
        self.assertTrue(
            ImportacaoIA.objects.filter(modelo='Cartorios').exists(),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')

    def test_origem_sem_numero_e_sem_cartorio_recusa_na_chave_da_origem(self):
        # Registro exigente sem origem no payload: a linha placeholder de
        # origem/cartorio existe (o tipo exige) e vazia — a revalidação da
        # revisão recusa com a pendência NA CHAVE da origem, antes da
        # gravação (contrato que esta rodada congela).
        self._tornar_exigente()
        extracao = self._extracao(payload_registro(self.job.job_id))
        versao_tela = services.versao_bloco(extracao)

        with self.assertRaises(RevisaoInvalidada):
            importar(extracao, self.usuario, versao_tela, ['/acts/0'])

        self.assertIn(
            {'chave': '/acts/0/origem/cartorio', 'motivo': 'obrigatorio_ausente'},
            modulo_importacao.pendencias_para_resposta(extracao),
        )
        self.assertEqual(Lancamento.objects.count(), 0)


class LivroFolhaDaOrigemTest(ImportacaoBase):
    """#324 (I-11d): livro/folha da origem vazios gravam NULL, nunca espaços.

    O formulário preserva espaços em texto; o mesmo ``strip() or None`` da
    transmissão vale para os DOIS destinos da origem — a coluna do
    lançamento e o mapeamento que alimenta a ``LancamentoOrigem``.
    """

    def _importar_com(self, livro, folha):
        payload = self._payload_origem()
        payload['acts'][0]['origem']['livro'] = self._campo(livro)
        payload['acts'][0]['origem']['folha'] = self._campo(folha)
        resultado = self._importar(self._extracao(payload))
        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        return lancamento, LancamentoOrigem.objects.get(lancamento=lancamento)

    def test_livro_e_folha_em_branco_gravam_none_nos_dois_destinos(self):
        lancamento, origem = self._importar_com('  ', ' \t\n ')

        self.assertIsNone(lancamento.livro_origem)
        self.assertIsNone(lancamento.folha_origem)
        self.assertIsNone(origem.livro)
        self.assertIsNone(origem.folha)

    def test_livro_e_folha_gravam_sem_bordas_nos_dois_destinos(self):
        lancamento, origem = self._importar_com(' 3-A ', '\t12v ')

        self.assertEqual(lancamento.livro_origem, '3-A')
        self.assertEqual(lancamento.folha_origem, '12v')
        self.assertEqual(origem.livro, '3-A')
        self.assertEqual(origem.folha, '12v')

    def test_sem_livro_e_folha_o_marcador_zero_fica_so_no_documento(self):
        # Só início de matrícula cria o documento de origem (anti-órfão).
        DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        payload = self._payload_origem()
        for nome in ('livro', 'folha'):
            del payload['acts'][0]['origem'][nome]
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        payload['acts'][0]['rotulo'] = self._campo('M-1', 'R-1/42.718')
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertIsNone(lancamento.livro_origem)
        self.assertIsNone(lancamento.folha_origem)
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertIsNone(origem.livro)
        self.assertIsNone(origem.folha)
        # As colunas do Documento são NOT NULL: só ele guarda o marcador '0'.
        documento_origem = Documento.objects.exclude(pk=self.documento.pk).get()
        self.assertEqual(documento_origem.livro, '0')
        self.assertEqual(documento_origem.folha, '0')


class AvisoLivroFolhaDaOrigemTest(ImportacaoBase):
    """#324 (I-11d): livro/folha da origem que o documento não traz.

    É aviso na resposta — o status do ato continua ``criado`` — e vale
    também quando a importação é repetida (replay do job já importado).
    """

    # Texto canônico POR CAMPO (``revisao.TEXTO_NAO_CONSTA``): o mesmo da tela.
    # Um aviso por campo ausente — nada de frase combinada "livro/folha".
    LIVRO = 'Livro da origem não consta no documento'
    FOLHA = 'Folha da origem não consta no documento'

    def _payload_sem(self, *nomes):
        payload = self._payload_origem()
        for nome in nomes:
            payload['acts'][0]['origem'][nome] = self._campo('  ')
        return payload

    def _importar_e_avisos(self, payload):
        extracao = self._extracao(payload)
        resultado = self._importar(extracao)
        (linha,) = resultado['linhas']
        self.assertEqual(linha['status'], 'criado')
        return extracao, linha['avisos']

    def test_sem_livro_e_folha_avisa_um_por_campo_e_o_ato_continua_criado(self):
        _, avisos = self._importar_e_avisos(self._payload_sem('livro', 'folha'))

        self.assertEqual(avisos, [self.LIVRO, self.FOLHA])

    def test_so_o_livro_faltando_cita_so_o_livro(self):
        _, avisos = self._importar_e_avisos(self._payload_sem('livro'))

        self.assertEqual(avisos, [self.LIVRO])

    def test_so_a_folha_faltando_cita_so_a_folha(self):
        _, avisos = self._importar_e_avisos(self._payload_sem('folha'))

        self.assertEqual(avisos, [self.FOLHA])

    def test_com_livro_e_folha_nao_avisa(self):
        _, avisos = self._importar_e_avisos(self._payload_origem())

        self.assertEqual(avisos, [])

    def test_origem_so_com_cartorio_nao_avisa(self):
        payload = self._payload_origem()
        payload['acts'][0]['origem'] = {
            'cartorio': self._campo('CRI de Origem', 'CRI de Guaíra'),
        }
        _, avisos = self._importar_e_avisos(payload)

        self.assertEqual(avisos, [])

    def test_ato_sem_origem_nao_avisa(self):
        _, avisos = self._importar_e_avisos(payload_registro(self.job.job_id))

        self.assertEqual(avisos, [])

    @staticmethod
    def _rotulo_da_tela(nome):
        return descrever_aviso({
            'chave': f'/acts/0/origem/{nome}',
            'motivo': f'{nome}_origem_nao_consta', 'bloqueante': False,
        })['rotulo']

    # Fonte única: o rótulo que a tela dá ao motivo é, letra por letra, o
    # aviso que a importação devolve para o mesmo campo.
    def test_o_texto_do_livro_e_o_mesmo_da_tela(self):
        _, avisos = self._importar_e_avisos(self._payload_sem('livro'))

        self.assertEqual(avisos, [self._rotulo_da_tela('livro')])

    def test_o_texto_da_folha_e_o_mesmo_da_tela(self):
        _, avisos = self._importar_e_avisos(self._payload_sem('folha'))

        self.assertEqual(avisos, [self._rotulo_da_tela('folha')])

    def test_reimportar_devolve_o_mesmo_aviso(self):
        extracao, avisos = self._importar_e_avisos(
            self._payload_sem('livro', 'folha'),
        )
        versao = services.versao_bloco(extracao)

        repetida = importar(extracao, self.usuario, versao, ['/acts/0'])

        (linha,) = repetida['linhas']
        self.assertEqual(linha['status'], 'criado')
        self.assertEqual(linha['avisos'], [self.LIVRO, self.FOLHA])
        self.assertEqual(linha['avisos'], avisos)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_reimportar_com_livro_e_folha_nao_inventa_aviso(self):
        extracao, _ = self._importar_e_avisos(self._payload_origem())
        versao = services.versao_bloco(extracao)

        repetida = importar(extracao, self.usuario, versao, ['/acts/0'])

        (linha,) = repetida['linhas']
        self.assertEqual(linha['avisos'], [])

    def test_reimportar_ato_sem_origem_nao_avisa(self):
        extracao, _ = self._importar_e_avisos(payload_registro(self.job.job_id))
        versao = services.versao_bloco(extracao)

        repetida = importar(extracao, self.usuario, versao, ['/acts/0'])

        (linha,) = repetida['linhas']
        self.assertEqual(linha['avisos'], [])


class HerancaLivroFolhaDaOrigemTest(ImportacaoBase):
    """#324 rodada 4 (P2 do Codex): a revisão vence a herança na importação IA.

    O documento de origem JÁ EXISTE e o primeiro lançamento dele tem
    ``livro_origem``/``folha_origem`` preenchidos. A herança legada copiava
    esses valores para a ``LancamentoOrigem`` mesmo quando a revisão deixou
    os campos VAZIOS — no caminho IA o valor revisado (inclusive a ausência)
    prevalece. Sem listar o documento no MESMO imóvel do job: o sinal
    ``post_save`` (escopo só do imóvel) herda primeiro e a chamada explícita
    da importação reconcilia — o estado final é o revisado.
    """

    NUMERO = 'T366'

    def setUp(self):
        super().setUp()
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        self.cartorio_origem = Cartorios.objects.create(
            nome='CRI de Origem', cns='CNS-H324', cidade='Guaíra', estado='SP',
        )

    def _documento_de_origem_com_primeiro_lancamento(self):
        documento = Documento.objects.create(
            imovel=self.imovel, tipo=self.tipo_transcricao,
            numero=self.NUMERO, data=date(1990, 1, 1),
            cartorio=self.cartorio_origem, livro='1', folha='1',
        )
        # ``data`` é NOT NULL no lançamento: sem ela o fixture nem chega ao
        # que o teste quer provar (a herança do primeiro lançamento).
        Lancamento.objects.create(
            documento=documento, tipo=self.tipo_registro,
            data=date(1990, 1, 2),
            livro_origem='HERDADO', folha_origem='99',
        )
        return documento

    def test_origem_vazia_na_revisao_grava_null_na_lancamento_origem(self):
        existente = self._documento_de_origem_com_primeiro_lancamento()
        payload = self._payload_origem()
        payload['acts'][0]['origem']['livro'] = self._campo('  ')
        payload['acts'][0]['origem']['folha'] = self._campo('  ')
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get(documento=self.documento)
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        # A herança ('HERDADO', '99') não preenche o que a revisão deixou vazio.
        self.assertIsNone(origem.livro)
        self.assertIsNone(origem.folha)
        self.assertIsNone(lancamento.livro_origem)
        self.assertIsNone(lancamento.folha_origem)
        # O documento existente é reaproveitado e a FK vinculada a ele.
        self.assertEqual(lancamento.documento_origem, existente)
        self.assertFalse(ImportacaoIA.objects.filter(modelo='Documento').exists())

    def test_origem_preenchida_na_revisao_grava_os_valores_informados(self):
        existente = self._documento_de_origem_com_primeiro_lancamento()
        # O payload-base traz livro '2' e folha '123' revisados.
        extracao = self._extracao(self._payload_origem())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get(documento=self.documento)
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertEqual(origem.livro, '2')
        self.assertEqual(origem.folha, '123')
        self.assertNotEqual(origem.livro, 'HERDADO')
        self.assertEqual(lancamento.documento_origem, existente)
