"""Testes do validador do payload de extração (schema A3 vendorizado).

O contrato é o JSON em ia_ocr/schemas/, cópia byte a byte do serviço de
OCR — nunca editado à mão. A validação estrutural usa Draft 2020-12 SEM
format_checker: `format` em campo de valor é anotação (data inválida vira
normalized=NULL + requer_revisao na desnormalização, não rejeição).
"""

import hashlib
import json
import logging
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from jsonschema import Draft202012Validator

from ia_ocr import extracao_schema
from ia_ocr.extracao_schema import (
    SCHEMA_PATH,
    SCHEMA_VERSION,
    PayloadExtracaoInvalido,
    validar_payload,
)
from ia_ocr.tests.payloads_extracao import payload_registro


def campo(normalized=None, raw=None, confianca=0.9, evidencia=None):
    """Campo A3 mínimo: raw/normalized/confianca/requer_revisao/evidencia."""
    return {
        'raw': raw,
        'normalized': normalized,
        'confianca': confianca,
        'requer_revisao': False,
        'evidencia': evidencia,
    }


def ato(ordem=1, partes=0):
    """Atos A3 mínimo: campos required de #/$defs/act + `partes`."""
    return {
        'ordem': ordem,
        'rotulo': campo('R-1'),
        'tipo_sugerido': campo('registro'),
        'data': campo('2024-01-01'),
        'partes': [
            {
                'papel': 'transmitente',
                'nome': campo('Fulano'),
                'confianca': 0.9,
                'requer_revisao': False,
                'evidencia': None,
            }
            for _ in range(partes)
        ],
        'confianca': 0.9,
        'requer_revisao': False,
        'evidencia': None,
    }


def payload_minimo(job_id='11111111-1111-1111-1111-111111111111', paginas=(1,)):
    """Payload que satisfaz o A3 por inteiro (âncora dos testes)."""
    return {
        'schema_version': SCHEMA_VERSION,
        'document': {
            'tipo': campo('matricula'),
            'numero': campo(
                '42.718',
                raw='Nº 42.718',
                evidencia={'pagina': 1, 'trecho': 'matrícula nº 42.718'},
            ),
            'cartorio': campo('CRI de Guaíra'),
        },
        'acts': [],
        'meta': {
            'job_id': job_id,
            'pages_used': list(paginas),
            'provider': 'local-model',
        },
    }


class SchemaVendorizado(SimpleTestCase):
    def test_schema_vendorizado_identico_ao_contrato(self):
        """Byte a byte com o contrato do serviço de OCR (dispatch 1/5)."""
        sha256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            sha256,
            'ae296837b964f180c8f80ac1a77815a43ff05eca52b6f3586a237129b9b2caff',
        )

    def test_versao_unica_derivada_do_vendorizado(self):
        """SCHEMA_VERSION é a fonte única da versão: o nome do arquivo e o
        $id/const do vendorizado derivam dela — e a requisição (services)
        envia essa mesma constante."""
        schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
        self.assertEqual(SCHEMA_VERSION, 'umbelino-extracao-matricula-v1.1')
        self.assertEqual(SCHEMA_PATH.name, f'{SCHEMA_VERSION}.json')
        self.assertEqual(schema['$id'], SCHEMA_VERSION)
        self.assertEqual(
            schema['properties']['schema_version']['const'], SCHEMA_VERSION,
        )

    def test_versao_deriva_do_const_do_vendorizado(self):
        """Derivação de verdade: numa cópia do contrato com o `const` da
        versão seguinte (v1.2), a versão derivada segue o JSON — nenhum
        literal de versão na mão no módulo."""
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            const_seguinte = 'umbelino-extracao-matricula-v1.2'
            schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
            schema['$id'] = const_seguinte
            schema['properties']['schema_version']['const'] = const_seguinte
            (diretorio / f'{const_seguinte}.json').write_text(
                json.dumps(schema), encoding='utf-8'
            )

            caminho, carregado = extracao_schema._carregar_contrato(diretorio)

            self.assertEqual(caminho.name, f'{const_seguinte}.json')
            self.assertEqual(
                extracao_schema._versao_do_schema(carregado), const_seguinte
            )

    def test_carregar_contrato_exige_arquivo_unico(self):
        """Dois contratos vendorizados juntos é troca mal feita (o antigo
        não saiu no PR) → erro, em vez de validar contra o errado."""
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            shutil.copy(SCHEMA_PATH, diretorio / SCHEMA_PATH.name)
            shutil.copy(
                SCHEMA_PATH,
                diretorio / 'umbelino-extracao-matricula-v1.2.json',
            )

            with self.assertRaises(FileNotFoundError):
                extracao_schema._carregar_contrato(diretorio)

    def test_schema_e_2020_12_valido(self):
        """O JSON vendorizado é um schema Draft 2020-12 válido."""
        Draft202012Validator.check_schema(
            json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
        )


