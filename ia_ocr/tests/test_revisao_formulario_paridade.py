"""Aceite c2: o POST do formulário mantém paridade com o fluxo manual."""

from dominial.models import Lancamento
from ia_ocr.models import ImportacaoIA

from .test_revisao_formulario_view_base import RevisaoFormularioBase, post_do_html


class ParidadeFormularioTest(RevisaoFormularioBase):
    def _foto(self):
        lancamento = Lancamento.objects.get(documento=self.documento)
        return {
            'lancamento': {
                campo.attname: getattr(lancamento, campo.attname)
                for campo in Lancamento._meta.concrete_fields
                if campo.name not in {'id', 'documento', 'documento_origem'}
                and not getattr(campo, 'auto_now', False)
                and not getattr(campo, 'auto_now_add', False)
            },
            'partes': sorted(lancamento.pessoas.values_list(
                'tipo', 'nome_digitado', 'pessoa__nome',
            )),
            'origens': sorted(lancamento.origens_estruturadas.values_list(
                'tipo_documento', 'numero_normalizado', 'cartorio_id', 'livro', 'folha',
            )),
        }

    def test_c2_mesmo_post_grava_o_mesmo_lancamento_partes_e_origens(self):
        post = post_do_html(self.client.get(self.url_ato(0)))
        from django.urls import reverse
        url_manual = reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

        manual = self.client.post(url_manual, post)
        self.assertEqual(manual.status_code, 302, self.mensagens(manual))
        fotografia_manual = self._foto()
        Lancamento.objects.filter(documento=self.documento).delete()
        self.documento.refresh_from_db()

        revisao = self.client.post(self.url_ato(0), post)
        self.assertEqual(revisao.status_code, 302, self.mensagens(revisao))

        self.assertEqual(self._foto(), fotografia_manual)
        self.assertTrue(ImportacaoIA.objects.filter(
            modelo='Lancamento', campo__chave='/acts/0',
        ).exists())
