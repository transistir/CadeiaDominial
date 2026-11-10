"""Testes de integração rótulos → importação (I-11b / #322, rodadas 3–5).

O contrato da gravação (#322 rodada 3): o número gravado é o COMPOSTO
canônico do V1 — ``'R-5'`` na matrícula grava ``'R5 {documento.numero}'``,
o MESMO texto que o fluxo manual compõe (decisão de produto do
orquestrador); o rótulo PREVALECE na decisão do tipo sobre o
``tipo_sugerido`` divergente (divergência vira aviso), e o tipo vazio cai
no tipo do prefixo. A duplicata compara os dois lados normalizados
(formato manual, legado do importador e número puro) e exige rótulos
compatíveis: R-5 × AV5 M237 não colidem. Rótulo não reconhecido mantém o
comportamento anterior (#322): não inventa número nem tipo — o destino do
bucket deles é decisão da UI (#321).

Rodada 4 (review Codex): o rótulo é lido pelo EFETIVO (``normalized`` ou,
sem ele, o ``raw`` da folha — a mesma leitura do ``classificar_atos``);
rótulo de MATRÍCULA não gera número de ato (aviso, nunca exceção); a
prévia (``resumo``) devolve o tipo que a gravação usará, com a divergência
no ``aviso`` do item; meia-risca/travessão valem como hífen.

Rodada 5 (review Codex): o rótulo CORRIGIDO pelo revisor (``valor_final``)
vence na leitura do efetivo — vazio (campo limpo) não decide nada; sob
rótulo de MATRÍCULA, o número de ato REVISADO que é rótulo R/Av válido (ou
número puro já sem prefixo) é preservado e composto — só a referência da
matrícula continua descartada.

Rodada 6 (review Codex, P1): linha DESCARTADA não decide. ``aplicar_linha``
com ``incluir=False`` preserva o ``valor_final`` da edição; sem olhar o
``status_revisao``, a edição descartada vencia e a importação criava o
lançamento que o usuário tinha descartado. O descarte PULA o candidato
(folha → linha estrutural), nunca volta ``None`` no meio.

A revisão vigente EXIGE ``tipo_sugerido`` preenchido por ato (pendência
bloqueante da I-5), então ``importar`` não alcança o estado ``tipo`` vazio
num fluxo limpo: os testes do fallback do rótulo exercitam a fronteira da
gravação (``_importar_ato``, o mesmo caminho que ``importar`` chama, com o
mesmo rótulo analisado e as mesmas linhas) com o ``AtoRevisado.tipo``
esvaziado — o estado que o fallback defende (re-extração, estado antigo).
"""

from dataclasses import replace
from datetime import date

from django.test import TestCase

from dominial.managers import documentos_for_user
from dominial.models import Lancamento, LancamentoTipo
from ia_ocr import importacao as modulo_importacao
from ia_ocr import revisao
from ia_ocr.importacao import ImportacaoInvalida, importar, resumo
from ia_ocr.models import OcrJob
from ia_ocr.revisao import RevisaoInvalidada
from ia_ocr.rotulos import analisar_rotulo

from .payloads_extracao import payload_registro
from .test_importacao import ImportacaoFixture

DATA_DO_ATO = date(2020, 2, 15)
TEXTO_SEM_ROTULO = 'O imóvel rural denominado Sítio Boa Vista'


