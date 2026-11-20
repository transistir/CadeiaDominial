"""Homônimos na tela e no save (#267, #324) — migração VERBATIM de
``ia_ocr/tests/test_revisao_tela.py`` (Etapa 10 do plano de 400 linhas):
mesmas classes, mesmos nomes de teste; só mudam os imports.
"""

import json
from datetime import date

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from dominial.managers import documentos_for_user
from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    TIs,
)
from ia_ocr import revisao, services

from .payloads_extracao import _campo, payload_registro
from .test_revisao_tela_base import TelaRevisaoBase


class HomonimoNaTelaTest(TelaRevisaoBase):
    """#267: o aviso de homônimo sai do escopo do USUÁRIO, nunca do global.

    #341 fase 3: a tela de cards se foi; o cálculo que ela exibia é o MESMO
    que a resposta do save (viva até a aposentadoria) devolve — o escopo é
    asserido direto em ``revisao.avisos`` com ``documentos_for_user``.
    """

    def _preparar(self, imovel_do_homonimo):
        cartorio = Cartorios.objects.create(
            nome='CRI Origem 267', cns='CNS-267T', cidade='X', estado='SP',
        )
        tipo = DocumentoTipo.objects.create(tipo='matricula')
        DocumentoTipo.objects.create(tipo='transcricao')
        Documento.objects.create(
            imovel=imovel_do_homonimo, tipo=tipo, numero='M366',
            data=timezone.now().date(), cartorio=cartorio, livro='1',
            folha='1',
        )
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['origem'] = {
            'numero': _campo('T366', 'R-1/42.718'),
            'tipo_documento': _campo('transcricao', 'R-1/42.718'),
            'cartorio': _campo('CRI Origem 267', 'CRI de Guaíra'),
        }
        extracao = self._extracao(payload)
        extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
            criar_novo=False, cartorio_escolhido_id=cartorio.pk,
        )
        return extracao

    def _avisos_do_escopo(self, extracao):
        return [
            revisao.descrever_aviso(item)
            for item in revisao.avisos(
                extracao, documentos_queryset=documentos_for_user(self.dono),
            )
        ]

    def _motivos(self, extracao):
        return [item['motivo'] for item in self._avisos_do_escopo(extracao)]

    def test_homonimo_no_escopo_do_usuario_aparece_com_rotulo(self):
        extracao = self._preparar(self.imovel)

        descritos = self._avisos_do_escopo(extracao)

        self.assertIn('origem_homonimo_outro_tipo', self._motivos(extracao))
        item = next(
            i for i in descritos
            if i['motivo'] == 'origem_homonimo_outro_tipo'
        )
        self.assertEqual(item['chave'], '/acts/0/origem/numero')
        self.assertIn('Há um documento de outro tipo', item['rotulo'])
        self.assertNotIn('M366', item['rotulo'])

    def test_homonimo_de_outra_ti_nao_aparece_nem_vaza(self):
        outra = TIs.objects.create(nome='TI Alheia T267', codigo='TI-T267', etnia='X')
        imovel_alheio = Imovel.objects.create(
            nome='ImovelAlheioT267', matricula='ALHEIO-T267',
            terra_indigena_id=outra, proprietario=self.imovel.proprietario,
            cartorio=self.imovel.cartorio,
        )
        extracao = self._preparar(imovel_alheio)

        descritos = self._avisos_do_escopo(extracao)

        self.assertNotIn('origem_homonimo_outro_tipo', self._motivos(extracao))
        for segredo in ('M366', 'ImovelAlheioT267', 'TI Alheia T267'):
            with self.subTest(segredo=segredo):
                self.assertNotIn(
                    segredo, json.dumps(descritos, ensure_ascii=False),
                )

    # #324 (PR #343): a resposta do save usa o MESMO escopo da abertura.

    def _salvar_e_ler_avisos(self, extracao):
        salvar = self.client.post(
            self.url('salvar_bloco_ocr'),
            data=json.dumps({
                'versao': services.versao_bloco(extracao),
                'decisoes': [{
                    'chave': '/acts/0/origem/livro', 'incluir': True,
                    'valor': '3-A',
                }],
            }),
            content_type='application/json',
        )
        self.assertEqual(salvar.status_code, 200, salvar.content)
        return salvar

    def test_save_devolve_o_homonimo_do_escopo_do_usuario(self):
        extracao = self._preparar(self.imovel)

        salvar = self._salvar_e_ler_avisos(extracao)

        (aviso,) = [
            item for item in salvar.json()['avisos']
            if item['motivo'] == 'origem_homonimo_outro_tipo'
        ]
        self.assertEqual(aviso['chave'], '/acts/0/origem/numero')
        self.assertFalse(aviso['nao_consta'])
        # O texto fala do tipo; nunca do número do documento homônimo.
        self.assertNotIn('M366', salvar.content.decode())

    def test_save_nao_devolve_homonimo_de_outra_ti_nem_vaza(self):
        outra = TIs.objects.create(nome='TI Alheia S267', codigo='TI-S267', etnia='X')
        imovel_alheio = Imovel.objects.create(
            nome='ImovelAlheioS267', matricula='ALHEIO-S267',
            terra_indigena_id=outra, proprietario=self.imovel.proprietario,
            cartorio=self.imovel.cartorio,
        )
        extracao = self._preparar(imovel_alheio)

        salvar = self._salvar_e_ler_avisos(extracao)

        self.assertNotIn(
            'origem_homonimo_outro_tipo',
            [item['motivo'] for item in salvar.json()['avisos']],
        )
        conteudo = salvar.content.decode()
        for segredo in ('M366', 'ImovelAlheioS267', 'TI Alheia S267'):
            with self.subTest(segredo=segredo):
                self.assertNotIn(segredo, conteudo)


