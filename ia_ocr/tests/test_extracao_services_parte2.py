"""Parte 2 de 2 do corpo de ``SolicitarExtracaoTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_extracao_services.py``.
"""

"""Orquestração da extração com backend falso, sem rede ou documentos reais."""



from ia_ocr import estados, services
from ia_ocr.extracao_backends import ExtracaoBackendError, ResultadoExtracao
from ia_ocr.models import ExtracaoSugerida, OcrJob

from .payloads_extracao import (
    PROVIDER, SCHEMA_VERSION, _campo,
)

# Pinados de propósito (não derivados de SCHEMA_VERSION): o que o serviço
# responde e o que o app pede são contratos, não detalhe de implementação.
V1_1 = 'umbelino-extracao-matricula-v1.1'
V1_2 = 'umbelino-extracao-matricula-v1.2'


V1_1 = 'umbelino-extracao-matricula-v1.1'
V1_2 = 'umbelino-extracao-matricula-v1.2'


class SolicitarExtracaoTestParte2:
    def test_vigente_alterada_durante_http_recusa_resposta(self):
        def extrair(requisicao):
            ExtracaoSugerida.objects.create(
                ocr_job=self.job, schema_version=SCHEMA_VERSION, provider=PROVIDER,
                payload=self.envelope['extracao'], payload_servico=self.envelope['extracao'],
            )
            return self.envelope

        self.extrair.side_effect = extrair
        with self.assertRaises(services.ExtracaoConcorrente):
            services.solicitar_extracao(self.job, self.usuario)

        self.assertReservaLimpa()
        self.assertEqual(self.job.extracoes.count(), 1)
        self.assertEqual(self.job.status, estados.CONCLUIDO)
        self.assertFalse(self.job.paginas.filter(corrigido_em__isnull=False).exists())

    def test_payload_invalido_limpa_reserva_sem_gravar(self):
        self.envelope['extracao']['meta']['job_id'] = 'id-invalido-do-servico'

        with self.assertRaises(services.ExtracaoPayloadInvalido) as contexto:
            services.solicitar_extracao(self.job, self.usuario)

        self.assertEqual(contexto.exception.codigo, 'job_id_invalido')
        self.assertEqual(contexto.exception.caminho, '$.meta.job_id')
        self.assertSemPersistencia()

    def test_requisicao_sai_com_o_schema_version_v1_2(self):
        """A requisição pede o contrato mais novo (literal pinado: o serviço
        já responde v1.2 e a versão pedida não pode voltar a v1.1)."""
        services.solicitar_extracao(self.job, self.usuario)

        requisicao = self.extrair.call_args.args[0]
        self.assertEqual(requisicao['schema_version'], V1_2)
        self.assertEqual(SCHEMA_VERSION, V1_2)

    def test_aceita_payload_v1_2_com_transmissao_do_ato(self):
        """Regressão do incidente: o serviço responde v1.2 com livro/folha/data
        da transmissão no ato e a extração é persistida — antes caía em
        'O serviço de extração não respondeu' (propriedade_extra)."""
        self.assertEqual(self.envelope['extracao']['schema_version'], V1_2)
        ato = self.envelope['extracao']['acts'][0]
        ato['livro_transacao'] = _campo('10-A', 'R-1/42.718')
        ato['folha_transacao'] = _campo('25v', 'R-1/42.718')
        ato['data_transacao'] = _campo('2019-12-20', 'R-1/42.718')

        extracao = services.solicitar_extracao(self.job, self.usuario)

        self.assertEqual(extracao.schema_version, V1_2)
        campos = {campo.chave: campo for campo in extracao.campos.all()}
        self.assertEqual(campos['/acts/0/livro_transacao'].normalized, '10-A')
        self.assertEqual(campos['/acts/0/folha_transacao'].normalized, '25v')
        self.assertEqual(campos['/acts/0/data_transacao'].normalized, '2019-12-20')
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertReservaLimpa()

    def test_aceita_payload_v1_1_de_servico_antigo(self):
        """Serviço que ainda responde v1.1 continua funcionando (rollout): o
        payload vale pelo contrato que declara e a versão é a do payload."""
        self.envelope['extracao']['schema_version'] = V1_1

        extracao = services.solicitar_extracao(self.job, self.usuario)

        self.assertEqual(extracao.schema_version, V1_1)
        self.assertEqual(extracao.payload_servico['schema_version'], V1_1)
        self.assertEqual(self.job.status, estados.EXTRAIDO)
        self.assertReservaLimpa()

    def test_payload_fora_do_contrato_vira_extracao_payload_invalido(self):
        """O serviço respondeu, mas o payload não cumpre o contrato que ele
        mesmo declara (aqui, v1.1 com `data_transacao`): exceção própria com
        código + caminho — não o genérico 'serviço indisponível'."""
        self.envelope['extracao']['schema_version'] = V1_1
        self.envelope['extracao']['acts'][0]['data_transacao'] = _campo(
            '2019-12-20', 'R-1/42.718',
        )

        with self.assertRaises(services.ExtracaoPayloadInvalido) as contexto:
            services.solicitar_extracao(self.job, self.usuario)

        erro = contexto.exception
        self.assertNotIsInstance(erro, services.ExtracaoIndisponivel)
        self.assertEqual(erro.code, 'extracao_payload_invalido')
        self.assertEqual(erro.codigo, 'propriedade_extra')
        self.assertEqual(erro.caminho, '$.acts[0].data_transacao')
        self.assertSemPersistencia()

    def test_schema_version_desconhecida_vira_extracao_payload_invalido(self):
        self.envelope['extracao']['schema_version'] = 'umbelino-extracao-matricula-v9'

        with self.assertRaises(services.ExtracaoPayloadInvalido) as contexto:
            services.solicitar_extracao(self.job, self.usuario)

        self.assertEqual(contexto.exception.codigo, 'schema_versao_desconhecida')
        self.assertEqual(contexto.exception.caminho, '$.schema_version')
        self.assertSemPersistencia()

    def test_payload_fora_do_contrato_loga_codigo_e_caminho_sem_valores(self):
        """Só estrutura vai ao log e à exceção: nenhum valor do serviço."""
        marcador = 'MARCADOR-PII-X7KQ39DF'
        self.envelope['extracao']['schema_version'] = V1_1
        ato = self.envelope['extracao']['acts'][0]
        ato['data_transacao'] = _campo(marcador, marcador, raw=marcador)
        ato['partes'][0]['nome'] = _campo(marcador, marcador)

        with self.assertLogs('ia_ocr.services', level='WARNING') as registros:
            with self.assertRaises(services.ExtracaoPayloadInvalido) as contexto:
                services.solicitar_extracao(self.job, self.usuario)

        saida = '\n'.join(registros.output)
        self.assertIn('propriedade_extra', saida)
        self.assertIn('$.acts[0].data_transacao', saida)
        self.assertIn(str(self.job.job_id), saida)
        self.assertNotIn(marcador, saida)
        self.assertNotIn(marcador, str(contexto.exception))
        self.assertNotIn(marcador, repr(contexto.exception))

    def test_payload_com_chave_inventada_loga_caminho_sanitizado(self):
        """P1 (#339 r2): os campos A3 aceitam chaves extras, então uma chave
        inventada (nome+CPF) com valor gigante passa na validação estrutural
        e explode na varredura — o caminho vai SANITIZADO ao log e à exceção;
        nem a chave nem o valor aparecem."""
        chave = 'JOAO_DA_SILVA_CPF_12345678900'
        self.envelope['extracao']['document']['numero'][chave] = 'x' * 10001

        with self.assertLogs('ia_ocr.services', level='WARNING') as registros:
            with self.assertRaises(services.ExtracaoPayloadInvalido) as contexto:
                services.solicitar_extracao(self.job, self.usuario)

        saida = '\n'.join(registros.output)
        self.assertIn('campo_muito_longo', saida)
        self.assertIn('$.document.numero.<campo>', saida)
        self.assertNotIn(chave, saida)
        self.assertNotIn('x' * 100, saida)
        erro = contexto.exception
        self.assertEqual(erro.codigo, 'campo_muito_longo')
        self.assertEqual(erro.caminho, '$.document.numero.<campo>')
        self.assertNotIn(chave, str(erro))
        self.assertSemPersistencia()

    def test_falha_do_backend_loga_codigo_sem_mensagem_e_segue_indisponivel(self):
        """Falha da chamada (transporte/autenticação/tamanho) continua sendo
        `ExtracaoIndisponivel` para a tela — o código estável vai ao log, a
        mensagem do backend não."""
        self.extrair.side_effect = ExtracaoBackendError(
            'PRAZO_ESGOTADO', 'Mensagem externa não deve vazar',
        )

        with self.assertLogs('ia_ocr.services', level='WARNING') as registros:
            with self.assertRaises(services.ExtracaoIndisponivel) as contexto:
                services.solicitar_extracao(self.job, self.usuario)

        saida = '\n'.join(registros.output)
        self.assertEqual(registros.records[0].levelname, 'WARNING')
        self.assertIn('PRAZO_ESGOTADO', saida)
        self.assertIn(str(self.job.job_id), saida)
        self.assertNotIn('Mensagem externa', saida)
        self.assertNotIsInstance(contexto.exception, services.ExtracaoPayloadInvalido)
        self.assertSemPersistencia()

    def test_incompativel_do_backend_vira_extracao_incompativel(self):
        """422 do serviço (EXTRACAO_INCOMPATIVEL): o serviço respondeu e
        recusou o formato da requisição — exceção própria em vez de
        `ExtracaoIndisponivel` ("não respondeu" mentiria); a reserva é
        limpa e nada é gravado."""
        self.extrair.side_effect = ExtracaoBackendError(
            'EXTRACAO_INCOMPATIVEL', 'Mensagem externa não deve vazar',
        )

        with self.assertLogs('ia_ocr.services', level='WARNING') as registros:
            with self.assertRaises(services.ExtracaoIncompativel) as contexto:
                services.solicitar_extracao(self.job, self.usuario)

        saida = '\n'.join(registros.output)
        self.assertIn('EXTRACAO_INCOMPATIVEL', saida)
        self.assertIn(str(self.job.job_id), saida)
        self.assertNotIn('Mensagem externa', saida)
        self.assertEqual(contexto.exception.code, 'extracao_incompativel')
        self.assertNotIsInstance(contexto.exception, services.ExtracaoIndisponivel)
        self.assertNotIsInstance(contexto.exception, services.ExtracaoPayloadInvalido)
        self.assertSemPersistencia()

    def test_codigo_do_backend_fora_do_padrao_nao_vai_ao_log(self):
        """O backend é plugável (EXTRACAO_BACKEND): só identificador estável
        (MAIUSCULAS_E_UNDERLINE) vira log — texto livre, quebra de linha,
        código gigante ou tipo errado viram DESCONHECIDO."""
        casos = (
            'mensagem solta com dado pessoal',
            'COD\nIGO',
            'X' * 200,
            None,
        )
        for codigo in casos:
            with self.subTest(codigo=repr(codigo)):
                self.extrair.side_effect = ExtracaoBackendError(codigo, 'detalhe')

                with self.assertLogs('ia_ocr.services', level='WARNING') as registros:
                    with self.assertRaises(services.ExtracaoIndisponivel):
                        services.solicitar_extracao(self.job, self.usuario)

                saida = '\n'.join(registros.output)
                self.assertIn('codigo=DESCONHECIDO', saida)
                if isinstance(codigo, str):
                    self.assertNotIn(codigo, saida)

    def test_erro_inesperado_loga_so_o_tipo_da_excecao(self):
        """O que não é backend nem payload segue `ExtracaoIndisponivel`, mas
        deixa rastro: o TIPO da exceção (sem mensagem, sem traceback)."""
        self.extrair.side_effect = RuntimeError('Detalhes internos não devem vazar')

        with self.assertLogs('ia_ocr.services', level='ERROR') as registros:
            with self.assertRaises(services.ExtracaoIndisponivel):
                services.solicitar_extracao(self.job, self.usuario)

        saida = '\n'.join(registros.output)
        self.assertIn('RuntimeError', saida)
        self.assertIn(str(self.job.job_id), saida)
        self.assertNotIn('Detalhes internos', saida)
        self.assertIsNone(registros.records[0].exc_info)
        self.assertSemPersistencia()

    def test_envelope_incompleto_limpa_reserva_sem_gravar(self):
        self.envelope['paginas'].pop()

        with self.assertRaises(services.ExtracaoIndisponivel):
            services.solicitar_extracao(self.job, self.usuario)

        self.assertSemPersistencia()

    def test_aceita_envelope_no_resultado_do_backend_atual(self):
        self.backend.envelope = ResultadoExtracao(payload=self.envelope)

        extracao = services.solicitar_extracao(self.job, self.usuario)

        self.assertEqual(extracao.payload_servico, self.envelope['extracao'])
        self.assertReservaLimpa()

    def test_ambas_transicoes_para_extraido_exigem_extracao(self):
        for status in (estados.CONCLUIDO, estados.TEXTO_CONFIRMADO):
            with self.subTest(status=status):
                OcrJob.objects.filter(pk=self.job.pk).update(status=status)
                self.job.refresh_from_db()
                with self.assertRaises(estados.TransicaoInvalida) as contexto:
                    self.job.transicionar(estados.EXTRAIDO, usuario=self.usuario)
                self.assertEqual(contexto.exception.code, 'sem_extracao')
                self.job.refresh_from_db()
                self.assertEqual(self.job.status, status)
                self.assertFalse(self.job.transicoes.exists())