class ValidarPayload(SimpleTestCase):
    JOB_ID = '11111111-1111-1111-1111-111111111111'

    def test_aceita_job_id_uuid_divergente_do_servico(self):
        """O ocrcadeia gera um UUID próprio a cada chamada de extração."""
        job_id = '4883db41-773e-4b54-9fdc-55ce8f525e05'
        for id_servico in (
            '15987107-0672-4d05-a5d6-675aaaf1419c',
            'b747b7f1-5abf-4dd4-82ba-6464135f1fff',
            '15987107-0672-4D05-A5D6-675AAAF1419C',
            '{15987107-0672-4d05-a5d6-675aaaf1419c}',
            'urn:uuid:15987107-0672-4d05-a5d6-675aaaf1419c',
        ):
            with self.subTest(id_servico=id_servico):
                payload = payload_registro(id_servico)
                payload['meta']['provider'] = 'workers-ai'
                payload['meta']['pages_used'] = [1, 2]

                validar_payload(payload, job_id, (1, 2))

    def test_rejeita_propriedade_extra(self):
        """Raiz com propriedade fora do A3 → código + caminho, sem valor."""
        payload = payload_minimo()
        payload['surpresa'] = True

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.surpresa')

    def test_rejeita_schema_version(self):
        """schema_version diferente do contrato (const) → rejeita."""
        payload = payload_minimo()
        payload['schema_version'] = 'umbelino-extracao-matricula-v2'

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'valor_const_inesperado')
        self.assertEqual(ctx.exception.caminho, '$.schema_version')

    def test_rejeita_confianca_fora_de_0_1(self):
        """Confiança fora do intervalo [0, 1] → rejeita (minimum/maximum)."""
        for confianca in (1.5, -0.1):
            with self.subTest(confianca=confianca):
                payload = payload_minimo()
                payload['document']['numero']['confianca'] = confianca

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'valor_fora_do_intervalo')
                self.assertEqual(
                    ctx.exception.caminho, '$.document.numero.confianca'
                )

    def test_rejeita_enum(self):
        """normalized fora do enum do domínio (ex.: tipo de documento)."""
        payload = payload_minimo()
        payload['document']['tipo']['normalized'] = 'certidao'

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'valor_fora_do_enum')
        self.assertEqual(ctx.exception.caminho, '$.document.tipo.normalized')

    def test_rejeita_job_id_divergente_nao_uuid(self):
        """ID diferente do job precisa ser um UUID do serviço."""
        for id_servico in ('outro-job', '', '15987107-0672-4d05-a5d6-675aaaf1419z'):
            with self.subTest(id_servico=id_servico):
                payload = payload_minimo(job_id=id_servico)

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'job_id_invalido')
                self.assertEqual(ctx.exception.caminho, '$.meta.job_id')
                self.assertEqual(str(ctx.exception), 'job_id_invalido ($.meta.job_id)')

    def test_job_id_continua_obrigatorio_e_string(self):
        for valor in (None, 123, [], {}):
            with self.subTest(valor=valor):
                payload = payload_minimo(job_id=valor)
                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))
                self.assertEqual(ctx.exception.codigo, 'schema_violado')
                self.assertEqual(ctx.exception.caminho, '$.meta.job_id')

        payload = payload_minimo()
        del payload['meta']['job_id']
        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))
        self.assertEqual(ctx.exception.codigo, 'schema_violado')
        self.assertEqual(ctx.exception.caminho, '$.meta')

    def test_uuid_divergente_nao_permite_pagina_fora_do_job(self):
        payload = payload_registro('15987107-0672-4d05-a5d6-675aaaf1419c')
        payload['meta']['pages_used'] = [1, 7]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1, 2))

        self.assertEqual(ctx.exception.codigo, 'pagina_fora_do_job')
        self.assertEqual(ctx.exception.caminho, '$.meta.pages_used')

    def test_rejeita_pages_used_inexistente(self):
        """pages_used citando página que não pertence ao job → rejeita."""
        payload = payload_minimo(paginas=(1,))
        payload['meta']['pages_used'] = [1, 7]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'pagina_fora_do_job')
        self.assertEqual(ctx.exception.caminho, '$.meta.pages_used')

    def test_rejeita_provider_de_101_chars(self):
        """provider acima de 100 chars não caberia na coluna → rejeita."""
        payload = payload_minimo()
        payload['meta']['provider'] = 'p' * 101

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'provider_muito_longo')
        self.assertEqual(ctx.exception.caminho, '$.meta.provider')

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
