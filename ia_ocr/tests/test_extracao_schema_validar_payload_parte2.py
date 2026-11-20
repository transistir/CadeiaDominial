"""Parte do corpo de ``ValidarPayload``; coletada pela fachada."""

import logging

from ia_ocr.extracao_schema import PayloadExtracaoInvalido, validar_payload
from .test_extracao_schema_base import (
    V1_2, ato, ato_com_transmissao, campo,
    payload_minimo,
)

class ValidarPayloadParte2:
    def test_data_invalida_em_campo_nao_derruba_payload(self):
        """format NÃO se aplica a campo de valor: data impossível ou fora
        do ISO passa na validação estrutural — quem trata é a
        desnormalização (normalized=NULL + requer_revisao).
        """
        for normalized in ('2024-02-30', '31/12/2024'):
            with self.subTest(normalized=normalized):
                payload = payload_minimo()
                payload['document']['data'] = campo(normalized, raw=normalized)

                validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_evidencia_aceita_bbox_opcional(self):
        """A3 v1.1: evidence aceita bbox [x0, y0, x1, y1] em pixels do OCR
        (opcional, array de 4 números) sem rejeitar o payload."""
        payload = payload_minimo()
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'trecho': 'matrícula nº 42.718',
            'bbox': [10.0, 20.0, 30.0, 40.0],
        }

        validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_evidencia_continua_exigindo_trecho(self):
        """A3 v1.1: bbox NÃO substitui o trecho — evidence sem `trecho`
        continua rejeitada (required de #/$defs/evidence)."""
        payload = payload_minimo()
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'bbox': [10.0, 20.0, 30.0, 40.0],
        }

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'schema_violado')
        self.assertEqual(ctx.exception.caminho, '$.document.numero.evidencia')

    def test_rejeita_meta_data_invalida(self):
        """texto_confirmado_em é o único lugar com formato estrito."""
        for valor in ('2024-02-30T10:00:00Z', '32/13/2024 10:00', 'ontem'):
            with self.subTest(valor='data impossível ou não-ISO'):
                payload = payload_minimo()
                payload['meta']['texto_confirmado_em'] = valor

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'formato_invalido')
                self.assertEqual(
                    ctx.exception.caminho, '$.meta.texto_confirmado_em'
                )

    def test_aceita_meta_data_iso_valida(self):
        """date-time ISO legítimo (com ou sem offset) passa em meta."""
        for valor in ('2024-02-29T10:00:00', '2024-02-29T10:00:00Z'):
            with self.subTest(valor=valor):
                payload = payload_minimo()
                payload['meta']['texto_confirmado_em'] = valor

                validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_rejeita_ordem_repetida(self):
        """Dois atos com a mesma `ordem` cronológica → rejeita no 2º."""
        payload = payload_minimo()
        payload['acts'] = [ato(ordem=1), ato(ordem=1)]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'ordem_repetida')
        self.assertEqual(ctx.exception.caminho, '$.acts[1].ordem')

    def test_rejeita_301_atos(self):
        """Mais de 300 atos é lixo estrutural (matrícula real tem dezenas)."""
        payload = payload_minimo()
        payload['acts'] = [ato(ordem=indice + 1) for indice in range(301)]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'limite_excedido')
        self.assertEqual(ctx.exception.caminho, '$.acts')

    def test_rejeita_41_partes_em_um_ato(self):
        """Atos com mais de 40 partes é lixo estrutural, não leitura real."""
        payload = payload_minimo()
        payload['acts'] = [ato(ordem=1, partes=41)]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'limite_excedido')
        self.assertEqual(ctx.exception.caminho, '$.acts[0].partes')

    def test_limites_sao_inclusivos(self):
        """300 atos e 40 partes em um ato (fronteira) passam, cada um."""
        com_300 = payload_minimo()
        com_300['acts'] = [ato(ordem=indice + 1) for indice in range(300)]
        validar_payload(com_300, self.JOB_ID, (1,))  # não levanta

        com_40 = payload_minimo()
        com_40['acts'] = [ato(ordem=1, partes=40)]
        validar_payload(com_40, self.JOB_ID, (1,))  # não levanta

    def test_rejeita_texto_de_10001_chars(self):
        """String de valor acima de 10 000 chars é lixo, não leitura real."""
        payload = payload_minimo()
        payload['document']['numero']['normalized'] = 'x' * 10001

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'campo_muito_longo')
        self.assertEqual(
            ctx.exception.caminho, '$.document.numero.normalized'
        )

    def test_campo_muito_longo_em_chave_inventada_sanitiza_caminho(self):
        """P1 (#339 r2): os campos A3 (`field*` em `$defs`) aceitam chaves
        extras, então uma chave inventada com nome+CPF e valor gigante passa
        na validação estrutural e explode na varredura — o caminho sai
        sanitizado; nem a chave nem o valor vão para a exceção ou para log."""
        chave = 'JOAO_DA_SILVA_CPF_12345678900'
        payload = payload_minimo()
        payload['document']['numero'][chave] = 'x' * 10001

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'campo_muito_longo')
        self.assertEqual(ctx.exception.caminho, '$.document.numero.<campo>')
        self.assertNotIn(chave, str(ctx.exception))
        self.assertNotIn(chave, repr(ctx.exception))

        with self.assertLogs('ia_ocr', level='ERROR') as registros:
            try:
                validar_payload(payload, self.JOB_ID, (1,))
            except PayloadExtracaoInvalido as exc:
                logging.getLogger('ia_ocr').error(str(exc))
        self.assertNotIn(chave, '\n'.join(registros.output))

    def test_campo_muito_longo_em_campo_conhecido_mantem_caminho(self):
        """Caso legítimo continua por extenso: campo conhecido dos contratos
        (`$.acts[0].data_transacao.normalized`) aparece no caminho."""
        payload = payload_minimo(versao=V1_2)
        payload['acts'] = [ato_com_transmissao()]
        payload['acts'][0]['data_transacao']['normalized'] = 'x' * 10001

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'campo_muito_longo')
        self.assertEqual(
            ctx.exception.caminho, '$.acts[0].data_transacao.normalized'
        )

    def test_erro_nao_carrega_valor(self):
        """`str(exc)` e os logs nunca carregam o valor do payload (PII).

        Mesmo na rejeição cujo critério é o próprio valor (tamanho), a
        mensagem vive só de código + caminho.
        """
        marcador = 'MARCADOR-UNICO-X7KQ39DF'
        payload = payload_minimo()
        payload['document']['numero']['normalized'] = (
            'z' * 10001 + ' ' + marcador
        )

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(
            str(ctx.exception),
            'campo_muito_longo ($.document.numero.normalized)',
        )
        self.assertNotIn(marcador, str(ctx.exception))
        self.assertNotIn(marcador, repr(ctx.exception))

        with self.assertLogs('ia_ocr', level='ERROR') as registros:
            try:
                validar_payload(payload, self.JOB_ID, (1,))
            except PayloadExtracaoInvalido as exc:
                logging.getLogger('ia_ocr').error(str(exc))
        self.assertNotIn(marcador, '\n'.join(registros.output))

