"""Aceite c1, c3, c5 e c6 do formulário de revisão (#341 fase 3)."""

from copy import deepcopy

from dominial.models import Lancamento
from ia_ocr.models import ImportacaoIA, OcrJobTransicao

from .test_revisao_formulario_view_base import RevisaoFormularioBase, post_do_html


class AceiteFormularioTest(RevisaoFormularioBase):
    def test_c1_tres_atos_navegam_sem_gravar(self):
        antes = self.contagens()

        entrada = self.client.get(self.url_entrada())
        pagina = self.client.get(self.url_ato(0))
        navegacao = self.client.post(
            self.url_ato(0), post_do_html(pagina, _ir_para='2'),
        )

        self.assertRedirects(entrada, self.url_ato(0), fetch_redirect_response=False)
        self.assertRedirects(navegacao, self.url_ato(2), fetch_redirect_response=False)
        html = pagina.content.decode()
        self.assertIn('1. R1', html)
        self.assertIn('2. Av1', html)
        self.assertIn('3. R2', html)
        self.assertEqual(self.contagens(), antes)

    def test_c3_estado_vem_do_banco_para_outro_cliente(self):
        self.salvar(0)
        outro_cliente = self.client_class()
        outro_cliente.force_login(self.usuario)

        entrada = outro_cliente.get(self.url_entrada())
        salvo = outro_cliente.get(self.url_ato(0))
        pendente = outro_cliente.get(self.url_ato(1))

        self.assertRedirects(entrada, self.url_ato(1), fetch_redirect_response=False)
        self.assertIn('1 de 3 salvo', pendente.content.decode())
        self.assertIn('✔ salvo', pendente.content.decode())
        from django.urls import reverse
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertRedirects(salvo, reverse('editar_lancamento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk,
            'lancamento_id': lancamento.pk,
        }), fetch_redirect_response=False)

    def test_c5_inicio_sem_origem_bloqueia_so_o_ato_e_banner_expoe_motivo(self):
        payload = self._payload_de_tres_atos()
        payload['acts'][0] = deepcopy(payload['acts'][0])
        payload['acts'][0]['tipo_sugerido'] = self._campo('inicio_matricula', 'M237')
        payload['acts'][0]['rotulo'] = self._campo('M-237', 'M237')
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        antes = self.contagens()

        pagina = self.client.get(self.url_ato(0))
        self.assertIn('Informe a origem deste início de matrícula', pagina.content.decode())
        bloqueado = self.client.post(self.url_ato(0), post_do_html(pagina))
        outro_ato = self.salvar(1)

        self.assertEqual(bloqueado.status_code, 200)
        self.assertIn('Informe a origem deste início de matrícula', bloqueado.content.decode())
        self.assertEqual(self.contagens()['Lancamento'] - antes['Lancamento'], 1)
        self.assertEqual(outro_ato.status_code, 302)

    def test_c6_ultimo_ato_importa_todos_com_auditoria_e_motivo(self):
        self.salvar(0)
        self.salvar(1)
        resposta = self.salvar(2)

        self.assertRedirects(resposta, self.url_documento(), fetch_redirect_response=False)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'importado')
        vinculos = ImportacaoIA.objects.filter(
            ocr_job=self.job, modelo='Lancamento',
        ).order_by('campo__chave')
        self.assertEqual(vinculos.count(), 3)
        self.assertEqual(
            list(vinculos.values_list('campo__chave', flat=True)),
            ['/acts/0', '/acts/1', '/acts/2'],
        )
        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 3)
        self.assertTrue(OcrJobTransicao.objects.filter(
            ocr_job=self.job, para_status='importado', motivo='revisao_formulario',
        ).exists())

    def test_c1_navegar_nao_escreve(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as consultas:
            self.client.get(self.url_entrada())
            for indice in range(3):
                resposta = self.client.get(self.url_ato(indice))
                self.assertEqual(resposta.status_code, 200)

        escritas = [
            consulta['sql'] for consulta in consultas.captured_queries
            if consulta['sql'].lstrip().upper().startswith(
                ('INSERT', 'UPDATE', 'DELETE'),
            )
        ]
        self.assertTrue(all('django_session' in sql for sql in escritas), escritas)

    def test_c5_fim_de_cadeia_destrava_o_salvar(self):
        payload = self._payload_de_tres_atos()
        payload['acts'][0] = deepcopy(payload['acts'][0])
        payload['acts'][0]['tipo_sugerido'] = self._campo('inicio_matricula', 'M237')
        payload['acts'][0]['rotulo'] = self._campo('M-237', 'M237')
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

        resposta = self.salvar(0, **{'fim_cadeia[]': '1'})

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Lancamento.objects.filter(documento=self.documento).count(), 1)
