"""Banner da revisão com DOIS grupos: bloqueios × avisos (#332)."""

from copy import deepcopy

from .payloads_extracao import payload_registro
from .test_revisao_formulario_view_base import RevisaoFormularioBase


def _grupo(html, classe):
    """Conteúdo do ``<ul class="classe">`` do banner (sem estilo)."""
    inicio = html.index(f'class="{classe}"')
    fim = html.index('</ul>', inicio)
    return html[inicio:fim]


def _banner(html):
    inicio = html.index('id="ia-revisao-banner"')
    fim = html.index('</section>', inicio)
    return html[inicio:fim]


class BannerGruposTest(RevisaoFormularioBase):
    def _com_area_em_alqueires(self, *, inicio_sem_data=False):
        payload = self._payload_de_tres_atos()
        payload['acts'] = [deepcopy(payload['acts'][0])]
        ato = payload['acts'][0]
        ato['area'] = {
            **self._campo('12.50', 'área 12,50 alqueires'),
            'unidade': 'alqueires', 'raw': '12,50 alqueires',
        }
        if inicio_sem_data:
            ato['tipo_sugerido'] = self._campo('inicio_matricula', 'M237')
            ato['rotulo'] = self._campo('M-237', 'M237')
            ato['data'] = self._campo(None, None)
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        return ato

    def test_area_bloqueante_fica_so_no_grupo_de_bloqueios(self):
        self._com_area_em_alqueires()

        html = self.client.get(self.url_ato(0)).content.decode()

        bloqueios = _grupo(html, 'ia-revisao-bloqueios')
        self.assertIn('12,5 alqueires no documento', bloqueios)
        self.assertIn('ia-revisao-descarte-area', bloqueios)
        # Não há grupo de avisos (ou ele não repete a pendência da área).
        if 'ia-revisao-avisos' in html:
            self.assertNotIn('Área', _grupo(html, 'ia-revisao-avisos'))

    def test_informativos_do_prefill_ficam_no_grupo_de_avisos(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        bloqueios = (
            _grupo(html, 'ia-revisao-bloqueios')
            if 'ia-revisao-bloqueios' in html else ''
        )
        avisos = _grupo(html, 'ia-revisao-avisos')
        self.assertIn('CPF/RG das partes', avisos)
        self.assertNotIn('CPF/RG das partes', bloqueios)

    def test_avisos_da_revisao_entram_no_grupo_de_avisos(self):
        self.tipo_registro.requer_forma = True
        self.tipo_registro.save(update_fields=['requer_forma'])

        html = self.client.get(self.url_ato(0)).content.decode()

        avisos = _grupo(html, 'ia-revisao-avisos')
        self.assertIn('forma', avisos)
        self.assertIn('Campo recomendado', avisos)
        self.assertNotIn('/acts/', avisos)

    def test_abertura_sem_data_aparece_no_get(self):
        self._com_area_em_alqueires(inicio_sem_data=True)

        html = self.client.get(self.url_ato(0)).content.decode()

        bloqueios = _grupo(html, 'ia-revisao-bloqueios')
        self.assertIn('Informe a data do ato de abertura', bloqueios)

    def test_reenvio_recusado_mostra_so_o_que_falta(self):
        self._com_area_em_alqueires(inicio_sem_data=True)

        resposta = self.salvar(0, area='0.012')

        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        bloqueios = _grupo(html, 'ia-revisao-bloqueios')
        self.assertNotIn('12,5 alqueires no documento', bloqueios)
        self.assertIn('Informe a data do ato de abertura', bloqueios)

    def test_reenvio_recusado_preserva_informativos_do_prefill(self):
        recusa = self.salvar(0, tipo_lancamento='')

        self.assertEqual(recusa.status_code, 200)
        avisos = _grupo(recusa.content.decode(), 'ia-revisao-avisos')
        self.assertIn('CPF/RG das partes', avisos)

    def test_area_invalida_no_reenvio_mantem_checkbox_de_descarte(self):
        self._com_area_em_alqueires()
        antes = self.contagens()

        resposta = self.salvar(0, area='1.000')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        bloqueios = _grupo(resposta.content.decode(), 'ia-revisao-bloqueios')
        self.assertIn('ia-revisao-descarte-area', bloqueios)

    def test_checkbox_de_descarte_sobrevive_ao_reenvio(self):
        self._com_area_em_alqueires(inicio_sem_data=True)

        recusa = self.salvar(0, area='')
        self.assertEqual(recusa.status_code, 200)
        self.assertIn(
            'ia-revisao-descarte-area',
            _grupo(recusa.content.decode(), 'ia-revisao-bloqueios'),
        )

        descartada = self.salvar(0, area='', descartar_area='1')
        self.assertEqual(descartada.status_code, 200)
        html = descartada.content.decode()
        avisos = _grupo(html, 'ia-revisao-avisos')
        self.assertIn('descartada pelo revisor', avisos)
        self.assertIn('ia-revisao-descarte-area', avisos)
        self.assertIn('checked', avisos)
        self.assertNotIn(
            '12,5 alqueires no documento',
            _grupo(html, 'ia-revisao-bloqueios'),
        )

    def test_nenhuma_chave_tecnica_no_banner(self):
        self._com_area_em_alqueires(inicio_sem_data=True)

        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertNotIn('/acts/', _banner(html))

    def test_lidos_sem_campo_nao_sao_deduplicados(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        avisos = _grupo(html, 'ia-revisao-avisos')
        self.assertIn('CPF/RG das partes', avisos)
        self.assertIn('Valor da transação', avisos)

    def test_data_da_origem_convive_com_cpf_rg(self):
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'data': self._campo('2019-01-01', '1º de janeiro de 2019'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        html = self.client.get(self.url_ato(0)).content.decode()

        avisos = _grupo(html, 'ia-revisao-avisos')
        self.assertIn('Data da origem', avisos)
        self.assertIn('CPF/RG das partes', avisos)

    def test_descarte_nao_efetivo_nao_afirma_descarte(self):
        self._com_area_em_alqueires(inicio_sem_data=True)

        resposta = self.salvar(0, area='0.012', descartar_area='1')

        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        avisos = (
            _grupo(html, 'ia-revisao-avisos')
            if 'ia-revisao-avisos' in html else ''
        )
        self.assertNotIn('descartada pelo revisor', avisos)

    def test_area_invalida_mostra_mensagem_do_parser(self):
        self._com_area_em_alqueires()

        resposta = self.salvar(0, area='1.000')

        self.assertEqual(resposta.status_code, 200)
        bloqueios = _grupo(resposta.content.decode(), 'ia-revisao-bloqueios')
        self.assertIn('Área ambígua', bloqueios)
        self.assertIn('ia-revisao-descarte-area', bloqueios)

    def test_area_vazia_mostra_texto_do_prefill(self):
        self._com_area_em_alqueires()

        resposta = self.salvar(0, area='')

        self.assertEqual(resposta.status_code, 200)
        bloqueios = _grupo(resposta.content.decode(), 'ia-revisao-bloqueios')
        self.assertIn('12,5 alqueires no documento', bloqueios)


class BannerSemRascunhoTest(RevisaoFormularioBase):
    def test_payload_limpo_nao_inventa_bloqueio(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['partes'] = []
        payload['acts'][0].pop('valor_transacao', None)
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertNotIn('ia-revisao-bloqueios', html)
