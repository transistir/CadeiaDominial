"""Ordem da sidebar: o início de matrícula vem da precedência da importação.

Regressão (#370, review do PR #377): ``eh_inicio`` era decidido por
``'inicio_matricula' in (ato.tipo, analisado.tipo)``, e ``ato.tipo`` é
``valor(tipo_sugerido) or tipo_resolvido`` — a sugestão crua do OCR vencia.
Um ato com rótulo ``R-5`` e ``tipo_sugerido=inicio_matricula`` ia para o FIM
da sidebar, embora a importação grave ``registro`` e a aba mostre ``R5``.
A decisão agora é o ``resolver_tipo`` da importação: explícito → rótulo R/Av
→ sugestão.
"""

import re

from ia_ocr import revisao_ato
from ia_ocr.models import CampoSugerido

from .test_revisao_formulario_view_base import RevisaoFormularioBase


class SidebarOrdemPelaPrecedenciaDoTipoTest(RevisaoFormularioBase):
    """O tipo que decide a ordem é o mesmo que a importação vai gravar."""

    def _abas_da_sidebar(self, html):
        sidebar = html[html.index('ia-revisao-sidebar'):]
        return re.findall(
            r'>(\d+)\. (R\d+|Av\d+|Abertura)',
            sidebar[:sidebar.index('</aside>')],
        )

    def _abrir_com_o_tipo_do_ato(self, indice, rotulo, tipo_sugerido):
        payload = self._payload_de_tres_atos()
        ato = payload['acts'][indice]
        ato['rotulo'] = self._campo(rotulo, rotulo)
        ato['tipo_sugerido'] = self._campo(tipo_sugerido, rotulo)
        self.extracao = self._aberta(payload)

    def _ato_e_abas(self, indice):
        ato = revisao_ato.atos_da_revisao(self.extracao)[indice]
        html = self.client.get(self.url_ato(0)).content.decode()
        return (ato['rotulo'], ato['eh_inicio']), self._abas_da_sidebar(html)

    def test_rotulo_de_registro_vence_a_sugestao_de_inicio(self):
        self._abrir_com_o_tipo_do_ato(0, 'R-1', 'inicio_matricula')

        aba, abas = self._ato_e_abas(0)

        self.assertEqual(aba, ('R1', False))
        self.assertEqual(abas, [('3', 'R2'), ('2', 'Av1'), ('1', 'R1')])

    def test_registro_divergente_no_meio_nao_vai_para_o_fim(self):
        self._abrir_com_o_tipo_do_ato(1, 'R-5', 'inicio_matricula')

        aba, abas = self._ato_e_abas(1)

        self.assertEqual(abas, [('3', 'R2'), ('2', 'R5'), ('1', 'R1')])
        self.assertEqual(aba, ('R5', False))

    def test_sugestao_de_inicio_sem_rotulo_r_av_continua_abertura(self):
        self._abrir_com_o_tipo_do_ato(0, 'M237', 'inicio_matricula')

        aba, abas = self._ato_e_abas(0)

        self.assertEqual(aba, ('Abertura', True))
        self.assertEqual(abas, [('3', 'R2'), ('2', 'Av1'), ('1', 'Abertura')])

    def test_escolha_explicita_de_inicio_continua_abertura(self):
        self._abrir_com_o_tipo_do_ato(0, 'X-1', 'registro')
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/tipo_sugerido',
        ).update(valor_final='inicio_matricula', escolha_explicita=True)

        aba, abas = self._ato_e_abas(0)

        self.assertEqual(aba, ('Abertura', True))
        self.assertEqual(abas, [('3', 'R2'), ('2', 'Av1'), ('1', 'Abertura')])