class HomonimoEmLoteNoSaveTest(TelaRevisaoBase):
    """#324 (PR #343, MUST-FIX do review): o save recalcula os avisos de
    TODOS os atos, e o número de consultas NÃO cresce com eles — o homônimo
    da origem é checado em lote (era um bloco de consultas por ato)."""

    # O endpoint tem custo fixo próprio (auth, contexto, lock, persistência e
    # pendências). O teto baixo incide na fatia que o homônimo pode multiplicar:
    # leituras de documentos/cartórios. A igualdade abaixo também cobre o POST
    # inteiro para impedir que outro N+1 por ato passe despercebido.
    LIMITE_CONSULTAS_HOMONIMO = 12

    def _extracao_com_origens(self, total):
        """``total`` atos, cada um com origem numerada, cartório escolhido e
        o seu homônimo M… no escopo do usuário — o caminho do homônimo roda
        para todos. A faixa de números sai do ``total``: duas chamadas no
        mesmo teste (50 e 100) não esbarram na identidade única do documento."""
        cartorio, _criado = Cartorios.objects.get_or_create(
            cns='CNS-324L',
            defaults={'nome': 'CRI Lote 324', 'cidade': 'X', 'estado': 'SP'},
        )
        base = 3000 + total
        Documento.objects.bulk_create([
            Documento(
                imovel=self.imovel, tipo=self.documento.tipo,
                numero=f'M{base + indice}', data=date(1990, 1, 1),
                cartorio=cartorio, livro='1', folha='1',
            )
            for indice in range(total)
        ])
        payload = payload_registro(self.job.job_id)
        payload['acts'] = [
            {
                'ordem': indice + 1,
                'rotulo': _campo(f'R-{indice + 1}', 'R-1/42.718', raw='R-1'),
                'tipo_sugerido': _campo('registro', 'R-1/42.718', raw='R-1'),
                'data': _campo('2020-02-15', '15 de fevereiro de 2020'),
                'origem': {
                    'numero': _campo(f'T{base + indice}', 'R-1/42.718'),
                    'tipo_documento': _campo('transcricao', 'R-1/42.718'),
                    'cartorio': _campo('CRI Lote 324', 'CRI de Guaíra'),
                },
            }
            for indice in range(total)
        ]
        extracao = self._extracao(payload)
        # Cartório JÁ cadastrado e escolhido em todos os atos: sem isso a
        # checagem do homônimo nem roda ("criar novo" não tem documentos).
        extracao.campos.filter(chave__endswith='/origem/cartorio').update(
            criar_novo=False, cartorio_escolhido_id=cartorio.pk,
        )
        return extracao

    def _consultas_do_save(self, total):
        """POST que muda só um campo do documento (como o review mediu) com
        ``total`` atos; devolve consultas do POST e da fatia de homônimos."""
        extracao = self._extracao_com_origens(total)
        versao = services.versao_bloco(extracao)
        with CaptureQueriesContext(connection) as capturado:
            resposta = self.client.post(
                self.url('salvar_bloco_ocr'),
                data=json.dumps({
                    'versao': versao,
                    'decisoes': [{
                        'chave': '/document/data', 'incluir': True,
                        'valor': '2020-01-10',
                    }],
                }),
                content_type='application/json',
            )
        self.assertEqual(resposta.status_code, 200, resposta.content)
        # Premissa do teste: o aviso de homônimo foi calculado para TODOS os
        # atos (cada origem T… tem a matrícula M… no cartório escolhido) —
        # dobrar os atos dobrou o trabalho do lote, não as consultas.
        avisos = resposta.json()['avisos']
        self.assertEqual(total, len([
            item for item in avisos
            if item['motivo'] == 'origem_homonimo_outro_tipo'
        ]))
        consultas_homonimo = [
            consulta for consulta in capturado.captured_queries
            if any(
                tabela in consulta['sql']
                for tabela in ('"dominial_documento"', '"dominial_cartorios"')
            )
        ]
        return len(capturado), len(consultas_homonimo)

    def test_consultas_do_save_nao_crescem_com_o_numero_de_atos(self):
        todas_com_50, homonimo_com_50 = self._consultas_do_save(50)
        todas_com_100, homonimo_com_100 = self._consultas_do_save(100)

        self.assertLess(
            homonimo_com_100, self.LIMITE_CONSULTAS_HOMONIMO,
            'a resolução em lote deve ter um teto baixo e fixo',
        )
        self.assertEqual(
            homonimo_com_100, homonimo_com_50,
            'dobrar os atos não pode multiplicar consultas de homônimos',
        )
        self.assertEqual(
            todas_com_100, todas_com_50,
            'dobrar os atos não pode aumentar as consultas do POST inteiro',
        )
