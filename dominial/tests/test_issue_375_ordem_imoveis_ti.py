"""Issue #375 — lista de imóveis da TI: cartório abreviado + ordem por atividade.

- A coluna Matrícula em ``tis_detail`` mostra, ao lado da matrícula, o
  cartório abreviado (``Cartório de Registro de Imóveis de Barreiras`` →
  ``CRI de Barreiras``), com o nome por extenso no ``title``.
- A ordem passa a considerar EDIÇÃO de documento/lançamento (não só
  criação): do mais recente para o mais antigo, desempate por matrícula.
- Linhas legadas (``atualizado_em`` NULL, pré-migração 0062) caem no
  fallback ``data_cadastro`` — inclusive o caso misto com lançamento
  recente.
"""

from datetime import date, datetime, timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoTipo,
    Pessoas,
    TIs,
)

# Instantes fixos (aware): nada depende do relógio nem de sleep/microssegundos.
INSTANTE_BASE = timezone.make_aware(datetime(2026, 11, 21, 10, 0, 0))
INSTANTE_EDICAO = timezone.make_aware(datetime(2026, 11, 21, 12, 0, 0))
# Cadastro dos imóveis fixado no passado: sem isso, o próprio
# ``data_cadastro`` do imóvel (hoje, pela auto_now_add) dominaria o
# ``Greatest`` e mascararia os instantes fixados de documento/lançamento.
DATA_CADASTRO_IMOVEIS = date(2026, 11, 20)


class ListaImoveisTIBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="t375", password="t375pass")
        self.client = Client()
        self.client.login(username="t375", password="t375pass")

        self.tis = TIs.objects.create(nome="TI 375", etnia="Teste", codigo="TI375")
        from dominial.tests.segregacao_fixtures import atribuir_tis
        atribuir_tis(self.user, self.tis)

        self.cartorio = Cartorios.objects.create(
            nome="Cartório de Registro de Imóveis de Barreiras",
            cns="CNS375375",
            cidade="Barreiras",
        )
        self.pessoa = Pessoas.objects.create(nome="Proprietário 375", cpf="37537537537")
        self.tipo_matricula = DocumentoTipo.objects.create(tipo="matricula")
        self.tipo_registro = LancamentoTipo.objects.create(tipo="registro")

    def _criar_imovel(self, matricula, arquivado=False):
        imovel = Imovel.objects.create(
            nome=f"Imóvel {matricula}",
            matricula=matricula,
            terra_indigena_id=self.tis,
            proprietario=self.pessoa,
            cartorio=self.cartorio,
            arquivado=arquivado,
        )
        Imovel.objects.filter(id=imovel.id).update(data_cadastro=DATA_CADASTRO_IMOVEIS)
        return imovel

    def _criar_documento_com_lancamento(self, imovel):
        documento = Documento.objects.create(
            numero=imovel.matricula,
            tipo=self.tipo_matricula,
            imovel=imovel,
            cartorio=self.cartorio,
            data=DATA_CADASTRO_IMOVEIS,
            livro="1",
            folha="1",
        )
        lancamento = Lancamento.objects.create(
            documento=documento,
            tipo=self.tipo_registro,
            data=DATA_CADASTRO_IMOVEIS,
            origem="",
        )
        return documento, lancamento

    def _criar_documento_legado(self, imovel, data_cadastro):
        """Documento estilo pré-migração 0062: ``atualizado_em`` NULL."""
        documento = Documento.objects.create(
            numero=imovel.matricula,
            tipo=self.tipo_matricula,
            imovel=imovel,
            cartorio=self.cartorio,
            data=data_cadastro,
            livro="1",
            folha="1",
        )
        Documento.objects.filter(id=documento.id).update(
            atualizado_em=None, data_cadastro=data_cadastro
        )
        return documento

    def _fixar_atividade(self, imovel, instant):
        """Pinha ``atualizado_em`` dos documentos e lançamentos do imóvel.

        ``.update()`` não dispara ``auto_now`` — por isso é o jeito
        determinístico de simular criação/edição em instantes conhecidos.
        """
        Documento.objects.filter(imovel=imovel).update(atualizado_em=instant)
        Lancamento.objects.filter(documento__imovel=imovel).update(atualizado_em=instant)

    def _ordem_na_pagina(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return [i.matricula for i in response.context["imoveis"]]


class CartorioAbreviadoTest(ListaImoveisTIBase):
    def test_tis_detail_mostra_cartorio_abreviado(self):
        imovel = self._criar_imovel("M100")
        self._criar_documento_com_lancamento(imovel)
        response = self.client.get(reverse("tis_detail", args=[self.tis.id]))
        conteudo = response.content.decode()
        self.assertIn("M100 · CRI de Barreiras", conteudo)
        self.assertIn('title="Cartório de Registro de Imóveis de Barreiras"', conteudo)

    def test_rota_legada_imoveis_mostra_cartorio_abreviado(self):
        imovel = self._criar_imovel("M200")
        self._criar_documento_com_lancamento(imovel)
        response = self.client.get(reverse("imoveis", args=[self.tis.id]))
        conteudo = response.content.decode()
        self.assertIn("M200 · CRI de Barreiras", conteudo)


class OrdemPorAtividadeTest(ListaImoveisTIBase):
    def test_edicao_de_lancamento_no_mesmo_dia_sobe_para_primeiro(self):
        imovel_a = self._criar_imovel("MA")
        imovel_b = self._criar_imovel("MB")
        imovel_c = self._criar_imovel("MC")
        for i, imovel in enumerate((imovel_a, imovel_b, imovel_c)):
            self._criar_documento_com_lancamento(imovel)
            self._fixar_atividade(imovel, INSTANTE_BASE + timedelta(minutes=i))
        url = reverse("tis_detail", args=[self.tis.id])
        # Instantes fixos: MC (10:02) é o mais recente na atividade.
        self.assertEqual(self._ordem_na_pagina(url), ["MC", "MB", "MA"])

        # Editar o lançamento do imóvel MAIS ANTIGO (MA) para 12:00: a
        # edição no mesmo dia precisa colocá-lo à frente.
        Lancamento.objects.filter(documento__imovel=imovel_a).update(
            atualizado_em=INSTANTE_EDICAO
        )
        self.assertEqual(self._ordem_na_pagina(url), ["MA", "MC", "MB"])

    def test_criacao_de_lancamento_em_imovel_com_documento_sobe(self):
        # Regressão do Coalesce: imóvel que JÁ TEM documento não pode ficar
        # preso à data do documento quando recebe um lançamento novo.
        imovel_a = self._criar_imovel("MA")
        imovel_b = self._criar_imovel("MB")
        documento_a, _ = self._criar_documento_com_lancamento(imovel_a)
        self._criar_documento_com_lancamento(imovel_b)
        self._fixar_atividade(imovel_a, INSTANTE_BASE)
        self._fixar_atividade(imovel_b, INSTANTE_BASE + timedelta(minutes=1))
        url = reverse("tis_detail", args=[self.tis.id])
        self.assertEqual(self._ordem_na_pagina(url), ["MB", "MA"])

        # Novo lançamento (pinado em 12:00) no documento do imóvel que
        # estava POR ÚLTIMO: o Greatest doc×lançamento o resgata.
        Lancamento.objects.create(
            documento=documento_a,
            tipo=self.tipo_registro,
            data=DATA_CADASTRO_IMOVEIS,
            origem="",
        )
        self._fixar_atividade(imovel_a, INSTANTE_EDICAO)
        self.assertEqual(self._ordem_na_pagina(url), ["MA", "MB"])

    def test_aba_arquivados_mantem_mesma_ordenacao(self):
        imovel_a = self._criar_imovel("MA", arquivado=True)
        imovel_z = self._criar_imovel("MZ", arquivado=True)
        self._criar_documento_com_lancamento(imovel_a)
        self._criar_documento_com_lancamento(imovel_z)
        self._fixar_atividade(imovel_a, INSTANTE_BASE)
        self._fixar_atividade(imovel_z, INSTANTE_BASE + timedelta(minutes=1))
        url = reverse("tis_detail", args=[self.tis.id]) + "?status=arquivados"
        self.assertEqual(self._ordem_na_pagina(url), ["MZ", "MA"])

        Lancamento.objects.filter(documento__imovel=imovel_a).update(
            atualizado_em=INSTANTE_EDICAO
        )
        self.assertEqual(self._ordem_na_pagina(url), ["MA", "MZ"])

    def test_segregacao_usuario_nao_ve_imoveis_de_outro_usuario(self):
        imovel = self._criar_imovel("M300")
        self._criar_documento_com_lancamento(imovel)
        outro_usuario = User.objects.create_user(username="t375-fora", password="t375pass")
        self.client.login(username="t375-fora", password="t375pass")
        response = self.client.get(reverse("tis_detail", args=[self.tis.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["imoveis"]), [])


class FallbackLegadoTest(ListaImoveisTIBase):
    """Linhas pré-migração 0062: ``atualizado_em`` NULL → ``data_cadastro``.

    O cadastro dos imóveis vai para 2025 para não dominar o ``Greatest``:
    documento legado de 2026 precisa poder vencer o próprio cadastro.
    """

    def _criar_dois_imoveis_legados(self, matricula_antiga="M900", matricula_nova="M901"):
        imovel_antigo = self._criar_imovel(matricula_antiga)
        imovel_novo = self._criar_imovel(matricula_nova)
        Imovel.objects.filter(id__in=[imovel_antigo.id, imovel_novo.id]).update(
            data_cadastro=date(2025, 1, 1)
        )
        return imovel_antigo, imovel_novo

    def test_documento_legado_sem_atualizado_em_usa_data_cadastro(self):
        imovel_antigo, imovel_novo = self._criar_dois_imoveis_legados()
        self._criar_documento_legado(imovel_antigo, date(2026, 3, 1))
        self._criar_documento_legado(imovel_novo, date(2026, 6, 1))
        url = reverse("tis_detail", args=[self.tis.id])
        # Sem atualizado_em, vence o documento de data_cadastro mais recente.
        self.assertEqual(self._ordem_na_pagina(url), ["M901", "M900"])

    def test_caso_misto_lancamento_recente_vence_documento_legado(self):
        imovel_doc_legado, imovel_com_lancamento = self._criar_dois_imoveis_legados(
            "M910", "M911"
        )
        # M910: documento legado de 05/2026 (sem lançamento).
        self._criar_documento_legado(imovel_doc_legado, date(2026, 5, 1))
        # M911: documento legado de 02/2026 + lançamento recente (12:00).
        self._criar_documento_legado(imovel_com_lancamento, date(2026, 2, 1))
        lancamento = Lancamento.objects.create(
            documento=Documento.objects.get(imovel=imovel_com_lancamento),
            tipo=self.tipo_registro,
            data=date(2026, 2, 1),
            origem="",
        )
        Lancamento.objects.filter(id=lancamento.id).update(atualizado_em=INSTANTE_EDICAO)

        url = reverse("tis_detail", args=[self.tis.id])
        # Sem o Greatest doc×lançamento (só Coalesce por documento),
        # M910 venceria pela data do documento.
        self.assertEqual(self._ordem_na_pagina(url), ["M911", "M910"])
