"""Testes de regressão para a issue #210.

BUG: editar `Imovel.cartorio` (admin ou views públicas) deixava o
`Documento` principal no cartório antigo. Como a cadeia dominial resolve o
documento inicial por (tipo, número normalizado, cartório) — ver
`eh_documento_do_imovel` em `dominial/utils/ordenacao_cadeia.py` —, a
matrícula principal sumia da cadeia quando os dois ficavam em cartórios
diferentes.

Escopo reduzido: só a sincronização de cartório. Tipo/número do documento
principal continuam fora daqui (issue #212).
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from dominial.models import (
    Cartorios,
    Documento,
    DocumentoTipo,
    Imovel,
    Lancamento,
    LancamentoOrigem,
    LancamentoTipo,
    Pessoas,
    TIs,
)
from dominial.services.hierarquia_service import HierarquiaService
from dominial.services.imovel_documento_service import ImovelDocumentoService


class _Issue210Fixture:
    """Mixin de fixtures — não herda de TestCase para não ser coletado como
    um caso de teste vazio. Classes filhas devem herdar de
    (_Issue210Fixture, TestCase)."""

    def setUp(self):
        super().setUp()
        self.tis = TIs.objects.create(nome='TI 210', codigo='TI-210', etnia='Teste')
        self.cartorio_a = Cartorios.objects.create(
            nome='Cartório A', cns='CNS-210-A', cidade='Cidade A', estado='MS',
        )
        self.cartorio_b = Cartorios.objects.create(
            nome='Cartório B', cns='CNS-210-B', cidade='Cidade B', estado='SP',
        )
        self.proprietario = Pessoas.objects.create(nome='Proprietário 210')
        self.tipo_matricula = DocumentoTipo.objects.create(tipo='matricula')

        self.imovel = Imovel.objects.create(
            terra_indigena_id=self.tis,
            nome='Imóvel 210',
            proprietario=self.proprietario,
            matricula='14511',
            tipo_documento_principal='matricula',
            cartorio=self.cartorio_a,
        )
        self.documento = Documento.objects.create(
            imovel=self.imovel,
            tipo=self.tipo_matricula,
            numero='14511',
            data='2024-01-01',
            cartorio=self.cartorio_a,
            livro='1',
            folha='1',
        )


class AdminSincronizaCartorioTest(_Issue210Fixture, TestCase):
    """Cobrem o fluxo real via `admin:dominial_imovel_change` (TestClient)."""

    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create_superuser(
            username='admin210', password='admin210pass', email='admin210@example.com',
        )
        self.client.force_login(self.admin_user)
        self.url = reverse('admin:dominial_imovel_change', args=[self.imovel.id])

    def _dados_base(self, **extra):
        dados = {
            'matricula': self.imovel.matricula,
            'nome': self.imovel.nome,
            'tipo_documento_principal': self.imovel.tipo_documento_principal,
            'terra_indigena_id': self.tis.id,
            'proprietario': self.proprietario.id,
            'cartorio': self.cartorio_a.id,
            'observacoes': '',
        }
        dados.update(extra)
        return dados

    def test_admin_post_sincroniza_cartorio_do_documento_principal(self):
        response = self.client.post(self.url, self._dados_base(cartorio=self.cartorio_b.id))

        self.assertEqual(response.status_code, 302)
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_b.id)
        self.assertEqual(self.documento.cartorio_id, self.cartorio_b.id)

    def test_admin_bloqueia_candidatos_ambiguos(self):
        outro_cartorio = Cartorios.objects.create(
            nome='Cartório C', cns='CNS-210-C', cidade='Cidade C', estado='RJ',
        )
        documento_ambiguo = Documento.objects.create(
            imovel=self.imovel, tipo=self.tipo_matricula, numero='M14511',
            data='2024-01-01', cartorio=outro_cartorio, livro='1', folha='1',
        )

        response = self.client.post(self.url, self._dados_base(cartorio=self.cartorio_b.id))

        self.assertEqual(response.status_code, 200)
        conteudo = response.content.decode()
        self.assertIn(str(self.documento.id), conteudo)
        self.assertIn(str(documento_ambiguo.id), conteudo)
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_a.id)
        self.assertEqual(self.documento.cartorio_id, self.cartorio_a.id)

    def test_admin_bloqueia_colisao_de_identidade_no_destino(self):
        outro_imovel = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Outro imóvel', proprietario=self.proprietario,
            matricula='999999', tipo_documento_principal='matricula', cartorio=self.cartorio_b,
        )
        documento_conflitante = Documento.objects.create(
            imovel=outro_imovel, tipo=self.tipo_matricula, numero='14511',
            data='2024-01-01', cartorio=self.cartorio_b, livro='1', folha='1',
        )

        response = self.client.post(self.url, self._dados_base(cartorio=self.cartorio_b.id))

        self.assertEqual(response.status_code, 200)
        self.assertIn(str(documento_conflitante.id), response.content.decode())
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_a.id)
        self.assertEqual(self.documento.cartorio_id, self.cartorio_a.id)

    def test_admin_bloqueia_colisao_por_identidade_semantica_mesmo_com_fk_diferente(self):
        # `DocumentoTipo.tipo` não é único: um segundo registro com o mesmo
        # texto 'matricula' mas FK diferente deve colidir do mesmo jeito,
        # pois a cadeia resolve documentos por tipo__tipo, não pela FK.
        tipo_matricula_outra_fk = DocumentoTipo.objects.create(tipo='matricula')
        outro_imovel = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Outro imóvel', proprietario=self.proprietario,
            matricula='999999', tipo_documento_principal='matricula', cartorio=self.cartorio_b,
        )
        documento_conflitante = Documento.objects.create(
            imovel=outro_imovel, tipo=tipo_matricula_outra_fk, numero='14511',
            data='2024-01-01', cartorio=self.cartorio_b, livro='1', folha='1',
        )

        response = self.client.post(self.url, self._dados_base(cartorio=self.cartorio_b.id))

        self.assertEqual(response.status_code, 200)
        self.assertIn(str(documento_conflitante.id), response.content.decode())
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_a.id)
        self.assertEqual(self.documento.cartorio_id, self.cartorio_a.id)

    def test_admin_trata_validation_error_concorrente_sem_500(self):
        with patch.object(
            ImovelDocumentoService,
            'sincronizar_cartorio_documento_principal',
            side_effect=ValidationError(
                'Outra alteração concorrente já ocupou esta identidade no '
                'cartório destino. Tente novamente.'
            ),
        ):
            response = self.client.post(
                self.url, self._dados_base(cartorio=self.cartorio_b.id), follow=True,
            )

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context['messages']]
        self.assertTrue(any('concorrente' in m.lower() for m in mensagens))

    def test_admin_zero_candidatos_salva_com_aviso(self):
        self.documento.delete()

        response = self.client.post(
            self.url, self._dados_base(cartorio=self.cartorio_b.id), follow=True,
        )

        self.assertEqual(response.status_code, 200)
        mensagens = [str(m) for m in response.context['messages']]
        self.assertTrue(any('nenhum documento' in m.lower() for m in mensagens))
        self.imovel.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_b.id)

    def test_admin_bloqueia_edicao_combinada_de_cartorio_e_matricula(self):
        response = self.client.post(
            self.url,
            self._dados_base(cartorio=self.cartorio_b.id, matricula='99999'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'Troque o cartório separadamente da matrícula/tipo do documento',
            response.content.decode(),
        )
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_a.id)
        self.assertEqual(self.imovel.matricula, '14511')
        self.assertEqual(self.documento.cartorio_id, self.cartorio_a.id)


class ImovelEditarSincronizaTest(_Issue210Fixture, TestCase):
    """Endpoint público `imovel_editar` (`imovel_form`) também sincroniza."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='user210', password='user210pass')
        self.client.force_login(self.user)

    def test_imovel_editar_sincroniza_cartorio_do_documento_principal(self):
        url = reverse('imovel_editar', kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel.id})

        response = self.client.post(url, {
            'nome': self.imovel.nome,
            'matricula': self.imovel.matricula,
            'tipo_documento_principal': self.imovel.tipo_documento_principal,
            'cartorio': self.cartorio_b.id,
            'proprietario_nome': self.proprietario.nome,
            'estado': self.cartorio_b.estado,
            'cidade': self.cartorio_b.cidade,
        })

        self.assertEqual(response.status_code, 302)
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_b.id)
        self.assertEqual(self.documento.cartorio_id, self.cartorio_b.id)


