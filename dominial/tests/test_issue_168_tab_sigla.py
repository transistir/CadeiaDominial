"""Teste de regressão para issue #168.

Relato: ao navegar pelo formulário de lançamento com TAB, o cursor não deve
parar em campos somente leitura preenchidos automaticamente:
`#sigla_documento` (campo visual/informativo — seu valor não é lido pelo
backend, que usa o hidden `sigla_matricula`) e `#numero_lancamento` (a sigla
completa gerada por JS a partir de `#numero_lancamento_simples`, e esse sim
lido pelo backend no POST).

`readonly` sozinho não remove o campo da ordem de tabulação — só
`tabindex="-1"` faz isso, sem tirar o campo do POST (o que `disabled` faria).
"""
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Pessoas,
    TIs,
)


class TestIssue168TabSigla(TestCase):
    """`#sigla_documento` deve ter tabindex="-1"; campos obrigatórios não."""

    def setUp(self):
        self.tis = TIs.objects.create(nome="TI #168", codigo="T168", etnia="Teste")
        self.pessoa = Pessoas.objects.create(nome="Pessoa #168", cpf="55544433322")
        self.cri = Cartorios.objects.create(
            nome="CRI #168", cns="168168", cidade="Cidade", estado="SP"
        )
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome="Imóvel #168",
            proprietario=self.pessoa,
            matricula="168",
            tipo_documento_principal="matricula",
            cartorio=self.cri,
        )
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero="M168",
            data=timezone.now().date(),
            cartorio=self.cri,
            # '0' = não definido (default de criação automática): o campo segue
            # editável/obrigatório; livro já definido ficaria readonly (#218).
            livro="0",
            folha="0",
        )

        usuario = get_user_model().objects.create_user(
            username="tester168", password="senha-168"
        )
        self.client.force_login(usuario)

        url = reverse(
            "novo_lancamento_documento",
            args=[self.tis.id, self.imovel.id, self.documento.id],
        )
        self.response = self.client.get(url)
        self.html = self.response.content.decode()

    def _tag_do_campo(self, field_id):
        match = re.search(
            rf'<input[^>]*\bid="{field_id}"[^>]*>', self.html
        )
        self.assertIsNotNone(match, f"Campo #{field_id} não encontrado no HTML")
        return match.group(0)

    def test_form_carrega(self):
        self.assertEqual(self.response.status_code, 200)

    def test_sigla_documento_tem_tabindex_negativo(self):
        """BUG #168: o TAB parava no campo de sigla, que é só leitura."""
        tag = self._tag_do_campo("sigla_documento")
        self.assertIn('tabindex="-1"', tag, f"#sigla_documento sem tabindex=-1: {tag!r}")
        self.assertIn("readonly", tag, "campo deve continuar readonly")
        self.assertIn('value="M168"', tag, "valor exibido deve continuar presente")
        self.assertIn(
            '<label for="sigla_documento"', self.html, "campo deve continuar rotulado"
        )

    def test_numero_lancamento_tem_tabindex_negativo(self):
        """BUG #168: o TAB também parava no campo de sigla completa gerada."""
        tag = self._tag_do_campo("numero_lancamento")
        self.assertIn('tabindex="-1"', tag, f"#numero_lancamento sem tabindex=-1: {tag!r}")
        self.assertIn("readonly", tag, "campo deve continuar readonly (lido no POST)")

    def test_campos_obrigatorios_nao_tem_tabindex_negativo(self):
        """A ordem de tabulação normal dos campos obrigatórios não foi afetada."""
        tag_livro = self._tag_do_campo("livro_documento")
        tag_data = self._tag_do_campo("data")

        self.assertNotIn('tabindex="-1"', tag_livro)
        self.assertNotIn('tabindex="-1"', tag_data)

        # tipo_lancamento é um <select>, não <input>
        match_tipo = re.search(r'<select[^>]*\bid="tipo_lancamento"[^>]*>', self.html)
        self.assertIsNotNone(match_tipo, "Campo #tipo_lancamento não encontrado no HTML")
        self.assertNotIn('tabindex="-1"', match_tipo.group(0))
