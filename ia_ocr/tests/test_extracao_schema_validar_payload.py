"""Primeira parte do corpo de ``ValidarPayload``; coletada pela fachada."""

from ia_ocr.extracao_schema import PayloadExtracaoInvalido, validar_payload
from ia_ocr.tests.payloads_extracao import payload_registro

from .test_extracao_schema_base import (
    CAMPOS_DE_TRANSMISSAO, V1_1, V1_2, ato, ato_com_transmissao, campo,
    payload_minimo,
)

class ValidarPayloadParte1:
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
        """Raiz com propriedade fora do A3 → código + caminho, sem valor. O
        nome da chave só entra se for campo conhecido dos contratos —
        `surpresa` não é, então vira o marcador fixo."""
        payload = payload_minimo()
        payload['surpresa'] = True

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.<campo>')

    def test_chave_extra_fora_dos_contratos_vira_marcador(self):
        """O caminho alimenta log e exceção: só NOME DE CAMPO conhecido dos
        contratos vendorizados entra nele. Chave inventada — mesmo com cara
        de identificador, possível PII (`JOAO_DA_SILVA_CPF_12345678900`),
        ou texto livre — vira o marcador fixo `<campo>`."""
        for chave in (
            'JOAO_DA_SILVA_CPF_12345678900',
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
                self.assertEqual(ctx.exception.caminho, '$.<campo>')
                self.assertNotIn(chave, str(ctx.exception))

    def test_propriedade_extra_com_nome_de_campo_conhecido_mantem_caminho(self):
        """Chave extra cujo nome É campo de algum contrato vendorizado (o
        incidente da #339: `data_transacao` num payload que se declara v1.1)
        continua por extenso — é o que torna o diagnóstico possível."""
        payload = payload_minimo(versao=V1_1)
        payload['data_transacao'] = campo('2019-12-20')

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.data_transacao')

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
        """Sem validação frouxa: o v1.2 só conhece as três folhas novas — e
        o nome inventado (`folha_inventada` não é campo de contrato nenhum)
        sai sanitizado do caminho."""
        payload = payload_minimo(versao=V1_2)
        payload['acts'] = [{**ato_com_transmissao(), 'folha_inventada': campo('x')}]

        with self.assertRaises(PayloadExtracaoInvalido) as ctx:
            validar_payload(payload, self.JOB_ID, (1,))

        self.assertEqual(ctx.exception.codigo, 'propriedade_extra')
        self.assertEqual(ctx.exception.caminho, '$.acts[0].<campo>')
        self.assertNotIn('folha_inventada', str(ctx.exception))

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

