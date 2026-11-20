"""Parte do corpo de ``CarregarContratos``; coletada pela fachada."""

import json
import tempfile
from pathlib import Path

from ia_ocr import extracao_schema
from ia_ocr.extracao_schema import CONTRATOS

from .test_extracao_schema_base import V1_1, V1_2

class CarregarContratosParte:
    """O loader lê TODOS os contratos da pasta, identificando cada um pelo
    `const` — nenhum literal de versão no código."""

    @staticmethod
    def _gravar(diretorio, versao, nome=None):
        """Cópia do v1.2 com o `const` trocado para `versao`."""
        schema = json.loads(CONTRATOS[V1_2].caminho.read_text(encoding='utf-8'))
        schema['properties']['schema_version']['const'] = versao
        arquivo = diretorio / (nome or f'{versao}.json')
        arquivo.write_text(json.dumps(schema), encoding='utf-8')
        return arquivo

    def test_versao_deriva_do_const_do_vendorizado(self):
        """Derivação de verdade: numa pasta com só uma versão futura, o mapa
        e a versão mais nova seguem o `const` do JSON."""
        futura = 'umbelino-extracao-matricula-v1.3'
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            arquivo = self._gravar(diretorio, futura)

            contratos = extracao_schema._carregar_contratos(diretorio)

            self.assertEqual(list(contratos), [futura])
            self.assertEqual(contratos[futura].caminho, arquivo)
            self.assertEqual(
                extracao_schema._versao_do_schema(contratos[futura].schema),
                futura,
            )
            self.assertEqual(extracao_schema._mais_nova(contratos), futura)

    def test_aceita_varios_contratos_ao_mesmo_tempo(self):
        """Antes dois arquivos juntos eram erro (troca mal feita); agora são
        intencionais — compatibilidade de rollout serviço/app."""
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            self._gravar(diretorio, V1_1)
            self._gravar(diretorio, V1_2)

            contratos = extracao_schema._carregar_contratos(diretorio)

            self.assertEqual(set(contratos), {V1_1, V1_2})
            self.assertEqual(extracao_schema._mais_nova(contratos), V1_2)

    def test_versao_mais_nova_ordena_como_versao_nao_como_texto(self):
        """v1.10 é mais nova que v1.2 (como texto, 'v1.10' < 'v1.2')."""
        dez = 'umbelino-extracao-matricula-v1.10'
        self.assertLess(dez, V1_2)  # a armadilha: como texto, v1.10 < v1.2
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            self._gravar(diretorio, V1_2)
            self._gravar(diretorio, dez)

            contratos = extracao_schema._carregar_contratos(diretorio)

            self.assertEqual(extracao_schema._mais_nova(contratos), dez)

    def test_versao_sem_sufixo_numerico_e_recusada(self):
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            self._gravar(diretorio, 'umbelino-extracao-matricula-final')

            with self.assertRaises(ValueError):
                extracao_schema._carregar_contratos(diretorio)

    def test_recusa_arquivo_com_nome_diferente_do_proprio_const(self):
        """Cópia renomeada sem trocar o `const` (o v1.1 posando de v1.2) é
        troca mal feita: erro, em vez de validar contra o contrato errado —
        e é o que impede a mesma versão em dois arquivos."""
        with tempfile.TemporaryDirectory() as tmp:
            diretorio = Path(tmp)
            self._gravar(diretorio, V1_1)
            self._gravar(diretorio, V1_1, nome=f'{V1_2}.json')

            with self.assertRaises(ValueError):
                extracao_schema._carregar_contratos(diretorio)

    def test_pasta_sem_contratos_levanta(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                extracao_schema._carregar_contratos(Path(tmp))

