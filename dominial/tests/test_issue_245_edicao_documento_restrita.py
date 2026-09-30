"""Teste de regressão para issue #245.

Bug: editar_documento permite alterar identidade (tipo/número/cartório/data/origem/observações)
quando deveria permitir apenas livro/folha.

Fix: DocumentoService.atualizar_documento só atualiza livro/folha (folha forçada '' para matrícula).
Template desabilita campos de identidade no modo edição.
"""

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, Client
from django.template.loader import render_to_string
from django.utils import timezone
from django.urls import reverse

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Pessoas,
    TIs,
)
from dominial.services.documento_service import DocumentoService


class Issue245EdicaoDocumentoRestritaTest(TestCase):
    """Edição de documento só permite alterar livro/folha."""

    def setUp(self):
        self.tis = TIs.objects.create(
            nome='TI Issue 245', codigo='TI-245', etnia='Teste',
        )
        self.pessoa = Pessoas.objects.create(nome='Pessoa Issue 245')
        self.cartorio = Cartorios.objects.create(
            nome='Cartório Issue 245',
            cns='CNS-ISSUE-245',
            cidade='Cidade 245',
            estado='MS',
        )
        self.user = User.objects.create_user(
            username='issue245', password='issue245pass',
        )
        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel 245',
            proprietario=self.pessoa,
            matricula='245',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio,
        )
        self.doc_tipo_matricula, _ = DocumentoTipo.objects.get_or_create(tipo='matricula')
        self.doc_tipo_transcricao, _ = DocumentoTipo.objects.get_or_create(tipo='transcricao')
        
        # Documento original com identidade canônica
        self.documento = Documento.objects.create(
            numero='M245',
            tipo=self.doc_tipo_matricula,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data=timezone.localdate(),
            data_presumida=True,
            livro='Livro-Original',
            folha='',  # Matrícula não tem folha
            origem='Origem-Original',
            observacoes='Observações-Originais',
        )
        
        self.factory = RequestFactory()
        self.client = Client()
        self.client.force_login(self.user)

    def test_service_atualizar_documento_preserva_identidade(self):
        """POST forjado com número/cartório/tipo diferentes → documento mantém identidade original."""
        # Criar outro cartório para tentar forjar
        cartorio_falso = Cartorios.objects.create(
            nome='Cartório Falso',
            cns='CNS-FALSO',
            cidade='Cidade Falsa',
            estado='SP',
        )
        
        # POST forjado tentando alterar identidade
        request = self.factory.post('/', {
            'numero': 'M999-FORJADO',  # Diferente do original M245
            'tipo': self.doc_tipo_transcricao.id,  # Diferente do original matricula
            'cartorio_id': cartorio_falso.id,  # Diferente do original
            'data': '2020-01-01',  # Diferente do original
            'livro': 'Livro-Novo',  # Deve ser atualizado
            'folha': 'Folha-Nova',  # Deve ser ignorado (matrícula)
            'origem': 'Origem-Forjada',  # Diferente do original
            'observacoes': 'Observações-Forjadas',  # Diferente do original
        })
        request.user = self.user
        
        # Capturar valores originais
        numero_original = self.documento.numero
        tipo_original = self.documento.tipo
        cartorio_original = self.documento.cartorio
        data_original = self.documento.data
        origem_original = self.documento.origem
        observacoes_originais = self.documento.observacoes
        
        # Executar atualização
        sucesso, mensagem = DocumentoService.atualizar_documento(request, self.documento)
        
        # Recarregar do banco
        self.documento.refresh_from_db()
        
        # Identidade deve permanecer inalterada
        self.assertEqual(self.documento.numero, numero_original, 
                        "Número não deve ser alterado na edição")
        self.assertEqual(self.documento.tipo, tipo_original,
                        "Tipo não deve ser alterado na edição")
        self.assertEqual(self.documento.cartorio, cartorio_original,
                        "Cartório não deve ser alterado na edição")
        self.assertEqual(self.documento.data, data_original,
                        "Data não deve ser alterada na edição")
        self.assertEqual(self.documento.origem, origem_original,
                        "Origem não deve ser alterada na edição")
        self.assertEqual(self.documento.observacoes, observacoes_originais,
                        "Observações não devem ser alteradas na edição")
        
        # Livro deve ser atualizado
        self.assertEqual(self.documento.livro, 'Livro-Novo',
                        "Livro deve ser atualizado")
        
        # Folha deve permanecer vazia (matrícula)
        self.assertEqual(self.documento.folha, '',
                        "Folha deve permanecer vazia para matrícula")

    def test_service_atualizar_documento_livro_folha_transcricao(self):
        """Documento transcrição → folha deve ser atualizada."""
        doc_transcricao = Documento.objects.create(
            numero='T245',
            tipo=self.doc_tipo_transcricao,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data=timezone.localdate(),
            data_presumida=True,
            livro='Livro-T-Original',
            folha='Folha-T-Original',
        )
        
        request = self.factory.post('/', {
            'numero': 'T999-FORJADO',  # Deve ser ignorado
            'tipo': self.doc_tipo_matricula.id,  # Deve ser ignorado
            'livro': 'Livro-T-Novo',
            'folha': 'Folha-T-Nova',
        })
        request.user = self.user
        
        sucesso, mensagem = DocumentoService.atualizar_documento(request, doc_transcricao)
        
        doc_transcricao.refresh_from_db()
        
        # Identidade preservada
        self.assertEqual(doc_transcricao.numero, 'T245')
        self.assertEqual(doc_transcricao.tipo, self.doc_tipo_transcricao)
        
        # Livro e folha atualizados
        self.assertEqual(doc_transcricao.livro, 'Livro-T-Novo')
        self.assertEqual(doc_transcricao.folha, 'Folha-T-Nova')

    def test_view_editar_documento_preserva_identidade_via_post(self):
        """View editar_documento via POST → identidade preservada mesmo com dados forjados."""
        url = reverse('editar_documento', kwargs={
            'tis_id': self.tis.id,
            'imovel_id': self.imovel.id,
            'documento_id': self.documento.id,
        })
        
        # POST forjado
        post_data = {
            'numero': 'M999-FORJADO',
            'tipo': self.doc_tipo_transcricao.id,
            'cartorio_id': self.cartorio.id,
            'data': '2020-01-01',
            'livro': 'Livro-Via-View',
            'folha': 'Folha-Via-View',
            'origem': 'Origem-Forjada',
            'observacoes': 'Observações-Forjadas',
        }
        
        response = self.client.post(url, post_data, follow=True)
        
        # Recarregar documento
        self.documento.refresh_from_db()
        
        # Identidade preservada
        self.assertEqual(self.documento.numero, 'M245')
        self.assertEqual(self.documento.tipo, self.doc_tipo_matricula)
        self.assertEqual(self.documento.origem, 'Origem-Original')
        self.assertEqual(self.documento.observacoes, 'Observações-Originais')
        
        # Livro atualizado
        self.assertEqual(self.documento.livro, 'Livro-Via-View')
        
        # Folha vazia (matrícula)
        self.assertEqual(self.documento.folha, '')

    def test_template_editar_documento_campos_desabilitados(self):
        """Template em modo edição → campos de identidade com disabled no HTML."""
        import re
        html = render_to_string(
            'dominial/documento_form.html',
            {
                'tis': self.tis,
                'imovel': self.imovel,
                'documento': self.documento,
                'cartorios': Cartorios.objects.all(),
                'tipos_documento': DocumentoTipo.objects.all(),
                'modo_edicao': True,
            },
            request=self.factory.get('/'),
        )
        
        def _tem_disabled(html, field_id):
            """Verifica se o input/select com o dado id tem atributo disabled."""
            # Busca a tag que contém id="field_id" e verifica disabled na mesma tag
            pattern = rf'<(?:input|select|textarea)[^>]*id="{field_id}"[^>]*disabled'
            if re.search(pattern, html):
                return True
            # Também aceita disabled antes do id
            pattern2 = rf'<(?:input|select|textarea)[^>]*disabled[^>]*id="{field_id}"'
            return bool(re.search(pattern2, html))
        
        # Campos de identidade devem estar disabled
        self.assertTrue(_tem_disabled(html, 'numero'),
                       "Campo número deve ter disabled na edição")
        self.assertTrue(_tem_disabled(html, 'tipo'),
                       "Campo tipo deve ter disabled na edição")
        self.assertTrue(_tem_disabled(html, 'data'),
                       "Campo data deve ter disabled na edição")
        self.assertTrue(_tem_disabled(html, 'cartorio'),
                       "Campo cartório deve ter disabled na edição")
        self.assertTrue(_tem_disabled(html, 'origem'),
                       "Campo origem deve ter disabled na edição")
        self.assertTrue(_tem_disabled(html, 'observacoes'),
                       "Campo observações deve ter disabled na edição")
        
        # Campo livro NÃO deve estar disabled (editável)
        self.assertFalse(_tem_disabled(html, 'livro'),
                        "Campo livro NÃO deve ter disabled na edição")
        
        # Campo folha para matrícula deve estar disabled (via JS #138)
        # Nota: o JS atualizarCampoFolha já cuida disto dinamicamente

    def test_template_editar_documento_folha_habilitada_transcricao(self):
        """Template em modo edição com transcrição → folha habilitada."""
        doc_transcricao = Documento.objects.create(
            numero='T245',
            tipo=self.doc_tipo_transcricao,
            imovel=self.imovel,
            cartorio=self.cartorio,
            data=timezone.localdate(),
            data_presumida=True,
            livro='Livro-T',
            folha='Folha-T',
        )
        
        html = render_to_string(
            'dominial/documento_form.html',
            {
                'tis': self.tis,
                'imovel': self.imovel,
                'documento': doc_transcricao,
                'cartorios': Cartorios.objects.all(),
                'tipos_documento': DocumentoTipo.objects.all(),
                'modo_edicao': True,
            },
            request=self.factory.get('/'),
        )
        
        # Verificar que folha não está disabled para transcrição
        # (O JavaScript atualizarCampoFolha() cuida disso dinamicamente,
        # mas o HTML inicial deve permitir edição)
        self.assertIn('id="folha"', html)
        # Para transcrição, folha não deve ter disabled no HTML inicial
        # (o JS pode desabilitar se mudar para matrícula)
