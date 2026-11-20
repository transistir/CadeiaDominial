"""Parte 1 de 3 do corpo de ``RotulosImportacaoTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_rotulos_importacao.py``.
"""

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


from dominial.managers import documentos_for_user
from dominial.models import Lancamento, LancamentoTipo
from ia_ocr import importacao as modulo_importacao, revisao
from ia_ocr.importacao import ImportacaoInvalida, resumo
from ia_ocr.rotulos import analisar_rotulo

from .payloads_extracao import payload_registro

DATA_DO_ATO = date(2020, 2, 15)
TEXTO_SEM_ROTULO = 'O imóvel rural denominado Sítio Boa Vista'


class RotulosImportacaoTestParte1:
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

