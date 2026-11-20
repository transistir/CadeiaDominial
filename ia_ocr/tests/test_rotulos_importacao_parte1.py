"""Parte 1 de 3 do corpo de ``RotulosImportacaoTest`` — migração VERBATIM.

Classe simples, sem ``TestCase``; quem coleta é a fachada em
``test_rotulos_importacao.py``.

Os testes de integração com o motor em lote (``importar``/
``_importar_ato``/``resumo``/``ImportacaoInvalida``) saíram com o motor,
aposentado na fase 4 da #341. Fica o setUp e o ``_payload`` que a parte 2
usa no caso do rótulo efetivo com linha descartada.
"""

from dominial.models import LancamentoTipo

from .payloads_extracao import payload_registro


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
