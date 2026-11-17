"""Testes do validador do payload de extração (schemas A3 vendorizados).

Os contratos são os JSONs em ia_ocr/schemas/ (v1.1 e v1.2), cópias byte a
byte do serviço de OCR — nunca editados à mão. A validação estrutural usa
Draft 2020-12 SEM format_checker: `format` em campo de valor é anotação (data
inválida vira normalized=NULL + requer_revisao na desnormalização, não
rejeição). Cada payload é validado pelo contrato que ELE declara em
``schema_version``.
"""

import hashlib
import json
import logging
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from jsonschema import Draft202012Validator

from ia_ocr import extracao_schema
from ia_ocr.extracao_schema import (
    CONTRATOS,
    SCHEMA_PATH,
    SCHEMA_VERSION,
    PayloadExtracaoInvalido,
    validar_payload,
)
from ia_ocr.tests.payloads_extracao import payload_registro

V1_1 = 'umbelino-extracao-matricula-v1.1'
V1_2 = 'umbelino-extracao-matricula-v1.2'
PASTA_SCHEMAS = Path(extracao_schema.__file__).parent / 'schemas'
# Pinado de propósito (não derivado do módulo): trocar um contrato é decisão
# explícita, com o novo sha256 do ocr-service.
SHA256_DOS_CONTRATOS = {
    V1_1: 'ae296837b964f180c8f80ac1a77815a43ff05eca52b6f3586a237129b9b2caff',
    V1_2: '8be9b56ff0c7a073c151d7c58e80efb7ed97c97ff0ff9f71b7488477c7940bc5',
}
CAMPOS_DE_TRANSMISSAO = ('livro_transacao', 'folha_transacao', 'data_transacao')


def campo(normalized=None, raw=None, confianca=0.9, evidencia=None):
    """Campo A3 mínimo: raw/normalized/confianca/requer_revisao/evidencia."""
    return {
        'raw': raw,
        'normalized': normalized,
        'confianca': confianca,
        'requer_revisao': False,
        'evidencia': evidencia,
    }


def ato(ordem=1, partes=0):
    """Atos A3 mínimo: campos required de #/$defs/act + `partes`."""
    return {
        'ordem': ordem,
        'rotulo': campo('R-1'),
        'tipo_sugerido': campo('registro'),
        'data': campo('2024-01-01'),
        'partes': [
            {
                'papel': 'transmitente',
                'nome': campo('Fulano'),
                'confianca': 0.9,
                'requer_revisao': False,
                'evidencia': None,
            }
            for _ in range(partes)
        ],
        'confianca': 0.9,
        'requer_revisao': False,
        'evidencia': None,
    }


def ato_com_transmissao(ordem=1):
    """Ato do contrato v1.2: livro/folha/data da transmissão (`*_transacao`)."""
    return {
        **ato(ordem),
        'livro_transacao': campo('10-A', raw='Livro 10-A'),
        'folha_transacao': campo('25v', raw='fl. 25v'),
        'data_transacao': campo('2019-12-20', raw='20/12/2019'),
    }


def payload_minimo(
    job_id='11111111-1111-1111-1111-111111111111', paginas=(1,),
    versao=SCHEMA_VERSION,
):
    """Payload que satisfaz o A3 por inteiro (âncora dos testes)."""
    return {
        'schema_version': versao,
        'document': {
            'tipo': campo('matricula'),
            'numero': campo(
                '42.718',
                raw='Nº 42.718',
                evidencia={'pagina': 1, 'trecho': 'matrícula nº 42.718'},
            ),
            'cartorio': campo('CRI de Guaíra'),
        },
        'acts': [],
        'meta': {
            'job_id': job_id,
            'pages_used': list(paginas),
            'provider': 'local-model',
        },
    }


