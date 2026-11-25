"""
Issue #400 — o prefill escreve SÓ texto documental em ``observacoes``
(§5, regra 1): análise nunca é preenchida automaticamente. E a ação
explícita "registrar análise" só aparece para usuário logado.

O formulário é renderizado a partir de ``dominial/lancamento_form.html`` com
``request`` no contexto (Django test client / ``render_to_string``), provando
que o include passa ``permite_registrar_analise=True`` mesmo o componente
sendo compartilhado com imóvel/documento.
"""

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.template.loader import render_to_string

from .payloads_extracao import payload_registro
from .test_revisao_formulario_prefill_base import PrefillBase


class PrefillSemMarcadorTest(PrefillBase):
    def test_prefill_copia_so_o_texto_documental(self):
        form_data = self._prefill(self._registro(
            observacoes=self._campo('Área remanescente de 55 ha'),
        ))['form_data']

        self.assertEqual(form_data['observacoes'], 'Área remanescente de 55 ha')
        self.assertNotIn('ANÁLISE', form_data['observacoes'])
        self.assertNotIn('[', form_data['observacoes'])

    def test_ato_sem_observacoes_nao_recebe_marcador(self):
        form_data = self._prefill(payload_registro(self.job.job_id))['form_data']

        self.assertNotIn('observacoes', form_data)


class AcaoRegistrarAnaliseNoFormularioTest(PrefillBase):
    def _render_formulario(self, user):
        request = RequestFactory().get('/lancamento/')
        request.user = user
        return render_to_string(
            'dominial/lancamento_form.html',
            {
                'tis': self.imovel.terra_indigena_id,
                'imovel': self.imovel,
                'documento': self.documento,
                'form_data': {},
                'modo_edicao': False,
            },
            request=request,
        )

    def test_usuario_logado_ve_a_acao_de_registrar_analise(self):
        html = self._render_formulario(self.usuario)

        self.assertIn('Registrar análise', html)
        self.assertIn('name="analise_texto"', html)
        self.assertIn(f'id="analise_texto"', html)
        self.assertIn(self.usuario.username, html)
        self.assertIn('ANÁLISE', html)

    def test_anonimo_nao_ve_a_acao(self):
        html = self._render_formulario(AnonymousUser())

        self.assertNotIn('Registrar análise', html)
        self.assertNotIn('name="analise_texto"', html)