class RotulosImportacaoTest(ImportacaoFixture, TestCase):
    """#322 na gravação: número sem prefixo, tipo pelo rótulo na falta."""

    def setUp(self):
        super().setUp()
        self.tipo_averbacao = LancamentoTipo.objects.create(tipo='averbacao')

    def _payload(self, rotulo='R-5', tipo='registro', numero=None):
        """Payload do registro com o rótulo/tipo/número da cena (#322)."""
        payload = payload_registro(self.job.job_id)
        ato = payload['acts'][0]
        ato['rotulo'] = self._campo(rotulo, 'R-1/42.718')
        ato['tipo_sugerido'] = self._campo(tipo, 'R-1/42.718')
        if numero is None:
            ato.pop('numero_lancamento', None)
        else:
            ato['numero_lancamento'] = self._campo(numero, 'R-1/42.718')
        return payload

    def _importar_ato_com_tipo(self, extracao, tipo=''):
        """Grava o ato com o ``AtoRevisado.tipo`` dado (fallback do rótulo).

        Mesmo ``_importar_ato`` que ``importar`` chama, com o rótulo
        analisado uma vez e as linhas da extração — só o estado do tipo
        muda (vazio/valor), porque a pendência da revisão impede
        ``importar`` de chegar a ele (ver
        ``test_tipo_sugerido_vazio_nao_chega_a_``).
        """
        dados = revisao.dados_revisados(extracao)
        (marcado,) = dados.atos
        linhas = modulo_importacao._linhas_por_chave(extracao)
        rotulo = analisar_rotulo(modulo_importacao._rotulo('/acts/0', linhas))
        return modulo_importacao._importar_ato(
            replace(marcado, tipo=tipo), rotulo, self.documento, self.imovel,
            self.usuario, self.job, linhas, {}, documentos_for_user(self.usuario),
            set(), set(),
        )

    def test_numero_com_prefixo_grava_no_formato_canonico(self):
        # 'R-5' no payload grava 'R5 {sigla}' — o formato canônico do V1,
        # o MESMO texto do fluxo manual (P1-1, decisão de produto da
        # rodada 3; sete consumidores ordenam por '^(R|AV)\d+').
        extracao = self._extracao(self._payload(numero='R-5'))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )
        self.assertEqual(lancamento.tipo, self.tipo_registro)

    def test_averbacao_grava_no_formato_canonico(self):
        # 'Av: 2-237' grava 'AV2 {sigla}' — prefixo AV, não Av.
        extracao = self._extracao(self._payload(
            rotulo='Av: 2-237', tipo='averbacao', numero='Av: 2-237',
        ))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_averbacao)
        self.assertEqual(
            lancamento.numero_lancamento, f'AV2 {self.documento.numero}',
        )

    def test_tipo_sugerido_vazio_cai_no_tipo_do_rotulo(self):
        # Sem tipo, o prefixo do rótulo decide: 'R-5' grava tipo registro —
        # nunca 'tipo_inexistente' (não cai no erro que o campo vazio dava
        # antes de #322).
        extracao = self._extracao(self._payload(numero='R-5'))

        resposta, erros = self._importar_ato_com_tipo(extracao)

        self.assertEqual(erros.itens, [])
        self.assertEqual(resposta['status'], 'criado')
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )

    def test_averbacao_sem_tipo_sugerido_cai_no_tipo_do_rotulo(self):
        # 'Av-7' sem tipo grava AVERBAÇÃO — mesmo que o payload trouxesse
        # 'registro' no tipo_sugerido: com o tipo vazio, quem decide é o
        # prefixo do rótulo (#322).
        extracao = self._extracao(self._payload(
            rotulo='Av-7', tipo='registro', numero='Av-7',
        ))

        resposta, erros = self._importar_ato_com_tipo(extracao)

        self.assertEqual(erros.itens, [])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_averbacao)
        self.assertEqual(
            lancamento.numero_lancamento, f'AV7 {self.documento.numero}',
        )

    def test_tipo_sugerido_divergente_o_rotulo_prevalece_com_aviso(self):
        # P2-3: rótulo 'R-5' com tipo_sugerido 'averbacao' grava REGISTRO
        # (o rótulo prevalece, como no classificar_atos) e a divergência
        # vira AVISO na resposta — nunca bloqueio.
        extracao = self._extracao(self._payload(tipo='averbacao', numero='R-5'))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )
        (linha,) = resultado['linhas']
        (aviso,) = linha['avisos']
        self.assertIn('registro', aviso)
        self.assertIn('averbacao', aviso)

    def test_rotulo_apenas_no_raw_define_o_tipo_como_o_classificar(self):
        # P1 (rodada 4): no payload real o rótulo vem com ``normalized=None``
        # e o carimbo no ``raw`` — sem o fallback a gravação não via o rótulo
        # e o tipo_sugerido divergente decidia sozinho, o contrário do
        # ``classificar_atos`` (que lê ``normalized or raw``).
        payload = self._payload(rotulo='R-5', tipo='averbacao', numero='R-5')
        payload['acts'][0]['rotulo']['normalized'] = None
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )
        (linha,) = resultado['linhas']
        (aviso,) = linha['avisos']
        self.assertIn('registro', aviso)
        self.assertIn('averbacao', aviso)

    def test_rotulo_apenas_no_raw_bloqueia_a_duplicata_do_tipo_certo(self):
        # P1 (rodada 4), cenário do review: rótulo 'R-5' só no raw com
        # tipo_sugerido divergente — a gravação seguia o tipo sugerido
        # ('averbacao'), gravava 'AV5 {sigla}' e não casava com o 'R-5' já
        # existente; com o rótulo efetivo o tipo é registro e a duplicata
        # volta a ser bloqueada (a base já bloqueava).
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_registro,
            numero_lancamento='R-5',
            data=DATA_DO_ATO,
        )
        payload = self._payload(rotulo='R-5', tipo='averbacao', numero='R-5')
        payload['acts'][0]['rotulo']['normalized'] = None
        extracao = self._extracao(payload)

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_rotulo_corrigido_pelo_revisor_define_o_tipo_da_duplicata(self):
        # P1 (rodada 5): raw='R-5', normalized=None e o revisor CORRIGIU o
        # rótulo para 'Av-5' — sem o ``valor_final`` na precedência, a
        # gravação seguia o carimbo do OCR ('R-5'), gravava registro e a
        # duplicata da averbação já na base passava (cenário do review).
        self.documento.numero = 'M237'
        self.documento.save(update_fields=['numero'])
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento='AV5 M237',
            data=DATA_DO_ATO,
        )
        payload = self._payload(rotulo='R-5', tipo='averbacao', numero='Av-5')
        payload['acts'][0]['rotulo']['normalized'] = None
        extracao = self._extracao(payload)
        campo = extracao.campos.get(chave='/acts/0/rotulo')
        revisao.aplicar_linha(
            campo, incluir=True, valor='Av-5', usuario=self.usuario,
        )
        campo.save()

        (ato,) = resumo(extracao)['atos']
        self.assertEqual(ato['tipo'], 'averbacao')
        self.assertTrue(ato['duplicado'])
        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_rotulo_com_valor_final_vazio_cai_no_normalized_e_no_raw(self):
        # P1 (rodada 5): ``valor_final`` vazio (o revisor LIMPOU o campo —
        # ``aplicar_linha`` grava '') não decide nada: a leitura cai no
        # ``normalized``/``raw`` como na rodada 4. Sem a guarda de vazio,
        # '' venceria o 'R-5' do raw e o rótulo desapareceria.
        payload = self._payload(rotulo='R-5', tipo='averbacao', numero='R-5')
        payload['acts'][0]['rotulo']['normalized'] = None
        extracao = self._extracao(payload)
        campo = extracao.campos.get(chave='/acts/0/rotulo')
        revisao.aplicar_linha(
            campo, incluir=True, valor='', usuario=self.usuario,
        )
        campo.save()
        self.assertEqual(campo.valor_final, '')

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )

    def test_rotulo_editado_e_descartado_nao_decide_a_duplicata(self):
        # P1 (rodada 6), o cenário do Codex: editar a FOLHA do rótulo para
        # 'Av-5' e depois DESCARTAR a linha — ``aplicar_linha`` preserva o
        # ``valor_final`` da edição e só marca ``descartado``. Sem ignorar
        # a linha descartada, a edição vencia: a prévia dizia averbação,
        # não via a duplicata e a importação criava 'AV5 M237'. O correto
        # é valer o carimbo do OCR na linha estrutural ('R-5'): registro,
        # duplicata do 'R5 M237' já gravado e importação recusada.
        self.documento.numero = 'M237'
        self.documento.save(update_fields=['numero'])
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_registro,
            numero_lancamento='R5 M237',
            data=DATA_DO_ATO,
        )
        extracao = self._extracao(self._payload(numero='R-5'))
        campo = extracao.campos.get(chave='/acts/0/rotulo')
        revisao.aplicar_linha(
            campo, incluir=True, valor='Av-5', usuario=self.usuario,
        )
        revisao.aplicar_linha(campo, incluir=False, usuario=self.usuario)
        campo.save()
        self.assertEqual(campo.status_revisao, 'descartado')
        self.assertEqual(campo.valor_final, 'Av-5')

        (ato,) = resumo(extracao)['atos']
        self.assertEqual(ato['tipo'], 'registro')
        self.assertTrue(ato['duplicado'])
        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_rotulo_editado_e_mantido_continua_decidindo(self):
        # Rodada 6, o outro lado: o MESMO cenário com a folha ATIVA — o
        # ``valor_final`` da rodada 5 continua vencendo o carimbo. A
        # edição 'Av-5' leva ao tipo averbação e à duplicata do
        # 'AV5 M237' já gravado; o descarte da linha vizinha não afrouxa
        # a regra da linha incluída.
        self.documento.numero = 'M237'
        self.documento.save(update_fields=['numero'])
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento='AV5 M237',
            data=DATA_DO_ATO,
        )
        extracao = self._extracao(self._payload(numero='R-5'))
        campo = extracao.campos.get(chave='/acts/0/rotulo')
        revisao.aplicar_linha(
            campo, incluir=True, valor='Av-5', usuario=self.usuario,
        )
        campo.save()

        (ato,) = resumo(extracao)['atos']
        self.assertEqual(ato['tipo'], 'averbacao')
        self.assertTrue(ato['duplicado'])
        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_folha_descartada_com_valor_final_vazio_cai_na_estrutural(self):
        # Rodada 6: a folha descartada não decide nem pelo ``valor_final``
        # vazio nem pelo carimbo dela — o candidato é PULADO e vale o
        # ``normalized`` da linha estrutural ('R-5'). O tipo_sugerido
        # divergente ('averbacao') é ignorado, como se a folha não
        # existisse: a gravação sai registro.
        extracao = self._extracao(self._payload(
            rotulo='R-5', tipo='averbacao', numero='R-5',
        ))
        campo = extracao.campos.get(chave='/acts/0/rotulo')
        revisao.aplicar_linha(
            campo, incluir=True, valor='', usuario=self.usuario,
        )
        revisao.aplicar_linha(campo, incluir=False, usuario=self.usuario)
        campo.save()
        self.assertEqual(campo.status_revisao, 'descartado')
        self.assertEqual(campo.valor_final, '')

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )

    def test_rotulo_efetivo_ignora_so_a_linha_descartada(self):
        # Rodada 6: a ordem vale candidato a candidato. Linha ESTRUTURAL
        # descartada → a FOLHA ativa ainda decide; descartar a folha
        # também → os dois candidatos são pulados e o leitor devolve
        # ``None`` sem exceção — o ``tipo_sugerido`` volta a decidir
        # (comportamento anterior à rodada 4).
        extracao = self._extracao(self._payload(
            rotulo='R-5', tipo='averbacao', numero='R-5',
        ))
        linhas = modulo_importacao._linhas_por_chave(extracao)
        (marcado,) = revisao.dados_revisados(extracao).atos
        estrutural = linhas['/acts/0']
        folha = linhas['/acts/0/rotulo']

        revisao.aplicar_linha(
            estrutural, incluir=False, usuario=self.usuario,
        )
        estrutural.save()
        efetivo = modulo_importacao._rotulo_efetivo('/acts/0', linhas)
        self.assertEqual(efetivo, 'R-5')
        tipo, _, _ = modulo_importacao._resolver_tipo_e_numero(
            marcado, analisar_rotulo(efetivo), self.documento,
        )
        self.assertEqual(tipo.tipo, 'registro')

        revisao.aplicar_linha(folha, incluir=False, usuario=self.usuario)
        folha.save()
        efetivo = modulo_importacao._rotulo_efetivo('/acts/0', linhas)
        self.assertIsNone(efetivo)
        tipo, _, _ = modulo_importacao._resolver_tipo_e_numero(
            marcado, analisar_rotulo(efetivo), self.documento,
        )
        self.assertEqual(tipo.tipo, 'averbacao')

    def test_rotulo_de_matricula_nao_gera_numero_de_lancamento(self):
        # P2-1 (rodada 4): 'M-3-14511' é referência de matrícula — compor
        # número com ele gravaria 'RM-3-14511 {sigla}'. O ato grava com o
        # tipo do tipo_sugerido, SEM número e com aviso; nada vira exceção
        # (o item segue sendo tratado pela UI, #321).
        extracao = self._extracao(self._payload(
            rotulo='M-3-14511', tipo='registro', numero='M-3-14511',
        ))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertIsNone(lancamento.numero_lancamento)
        (linha,) = resultado['linhas']
        (aviso,) = linha['avisos']
        self.assertIn('matrícula', aviso)

    def test_rotulo_de_matricula_preserva_o_numero_revisado(self):
        # P2 (rodada 5): 'M-3-14511' no rótulo e o revisor corrigiu o
        # /numero_lancamento para 'R-5' — o rótulo M só descarta o número
        # que VEIO da referência de matrícula; o número de ato válido do
        # campo revisado é preservado e composto (a rodada 4 zerava para
        # NULL o que a base sempre gravou: 'R5 M237').
        self.documento.numero = 'M237'
        self.documento.save(update_fields=['numero'])
        extracao = self._extracao(self._payload(
            rotulo='M-3-14511', tipo='registro', numero='M-3-14511',
        ))
        campo = extracao.campos.get(chave='/acts/0/numero_lancamento')
        revisao.aplicar_linha(
            campo, incluir=True, valor='R-5', usuario=self.usuario,
        )
        campo.save()

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(lancamento.numero_lancamento, 'R5 M237')
        (linha,) = resultado['linhas']
        (aviso,) = linha['avisos']
        self.assertIn('matrícula', aviso)
        self.assertIn('campo revisado', aviso)

    def test_rotulo_de_matricula_preserva_numero_puro_revisado(self):
        # P2 (rodada 5): o número de ato válido também pode vir JÁ SEM
        # prefixo ('5') — o normalizador devolve número, então ele é
        # preservado e composto. Só a referência de matrícula e o texto
        # sem número ficam de fora (testes vizinhos).
        self.documento.numero = 'M237'
        self.documento.save(update_fields=['numero'])
        extracao = self._extracao(self._payload(
            rotulo='M-3-14511', tipo='registro', numero='M-3-14511',
        ))
        campo = extracao.campos.get(chave='/acts/0/numero_lancamento')
        revisao.aplicar_linha(
            campo, incluir=True, valor='5', usuario=self.usuario,
        )
        campo.save()

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(
            Lancamento.objects.get().numero_lancamento, 'R5 M237',
        )
        (linha,) = resultado['linhas']
        (aviso,) = linha['avisos']
        self.assertIn('campo revisado', aviso)

    def test_rotulo_de_matricula_com_numero_revisado_invalido_grava_sem_numero(self):
        # P2 (rodada 5), o outro lado da regra: 'X-9' editado no
        # /numero_lancamento não é rótulo de ato R/Av válido — sob rótulo
        # M nada é composto com ele. O ato grava SEM número e com o aviso
        # da rodada 4 (comportamento mantido; o bucket segue com a UI,
        # #321) — igual ao caso sem edição do teste de cima.
        extracao = self._extracao(self._payload(
            rotulo='M-3-14511', tipo='registro', numero='M-3-14511',
        ))
        campo = extracao.campos.get(chave='/acts/0/numero_lancamento')
        revisao.aplicar_linha(
            campo, incluir=True, valor='X-9', usuario=self.usuario,
        )
        campo.save()

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertIsNone(lancamento.numero_lancamento)
        (linha,) = resultado['linhas']
        (aviso,) = linha['avisos']
        self.assertIn('matrícula', aviso)
        self.assertIn('nenhum número de ato', aviso)

    def test_resumo_mostra_o_tipo_que_a_gravacao_usara(self):
        # P2-2 (rodada 4): rótulo 'R-5' × tipo_sugerido 'averbacao' — a
        # prévia devolve o tipo RESOLVIDO (registro, o mesmo da gravação) e
        # expõe a divergência no aviso do item, antes de confirmar.
        extracao = self._extracao(self._payload(tipo='averbacao', numero='R-5'))

        dados = resumo(extracao)

        (ato,) = dados['atos']
        self.assertEqual(ato['tipo'], 'registro')
        self.assertIn('registro', ato['aviso'])
        self.assertIn('averbacao', ato['aviso'])
        self.assertFalse(ato['duplicado'])

    def test_resumo_sem_divergencia_nao_tem_aviso(self):
        extracao = self._extracao(self._payload(numero='R-5'))

        (ato,) = resumo(extracao)['atos']

        self.assertEqual(ato['tipo'], 'registro')
        self.assertIsNone(ato['aviso'])

    def test_meia_risca_no_rotulo_grava_no_formato_canonico(self):
        # P2-4 (rodada 4): 'R–5' (meia-risca U+2013) é registro nº 5 — sem
        # o travessão como separador o texto caía em sem_prefixo e a
        # recomposição gravava 'RR–5 {sigla}'.
        extracao = self._extracao(self._payload(
            rotulo='R–5', tipo='registro', numero='R–5',
        ))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(
            Lancamento.objects.get().numero_lancamento,
            f'R5 {self.documento.numero}',
        )

    def test_tipo_sugerido_invalido_nao_vence_o_rotulo(self):
        # P2-3: 'transcricao' (fora de TIPO_CHOICES) não pode vencer o
        # rótulo — antes virava 'tipo_inexistente'; o rótulo decide. A
        # revisão não entrega esse valor (enum validado); a fronteira da
        # gravação defende o estado que vencer a parede.
        extracao = self._extracao(self._payload(numero='R-5'))

        resposta, erros = self._importar_ato_com_tipo(extracao, 'transcricao')

        self.assertEqual(erros.itens, [])
        self.assertEqual(resposta['status'], 'criado')
        self.assertEqual(Lancamento.objects.get().tipo, self.tipo_registro)

    def test_registro_do_ocr_nao_e_duplicata_de_averbacao_manual(self):
        # P2-1: 'R-5' e 'AV5 M237' têm o MESMO número normalizado ('5'), mas
        # os rótulos declaram tipos DIFERENTES — não é duplicata (a
        # numeração é por tipo: transcrição, numeração antiga).
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento='AV5 M237',
            data=DATA_DO_ATO,
        )

        resultado = self._importar(self._extracao(self._payload(numero='R-5')))

        self.assertTrue(resultado['ok'])
        self.assertEqual(Lancamento.objects.count(), 2)

    def test_duplicata_entre_ocr_e_manual(self):
        # P2-7: o OCR importa 'R-5' (grava 'R5 {sigla}'); o fluxo MANUAL
        # cria 'R5 M237' no mesmo documento/tipo/data; a próxima importação
        # do mesmo carimbo é recusada — a MESMA normalização dos DOIS lados
        # (#322): o formato do fluxo manual é entendido na comparação.
        self._importar(self._extracao(self._payload(numero='R-5')))
        self.assertEqual(
            Lancamento.objects.get().numero_lancamento,
            f'R5 {self.documento.numero}',
        )
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_registro,
            numero_lancamento='R5 M237',
            data=DATA_DO_ATO,
        )

        self.job.status = 'importado'
        self.job.save(update_fields=['status'])
        self.job = OcrJob.objects.create(
            documento_digital=self.arquivo, status='revisado',
        )
        segunda = self._extracao(self._payload(numero='R-5'))

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(segunda)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(Lancamento.objects.count(), 2)

    def test_duplicata_inversa_averbacao_do_ocr_contra_o_manual(self):
        # P2-7, caso inverso: o OCR traz 'Av: 2-237' e já existe 'AV2 M237'
        # gravado pelo fluxo manual → duplicata.
        Lancamento.objects.create(
            documento=self.documento,
            tipo=self.tipo_averbacao,
            numero_lancamento='AV2 M237',
            data=DATA_DO_ATO,
        )
        extracao = self._extracao(self._payload(
            rotulo='Av: 2-237', tipo='averbacao', numero='Av: 2-237',
        ))

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'lancamento_duplicado')
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_rotulo_nao_reconhecido_nao_inventa_tipo(self):
        # Rótulo em texto comum segue o fluxo de erro que já existe: sem
        # tipo no rótulo e sem LancamentoTipo configurado, o ato cai em
        # 'tipo_inexistente' — o rótulo não inventa tipo (igual ao
        # comportamento de antes de #322; o bucket deles é decisão da UI,
        # #321).
        self.tipo_averbacao.delete()
        extracao = self._extracao(self._payload(
            rotulo=TEXTO_SEM_ROTULO, tipo='averbacao',
        ))

        with self.assertRaises(ImportacaoInvalida) as contexto:
            self._importar(extracao)

        (linha,) = contexto.exception.linhas
        (erro,) = linha['erros']
        self.assertEqual(erro['codigo'], 'tipo_inexistente')
        self.assertEqual(erro['chave'], '/acts/0/tipo_sugerido')
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_rotulo_nao_reconhecido_nao_inventa_numero(self):
        # Rótulo em texto comum não extrai número: o lançamento grava com
        # ``numero_lancamento`` None quando o payload não traz um — nada é
        # inventado do texto do rótulo (o tipo vem do tipo_sugerido).
        extracao = self._extracao(self._payload(rotulo=TEXTO_SEM_ROTULO))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertIsNone(lancamento.numero_lancamento)

    def test_tipo_sugerido_vazio_nao_chega_a_importar(self):
        # Parede da revisão (I-5 / #322 rodada 7): sem rótulo, tipo_sugerido
        # vazio é pendência bloqueante — ``importar`` recusa a extração
        # inteira antes de gravação alguma.
        payload = self._payload(rotulo=TEXTO_SEM_ROTULO, numero=None)
        payload['acts'][0]['tipo_sugerido'] = self._campo(None, 'R-1/42.718')
        extracao = self._extracao(payload)

        with self.assertRaises(RevisaoInvalidada):
            self._importar(extracao)

        self.assertEqual(Lancamento.objects.count(), 0)

    def test_tipo_sugerido_vazio_com_rotulo_importa(self):
        # #322 rodada 7: com rótulo R/Av, tipo_sugerido vazio conclui e importa
        payload = self._payload(numero='R-5')
        payload['acts'][0]['tipo_sugerido'] = self._campo(None, 'R-1/42.718')
        extracao = self._extracao(payload)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        lancamento = Lancamento.objects.get()
        self.assertEqual(lancamento.tipo, self.tipo_registro)
        self.assertEqual(
            lancamento.numero_lancamento, f'R5 {self.documento.numero}',
        )
