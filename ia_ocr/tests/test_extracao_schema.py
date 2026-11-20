"""Fachada dos testes do schema de extração."""

from django.test import SimpleTestCase

from .test_extracao_schema_base import ExtracaoSchemaBase
from .test_extracao_schema_carregar_contratos import CarregarContratosParte
from .test_extracao_schema_validar_payload import ValidarPayloadParte1
from .test_extracao_schema_validar_payload_parte2 import ValidarPayloadParte2
from .test_extracao_schema_vendorizado import SchemaVendorizadoParte


class SchemaVendorizado(SchemaVendorizadoParte, ExtracaoSchemaBase, SimpleTestCase):
    """Nome preservado para os ids dos testes vendorizados."""


class CarregarContratos(CarregarContratosParte, ExtracaoSchemaBase, SimpleTestCase):
    """Nome preservado para os ids dos testes de carregamento."""


class ValidarPayload(
    ValidarPayloadParte1,
    ValidarPayloadParte2,
    ExtracaoSchemaBase,
    SimpleTestCase,
):
    """Nome preservado para os ids dos testes de validação."""
