"""
Factory classes for creating test data using factory_boy.

These factories provide convenient ways to create model instances for testing
with sensible defaults while allowing customization as needed.

Usage examples:
    # Create with defaults
    ti = TIsFactory()

    # Create with custom values
    ti = TIsFactory(nome="Custom TI Name", codigo="CUSTOM001")

    # Create with relationships
    imovel = ImovelFactory(terra_indigena_id=ti)

    # Create multiple instances
    pessoas = PessoasFactory.create_batch(5)
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from datetime import date, timedelta
import random

from dominial.models import (
    TIs,
    TerraIndigenaReferencia,
    Pessoas,
    Imovel,
    Cartorios,
    Documento,
    DocumentoTipo,
    Lancamento,
    LancamentoTipo,
)

fake = Faker('pt_BR')


# ============================================================================
# Terra Indígena Factories
# ============================================================================

class TerraIndigenaReferenciaFactory(DjangoModelFactory):
    """Factory for TerraIndigenaReferencia model."""

    class Meta:
        model = TerraIndigenaReferencia
        django_get_or_create = ('codigo',)

    codigo = factory.Sequence(lambda n: f"REF{n:04d}")
    nome = factory.Sequence(lambda n: f"Terra Indígena Test {n}")
    etnia = factory.LazyFunction(lambda: fake.random_element([
        'Guarani', 'Yanomami', 'Kaingang', 'Xavante', 'Pataxó'
    ]))
    estado = factory.LazyFunction(lambda: fake.random_element([
        'AM', 'PA', 'MT', 'RO', 'RR', 'AC', 'BA', 'MG'
    ]))
    municipio = factory.LazyFunction(lambda: fake.city())
    area_ha = factory.LazyFunction(lambda: round(random.uniform(1000, 500000), 2))
    fase = factory.LazyFunction(lambda: fake.random_element([
        'Regularizada', 'Homologada', 'Declarada', 'Delimitada'
    ]))
    modalidade = 'Tradicional'
    data_regularizada = factory.LazyFunction(lambda: fake.date_between(
        start_date=date(2000, 1, 1),
        end_date=date.today()
    ))


class TIsFactory(DjangoModelFactory):
    """Factory for TIs (Terras Indígenas) model."""

    class Meta:
        model = TIs
        django_get_or_create = ('codigo',)

    terra_referencia = None  # Can be set to TerraIndigenaReferenciaFactory()
    nome = factory.Sequence(lambda n: f"TI Test {n}")
    codigo = factory.Sequence(lambda n: f"TI{n:04d}")
    etnia = factory.LazyFunction(lambda: fake.random_element([
        'Guarani', 'Yanomami', 'Kaingang', 'Xavante', 'Pataxó'
    ]))
    estado = factory.LazyFunction(lambda: fake.random_element([
        'AM', 'PA', 'MT', 'RO', 'RR', 'AC', 'BA', 'MG'
    ]))
    area = factory.LazyFunction(lambda: round(random.uniform(1000, 500000), 2))


# ============================================================================
# Pessoas Factory
# ============================================================================

class PessoasFactory(DjangoModelFactory):
    """Factory for Pessoas model."""

    class Meta:
        model = Pessoas

    nome = factory.LazyFunction(lambda: fake.name())
    cpf = factory.Sequence(lambda n: f"{n:011d}")  # Simple sequential CPF for testing
    rg = factory.LazyFunction(lambda: fake.random_number(digits=9, fix_len=True))
    data_nascimento = factory.LazyFunction(lambda: fake.date_of_birth(
        minimum_age=18,
        maximum_age=90
    ))
    email = factory.LazyAttribute(lambda obj: f"{obj.nome.lower().replace(' ', '.')}@example.com")
    telefone = factory.LazyFunction(lambda: fake.phone_number())


# ============================================================================
# Cartórios Factory
# ============================================================================

class CartoriosFactory(DjangoModelFactory):
    """Factory for Cartorios model."""

    class Meta:
        model = Cartorios
        django_get_or_create = ('cns',)

    nome = factory.Sequence(lambda n: f"Cartório Test {n}")
    cns = factory.Sequence(lambda n: f"CNS{n:05d}")
    endereco = factory.LazyFunction(lambda: fake.address())
    telefone = factory.LazyFunction(lambda: fake.phone_number())
    email = factory.LazyFunction(lambda: fake.company_email())
    estado = factory.LazyFunction(lambda: fake.random_element([
        'BA', 'SP', 'RJ', 'MG', 'AM', 'PA', 'MT'
    ]))
    cidade = factory.LazyFunction(lambda: fake.city())
    tipo = 'CRI'


# ============================================================================
# Imóvel Factory
# ============================================================================

class ImovelFactory(DjangoModelFactory):
    """Factory for Imovel model."""

    class Meta:
        model = Imovel

    terra_indigena_id = factory.SubFactory(TIsFactory)
    nome = factory.Sequence(lambda n: f"Imóvel Test {n}")
    proprietario = factory.SubFactory(PessoasFactory)
    matricula = factory.Sequence(lambda n: f"{n:05d}")
    tipo_documento_principal = 'matricula'
    observacoes = factory.LazyFunction(lambda: fake.text(max_nb_chars=200))
    cartorio = factory.SubFactory(CartoriosFactory)
    arquivado = False


# ============================================================================
# Documento Factories
# ============================================================================

class DocumentoTipoFactory(DjangoModelFactory):
    """Factory for DocumentoTipo model."""

    class Meta:
        model = DocumentoTipo
        django_get_or_create = ('tipo',)

    tipo = 'matricula'

    @classmethod
    def matricula(cls):
        """Create or get matrícula type."""
        return cls(tipo='matricula')

    @classmethod
    def transcricao(cls):
        """Create or get transcrição type."""
        return cls(tipo='transcricao')


class DocumentoFactory(DjangoModelFactory):
    """Factory for Documento model."""

    class Meta:
        model = Documento

    imovel = factory.SubFactory(ImovelFactory)
    tipo = factory.SubFactory(DocumentoTipoFactory, tipo='matricula')
    numero = factory.Sequence(lambda n: f"M-{n:05d}")
    data = factory.LazyFunction(lambda: fake.date_between(
        start_date=date(1976, 1, 1),  # Matrículas started in 1976
        end_date=date.today()
    ))
    cartorio = factory.SubFactory(CartoriosFactory)
    livro = factory.Sequence(lambda n: f"L{n % 100 + 1:02d}")
    folha = factory.Sequence(lambda n: f"{n % 200 + 1:03d}")
    origem = None
    observacoes = factory.LazyFunction(lambda: fake.text(max_nb_chars=100))
    nivel_manual = None
    classificacao_fim_cadeia = None
    sigla_patrimonio_publico = None
    cri_atual = factory.SubFactory(CartoriosFactory)
    cri_origem = None

    @classmethod
    def matricula(cls, **kwargs):
        """Create a matrícula document."""
        return cls(
            tipo=DocumentoTipoFactory.matricula(),
            numero=factory.Sequence(lambda n: f"M-{n:05d}"),
            **kwargs
        )

    @classmethod
    def transcricao(cls, **kwargs):
        """Create a transcrição document."""
        return cls(
            tipo=DocumentoTipoFactory.transcricao(),
            numero=factory.Sequence(lambda n: f"T-{n:05d}"),
            data=factory.LazyFunction(lambda: fake.date_between(
                start_date=date(1900, 1, 1),
                end_date=date(1976, 12, 31)  # Before matrícula system
            )),
            **kwargs
        )


# ============================================================================
# Lançamento Factories
# ============================================================================

class LancamentoTipoFactory(DjangoModelFactory):
    """Factory for LancamentoTipo model."""

    class Meta:
        model = LancamentoTipo
        django_get_or_create = ('tipo',)

    tipo = 'registro'
    requer_transmissao = True
    requer_detalhes = False
    requer_titulo = True
    requer_cartorio_origem = True
    requer_livro_origem = False
    requer_folha_origem = False
    requer_data_origem = False
    requer_forma = False
    requer_descricao = False
    requer_observacao = True

    @classmethod
    def registro(cls):
        """Create or get registro type."""
        return cls(
            tipo='registro',
            requer_transmissao=True,
            requer_titulo=True,
            requer_cartorio_origem=True,
        )

    @classmethod
    def averbacao(cls):
        """Create or get averbação type."""
        return cls(
            tipo='averbacao',
            requer_transmissao=False,
            requer_titulo=False,
            requer_cartorio_origem=False,
            requer_descricao=True,
        )

    @classmethod
    def inicio_matricula(cls):
        """Create or get início de matrícula type."""
        return cls(
            tipo='inicio_matricula',
            requer_transmissao=False,
            requer_titulo=True,
            requer_cartorio_origem=True,
            requer_livro_origem=True,
            requer_folha_origem=True,
            requer_data_origem=True,
        )


class LancamentoFactory(DjangoModelFactory):
    """Factory for Lancamento model."""

    class Meta:
        model = Lancamento

    documento = factory.SubFactory(DocumentoFactory)
    tipo = factory.SubFactory(LancamentoTipoFactory, tipo='registro')
    numero_lancamento = factory.Sequence(lambda n: f"R-{n:05d}")
    data = factory.LazyFunction(lambda: fake.date_between(
        start_date=date(1980, 1, 1),
        end_date=date.today()
    ))
    transmitente = factory.SubFactory(PessoasFactory)
    adquirente = factory.SubFactory(PessoasFactory)
    valor_transacao = factory.LazyFunction(lambda: round(random.uniform(10000, 5000000), 2))
    area = factory.LazyFunction(lambda: round(random.uniform(100, 10000), 4))
    origem = None
    detalhes = None
    observacoes = factory.LazyFunction(lambda: fake.text(max_nb_chars=100))

    # Campos específicos
    forma = None
    descricao = None
    titulo = factory.LazyFunction(lambda: fake.random_element([
        'Compra e Venda',
        'Doação',
        'Permuta',
        'Herança',
        'Usucapião'
    ]))

    # Cartórios
    cartorio_origem = factory.SubFactory(CartoriosFactory)
    cartorio_transacao = None
    cartorio_transmissao = None

    # Dados de transação
    livro_transacao = None
    folha_transacao = None
    data_transacao = None

    # Dados de origem
    livro_origem = None
    folha_origem = None
    data_origem = None

    # Flags
    eh_inicio_matricula = False

    # Documento de origem (chain link)
    documento_origem = None

    @classmethod
    def registro(cls, **kwargs):
        """Create a registro lancamento."""
        return cls(
            tipo=LancamentoTipoFactory.registro(),
            numero_lancamento=factory.Sequence(lambda n: f"R-{n:05d}"),
            titulo=factory.LazyFunction(lambda: fake.random_element([
                'Compra e Venda', 'Doação', 'Permuta'
            ])),
            **kwargs
        )

    @classmethod
    def averbacao(cls, **kwargs):
        """Create an averbação lancamento."""
        return cls(
            tipo=LancamentoTipoFactory.averbacao(),
            numero_lancamento=factory.Sequence(lambda n: f"AV-{n:05d}"),
            descricao=factory.LazyFunction(lambda: fake.text(max_nb_chars=200)),
            transmitente=None,
            adquirente=None,
            titulo=None,
            **kwargs
        )

    @classmethod
    def inicio_matricula(cls, **kwargs):
        """Create an início de matrícula lancamento."""
        return cls(
            tipo=LancamentoTipoFactory.inicio_matricula(),
            numero_lancamento=factory.Sequence(lambda n: f"IM-{n:05d}"),
            eh_inicio_matricula=True,
            livro_origem=factory.Sequence(lambda n: f"L{n % 50 + 1:02d}"),
            folha_origem=factory.Sequence(lambda n: f"{n % 100 + 1:03d}"),
            data_origem=factory.LazyFunction(lambda: fake.date_between(
                start_date=date(1900, 1, 1),
                end_date=date(1976, 12, 31)
            )),
            **kwargs
        )

    @classmethod
    def with_chain(cls, origin_documento, **kwargs):
        """Create a lancamento linked to an origin document (chain link)."""
        return cls(
            documento_origem=origin_documento,
            **kwargs
        )


# ============================================================================
# Helper Functions
# ============================================================================

def create_simple_chain(length=3):
    """
    Create a simple linear chain of documents.

    Args:
        length: Number of documents in the chain

    Returns:
        list: List of Documento instances in order (oldest to newest)
    """
    imovel = ImovelFactory()
    documents = []

    # First document (oldest, no origin)
    doc = DocumentoFactory.transcricao(imovel=imovel)
    documents.append(doc)

    # Chain subsequent documents
    for i in range(1, length):
        new_doc = DocumentoFactory.matricula(imovel=imovel)
        # Create lancamento with both documento_origem link AND textual origem field
        # so HierarquiaArvoreService can discover the chain
        LancamentoFactory.inicio_matricula(
            documento=new_doc,
            documento_origem=documents[-1],
            origem=documents[-1].numero  # Set textual origem field for discovery
        )
        documents.append(new_doc)

    return documents


def create_complex_chain_with_branches():
    """
    Create a complex chain with multiple branches (multiple origins).

    Returns:
        dict: Dictionary with 'main' chain and 'branches'
    """
    imovel = ImovelFactory()

    # Main chain
    doc1 = DocumentoFactory.transcricao(imovel=imovel)
    doc2 = DocumentoFactory.matricula(imovel=imovel)
    doc3 = DocumentoFactory.matricula(imovel=imovel)

    # Link main chain
    LancamentoFactory.inicio_matricula(documento=doc2, documento_origem=doc1)
    LancamentoFactory.registro(documento=doc3, documento_origem=doc2)

    # Create branch from doc1
    branch_doc = DocumentoFactory.matricula(imovel=imovel)
    LancamentoFactory.inicio_matricula(documento=branch_doc, documento_origem=doc1)

    return {
        'main': [doc1, doc2, doc3],
        'branches': [[doc1, branch_doc]]
    }
