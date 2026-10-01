"""Teste do P2 do Greptile no #184: evitar N+1 em OrigemFimCadeia.

O service carregava cada OrigemFimCadeia com .only(...) mas sem
select_related('lancamento'), então cada iteração do loop disparava
um SELECT extra em Lancamento quando o código acessava
ofc.lancamento.documento_id. N+1 queries para TIs com muitas cadeias
finalizadas.

Este teste cria N imóveis com N fins de cadeia alcançáveis, captura o
número de queries com CaptureQueriesContext e valida que o total fica
abaixo de um limite razoável. Com select_related, esperamos 1 query
para todos os OrigemFimCadeia (em vez de 1 + N).
"""
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from dominial.models import (
    TIs, Imovel, DocumentoTipo, Cartorios, Documento, Pessoas,
    LancamentoTipo, Lancamento, OrigemFimCadeia,
)
from dominial.services.status_cadeia_service import StatusCadeiaService


class GreptileP2N1QueryTest(TestCase):
    """Garante que OrigemFimCadeia não dispara N queries por fim de cadeia."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user('u', 'u@x.com', 'pw')

        self.pessoa = Pessoas.objects.create(nome='P')
        self.ti = TIs.objects.create(nome='TI Perf')
        self.cart = Cartorios.objects.create(nome='CRI P', cidade='C')
        self.tipo_m = DocumentoTipo.objects.get_or_create(tipo='matricula')[0]
        self.tipo_reg = LancamentoTipo.objects.get_or_create(tipo='registro')[0]

        # 5 imóveis, cada um com 1 doc + 1 OrigemFimCadeia alcançável.
        self.quantidade = 5
        self.imoveis = []
        for i in range(self.quantidade):
            imo = Imovel.objects.create(
                nome=f'Im {i}', matricula=str(100 + i),
                tipo_documento_principal='M', cartorio=self.cart,
                terra_indigena_id=self.ti, proprietario=self.pessoa,
            )
            doc = Documento.objects.create(
                tipo=self.tipo_m, numero=str(100 + i),
                cartorio=self.cart, imovel=imo,
                data=date(2020, 1, 1), livro='1', folha='1',
            )
            lanc = Lancamento.objects.create(
                documento=doc, tipo=self.tipo_reg,
                data=date(2020, 1, 1),
            )
            OrigemFimCadeia.objects.create(
                lancamento=lanc, indice_origem=0, fim_cadeia=True,
                tipo_fim_cadeia='destacamento_publico',
                classificacao_fim_cadeia='origem_lidima',
            )
            self.imoveis.append(imo)

    def test_origem_fim_cadeia_carregado_em_uma_query_por_ti(self):
        """O queryset de OrigemFimCadeia deve disparar exatamente 1 query,
        independentemente do número de imóveis/fins na TI.

        Observação: o service chama construir_arvore_cadeia_dominial por
        imóvel (essa parte não é alvo do P2 do Greptile). Aqui validamos
        só o queryset final do service: a leitura de OrigemFimCadeia +
        Lancamento deve ser UMA query com JOIN.
        """
        # Roda uma vez para aquecer caches internos do ORM e não contar
        # setup de tipos.
        StatusCadeiaService.status_por_imovel(self.ti.id)

        # Mede só o queryset-alvo: OrigemFimCadeia com JOIN Lancamento.
        from dominial.models import OrigemFimCadeia
        with CaptureQueriesContext(connection) as ctx:
            list(
                OrigemFimCadeia.objects.filter(
                    fim_cadeia=True,
                ).select_related('lancamento').only(
                    'lancamento__documento_id',
                    'classificacao_fim_cadeia',
                )
            )

        ofc_queries = [
            q['sql'] for q in ctx.captured_queries
            if 'dominial_origemfimcadeia' in q['sql'].lower()
        ]
        self.assertEqual(
            len(ofc_queries), 1,
            f'P2 Greptile: select_related deveria gerar exatamente 1 query '
            f'JOIN, capturado {len(ofc_queries)} queries: {ofc_queries}',
        )
        # Sanidade: a query única usa JOIN com Lancamento.
        self.assertIn(
            'join', ofc_queries[0].lower(),
            f'P2 Greptile: query única deveria ter JOIN: {ofc_queries[0]}',
        )

    def test_service_nao_dispara_n_plus_um_por_fim_de_cadeia(self):
        """Valida que o loop de OrigemFimCadeia do service usa 1 query
        com JOIN Lancamento (não N queries, uma por marcador).

        Filtra queries do service de status e conta OrigemFimCadeia com
        INNER JOIN Lancamento — esperado: exatamente 1.
        """
        with CaptureQueriesContext(connection) as ctx:
            result = StatusCadeiaService.status_por_imovel(self.ti.id)

        self.assertEqual(len(result), self.quantidade)

        # O service gera exatamente 1 query cobrindo OrigemFimCadeia
        # INNER JOIN Lancamento com documento_id IN (...).
        ofc_join_lanc = [
            q['sql'] for q in ctx.captured_queries
            if 'from "dominial_origemfimcadeia"' in q['sql'].lower()
            and 'inner join "dominial_lancamento"' in q['sql'].lower()
            and '"documento_id" in (' in q['sql'].lower()
        ]
        self.assertEqual(
            len(ofc_join_lanc), 1,
            f'P2 Greptile: service deveria usar 1 query com JOIN '
            f'OrigemFimCadeia+Lancamento+documento_id IN. Capturado '
            f'{len(ofc_join_lanc)}: {ofc_join_lanc}',
        )
