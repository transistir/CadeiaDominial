"""Pendências e avisos da revisão — parte 3 de 3 do corpo de
``PendenciasEAvisosTest`` (``ia_ocr/tests/test_revisao.py``,
Etapa 5, grupo 3 do plano de 400 linhas). Classe SIMPLES (sem
``TestCase``): o discovery do Django não a coleta; quem coleta é a
fachada em ``test_revisao_pendencias.py``. Corpos verbatim.
"""

from copy import deepcopy
from django.utils import timezone

from dominial.models import Cartorios, Pessoas
from ia_ocr.models import ExtracaoSugerida

from ia_ocr.revisao import (
    RevisaoInvalidada, _tipos_efetivos, aplicar_linha, avisos, dados_revisados,
    garantir_placeholders_obrigatorios, pendencias,
)
from .payloads_extracao import payload_averbacao, payload_registro


class PendenciasEAvisosTestParte3:
    def test_mudar_tipo_cria_linhas_exigidas_e_remove_as_do_antigo(self):
        # (b) mudar tipo cria as linhas exigidas do tipo novo e remove as do antigo (#322 rodada 7)
        payload = payload_averbacao(self.job.job_id)
        linhas = self._persistir(payload)
        self.assertEqual(pendencias(self.extracao), [])

        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='registro')
        tipo.save()
        novas = garantir_placeholders_obrigatorios(self.extracao)
        # #324 rodada 2: o tipo que exige o cartório de origem leva a origem
        # inteira (cartório + tipo/número/livro/folha/data), não só o cartório.
        self.assertCountEqual(
            [campo.chave for campo in novas],
            [
                '/acts/0/titulo', '/acts/0/origem/cartorio',
                '/acts/0/origem/tipo_documento', '/acts/0/origem/numero',
                '/acts/0/origem/livro', '/acts/0/origem/folha',
                '/acts/0/origem/data',
            ],
        )
        pends = pendencias(self.extracao)
        self.assertIn(self._obrigatorio('/acts/0/titulo'), pends)
        self.assertIn(self._obrigatorio('/acts/0/origem/cartorio'), pends)
        self.assertNotIn(self._obrigatorio('/acts/0/descricao'), pends)

    def test_rotulo_vence_sugestao_quando_nao_ha_edicao(self):
        # (c) rótulo vence sugestão quando não há edição (#322 rodada 7)
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['rotulo'] = {
            'raw': 'Av-1', 'normalized': 'Av-1', 'confianca': 0.95,
            'requer_revisao': False,
        }
        linhas = self._persistir(payload)
        tipos_por_ato, _ = _tipos_efetivos(linhas, [linhas['/acts/0']])
        self.assertEqual(tipos_por_ato['/acts/0'], 'averbacao')

    def test_sugestao_vence_quando_nao_ha_rotulo_nem_edicao(self):
        # (d) sugestão vence quando não há rótulo nem edição (#322 rodada 7)
        payload = payload_averbacao(self.job.job_id)
        linhas = self._persistir(payload)
        self._sem_rotulo()
        linhas_atualizadas = {c.chave: c for c in self.extracao.campos.all()}
        tipos_por_ato, _ = _tipos_efetivos(
            linhas_atualizadas, [linhas_atualizadas['/acts/0']],
        )
        self.assertEqual(tipos_por_ato['/acts/0'], 'averbacao')

    def test_tipo_sugerido_vazio_com_rotulo_conclui(self):
        # (e) tipo_sugerido vazio + rótulo → conclui (#322 rodada 7)
        payload = self._registro_completo()
        linhas = self._persistir(payload)
        tipo = linhas['/acts/0/tipo_sugerido']
        tipo.normalized = None
        tipo.raw = None
        tipo.valor_final = None
        tipo.save()
        self.assertEqual(pendencias(self.extracao), [])
        self.job.status = 'revisado'
        self.job.save()
        self.extracao.finalizada_em = timezone.now()
        dados = dados_revisados(self.extracao)
        self.assertEqual(len(dados.atos), 1)

    def test_tipo_sugerido_vazio_sem_rotulo_continua_bloqueando(self):
        # (f) tipo_sugerido vazio + sem rótulo → continua bloqueando (#322 rodada 7)
        payload = self._registro_completo()
        linhas = self._persistir(payload)
        self._sem_rotulo()
        tipo = linhas['/acts/0/tipo_sugerido']
        tipo.normalized = None
        tipo.raw = None
        tipo.valor_final = None
        tipo.save()
        self.assertIn(
            self._obrigatorio('/acts/0/tipo_sugerido'),
            pendencias(self.extracao),
        )
        self.job.status = 'revisado'
        self.job.save()
        self.extracao.finalizada_em = timezone.now()
        with self.assertRaises(RevisaoInvalidada):
            dados_revisados(self.extracao)

    def test_tipo_limpo_no_formulario_bloqueia_e_nao_importa(self):
        # P2-1 (#322/PR #327): limpar o tipo no <select> grava
        # ``valor_final=''`` — decisão de "sem tipo", não ausência de
        # decisão. Sem isto o '' caía no rótulo/sugestão e o tipo apagado
        # era importado sem aviso; a pendência de ``tipo_sugerido`` volta
        # a bloquear (o formulário é a fonte de verdade).
        payload = self._registro_completo()
        linhas = self._persistir(payload)
        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='')
        tipo.save()
        self.assertEqual(tipo.valor_final, '')
        self.assertEqual(tipo.status_revisao, 'editado')
        self.assertIn(
            self._obrigatorio('/acts/0/tipo_sugerido'),
            pendencias(self.extracao),
        )
        self.job.status = 'revisado'
        self.job.save()
        self.extracao.finalizada_em = timezone.now()
        with self.assertRaises(RevisaoInvalidada):
            dados_revisados(self.extracao)

    def test_requer_forma_e_observacao_sao_aviso_nao_bloqueio(self):
        self.averbacao.requer_forma = True
        self.averbacao.requer_observacao = True
        self.averbacao.save()
        payload = payload_averbacao(self.job.job_id)
        self._persistir(payload)
        esperados = [
            {'chave': '/acts/0/forma', 'motivo': 'requer_forma',
             'bloqueante': False},
            {'chave': '/acts/0/observacoes', 'motivo': 'requer_observacao',
             'bloqueante': False},
        ]
        self.assertCountEqual(avisos(self.extracao), esperados)
        self.assertEqual(pendencias(self.extracao), [])

        for flag, caminho in (
            ('requer_transmissao', 'partes'),
            ('requer_livro_origem', 'origem/livro'),
            ('requer_folha_origem', 'origem/folha'),
            ('requer_data_origem', 'origem/data'),
        ):
            setattr(self.averbacao, flag, True)
            esperados.append({
                'chave': f'/acts/0/{caminho}', 'motivo': flag,
                'bloqueante': False,
            })
        # #328 rodada 2: a flag segue no tipo e fica ligada JUNTO das
        # outras, mas ``detalhes`` não entra em ``esperados`` — devolver a
        # tupla ``('requer_detalhes', 'detalhes')`` a ``avisos()`` quebra
        # o teste abaixo.
        self.averbacao.requer_detalhes = True
        self.averbacao.save()
        self.assertCountEqual(avisos(self.extracao), esperados)
        self.assertEqual(pendencias(self.extracao), [])

        ato = payload['acts'][0]
        for campo in ('forma', 'observacoes'):
            ato[campo] = ato['descricao'].copy()
        ato['origem'] = {
            campo: payload['document'][campo].copy()
            for campo in ('livro', 'folha', 'data')
        }
        ato['partes'] = payload_registro(self.job.job_id)['acts'][0]['partes']
        linhas = self._persistir(payload)
        self.assertEqual(avisos(self.extracao), [])
        self.assertEqual(pendencias(self.extracao), [])

        for papel in ('transmitente', 'adquirente'):
            with self.subTest(papel=papel):
                partes = self.extracao.campos.filter(
                    tipo_valor='parte', normalized=papel,
                )
                partes.update(status_revisao='descartado')
                self.assertEqual(avisos(self.extracao), [{
                    'chave': '/acts/0/partes', 'motivo': 'requer_transmissao',
                    'bloqueante': False,
                }])
                self.assertEqual(pendencias(self.extracao), [])
                partes.update(status_revisao='sugerido')

        forma = linhas['/acts/0/forma']
        forma.status_revisao = 'descartado'
        forma.save()
        self.assertEqual(avisos(self.extracao), [esperados[0]])
        # P1-2 (rodada 7): quem decide o tipo é o rótulo — 'Av-1' → 'R-1'.
        rotulo = linhas['/acts/0/rotulo']
        aplicar_linha(rotulo, incluir=True, valor='R-1')
        rotulo.save()
        self.assertEqual(avisos(self.extracao), [])

    def test_ato_descartado_nao_gera_pendencias_filhas(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['data']['normalized'] = None
        payload['acts'][0]['area']['unidade'] = 'm2'
        payload['acts'].append(payload_averbacao(self.job.job_id)['acts'][0])
        linhas = self._persistir(payload)
        parte = linhas['/acts/0/partes/0']
        parte.criar_novo = False
        parte.requer_revisao = True
        parte.motivos_revisao = ['match_invalidado']
        parte.save()
        nome = linhas['/acts/0/partes/0/nome']
        nome.requer_revisao = True
        nome.save()
        for motivo in ('revisao_pendente', 'escolha_pendente', 'match_invalidado'):
            self.assertIn({
                'chave': parte.chave, 'motivo': motivo, 'bloqueante': True,
            }, pendencias(self.extracao))
        self.assertIn({
            'chave': '/acts/0/area', 'motivo': 'unidade_area', 'bloqueante': True,
        }, pendencias(self.extracao))

        parte.status_revisao = 'descartado'
        parte.save()
        self.assertFalse(any(
            item['chave'].startswith('/acts/0/partes/0')
            for item in pendencias(self.extracao)
        ))
        ato = linhas['/acts/0']
        ato.status_revisao = 'descartado'
        ato.save()
        self.registro.requer_forma = True
        self.registro.save()
        self.assertEqual(pendencias(self.extracao), [])
        self.assertEqual(avisos(self.extracao), [])

    def test_decisao_perdida_vira_pendencia(self):
        for chave, atributo, registro in (
            ('/acts/0/partes/0', 'pessoa_escolhida',
             Pessoas.objects.create(nome='Pessoa sintética escolhida')),
            ('/document/cartorio', 'cartorio_escolhido',
             Cartorios.objects.create(
                 nome='Cartório sintético escolhido', cns='CNS-escolhido',
                 estado='SP',
             )),
        ):
            with self.subTest(chave=chave):
                linha = self._persistir(self._registro_completo())[chave]
                linha.criar_novo = False
                linha.save()
                self.assertEqual(pendencias(self.extracao), [{
                    'chave': chave, 'motivo': 'escolha_pendente',
                    'bloqueante': True,
                }])
                setattr(linha, atributo, registro)
                linha.status_revisao = 'aceito'
                linha.save()
                # Simula remoção concorrente após as linhas serem carregadas.
                extracao = ExtracaoSugerida.objects.prefetch_related('campos').get(
                    pk=self.extracao.pk
                )
                self.assertEqual(pendencias(extracao), [])
                registro.delete()
                self.assertEqual(pendencias(extracao), [{
                    'chave': chave, 'motivo': 'decisao_perdida',
                    'bloqueante': True,
                }])

    def test_conjuge_sem_escolha_nao_gera_pendencia(self):
        payload = self._registro_completo()
        conjuge = deepcopy(payload['acts'][0]['partes'][0])
        conjuge['papel'] = 'conjuge'
        payload['acts'][0]['partes'].append(conjuge)
        linhas = self._persistir(payload)
        chave = '/acts/0/partes/3'
        campo = linhas[chave]
        campo.criar_novo = False
        campo.pessoa_escolhida = None
        campo.save()

        self.assertFalse(any(
            item['chave'] == chave and item['motivo'] == 'escolha_pendente'
            for item in pendencias(self.extracao)
        ))

    def test_transmitente_sem_escolha_gera_pendencia(self):
        linhas = self._persistir(self._registro_completo())
        chave = '/acts/0/partes/0'
        campo = linhas[chave]
        campo.criar_novo = False
        campo.pessoa_escolhida = None
        campo.save()

        self.assertIn({
            'chave': chave, 'motivo': 'escolha_pendente', 'bloqueante': True,
        }, pendencias(self.extracao))

    def test_nenhum_ato_incluido_bloqueia(self):
        for sem_atos in (False, True):
            with self.subTest(sem_atos=sem_atos):
                payload = payload_registro(self.job.job_id)
                if sem_atos:
                    payload['acts'] = []
                    payload['document'] = {}
                self._persistir(payload)
                self.extracao.campos.filter(tipo_valor='ato').update(
                    status_revisao='descartado'
                )
                self.assertEqual(pendencias(self.extracao), [{
                    'chave': '/acts', 'motivo': 'nenhum_ato', 'bloqueante': True,
                }])
                self.assertEqual(avisos(self.extracao), [])
