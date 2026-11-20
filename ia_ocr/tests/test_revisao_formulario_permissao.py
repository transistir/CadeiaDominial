"""Cenários de permissão, paridade com o manual e cartório da transmissão —
migração VERBATIM de ``ia_ocr/tests/test_revisao_formulario_view.py``
(Etapa 12 do plano de 400 linhas). Corpos e nomes de classes preservados.
"""

from django.contrib.auth.models import User
from django.urls import reverse

from dominial.models import Cartorios, Documento, Lancamento, UserTI
from ia_ocr.models import ImportacaoIA

from .factories import criar_documento_digital
from .test_revisao_formulario_view_base import (
    RevisaoFormularioBase, post_do_html,
)


class PermissaoTest(RevisaoFormularioBase):
    def setUp(self):
        super().setUp()
        self.intruso = User.objects.create_user(username='intruso-revisao')

    def test_sem_acesso_recebe_404_no_get_e_no_post(self):
        self.client.force_login(self.intruso)
        antes = self.contagens()

        for url in (self.url_entrada(), self.url_ato(0)):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(self.url_ato(0), {'tipo_lancamento': '1'}).status_code, 404)
        self.assertEqual(
            self.client.post(self.url_ato(0), {'_ir_para': '1'}).status_code, 404,
        )

        self.assertEqual(self.contagens(), antes)
        self.assertNotIn('ia_ocr_rascunhos', self.client.session)

    def test_ti_de_outro_documento_recebe_404(self):
        outro = criar_documento_digital(upload_por=self.usuario)
        UserTI.objects.create(
            user=self.usuario, tis=outro.documento.imovel.terra_indigena_id,
        )
        url = reverse('revisar_ato_ocr', kwargs={
            'tis_id': outro.documento.imovel.terra_indigena_id.pk,
            'imovel_id': outro.documento.imovel.pk,
            'documento_id': outro.documento.pk,
            'job_id': self.job.job_id, 'indice': 0,
        })

        self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonimo_vai_para_o_login(self):
        self.client.logout()

        resposta = self.client.get(self.url_ato(0))

        self.assertEqual(resposta.status_code, 302)
        self.assertIn('login', resposta['Location'])

    def test_metodo_nao_permitido(self):
        self.assertEqual(self.client.put(self.url_ato(0)).status_code, 405)
        self.assertEqual(self.client.post(self.url_entrada()).status_code, 405)

class ParidadeComOFormularioManualTest(RevisaoFormularioBase):
    """O HTML da revisão, enviado como o navegador envia, grava o mesmo que o manual.

    O POST sai do HTML renderizado da revisão (prova que o template emite os
    nomes certos) e vai, com o mesmo corpo, para o ``novo_lancamento`` e para
    a revisão — um depois do outro no MESMO documento, com a limpeza entre
    eles. Só pode diferir o vínculo de auditoria (``ImportacaoIA``).
    """

    def setUp(self):
        super().setUp()
        cartorio = self._cartorio('CRI da Origem da Paridade')
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['origem'] = {
            'tipo_documento': self._campo('matricula', 'MATRÍCULA Nº 42.718'),
            'numero': self._campo('M42.718', '42.718'),
            'cartorio': self._campo('CRI da Origem', 'CRI de Guaíra'),
            'livro': self._campo('2', 'Livro 2-RG'),
            'folha': self._campo('123', 'Folha 087'),
        }
        payload['acts'][0].update(
            forma=self._campo('Compra e Venda', 'Compra e Venda'),
            titulo=self._campo('Escritura Pública', 'Escritura Pública'),
            livro_transacao=self._campo('10-A', 'Livro 2-RG'),
            folha_transacao=self._campo('25v', 'Folha 087'),
            data_transacao=self._campo('2019-12-20', '10 de janeiro de 2020'),
            observacoes=self._campo('Observação lida', 'Observação lida'),
        )
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)
        self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            cartorio_escolhido=cartorio,
        )
        self.url_manual = reverse('novo_lancamento_documento', kwargs={
            'tis_id': self.imovel.terra_indigena_id.pk,
            'imovel_id': self.imovel.pk, 'documento_id': self.documento.pk,
        })

    def _fotografia(self):
        lancamento = Lancamento.objects.get(documento=self.documento)
        campos = {
            campo.attname: getattr(lancamento, campo.attname)
            for campo in Lancamento._meta.concrete_fields
            if campo.name not in ('id', 'documento')
            and not getattr(campo, 'auto_now', False)
            and not getattr(campo, 'auto_now_add', False)
        }
        return {
            'campos': campos,
            'pessoas': sorted(lancamento.pessoas.values_list(
                'tipo', 'nome_digitado', 'pessoa__nome',
            )),
            'origens': sorted(lancamento.origens_estruturadas.values_list(
                'tipo_documento', 'numero_normalizado', 'cartorio_id',
                'livro', 'folha',
            )),
            'documentos_criados': sorted(
                (doc.tipo.tipo, doc.numero, doc.cartorio_id, doc.livro, doc.folha)
                for doc in Documento.objects.filter(imovel=self.imovel)
                .exclude(pk=self.documento.pk).select_related('tipo')
            ),
            'documento': Documento.objects.values_list('livro', 'folha').get(
                pk=self.documento.pk,
            ),
        }

    def _limpar(self):
        Lancamento.objects.filter(documento=self.documento).delete()
        Documento.objects.filter(imovel=self.imovel).exclude(
            pk=self.documento.pk,
        ).delete()
        Documento.objects.filter(pk=self.documento.pk).update(livro='', folha='')

    def _comparar(self, indice):
        post = post_do_html(self.client.get(self.url_ato(indice)))

        manual = self.client.post(self.url_manual, post)
        self.assertEqual(manual.status_code, 302, self.mensagens(manual))
        fotografia_manual = self._fotografia()
        self.assertEqual(ImportacaoIA.objects.count(), 0)
        self._limpar()

        revisao = self.client.post(self.url_ato(indice), post)
        self.assertEqual(revisao.status_code, 302, self.mensagens(revisao))
        fotografia_revisao = self._fotografia()

        self.assertEqual(fotografia_revisao, fotografia_manual)
        self.assertTrue(ImportacaoIA.objects.filter(
            modelo='Lancamento',
            lancamento=Lancamento.objects.get(documento=self.documento),
        ).exists())
        return fotografia_revisao

    def test_registro_com_origem_transmissao_e_partes(self):
        fotografia = self._comparar(0)

        campos = fotografia['campos']
        self.assertEqual(campos['numero_lancamento'], 'R1 M237')
        self.assertEqual(campos['forma'], 'Compra e Venda')
        self.assertEqual(campos['titulo'], 'Escritura Pública')
        self.assertEqual(campos['livro_transacao'], '10-A')
        self.assertEqual(campos['origem'], 'M42.718')
        self.assertEqual(len(fotografia['pessoas']), 3)
        self.assertEqual(len(fotografia['origens']), 1)

    def test_averbacao_com_descricao(self):
        fotografia = self._comparar(1)

        campos = fotografia['campos']
        self.assertEqual(campos['numero_lancamento'], 'AV1 M237')
        self.assertEqual(campos['descricao'], 'averbação de construção de casa sede')
        self.assertEqual(fotografia['pessoas'], [])