class SchemaVendorizado(SimpleTestCase):
    def test_schemas_vendorizados_identicos_ao_contrato(self):
        """Byte a byte com o contrato do serviço de OCR: os DOIS arquivos."""
        for versao, esperado in SHA256_DOS_CONTRATOS.items():
            with self.subTest(versao=versao):
                arquivo = PASTA_SCHEMAS / f'{versao}.json'
                self.assertEqual(
                    hashlib.sha256(arquivo.read_bytes()).hexdigest(), esperado,
                )

    def test_so_ha_os_contratos_v1_1_e_v1_2(self):
        """Contrato novo (ou aposentadoria de um) é decisão explícita: o
        conjunto vendorizado é pinado, com o sha256 de cada um acima."""
        arquivos = sorted(
            caminho.name
            for caminho in PASTA_SCHEMAS.glob('umbelino-extracao-matricula-*.json')
        )
        self.assertEqual(arquivos, [f'{V1_1}.json', f'{V1_2}.json'])
        self.assertEqual(set(CONTRATOS), {V1_1, V1_2})
        for versao, esperado in SHA256_DOS_CONTRATOS.items():
            with self.subTest(versao=versao):
                self.assertEqual(
                    CONTRATOS[versao].caminho, PASTA_SCHEMAS / f'{versao}.json',
                )
                self.assertEqual(
                    hashlib.sha256(CONTRATOS[versao].caminho.read_bytes()).hexdigest(),
                    esperado,
                )

    def test_cada_contrato_e_coerente_com_o_proprio_const(self):
        """A identidade do contrato é o `const` de `schema_version`: a chave
        do mapa, o nome do arquivo e o schema carregado concordam com ele."""
        for versao, contrato in CONTRATOS.items():
            with self.subTest(versao=versao):
                schema = json.loads(contrato.caminho.read_text(encoding='utf-8'))
                self.assertEqual(
                    schema['properties']['schema_version']['const'], versao,
                )
                self.assertEqual(contrato.caminho.name, f'{versao}.json')
                self.assertEqual(contrato.schema, schema)
                self.assertIsInstance(contrato.validador, Draft202012Validator)

    def test_id_do_v1_2_ainda_diz_v1_1_por_descuido_do_servico(self):
        """O `$id` do v1.1 é a própria versão, mas o do v1.2 do serviço
        continua `...-v1.1` (descuido de lá). O JSON é byte a byte e NÃO se
        conserta aqui: a identidade do contrato é o `const`, nunca o `$id`
        (por isso nenhum código ou teste compara `$id` com a versão)."""
        self.assertEqual(CONTRATOS[V1_1].schema['$id'], V1_1)
        self.assertEqual(CONTRATOS[V1_2].schema['$id'], V1_1)

    def test_schema_version_e_o_contrato_mais_novo(self):
        """A requisição pede a versão mais nova (services envia SCHEMA_VERSION)
        e SCHEMA_PATH aponta para o arquivo dela."""
        self.assertEqual(SCHEMA_VERSION, V1_2)
        self.assertEqual(SCHEMA_PATH, CONTRATOS[V1_2].caminho)

    def test_schemas_sao_2020_12_validos(self):
        """Cada JSON vendorizado é um schema Draft 2020-12 válido."""
        for versao, contrato in CONTRATOS.items():
            with self.subTest(versao=versao):
                Draft202012Validator.check_schema(
                    json.loads(contrato.caminho.read_text(encoding='utf-8'))
                )

    def test_v1_2_so_acrescenta_os_campos_de_transmissao_ao_ato(self):
        """O v1.2 é o v1.1 + livro/folha/data da transmissão no ato (opcionais)
        e o novo `const`: nada mais mudou, nada ficou obrigatório."""
        ato_v1_1 = CONTRATOS[V1_1].schema['$defs']['act']
        ato_v1_2 = CONTRATOS[V1_2].schema['$defs']['act']
        self.assertEqual(
            set(ato_v1_2['properties']) - set(ato_v1_1['properties']),
            set(CAMPOS_DE_TRANSMISSAO),
        )
        self.assertEqual(ato_v1_2['required'], ato_v1_1['required'])
        self.assertIs(ato_v1_2['additionalProperties'], False)


class CarregarContratos(SimpleTestCase):
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


