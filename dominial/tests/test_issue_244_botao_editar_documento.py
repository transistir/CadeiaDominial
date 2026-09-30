"""Teste de regressão para issue #244.

Bug: editar_documento renderiza botão "Criar Documento" em vez de
"Atualizar Documento" porque documento_form.html:84 testa a variável
``modo`` (nunca passada), mas a view passa ``modo_edicao=True``.

Fix: template usa ``{% if modo_edicao %}`` (variável que a view já passa).
"""

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.template.loader import render_to_string
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Pessoas,
    TIs,
)


class Issue244BotaoEditarDocumentoTest(TestCase):
    """Botão de submit mostra o texto correto em cada modo."""

    @classmethod
    def setUpTestData(cls):
        cls.tis = TIs.objects.create(
            nome='TI Issue 244', codigo='TI-244', etnia='Teste',
        )
        cls.pessoa = Pessoas.objects.create(nome='Pessoa Issue 244')
        cls.cartorio = Cartorios.objects.create(
            nome='Cartório Issue 244',
            cns='CNS-ISSUE-244',
            cidade='Cidade 244',
            estado='MS',
        )
        cls.user = User.objects.create_user(
            username='issue244', password='issue244pass',
        )
        cls.imovel = Imovel.objects.create(
            terra_indigena_id=cls.tis,
            nome='Imóvel 244',
            proprietario=cls.pessoa,
            matricula='244',
            tipo_documento_principal='matricula',
            cartorio=cls.cartorio,
        )
        cls.doc_tipo, _ = DocumentoTipo.objects.get_or_create(tipo='matricula')
        cls.documento = Documento.objects.create(
            numero='M244',
            tipo=cls.doc_tipo,
            imovel=cls.imovel,
            cartorio=cls.cartorio,
            data=timezone.localdate(),
            data_presumida=True,
        )
        cls.tipos_documento = DocumentoTipo.objects.all().order_by('tipo')

    def _render_documento_form(self, contexto_extra=None):
        """Renderiza o template com contexto base + extras, simulando request."""
        factory = RequestFactory()
        request = factory.get('/')
        request.user = self.user

        context = {
            'tis': self.tis,
            'imovel': self.imovel,
            'documento': self.documento,
            'cartorios': Cartorios.objects.all(),
            'tipos_documento': self.tipos_documento,
        }
        if contexto_extra:
            context.update(contexto_extra)
        return render_to_string('dominial/documento_form.html', context, request=request)

    def test_editar_documento_renderiza_botao_atualizar(self):
        """Contexto com modo_edicao=True → botão 'Atualizar Documento'."""
        html = self._render_documento_form({'modo_edicao': True})
        self.assertIn('Atualizar Documento', html)

    def test_novo_documento_renderiza_botao_criar(self):
        """Contexto sem modo_edicao → botão 'Criar Documento'."""
        html = self._render_documento_form()
        self.assertIn('Criar Documento', html)
        self.assertNotIn('Atualizar Documento', html)