class ImovelDetailSincronizaTest(_Issue210Fixture, TestCase):
    """`imovel_detail` é o segundo writer que chama `ImovelForm.save(commit=True)`
    (além de `imovel_editar`) e também precisa sincronizar o cartório."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='user210b', password='user210bpass')
        self.client.force_login(self.user)

    def test_imovel_detail_sincroniza_cartorio_do_documento_principal(self):
        url = reverse('imovel_detail', kwargs={'tis_id': self.tis.id, 'imovel_id': self.imovel.id})

        response = self.client.post(url, {
            'nome': self.imovel.nome,
            'matricula': self.imovel.matricula,
            'tipo_documento_principal': self.imovel.tipo_documento_principal,
            'cartorio': self.cartorio_b.id,
            'proprietario_nome': self.proprietario.nome,
            'estado': self.cartorio_b.estado,
            'cidade': self.cartorio_b.cidade,
        })

        self.assertEqual(response.status_code, 302)
        self.imovel.refresh_from_db()
        self.documento.refresh_from_db()
        self.assertEqual(self.imovel.cartorio_id, self.cartorio_b.id)
        self.assertEqual(self.documento.cartorio_id, self.cartorio_b.id)


class CadeiaAposSincronizacaoTest(_Issue210Fixture, TestCase):
    """Regressão de campo: a matrícula principal precisa continuar na cadeia
    depois da troca de cartório (a causa raiz do bug #210)."""

    def test_cadeia_reconhece_o_documento_principal_apos_sincronizacao(self):
        self.imovel.cartorio = self.cartorio_b
        self.imovel.save()
        ImovelDocumentoService.sincronizar_cartorio_documento_principal(self.imovel)

        self.documento.refresh_from_db()
        self.imovel.refresh_from_db()
        self.assertEqual(self.documento.cartorio_id, self.imovel.cartorio_id)

        tronco = HierarquiaService.obter_tronco_principal(self.imovel)
        self.assertTrue(tronco)
        self.assertEqual(tronco[0].id, self.documento.id)

    def test_cache_desabilitado_reflete_novo_cartorio_imediatamente(self):
        tronco_antes = HierarquiaService.obter_tronco_principal(self.imovel)
        self.assertEqual(tronco_antes[0].cartorio_id, self.cartorio_a.id)

        self.imovel.cartorio = self.cartorio_b
        self.imovel.save()
        ImovelDocumentoService.sincronizar_cartorio_documento_principal(self.imovel)

        tronco_depois = HierarquiaService.obter_tronco_principal(self.imovel)
        self.assertEqual(tronco_depois[0].cartorio_id, self.cartorio_b.id)


class AuditoriaDivergenciaCartorioTest(_Issue210Fixture, TestCase):
    """O comando de auditoria é somente leitura e classifica os 3 estados."""

    def test_auditoria_e_read_only_e_classifica_os_tres_estados(self):
        # Divergente: força a divergência direto no banco (sem passar pelo
        # service), simulando o estado de produção antes do hotfix.
        Imovel.objects.filter(pk=self.imovel.pk).update(cartorio=self.cartorio_b)

        imovel_ausente = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Sem documento', proprietario=self.proprietario,
            matricula='777', tipo_documento_principal='matricula', cartorio=self.cartorio_a,
        )

        imovel_ambiguo = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Ambíguo', proprietario=self.proprietario,
            matricula='888', tipo_documento_principal='matricula', cartorio=self.cartorio_a,
        )
        Documento.objects.create(
            imovel=imovel_ambiguo, tipo=self.tipo_matricula, numero='888',
            data='2024-01-01', cartorio=self.cartorio_a, livro='1', folha='1',
        )
        Documento.objects.create(
            imovel=imovel_ambiguo, tipo=self.tipo_matricula, numero='888',
            data='2024-01-01', cartorio=self.cartorio_b, livro='1', folha='1',
        )

        saida = StringIO()
        with CaptureQueriesContext(connection) as queries:
            call_command('auditar_divergencia_cartorio_imovel_documento', stdout=saida)

        for query in queries.captured_queries:
            sql = query['sql'].upper()
            self.assertFalse(sql.startswith('INSERT'), sql)
            self.assertFalse(sql.startswith('UPDATE'), sql)
            self.assertFalse(sql.startswith('DELETE'), sql)

        texto = saida.getvalue()
        self.assertIn(f'Imóvel {self.imovel.id}', texto)
        self.assertIn(f'Imóvel {imovel_ausente.id}', texto)
        self.assertIn(f'Imóvel {imovel_ambiguo.id}', texto)
        self.assertIn('1 divergente(s)', texto)
        self.assertIn('1 ausente(s)', texto)
        self.assertIn('1 ambíguo(s)', texto)


