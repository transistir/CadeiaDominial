"""Parte 3 de 3 do corpo de ``RotulosImportacaoTest`` — migração VERBATIM.

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
from ia_ocr import estados, services


DATA_DO_ATO = date(2020, 2, 15)
TEXTO_SEM_ROTULO = 'O imóvel rural denominado Sítio Boa Vista'


class RotulosImportacaoTestParte3:
    def _salvar_card_tipo(self, extracao, decisao, chave='/acts/0/tipo_sugerido'):
        """Salva um card como a tela faz, com o job ainda em revisão.

        A fixture já entrega o job ``revisado`` e a extração finalizada; o
        save da revisão acontece ANTES disso na vida real — o teste volta os
        dois estados, aplica a decisão e refinaliza pelo serviço. O JS manda
        UM card por request: a chave padrão é o card do tipo, mas um teste
        pode salvar outro (``/acts/0/data``) para probar que a escolha
        explícita não vaza para ele.
        """
        job = extracao.ocr_job
        job.status = estados.EXTRAIDO
        job.save(update_fields=['status'])
        extracao.finalizada_em = None
        extracao.save(update_fields=['finalizada_em'])
        services.salvar_bloco(
            extracao,
            {chave: decisao},
            self.usuario,
            services.versao_bloco(extracao),
        )
        services.finalizar_revisao(extracao, self.usuario)

    def test_revisor_confirma_o_tipo_no_card_e_a_importacao_grava_ele(self):
        # P1 (Greptile, #322/PR #327): o revisor salva o card do tipo
        # CONFIRMANDO o 'registro' que o OCR sugeriu — o valor enviado é
        # igual ao sugerido, o ``valor_final`` fica nulo e antes a
        # precedência não via escolha alguma: o rótulo 'Av-5' vencia e a
        # importação gravava AVERBAÇÃO. Com a escolha explícita marcada na
        # linha, o card confirmado vence o rótulo.
        extracao = self._extracao(self._payload(
            rotulo='Av-5', tipo='registro', numero='R-5',
        ))

        self._salvar_card_tipo(
            extracao, {'incluir': True, 'conferido': True},
        )

        campo_tipo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertTrue(campo_tipo.escolha_explicita)
        self.assertIsNone(campo_tipo.valor_final)
        self.assertEqual(campo_tipo.status_revisao, 'aceito')
        self.assertEqual(campo_tipo.revisado_por, self.usuario)
        self.assertIsNotNone(campo_tipo.revisado_em)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(Lancamento.objects.get().tipo, self.tipo_registro)

    def test_revisor_confirma_digitando_o_mesmo_valor_e_ele_vence(self):
        # Mesma cena pelo outro caminho da tela: o revisor REENVIA o valor
        # igual ao sugerido (editou e voltou). ``canonico == normalized``
        # limpa o ``valor_final``; a escolha explícita marca que ele passou
        # pelo card — o 'registro' confirmado vence o rótulo 'Av-5'.
        extracao = self._extracao(self._payload(
            rotulo='Av-5', tipo='registro', numero='R-5',
        ))

        self._salvar_card_tipo(extracao, {'incluir': True, 'valor': 'registro'})

        campo_tipo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertTrue(campo_tipo.escolha_explicita)
        self.assertEqual(campo_tipo.revisado_por, self.usuario)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(Lancamento.objects.get().tipo, self.tipo_registro)

    def test_sem_decisao_no_card_o_rotulo_continua_vencendo(self):
        # Caso de CONTROLE do P1: o revisor não toca no card do tipo — sem
        # escolha explícita, o rótulo 'Av-5' segue vencendo o
        # tipo_sugerido divergente (mesma regra de antes da flag).
        extracao = self._extracao(self._payload(
            rotulo='Av-5', tipo='registro', numero='R-5',
        ))

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(Lancamento.objects.get().tipo, self.tipo_averbacao)

    def test_salvar_outro_card_nao_marca_a_escolha_do_tipo(self):
        # MUST-FIX (revisão Opus): o JS manda UM card por request
        # (ocr_revisao.js) — salvar o card da DATA não pode marcar escolha
        # explícita no card do TIPO; sem a flag, a importação continua
        # gravando o tipo do RÓTULO ('Av-5' vence o tipo_sugerido 'registro').
        extracao = self._extracao(self._payload(
            rotulo='Av-5', tipo='registro', numero='R-5',
        ))

        self._salvar_card_tipo(
            extracao, {'incluir': True, 'conferido': True},
            chave='/acts/0/data',
        )

        # O card salvado marca a escolha; o do tipo, não.
        self.assertTrue(
            extracao.campos.get(chave='/acts/0/data').escolha_explicita,
        )
        campo_tipo = extracao.campos.get(chave='/acts/0/tipo_sugerido')
        self.assertFalse(campo_tipo.escolha_explicita)
        self.assertIsNone(campo_tipo.valor_final)

        resultado = self._importar(extracao)

        self.assertTrue(resultado['ok'])
        self.assertEqual(Lancamento.objects.get().tipo, self.tipo_averbacao)