class CartorioDaTransmissaoTest(RevisaoFormularioBase):
    """O nome lido pelo OCR nunca vira cartório novo pelo fluxo da revisão."""

    def _com_transmissao(self, nome):
        payload = self._payload_de_tres_atos()
        payload['acts'][0]['cartorio_transmissao'] = self._campo(nome, nome)
        self.job.extracoes.all().delete()
        self.extracao = self._aberta(payload)

    def test_nome_sem_cadastro_e_recusado_sem_criar_cartorio(self):
        self._com_transmissao('Cartório Inventado pelo OCR')
        antes = self.contagens()

        resposta = self.salvar(0, observacoes='digitado')

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.contagens(), antes)
        self.assertFalse(
            Cartorios.objects.filter(nome='Cartório Inventado pelo OCR').exists(),
        )
        self.assertTrue(any(
            "'Cartório Inventado pelo OCR' não está cadastrado" in texto
            for texto in self.mensagens(resposta)
        ))
        html = resposta.content.decode()
        self.assertIn('digitado', html)
        self.assertRegex(
            html, r'name="cartorio_transmissao_nome"[^>]*value="Cartório Inventado pelo OCR"',
        )

    def test_cartorio_escolhido_grava_o_do_cadastro(self):
        cartorio = self._cartorio('Cartório Cadastrado da Transmissão')
        self._com_transmissao('CRI de Guaíra')
        self.extracao.campos.filter(chave='/acts/0/cartorio_transmissao').update(
            cartorio_escolhido=cartorio,
        )
        antes = Cartorios.objects.count()

        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Cartorios.objects.count(), antes)
        lancamento = Lancamento.objects.get(documento=self.documento)
        self.assertEqual(lancamento.cartorio_transmissao_id, cartorio.pk)

    def test_nome_que_ja_existe_no_cadastro_segue_sem_criar_outro(self):
        # Só a caixa difere, em ASCII: o ``iexact`` do SQLite dos testes não
        # dobra a caixa de letra acentuada (o Postgres de produção dobra).
        existente = self._cartorio('Cartorio Que Ja Existe')
        self._com_transmissao('CARTORIO QUE JA EXISTE')
        antes = Cartorios.objects.count()

        resposta = self.salvar(0)

        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(Cartorios.objects.count(), antes)
        self.assertEqual(
            Lancamento.objects.get(documento=self.documento).cartorio_transmissao_id,
            existente.pk,
        )
