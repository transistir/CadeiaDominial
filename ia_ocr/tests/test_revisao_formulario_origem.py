"""Cenários da origem do ato — migração VERBATIM de
``ia_ocr/tests/test_revisao_formulario_view.py`` (Etapa 12 do plano de
400 linhas).

``OrigemAcrescentadaANaoTest`` herda de ``OrigemComPontoTest``: as duas
classes precisam ficar no MESMO arquivo. Corpos preservados.
"""

import re

from django.urls import reverse

from dominial.models import Lancamento, LancamentoOrigem
from ia_ocr.models import ImportacaoIA

from .payloads_extracao import payload_registro
from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase, post_do_html,
)


class OrigemComPontoTest(RevisaoFormularioBase):
    """O OCR traz ``42.718``; o campo visível e o POST não podem perdê-lo."""

    def setUp(self):
        super().setUp()
        self.cartorio_origem = self._cartorio('CRI da Origem Pontuada')
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': self._campo('CRI da Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=self.cartorio_origem,
        )

    def test_numero_com_ponto_aparece_inteiro_no_input_e_no_texto_oculto(self):
        html = self.client.get(self.url_ato(0)).content.decode()

        self.assertRegex(html, r'<input[^>]*name="numero_origem_0"[^>]*value="42.718"')
        self.assertRegex(
            html, r'name="origem_completa\[\]"[^>]*value="M42.718"',
        )

    def test_pattern_e_maxlength_aceitam_o_numero_com_ponto(self):
        html = self.client.get(self.url_ato(0)).content.decode()
        entrada = re.search(r'<input[^>]*name="numero_origem_0"[^>]*>', html).group(0)

        padrao = re.search(r'pattern="([^"]*)"', entrada).group(1)
        limite = int(re.search(r'maxlength="(\d+)"', entrada).group(1))

        self.assertTrue(re.fullmatch(padrao, '42.718'))
        self.assertTrue(re.fullmatch(padrao, '366'))
        self.assertFalse(re.fullmatch(padrao, '42.'))
        self.assertFalse(re.fullmatch(padrao, 'abc'))
        self.assertGreaterEqual(limite, len('12.345.678'))

    def test_pattern_vale_tambem_para_a_origem_em_branco_do_formulario_manual(self):
        resposta = self.client.get(reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        }))

        self.assertIn('pattern="[0-9]+([.][0-9]+)*"', resposta.content.decode())

    def test_o_post_leva_o_numero_com_ponto_e_o_lancamento_guarda(self):
        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.origem, 'M42.718')
        self.assertEqual(
            list(LancamentoOrigem.objects.filter(lancamento=lancamento)
                 .values_list('numero_normalizado', flat=True)),
            ['42.718'],
        )

    def test_origem_estruturada_entra_na_auditoria_com_a_linha_da_origem(self):
        self.salvar(0)

        vinculo = ImportacaoIA.objects.get(modelo='LancamentoOrigem')
        self.assertEqual(vinculo.campo.chave, '/acts/0/origem/numero')
        self.assertEqual(
            vinculo.objeto_id,
            Lancamento.objects.get(documento=self.documento)
            .origens_estruturadas.get().pk,
        )

    def test_rascunho_e_re_render_de_erro_mantem_o_numero_inteiro(self):
        resposta = self.salvar(0, tipo_lancamento='')

        html = resposta.content.decode()
        self.assertRegex(html, r'<input[^>]*name="numero_origem_0"[^>]*value="42.718"')
        self.assertRegex(html, r'name="origem_completa\[\]"[^>]*value="M42.718"')


class OrigemAcrescentadaANaoTest(OrigemComPontoTest):
    """N1 (#341): TODAS as origens persistidas ganham vínculo de auditoria.

    O ``.first()`` auditava só a primeira — com a origem lida MAIS uma
    acrescentada no formulário, a segunda nascia sem ``ImportacaoIA``.
    """

    def test_origem_acrescentada_a_mao_tambem_recebe_vinculo(self):
        segunda = self._cartorio('CRI da Segunda Origem')
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        post['origem_completa[]'] = post['origem_completa[]'] + ['T366']
        post['cartorio_origem_nome[]'] = (
            post['cartorio_origem_nome[]'] + [segunda.nome]
        )
        post['cartorio_origem[]'] = post['cartorio_origem[]'] + [str(segunda.pk)]
        post['livro_origem[]'] = post.get('livro_origem[]', ['']) + ['']
        post['folha_origem[]'] = post.get('folha_origem[]', ['']) + ['']

        resposta = self.client.post(self.url_ato(0), post)

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        lancamento = Lancamento.objects.get(documento=self.documento)
        origens = list(
            lancamento.origens_estruturadas.order_by('indice_origem')
        )
        self.assertEqual([origem.numero for origem in origens], ['M42.718', 'T366'])

        vinculos = ImportacaoIA.objects.filter(modelo='LancamentoOrigem')
        # Uma por origem persistida — nenhuma fica sem vínculo.
        self.assertEqual(
            set(vinculos.values_list('objeto_id', flat=True)),
            {origem.pk for origem in origens},
        )
        # Só a origem que o OCR leu carrega a linha dela; a digitada à mão
        # não vem de linha nenhuma.
        lida = vinculos.get(objeto_id=origens[0].pk)
        self.assertEqual(lida.campo.chave, '/acts/0/origem/numero')
        manual = vinculos.get(objeto_id=origens[1].pk)
        self.assertIsNone(manual.campo)

    def test_origem_extraida_editada_mantem_a_linha_e_manual_nao_a_herda(self):
        segunda = self._cartorio('Cartório Manual com Valor Antigo')
        pagina = self.client.get(self.url_ato(0))
        post = post_do_html(pagina)
        # A linha zero veio do OCR, mas o revisor corrigiu M42.718 para T777.
        # A segunda foi acrescentada à mão e reutiliza o texto OCR antigo.
        post['origem_completa[]'][0] = 'T777'
        post['origem_completa[]'].append('M42.718')
        post['cartorio_origem_nome[]'].append(segunda.nome)
        post['cartorio_origem[]'].append(str(segunda.pk))
        post['livro_origem[]'] = post.get('livro_origem[]', ['']) + ['']
        post['folha_origem[]'] = post.get('folha_origem[]', ['']) + ['']

        resposta = self.client.post(self.url_ato(0), post)

        self.assertEqual(resposta.status_code, 302, self.mensagens(resposta))
        origens = list(
            Lancamento.objects.get(documento=self.documento)
            .origens_estruturadas.order_by('indice_origem')
        )
        self.assertEqual([origem.numero for origem in origens], ['T777', 'M42.718'])
        vinculos = ImportacaoIA.objects.filter(modelo='LancamentoOrigem')
        self.assertEqual(
            set(vinculos.values_list('objeto_id', flat=True)),
            {origem.pk for origem in origens},
        )
        extraida = vinculos.get(objeto_id=origens[0].pk)
        self.assertEqual(extraida.campo.chave, '/acts/0/origem/numero')
        manual = vinculos.get(objeto_id=origens[1].pk)
        self.assertIsNone(manual.campo)
