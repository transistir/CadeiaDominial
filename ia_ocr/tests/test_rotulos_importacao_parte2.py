"""Parte 2 de 3 do corpo de ``RotulosImportacaoTest`` — migração VERBATIM.

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

from datetime import date


from dominial.models import Lancamento
from ia_ocr import importacao as modulo_importacao, revisao
from ia_ocr.importacao import ImportacaoInvalida, resumo
from ia_ocr.models import OcrJob
from ia_ocr.revisao import RevisaoInvalidada
from ia_ocr.rotulos import analisar_rotulo


DATA_DO_ATO = date(2020, 2, 15)
TEXTO_SEM_ROTULO = 'O imóvel rural denominado Sítio Boa Vista'


class RotulosImportacaoTestParte2:
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