class LancamentoOrigemMigracaoTest(_Issue210Fixture, TestCase):
    """`LancamentoOrigem.cartorio` migra quando a identidade é exata;
    referência textual legada e ambígua bloqueia a troca."""

    def setUp(self):
        super().setUp()
        self.outro_imovel = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Descendente', proprietario=self.proprietario,
            matricula='222', tipo_documento_principal='matricula', cartorio=self.cartorio_a,
        )
        self.documento_descendente = Documento.objects.create(
            imovel=self.outro_imovel, tipo=self.tipo_matricula, numero='222',
            data='2024-01-01', cartorio=self.cartorio_a, livro='1', folha='1',
        )
        self.tipo_inicio = LancamentoTipo.objects.create(tipo='inicio_matricula')

    def _criar_lancamento_sem_signal(self, **kwargs):
        # bulk_create não dispara o signal `processar_origens_automaticas_signal`
        # (dominial/signals.py), que criaria a origem estruturada automaticamente
        # a partir do texto e invalidaria os cenários abaixo.
        Lancamento.objects.bulk_create([Lancamento(**kwargs)])
        return Lancamento.objects.get(documento=kwargs['documento'], origem=kwargs['origem'])

    def test_lancamento_origem_migra_quando_identidade_exata(self):
        lancamento = self._criar_lancamento_sem_signal(
            documento=self.documento_descendente, tipo=self.tipo_inicio,
            data='2024-01-01', origem='M14511',
        )
        origem_estruturada = LancamentoOrigem.objects.create(
            lancamento=lancamento, indice_origem=0, tipo_documento='matricula',
            numero='14511', cartorio=self.cartorio_a,
        )

        self.imovel.cartorio = self.cartorio_b
        self.imovel.save()
        ImovelDocumentoService.sincronizar_cartorio_documento_principal(self.imovel)

        origem_estruturada.refresh_from_db()
        self.assertEqual(origem_estruturada.cartorio_id, self.cartorio_b.id)

    def test_origem_textual_legada_e_ambigua_bloqueia_a_troca(self):
        self._criar_lancamento_sem_signal(
            documento=self.documento_descendente, tipo=self.tipo_inicio,
            data='2024-01-01', origem='M14511', cartorio_origem=self.cartorio_a,
        )

        self.imovel.cartorio = self.cartorio_b
        self.imovel.save()

        with self.assertRaises(ValidationError):
            ImovelDocumentoService.sincronizar_cartorio_documento_principal(self.imovel)

        self.documento.refresh_from_db()
        self.assertEqual(self.documento.cartorio_id, self.cartorio_a.id)

    def test_origem_sem_prefixo_m_e_detectada_pelo_prefiltro_normalizado(self):
        """Regressão do prefiltro (N-1): filtrar por `imovel.matricula` crua
        ("M99887") não bate com uma origem textual sem o prefixo ("99887"),
        deixando o lançamento ambíguo passar despercebido. O prefiltro deve
        usar o número normalizado ("99887"), que é substring de qualquer
        apresentação textual dessa identidade."""
        imovel_m = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Imóvel com prefixo M',
            proprietario=self.proprietario, matricula='M99887',
            tipo_documento_principal='matricula', cartorio=self.cartorio_a,
        )
        documento_m = Documento.objects.create(
            imovel=imovel_m, tipo=self.tipo_matricula, numero='M99887',
            data='2024-01-01', cartorio=self.cartorio_a, livro='1', folha='1',
        )
        self._criar_lancamento_sem_signal(
            documento=self.documento_descendente, tipo=self.tipo_inicio,
            data='2024-01-01', origem='99887', cartorio_origem=self.cartorio_a,
        )

        imovel_m.cartorio = self.cartorio_b
        imovel_m.save()

        with self.assertRaises(ValidationError):
            ImovelDocumentoService.sincronizar_cartorio_documento_principal(imovel_m)

        documento_m.refresh_from_db()
        self.assertEqual(documento_m.cartorio_id, self.cartorio_a.id)

    def test_origem_com_espaco_apos_prefixo_m_e_detectada(self):
        """Mesma regressão, variante com espaço entre o prefixo e o número
        ("M 99887")."""
        imovel_m = Imovel.objects.create(
            terra_indigena_id=self.tis, nome='Imóvel com prefixo M e espaço',
            proprietario=self.proprietario, matricula='M99887',
            tipo_documento_principal='matricula', cartorio=self.cartorio_a,
        )
        documento_m = Documento.objects.create(
            imovel=imovel_m, tipo=self.tipo_matricula, numero='M99887',
            data='2024-01-01', cartorio=self.cartorio_a, livro='1', folha='1',
        )
        self._criar_lancamento_sem_signal(
            documento=self.documento_descendente, tipo=self.tipo_inicio,
            data='2024-01-01', origem='M 99887', cartorio_origem=self.cartorio_a,
        )

        imovel_m.cartorio = self.cartorio_b
        imovel_m.save()

        with self.assertRaises(ValidationError):
            ImovelDocumentoService.sincronizar_cartorio_documento_principal(imovel_m)

        documento_m.refresh_from_db()
        self.assertEqual(documento_m.cartorio_id, self.cartorio_a.id)

    def test_documento_ja_alinhado_ao_destino_nao_e_bloqueado_por_origem_legada(self):
        # Direção real do incidente: o documento já foi corrigido manualmente
        # para o cartório destino e o imóvel está sendo atualizado para
        # acompanhar. Não há migração a fazer, então uma origem textual
        # legada que referencia essa identidade (já correta) não deve
        # bloquear o save.
        self.documento.cartorio = self.cartorio_b
        self.documento.save(update_fields=['cartorio'])

        self._criar_lancamento_sem_signal(
            documento=self.documento_descendente, tipo=self.tipo_inicio,
            data='2024-01-01', origem='M14511', cartorio_origem=self.cartorio_b,
        )

        self.imovel.cartorio = self.cartorio_b
        self.imovel.save()

        ImovelDocumentoService.sincronizar_cartorio_documento_principal(self.imovel)

        self.documento.refresh_from_db()
        self.assertEqual(self.documento.cartorio_id, self.cartorio_b.id)
