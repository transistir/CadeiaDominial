"""Testes da importação assistida — migração VERBATIM de
``ia_ocr/tests/test_importacao.py`` (Etapa 9 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports e a linha
``class X(ImportacaoBase)``.

Parte 1 de 3 da classe ``VinculoDocumentoOrigemTest`` — 816 linhas
não cabem em um arquivo de 400. Classe SIMPLES (sem ``TestCase``):
o discovery do Django não a coleta; quem coleta é a fachada em
``test_importacao_vinculo_origem.py``. Corpos verbatim.
"""

from copy import deepcopy
from datetime import date
from django.db.models import ProtectedError
from django.urls import reverse
from dominial.models import (
    Cartorios, Documento, DocumentoDigital, DocumentoTipo, Imovel, Lancamento,
    LancamentoOrigem, LancamentoPessoa, LancamentoTipo, Pessoas, TIs, UserTI,
)
from dominial.utils.segregacao_utils import MENSAGEM_ORIGEM_RESTRITA
from ia_ocr import services
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import CampoSugerido, ExtracaoSugerida, ImportacaoIA, OcrJob, PaginaOcr
from ia_ocr.revisao import (
    CAMPOS_DA_ORIGEM, ParteRevisada, RevisaoInvalidada, dados_revisados,
    desnormalizar, descrever_aviso,
)
from .factories import criar_documento_digital, criar_usuario
from .payloads_extracao import (
    SCHEMA_VERSION, TEXTO_PAGINA_1, payload_averbacao, payload_com_closure,
    payload_registro,
)