class ValidarPayload(SimpleTestCase):
    JOB_ID = '11111111-1111-1111-1111-111111111111'

    def test_aceita_job_id_uuid_divergente_do_servico(self):
        """O ocrcadeia gera um UUID próprio a cada chamada de extração."""
        job_id = '4883db41-773e-4b54-9fdc-55ce8f525e05'
        for id_servico in (
            '15987107-0672-4d05-a5d6-675aaaf1419c',
            'b747b7f1-5abf-4dd4-82ba-6464135f1fff',
            '15987107-0672-4D05-A5D6-675AAAF1419C',
            '{15987107-0672-4d05-a5d6-675aaaf1419c}',
            'urn:uuid:15987107-0672-4d05-a5d6-675aaaf1419c',
        ):
            with self.subTest(id_servico=id_servico):
                payload = payload_registro(id_servico)
                payload['meta']['provider'] = 'workers-ai'
                payload['meta']['pages_used'] = [1, 2]

                validar_payload(payload, job_id, (1, 2))

    def test_rejeita_propriedade_extra(self):
        """Raiz com propriedade fora do A3 → código + caminho, sem valor."""
        payload = payload_minimo()
        payload['surpresa'] = True

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.surpresa')

    def test_chave_extra_so_entra_no_caminho_se_tiver_cara_de_campo(self):
        """O caminho alimenta log e exceção: o nome de uma chave extra é
        estrutura quando é um identificador (`data_transacao`), mas texto
        livre do serviço — possível PII numa chave inventada — vira marcador."""
        for chave in (
            'João da Silva CPF 123.456.789-00',
            'chave com espaço',
            'x' * 65,
            '1comecaComDigito',
        ):
            with self.subTest(chave=chave):
                payload = payload_minimo()
                payload[chave] = True

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
                self.assertEqual(ctx.exception.caminho, '$.<chave_extra>')
                self.assertNotIn(chave, str(ctx.exception))

    def test_rejeita_schema_version_desconhecida(self):
        """schema_version fora dos contratos vendorizados → rejeita: não há
        contrato contra o qual validar."""
        payload = payload_minimo()
        payload['schema_version'] = 'umbelino-extracao-matricula-v2'

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'schema_versao_desconhecida')
        self.assertEqual(ctx.exception.caminho, '$.schema_version')
        self.assertEqual(
            str(ctx.exception), 'schema_versao_desconhecida ($.schema_version)',
        )

    def test_rejeita_schema_version_ausente_ou_de_tipo_errado(self):
        """Ausente, não-texto (inclusive não-hashável) ou vazio: mesmo código
        e caminho — nunca TypeError no lookup do contrato."""
        ausente = payload_minimo()
        del ausente['schema_version']
        casos = [('ausente', ausente)]
        for valor in (None, 123, True, [], {}, '', 'v1.2', V1_2.upper()):
            payload = payload_minimo()
            payload['schema_version'] = valor
            casos.append((repr(valor), payload))

        for nome, payload in casos:
            with self.subTest(schema_version=nome):
                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'schema_versao_desconhecida')
                self.assertEqual(ctx.exception.caminho, '$.schema_version')

    def test_aceita_v1_2_com_livro_folha_data_da_transmissao_no_ato(self):
        """Contrato novo (o que o serviço já responde): as três folhas do ato
        passam sem rejeição."""
        payload = payload_minimo(versao=V1_2)
        payload['acts'] = [ato_com_transmissao()]

        validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_aceita_v1_2_sem_os_campos_de_transmissao(self):
        """No v1.2 as três folhas são opcionais: ato sem elas segue válido."""
        payload = payload_minimo(versao=V1_2)
        payload['acts'] = [ato()]

        validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_aceita_v1_1_de_servico_antigo(self):
        """Serviço ainda no v1.1 (sem as três folhas): continua aceito, pelo
        contrato que o payload declara."""
        payload = payload_minimo(versao=V1_1)
        payload['acts'] = [ato()]

        validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_v1_1_continua_rejeitando_as_folhas_que_so_o_v1_2_conhece(self):
        """O contrato antigo NÃO é afrouxado: payload que se declara v1.1 e
        traz `data_transacao` é o incidente original (propriedade_extra) —
        cada payload vale pelo contrato que ele próprio declara."""
        payload = payload_minimo(versao=V1_1)
        payload['acts'] = [ato_com_transmissao()]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.acts[0].data_transacao')

    def test_v1_2_continua_rejeitando_propriedade_desconhecida_no_ato(self):
        """Sem validação frouxa: o v1.2 só conhece as três folhas novas."""
        payload = payload_minimo(versao=V1_2)
        payload['acts'] = [{**ato_com_transmissao(), 'folha_inventada': campo('x')}]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.acts[0].folha_inventada')

    def test_v1_2_exige_o_formato_de_campo_nas_folhas_de_transmissao(self):
        """As folhas novas são campos A3 (objeto), não texto solto."""
        for nome in CAMPOS_DE_TRANSMISSAO:
            with self.subTest(campo=nome):
                payload = payload_minimo(versao=V1_2)
                payload['acts'] = [{**ato_com_transmissao(), nome: 'texto solto'}]

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'schema_violado')
                self.assertEqual(ctx.exception.caminho, f'$.acts[0].{nome}')

    def test_v1_2_data_da_transmissao_invalida_nao_derruba_payload(self):
        """Como em todo campo de valor, `format: date` é anotação: quem trata
        data impossível é a desnormalização, não a validação estrutural."""
        for normalizado in ('2024-02-30', '31/12/2024'):
            with self.subTest(normalized=normalizado):
                payload = payload_minimo(versao=V1_2)
                transmissao = ato_com_transmissao()
                transmissao['data_transacao'] = campo(normalizado, raw=normalizado)
                payload['acts'] = [transmissao]

                validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_rejeita_confianca_fora_de_0_1(self):
        """Confiança fora do intervalo [0, 1] → rejeita (minimum/maximum)."""
        for confianca in (1.5, -0.1):
            with self.subTest(confianca=confianca):
                payload = payload_minimo()
                payload['document']['numero']['confianca'] = confianca

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'valor_fora_do_intervalo')
                self.assertEqual(
                    ctx.exception.caminho, '$.document.numero.confianca'
                )

    def test_rejeita_enum(self):
        """normalized fora do enum do domínio (ex.: tipo de documento)."""
        payload = payload_minimo()
        payload['document']['tipo']['normalized'] = 'certidao'

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'valor_fora_do_enum')
        self.assertEqual(ctx.exception.caminho, '$.document.tipo.normalized')

    def test_rejeita_job_id_divergente_nao_uuid(self):
        """ID diferente do job precisa ser um UUID do serviço."""
        for id_servico in ('outro-job', '', '15987107-0672-4d05-a5d6-675aaaf1419z'):
            with self.subTest(id_servico=id_servico):
                payload = payload_minimo(job_id=id_servico)

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'job_id_invalido')
                self.assertEqual(ctx.exception.caminho, '$.meta.job_id')
                self.assertEqual(str(ctx.exception), 'job_id_invalido ($.meta.job_id)')

    def test_job_id_continua_obrigatorio_e_string(self):
        for valor in (None, 123, [], {}):
            with self.subTest(valor=valor):
                payload = payload_minimo(job_id=valor)
                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))
                self.assertEqual(ctx.exception.codigo, 'schema_violado')
                self.assertEqual(ctx.exception.caminho, '$.meta.job_id')

        payload = payload_minimo()
        del payload['meta']['job_id']
        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))
        self.assertEqual(ctx.exception.codigo, 'schema_violado')
        self.assertEqual(ctx.exception.caminho, '$.meta')

    def test_uuid_divergente_nao_permite_pagina_fora_do_job(self):
        payload = payload_registro('15987107-0672-4d05-a5d6-675aaaf1419c')
        payload['meta']['pages_used'] = [1, 7]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1, 2))

        self.assertEqual(ctx.exception.codigo, 'pagina_fora_do_job')
        self.assertEqual(ctx.exception.caminho, '$.meta.pages_used')

    def test_rejeita_pages_used_inexistente(self):
        """pages_used citando página que não pertence ao job → rejeita."""
        payload = payload_minimo(paginas=(1,))
        payload['meta']['pages_used'] = [1, 7]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'pagina_fora_do_job')
        self.assertEqual(ctx.exception.caminho, '$.meta.pages_used')

    def test_rejeita_provider_de_101_chars(self):
        """provider acima de 100 chars não caberia na coluna → rejeita."""
        payload = payload_minimo()
        payload['meta']['provider'] = 'p' * 101

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'provider_muito_longo')
        self.assertEqual(ctx.exception.caminho, '$.meta.provider')

    def test_data_invalida_em_campo_nao_derruba_payload(self):
        """format NÃO se aplica a campo de valor: data impossível ou fora
        do ISO passa na validação estrutural — quem trata é a
        desnormalização (normalized=NULL + requer_revisao).
        """
        for normalized in ('2024-02-30', '31/12/2024'):
            with self.subTest(normalized=normalized):
                payload = payload_minimo()
                payload['document']['data'] = campo(normalized, raw=normalized)

                validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_evidencia_aceita_bbox_opcional(self):
        """A3 v1.1: evidence aceita bbox [x0, y0, x1, y1] em pixels do OCR
        (opcional, array de 4 números) sem rejeitar o payload."""
        payload = payload_minimo()
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'trecho': 'matrícula nº 42.718',
            'bbox': [10.0, 20.0, 30.0, 40.0],
        }

        validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_evidencia_continua_exigindo_trecho(self):
        """A3 v1.1: bbox NÃO substitui o trecho — evidence sem `trecho`
        continua rejeitada (required de #/$defs/evidence)."""
        payload = payload_minimo()
        payload['document']['numero']['evidencia'] = {
            'pagina': 1,
            'bbox': [10.0, 20.0, 30.0, 40.0],
        }

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'schema_violado')
        self.assertEqual(ctx.exception.caminho, '$.document.numero.evidencia')

    def test_rejeita_meta_data_invalida(self):
        """texto_confirmado_em é o único lugar com formato estrito."""
        for valor in ('2024-02-30T10:00:00Z', '32/13/2024 10:00', 'ontem'):
            with self.subTest(valor='data impossível ou não-ISO'):
                payload = payload_minimo()
                payload['meta']['texto_confirmado_em'] = valor

                with self.assertRaises(PayloadExtracaoInvalido) as ctx:
                    validar_payload(payload, self.JOB_ID, (1,))

                self.assertEqual(ctx.exception.codigo, 'formato_invalido')
                self.assertEqual(
                    ctx.exception.caminho, '$.meta.texto_confirmado_em'
                )

    def test_aceita_meta_data_iso_valida(self):
        """date-time ISO legítimo (com ou sem offset) passa em meta."""
        for valor in ('2024-02-29T10:00:00', '2024-02-29T10:00:00Z'):
            with self.subTest(valor=valor):
                payload = payload_minimo()
                payload['meta']['texto_confirmado_em'] = valor

                validar_payload(payload, self.JOB_ID, (1,))  # não levanta

    def test_rejeita_ordem_repetida(self):
        """Dois atos com a mesma `ordem` cronológica → rejeita no 2º."""
        payload = payload_minimo()
        payload['acts'] = [ato(ordem=1), ato(ordem=1)]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'ordem_repetida')
        self.assertEqual(ctx.exception.caminho, '$.acts[1].ordem')

    def test_rejeita_301_atos(self):
        """Mais de 300 atos é lixo estrutural (matrícula real tem dezenas)."""
        payload = payload_minimo()
        payload['acts'] = [ato(ordem=indice + 1) for indice in range(301)]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'limite_excedido')
        self.assertEqual(ctx.exception.caminho, '$.acts')

    def test_rejeita_41_partes_em_um_ato(self):
        """Atos com mais de 40 partes é lixo estrutural, não leitura real."""
        payload = payload_minimo()
        payload['acts'] = [ato(ordem=1, partes=41)]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'limite_excedido')
        self.assertEqual(ctx.exception.caminho, '$.acts[0].partes')

    def test_limites_sao_inclusivos(self):
        """300 atos e 40 partes em um ato (fronteira) passam, cada um."""
        com_300 = payload_minimo()
        com_300['acts'] = [ato(ordem=indice + 1) for indice in range(300)]
        validar_payload(com_300, self.JOB_ID, (1,))  # não levanta

        com_40 = payload_minimo()
        com_40['acts'] = [ato(ordem=1, partes=40)]
        validar_payload(com_40, self.JOB_ID, (1,))  # não levanta

    def test_rejeita_texto_de_10001_chars(self):
        """String de valor acima de 10 000 chars é lixo, não leitura real."""
        payload = payload_minimo()
        payload['document']['numero']['normalized'] = 'x' * 10001

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'campo_muito_longo')
        self.assertEqual(
            ctx.exception.caminho, '$.document.numero.normalized'
        )

    def test_erro_nao_carrega_valor(self):
        """`str(exc)` e os logs nunca carregam o valor do payload (PII).

        Mesmo na rejeição cujo critério é o próprio valor (tamanho), a
        mensagem vive só de código + caminho.
        """
        marcador = 'MARCADOR-UNICO-X7KQ39DF'
        payload = payload_minimo()
        payload['document']['numero']['normalized'] = (
            'z' * 10001 + ' ' + marcador
        )

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(
            str(ctx.exception),
            'campo_muito_longo ($.document.numero.normalized)',
        )
        self.assertNotIn(marcador, str(ctx.exception))
        self.assertNotIn(marcador, repr(ctx.exception))

        with self.assertLogs('ia_ocr', level='ERROR') as registros:
            try:
                validar_payload(payload, self.JOB_ID, (1,))
            except PayloadExtracaoInvalido as exc:
                logging.getLogger('ia_ocr').error(str(exc))
        self.assertNotIn(marcador, '\n'.join(registros.output))
