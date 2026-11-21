"""Ordem da sidebar: o tipo da aba vem do que a importação grava/gravou.

Regressão (#370, review do PR #377): ``eh_inicio`` era decidido por
``'inicio_matricula' in (ato.tipo, analisado.tipo)``, e ``ato.tipo`` é
``valor(tipo_sugerido) or tipo_resolvido`` — a sugestão crua do OCR vencia.
Um ato com rótulo ``R-5`` e ``tipo_sugerido=inicio_matricula`` ia para o FIM
da sidebar, embora a importação grave ``registro`` e a aba mostre ``R5``.
A decisão é o ``resolver_tipo`` da importação (explícito → rótulo R/Av →
sugestão); depois de salvo, manda o ``Lancamento.tipo`` gravado — o revisor
pode MUDAR o tipo no formulário e salvar. ``inicio_matricula`` responde
``Abertura`` ANTES do ramo R/Av.
"""

import re
from copy import deepcopy
from datetime import date

from django.db import connection
from django.test.utils import CaptureQueriesContext

from dominial.models import Lancamento
from ia_ocr import revisao_ato
from ia_ocr.models import CampoSugerido, ImportacaoIA

from .payloads_extracao import payload_averbacao
from .test_revisao_formulario_view_base import RevisaoFormularioBase


class SidebarBase(RevisaoFormularioBase):
    """Leituras da sidebar (nenhum teste): aba de um ato e ordem das abas."""

    def _abas_da_sidebar(self, html):
        sidebar = html[html.index('ia-revisao-sidebar'):]
        return re.findall(
            r'>(\d+)\. (R\d+|Av\d+|Abertura|Ato \d+)',
            sidebar[:sidebar.index('</aside>')],
        )

    def _abrir_com_o_tipo_do_ato(self, indice, rotulo, tipo_sugerido):
        payload = self._payload_de_tres_atos()
        ato = payload['acts'][indice]
        ato['rotulo'] = self._campo(rotulo, rotulo)
        ato['tipo_sugerido'] = self._campo(tipo_sugerido, rotulo)
        self.extracao = self._aberta(payload)

    def _ato_e_abas(self, indice, pagina=0):
        ato = revisao_ato.atos_da_revisao(self.extracao)[indice]
        html = self.client.get(self.url_ato(pagina)).content.decode()
        return (ato['rotulo'], ato['eh_inicio']), self._abas_da_sidebar(html)

    def _importado(self, extracao, indice, tipo):
        """O ato ``indice`` salvo com ``tipo``, no formato da importação."""
        lancamento = Lancamento.objects.create(
            documento=self.documento, tipo=tipo, data=date(2020, 2, 15),
        )
        ImportacaoIA.objects.create(
            ocr_job=self.job,
            documento_digital_id=self.job.documento_digital_id,
            campo=CampoSugerido.objects.get(
                extracao=extracao, chave=f'/acts/{indice}',
            ),
            pagina=1,
            modelo='Lancamento',
            objeto_id=lancamento.pk,
            lancamento=lancamento,
            criado_por=self.usuario,
        )
        return lancamento


class SidebarOrdemPelaPrecedenciaDoTipoTest(SidebarBase):
    """O tipo que decide a ordem é o mesmo que a importação vai gravar."""

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

    def test_escolha_explicita_de_inicio_vence_o_rotulo_av(self):
        self._abrir_com_o_tipo_do_ato(0, 'Av-1', 'averbacao')
        CampoSugerido.objects.filter(
            extracao=self.extracao, chave='/acts/0/tipo_sugerido',
        ).update(valor_final='inicio_matricula', escolha_explicita=True)

        aba, abas = self._ato_e_abas(0)

        self.assertEqual(aba, ('Abertura', True))
        self.assertEqual(abas, [('3', 'R2'), ('2', 'Av1'), ('1', 'Abertura')])


class SidebarTipoSalvoTest(SidebarBase):
    """O ``Lancamento.tipo`` gravado vence a leitura da extração."""

    def _extracao_com_atos_importados(self, total):
        payload = payload_averbacao(self.job.job_id)
        ato = payload['acts'][0]
        payload['acts'] = [deepcopy(ato) for _ in range(total)]
        for indice, ato in enumerate(payload['acts']):
            ato['rotulo'] = self._campo(f'Av-{indice + 1}', f'AV-{indice + 1}')
        extracao = self._aberta(payload)
        for indice in range(total):
            self._importado(extracao, indice, self.tipo_averbacao)
        return extracao

    def test_salvo_como_inicio_vira_abertura_e_vai_para_o_fim(self):
        self._importado(self.extracao, 0, self.tipo_inicio)

        # Ato 0 importado redireciona para a edição; a sidebar sai do ato 1.
        aba, abas = self._ato_e_abas(0, pagina=1)

        self.assertEqual(aba, ('Abertura', True))
        self.assertEqual(abas, [('3', 'R2'), ('2', 'Av1'), ('1', 'Abertura')])

    def test_convertido_de_inicio_para_registro_perde_a_abertura(self):
        self._abrir_com_o_tipo_do_ato(1, 'M237', 'inicio_matricula')
        self._importado(self.extracao, 1, self.tipo_registro)

        aba, abas = self._ato_e_abas(1)

        self.assertEqual(aba, ('Ato 2', False))
        self.assertEqual(abas, [('3', 'R2'), ('2', 'Ato 2'), ('1', 'R1')])

    def test_leitura_dos_tipos_salvos_e_uma_so_qualquer_que_seja_a_quantidade(self):
        pequena = self._extracao_com_atos_importados(3)
        grande = self._extracao_com_atos_importados(30)

        with CaptureQueriesContext(connection) as tres:
            atos_tres = revisao_ato.atos_da_revisao(pequena)
        with CaptureQueriesContext(connection) as trinta:
            atos_trinta = revisao_ato.atos_da_revisao(grande)

        self.assertEqual(len(atos_tres), 3)
        self.assertEqual(len(atos_trinta), 30)
        # Uma leitura em lote: 30 atos salvos custam as mesmas queries de 3.
        self.assertEqual(len(tres), len(trinta))
