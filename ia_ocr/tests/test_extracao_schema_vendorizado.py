"""Parte do corpo de ``SchemaVendorizado``; coletada pela fachada."""

import hashlib
import json

from jsonschema import Draft202012Validator

from ia_ocr.extracao_schema import CONTRATOS, SCHEMA_PATH, SCHEMA_VERSION

from .test_extracao_schema_base import (
    CAMPOS_DE_TRANSMISSAO, PASTA_SCHEMAS, SHA256_DOS_CONTRATOS, V1_1, V1_2,
)

class SchemaVendorizadoParte:
    def test_schemas_vendorizados_identicos_ao_contrato(self):
        """Byte a byte com o contrato do serviço de OCR: os DOIS arquivos."""
        for versao, esperado in SHA256_DOS_CONTRATOS.items():
            with self.subTest(versao=versao):
                arquivo = PASTA_SCHEMAS / f'{versao}.json'
                self.assertEqual(
                    hashlib.sha256(arquivo.read_bytes()).hexdigest(), esperado,
                )

    def test_so_ha_os_contratos_v1_1_e_v1_2(self):
        """Contrato novo (ou aposentadoria de um) é decisão explícita: o
        conjunto vendorizado é pinado, com o sha256 de cada um acima."""
        arquivos = sorted(
            caminho.name
            for caminho in PASTA_SCHEMAS.glob('umbelino-extracao-matricula-*.json')
        )
        self.assertEqual(arquivos, [f'{V1_1}.json', f'{V1_2}.json'])
        self.assertEqual(set(CONTRATOS), {V1_1, V1_2})
        for versao, esperado in SHA256_DOS_CONTRATOS.items():
            with self.subTest(versao=versao):
                self.assertEqual(
                    CONTRATOS[versao].caminho, PASTA_SCHEMAS / f'{versao}.json',
                )
                self.assertEqual(
                    hashlib.sha256(CONTRATOS[versao].caminho.read_bytes()).hexdigest(),
                    esperado,
                )

    def test_cada_contrato_e_coerente_com_o_proprio_const(self):
        """A identidade do contrato é o `const` de `schema_version`: a chave
        do mapa, o nome do arquivo e o schema carregado concordam com ele."""
        for versao, contrato in CONTRATOS.items():
            with self.subTest(versao=versao):
                schema = json.loads(contrato.caminho.read_text(encoding='utf-8'))
                self.assertEqual(
                    schema['properties']['schema_version']['const'], versao,
                )
                self.assertEqual(contrato.caminho.name, f'{versao}.json')
                self.assertEqual(contrato.schema, schema)
                self.assertIsInstance(contrato.validador, Draft202012Validator)

    def test_id_do_v1_2_ainda_diz_v1_1_por_descuido_do_servico(self):
        """O `$id` do v1.1 é a própria versão, mas o do v1.2 do serviço
        continua `...-v1.1` (descuido de lá). O JSON é byte a byte e NÃO se
        conserta aqui: a identidade do contrato é o `const`, nunca o `$id`
        (por isso nenhum código ou teste compara `$id` com a versão)."""
        self.assertEqual(CONTRATOS[V1_1].schema['$id'], V1_1)
        self.assertEqual(CONTRATOS[V1_2].schema['$id'], V1_1)

    def test_schema_version_e_o_contrato_mais_novo(self):
        """A requisição pede a versão mais nova (services envia SCHEMA_VERSION)
        e SCHEMA_PATH aponta para o arquivo dela."""
        self.assertEqual(SCHEMA_VERSION, V1_2)
        self.assertEqual(SCHEMA_PATH, CONTRATOS[V1_2].caminho)

    def test_schemas_sao_2020_12_validos(self):
        """Cada JSON vendorizado é um schema Draft 2020-12 válido."""
        for versao, contrato in CONTRATOS.items():
            with self.subTest(versao=versao):
                Draft202012Validator.check_schema(
                    json.loads(contrato.caminho.read_text(encoding='utf-8'))
                )

    def test_v1_2_so_acrescenta_os_campos_de_transmissao_ao_ato(self):
        """O v1.2 é o v1.1 + livro/folha/data da transmissão no ato (opcionais)
        e o novo `const`: nada mais mudou, nada ficou obrigatório."""
        ato_v1_1 = CONTRATOS[V1_1].schema['$defs']['act']
        ato_v1_2 = CONTRATOS[V1_2].schema['$defs']['act']
        self.assertEqual(
            set(ato_v1_2['properties']) - set(ato_v1_1['properties']),
            set(CAMPOS_DE_TRANSMISSAO),
        )
        self.assertEqual(ato_v1_2['required'], ato_v1_1['required'])
        self.assertIs(ato_v1_2['additionalProperties'], False)