class VinculoDocumentoOrigemParte1:
    """#324 (I-11d): a importação grava ``Lancamento.documento_origem``.

    Só a importação assistida grava essa FK (o fluxo manual segue como
    está). O documento só é CRIADO pela regra anti-órfão (início de
    matrícula); nos demais tipos o vínculo vale quando a identidade
    (tipo + número + cartório) já existe NO ESCOPO do usuário.
    """

    NUMERO = 'T366'


    def setUp(self):
        super().setUp()
        self.tipo_transcricao = DocumentoTipo.objects.create(tipo='transcricao')
        LancamentoTipo.objects.create(tipo='inicio_matricula')
        self.cartorio_origem = Cartorios.objects.create(
            nome='CRI de Origem', cns='CNS-324', cidade='Guaíra', estado='SP',
        )


    def _payload_inicio(self):
        """Início de matrícula: único tipo que cria o documento de origem."""
        payload = self._payload_origem()
        payload['acts'][0]['tipo_sugerido'] = self._campo(
            'inicio_matricula', 'R-1/42.718',
        )
        # O rótulo de matrícula evita que o 'R-1' do payload-base vença.
        payload['acts'][0]['rotulo'] = self._campo('M-1', 'R-1/42.718')
        return payload


    def _imovel_em(self, ti, nome):
        return Imovel.objects.create(
            nome=nome, matricula=f'MAT-{nome}', terra_indigena_id=ti,
            proprietario=self.imovel.proprietario, cartorio=self.imovel.cartorio,
        )


    def _documento_da_origem_em(self, imovel):
        return Documento.objects.create(
            imovel=imovel, tipo=self.tipo_transcricao, numero=self.NUMERO,
            data=date(1990, 1, 1), cartorio=self.cartorio_origem,
            livro='1', folha='1',
        )


    def _outros_documentos(self):
        return Documento.objects.exclude(pk=self.documento.pk)


    def test_origem_nova_cria_o_documento_e_vincula_a_fk(self):
        extracao = self._extracao(self._payload_inicio())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        (documento_origem,) = self._outros_documentos()
        self.assertEqual(lancamento.documento_origem, documento_origem)
        self.assertEqual(documento_origem.imovel, self.imovel)
        # A auditoria já registrava o documento criado e segue registrando.
        vinculo = ImportacaoIA.objects.get(modelo='Documento')
        self.assertEqual(vinculo.objeto_id, documento_origem.pk)
        self.assertEqual(vinculo.campo.chave, '/acts/0/origem/numero')


    def test_troca_de_tipo_na_revisao_leva_a_origem_declarada_ate_a_fk(self):
        """P1 (rodada 2) ponta a ponta: a origem declarada NA REVISÃO chega à FK.

        O serviço sugeriu AVERBAÇÃO sem bloco de origem no payload. O revisor
        troca o tipo para início de matrícula pelo caminho real de salvar o
        bloco (o mesmo ``services.salvar_bloco`` da view — as linhas da
        origem nascem AÍ, não no desmonte), preenche a origem, finaliza e
        importa: ``LancamentoOrigem``, ``Documento`` criado com o
        tipo+número+cartório declarados e a ``documento_origem`` vinculada.
        """
        # O fixture cria o job já ``revisado`` e a extração finalizada; a
        # revisão real roda com o job ``extraido`` e a extração aberta.
        OcrJob.objects.filter(pk=self.job.pk).update(status='extraido')
        extracao = self._extracao(payload_averbacao(self.job.job_id))
        ExtracaoSugerida.objects.filter(pk=extracao.pk).update(
            finalizada_em=None,
        )

        _, versao, _, _ = services.salvar_bloco(
            extracao,
            {'/acts/0/tipo_sugerido': {
                'incluir': True, 'valor': 'inicio_matricula', 'conferido': True,
            }},
            self.usuario, services.versao_bloco(extracao),
        )
        for nome in CAMPOS_DA_ORIGEM:
            with self.subTest(nome=nome):
                self.assertEqual(
                    extracao.campos.filter(
                        chave=f'/acts/0/origem/{nome}',
                    ).count(),
                    1,
                )

        decisoes = {
            f'/acts/0/origem/{nome}': {
                'incluir': True, 'valor': valor, 'conferido': True,
            }
            for nome, valor in (
                ('tipo_documento', 'transcricao'),
                ('numero', self.NUMERO),
                ('livro', '2'),
                ('folha', '123'),
                ('data', '1990-01-02'),
            )
        }
        # O cartório da origem já existe no cadastro: o revisor o escolhe.
        decisoes['/acts/0/origem/cartorio'] = {
            'incluir': True, 'conferido': True,
            'escolha': {'cartorio_escolhido_id': self.cartorio_origem.pk},
        }
        services.salvar_bloco(extracao, decisoes, self.usuario, versao)

        extracao = services.finalizar_revisao(extracao, self.usuario)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        origem = LancamentoOrigem.objects.get(lancamento=lancamento)
        self.assertEqual(origem.tipo_documento, 'transcricao')
        self.assertEqual(origem.numero, self.NUMERO)
        self.assertEqual(origem.cartorio, self.cartorio_origem)
        (documento_origem,) = self._outros_documentos()
        self.assertEqual(documento_origem.tipo, self.tipo_transcricao)
        self.assertEqual(documento_origem.numero, self.NUMERO)
        self.assertEqual(documento_origem.cartorio, self.cartorio_origem)
        self.assertIsNotNone(lancamento.documento_origem)
        self.assertEqual(lancamento.documento_origem, documento_origem)


    def test_registro_com_origem_inexistente_nao_cria_nem_vincula(self):
        extracao = self._extracao(self._payload_origem())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertIsNone(Lancamento.objects.get().documento_origem)
        self.assertFalse(self._outros_documentos().exists())


    def test_origem_existente_em_outro_imovel_do_usuario_vincula_sem_criar(self):
        irmao = self._imovel_em(self.imovel.terra_indigena_id, 'Irmão')
        existente = self._documento_da_origem_em(irmao)
        extracao = self._extracao(self._payload_origem())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(
            list(self._outros_documentos()), [existente],
        )
        self.assertEqual(Lancamento.objects.get().documento_origem, existente)
        self.assertFalse(ImportacaoIA.objects.filter(modelo='Documento').exists())


    def test_origem_em_ti_de_outro_usuario_nao_vincula_nem_vaza(self):
        ti_alheia = TIs.objects.create(
            nome='TI Alheia 324', codigo='TI-A324', etnia='Teste',
        )
        alheio = self._imovel_em(ti_alheia, 'ImovelAlheio324')
        documento_alheio = self._documento_da_origem_em(alheio)
        extracao = self._extracao(self._payload_origem())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        (linha,) = resultado['linhas']
        self.assertEqual(linha['status'], 'criado')
        lancamento = Lancamento.objects.get()
        self.assertIsNone(lancamento.documento_origem)
        # Nenhum documento novo: o alheio é o único além do do job.
        self.assertEqual(list(self._outros_documentos()), [documento_alheio])
        self.assertTrue(any(
            MENSAGEM_ORIGEM_RESTRITA in aviso for aviso in linha['avisos']
        ), linha['avisos'])
        # Nada do documento/imóvel alheio no que o usuário recebe nem no
        # rastro de auditoria (o número é de quem não tem acesso).
        visivel = repr(resultado) + repr(list(
            ImportacaoIA.objects.values()
        ))
        for segredo in (self.NUMERO, 'ImovelAlheio324', 'TI Alheia 324'):
            with self.subTest(segredo=segredo):
                self.assertNotIn(segredo, visivel)
        # O id do documento alheio nunca vira vínculo de auditoria.
        self.assertFalse(ImportacaoIA.objects.filter(modelo='Documento').exists())
        self.assertFalse(
            ImportacaoIA.objects.filter(objeto_id=documento_alheio.pk)
            .exclude(modelo__in=('Lancamento', 'LancamentoOrigem', 'Cartorios',
                                 'LancamentoPessoa', 'Pessoas'))
            .exists()
        )


    def test_dois_atos_com_a_mesma_origem_geram_um_documento(self):
        payload = self._payload_inicio()
        segundo = deepcopy(payload['acts'][0])
        segundo['ordem'] = 2
        segundo['rotulo'] = self._campo('R-2', 'R-1/42.718')
        segundo['tipo_sugerido'] = self._campo('registro', 'R-1/42.718')
        payload['acts'].append(segundo)
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(Lancamento.objects.count(), 2)
        (documento_origem,) = self._outros_documentos()
        self.assertEqual(
            set(Lancamento.objects.values_list('documento_origem', flat=True)),
            {documento_origem.pk},
        )
        self.assertEqual(
            ImportacaoIA.objects.filter(modelo='Documento').count(), 1,
        )


    def test_reimportar_nao_muda_documentos_nem_fk(self):
        extracao = self._extracao(self._payload_inicio())
        primeira = self._importar(extracao)
        lancamento = Lancamento.objects.get()
        (documento_origem,) = self._outros_documentos()
        versao = services.versao_bloco(extracao)

        segunda = importar(extracao, self.usuario, versao, ['/acts/0'])

        self.assertEqual(segunda['linhas'][0]['lancamento_id'], lancamento.pk)
        self.assertEqual(primeira['ok'], segunda['ok'])
        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(list(self._outros_documentos()), [documento_origem])
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.documento_origem, documento_origem)

    # Número do documento da TI B gravado COM espaço interno: a mesma
    # identidade da origem declarada 'T366' (a normalização só tira o prefixo
    # e as bordas), mas um texto que só o card do DOCUMENTO imprime. O 'T366'
    # da origem declarada é dado do PRÓPRIO lançamento e segue na página de
    # quem não tem o escopo; sem esta diferença o teste não distinguiria o
    # que vem do documento alheio do que é do lançamento.
    NUMERO_DO_DOCUMENTO_NA_TI_B = 'T 366'


    def test_leitor_sem_escopo_na_fk_nao_ve_o_documento_de_origem(self):
        """P1 (rodada 4, Codex): a FK vale o escopo de QUEM LÊ.

        O usuário A (TIs A+B) importa um início de matrícula cuja origem já
        existe na TI B: a importação reaproveita o documento e grava a FK. O
        usuário B (só a TI A) abre o detalhe do lançamento — a página vem,
        mas sem o card "Documento de Origem" e sem nada do documento da TI B
        (número, imóvel, TI, link). Para A, que tem as duas TIs, o card
        aparece. A view nunca salva: a FK segue gravada no banco depois das
        duas leituras.
        """
        ti_b = TIs.objects.create(
            nome='TI B do A 324', codigo='TI-B324', etnia='Teste',
        )
        imovel_b = self._imovel_em(ti_b, 'ImovelDoA324')
        UserTI.objects.create(user=self.usuario, tis=ti_b)
        documento_ti_b = Documento.objects.create(
            imovel=imovel_b, tipo=self.tipo_transcricao,
            numero=self.NUMERO_DO_DOCUMENTO_NA_TI_B, data=date(1990, 1, 1),
            cartorio=self.cartorio_origem, livro='1', folha='1',
        )
        extracao = self._extracao(self._payload_inicio())

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        # O documento da TI B é o único além do do job: a importação o
        # reaproveitou (escopo de A) e a FK aponta para ele.
        self.assertEqual(list(self._outros_documentos()), [documento_ti_b])
        self.assertEqual(lancamento.documento_origem, documento_ti_b)
        self.assertEqual(documento_ti_b.imovel, imovel_b)

        url = reverse('lancamento_detail', kwargs={
            'tis_id': self.imovel.terra_indigena_id_id,
            'imovel_id': self.imovel.pk,
            'lancamento_id': lancamento.pk,
        })
        leitor = criar_usuario()
        UserTI.objects.create(
            user=leitor, tis=self.imovel.terra_indigena_id,
        )
        self.client.force_login(leitor)

        pagina_do_leitor = self.client.get(url)

        self.assertEqual(pagina_do_leitor.status_code, 200)
        conteudo_do_leitor = pagina_do_leitor.content.decode()
        # O card do documento de origem some e com ele o que é só do
        # documento alheio: número, imóvel, TI e o link por id.
        self.assertNotIn('Documento de Origem', conteudo_do_leitor)
        for alheio in (
            self.NUMERO_DO_DOCUMENTO_NA_TI_B, 'ImovelDoA324', 'TI B do A 324',
            f'/documento/{documento_ti_b.pk}/',
        ):
            with self.subTest(alheio=alheio):
                self.assertNotIn(alheio, conteudo_do_leitor)
        # O que é do PRÓPRIO lançamento continua na página do leitor.
        self.assertIn('T366', conteudo_do_leitor)
        # A leitura de quem não tem o escopo não grava nada no vínculo.
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.documento_origem_id, documento_ti_b.pk)

        self.client.force_login(self.usuario)

        pagina_do_a = self.client.get(url)

        self.assertEqual(pagina_do_a.status_code, 200)
        conteudo_do_a = pagina_do_a.content.decode()
        self.assertIn('Documento de Origem', conteudo_do_a)
        self.assertIn(self.NUMERO_DO_DOCUMENTO_NA_TI_B, conteudo_do_a)
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.documento_origem_id, documento_ti_b.pk)

    # --- FK PROTECT: o documento de origem importado não se exclui ----------
    # Comportamento ATUAL (``on_delete=PROTECT``), fixado sem mexer no modelo:
    # trocar o ``on_delete`` é decisão de modelo/migration, fora desta rodada.


    def _importar_inicio_e_pegar_o_documento_de_origem(self):
        extracao = self._extracao(self._payload_inicio())
        self.assertTrue(self._importar(extracao)['ok'])
        lancamento = Lancamento.objects.get()
        (documento_origem,) = self._outros_documentos()
        self.assertEqual(lancamento.documento_origem, documento_origem)
        return lancamento, documento_origem


    def test_excluir_o_documento_de_origem_importado_levanta_protected_error(self):
        lancamento, documento_origem = (
            self._importar_inicio_e_pegar_o_documento_de_origem()
        )

        with self.assertRaises(ProtectedError) as contexto:
            documento_origem.delete()

        # O que bloqueia é o lançamento importado pela IA; nada foi apagado.
        self.assertEqual(
            list(contexto.exception.protected_objects), [lancamento],
        )
        self.assertTrue(
            Documento.objects.filter(pk=documento_origem.pk).exists()
        )
        lancamento.refresh_from_db()
        self.assertEqual(lancamento.documento_origem, documento_origem)
