"""Pendências e avisos da revisão — parte 2 de 3 do corpo de
``PendenciasEAvisosTest`` (``ia_ocr/tests/test_revisao.py``,
Etapa 5, grupo 3 do plano de 400 linhas). Classe SIMPLES (sem
``TestCase``): o discovery do Django não a coleta; quem coleta é a
fachada em ``test_revisao_pendencias.py``. Corpos verbatim.
"""

from datetime import date
from dominial.models import Cartorios, Documento, DocumentoTipo, LancamentoTipo

from ia_ocr.revisao import _tipos_efetivos, aplicar_linha, avisos, pendencias
from .payloads_extracao import payload_averbacao, payload_registro


class PendenciasEAvisosTestParte2:
    def _com_origem_numerada(self, payload=None):
        payload = payload or self._registro_completo()
        payload['acts'][0].setdefault('origem', {})['numero'] = {
            'raw': 'M42.718', 'normalized': 'M42.718', 'confianca': 0.95,
            'requer_revisao': False,
            'evidencia': {'pagina': 1, 'trecho': 'Nº 42.718'},
        }
        return payload

    @staticmethod
    def _nao_consta(nome):
        return {
            'chave': f'/acts/0/origem/{nome}',
            'motivo': f'{nome}_origem_nao_consta', 'bloqueante': False,
        }

    def test_origem_com_numero_sem_livro_e_folha_avisa_sem_bloquear(self):
        self._persistir(self._com_origem_numerada())

        self.assertCountEqual(avisos(self.extracao), [
            self._nao_consta('livro'), self._nao_consta('folha'),
        ])
        self.assertEqual(pendencias(self.extracao), [])

    def test_livro_e_folha_da_origem_preenchidos_saem_do_aviso(self):
        linhas = self._persistir(self._com_origem_numerada())

        for nome, valor, restantes in (
            ('livro', '3-A', ['folha']), ('folha', '12', []),
        ):
            with self.subTest(nome=nome):
                linha = linhas[f'/acts/0/origem/{nome}']
                aplicar_linha(linha, incluir=True, valor=valor)
                linha.save()
                self.assertCountEqual(
                    avisos(self.extracao),
                    [self._nao_consta(resto) for resto in restantes],
                )
                self.assertEqual(pendencias(self.extracao), [])

    def test_origem_sem_numero_nao_avisa_livro_nem_folha(self):
        linhas = self._persistir(self._registro_completo())
        self.assertEqual(avisos(self.extracao), [])

        # Número descartado: a origem deixa de ser citada pelo ato.
        linhas_numeradas = self._persistir(self._com_origem_numerada())
        self.assertEqual(len(avisos(self.extracao)), 2)
        numero = linhas_numeradas['/acts/0/origem/numero']
        numero.status_revisao = 'descartado'
        numero.save()
        self.assertEqual(avisos(self.extracao), [])
        self.assertEqual(pendencias(self.extracao), [])

    def test_aviso_da_origem_vale_para_qualquer_tipo(self):
        esperados = [self._nao_consta('livro'), self._nao_consta('folha')]
        averbacao = payload_averbacao(self.job.job_id)
        averbacao['acts'][0]['origem'] = {
            'cartorio': averbacao['document']['cartorio'].copy(),
        }
        casos = {
            'averbacao': self._com_origem_numerada(averbacao),
            'registro': self._com_origem_numerada(),
        }
        for nome, payload in casos.items():
            with self.subTest(tipo=nome):
                self._persistir(payload)
                self.assertCountEqual(avisos(self.extracao), esperados)
                self.assertEqual(pendencias(self.extracao), [])
        # Tipo sem configuração: o aviso não depende do ``LancamentoTipo``.
        LancamentoTipo.objects.all().delete()
        self.assertCountEqual(avisos(self.extracao), esperados)

    def test_um_aviso_por_chave_mesmo_com_requer_origem_no_tipo(self):
        for flag in ('requer_livro_origem', 'requer_folha_origem'):
            setattr(self.registro, flag, True)
        self.registro.save()
        self._persistir(self._com_origem_numerada())

        resultado = avisos(self.extracao)

        self.assertCountEqual(resultado, [
            self._nao_consta('livro'), self._nao_consta('folha'),
        ])
        chaves = [item['chave'] for item in resultado]
        self.assertEqual(len(chaves), len(set(chaves)))

    # --- #267 (parte IA): homônimo de outro tipo, só no escopo do usuário ----

    def _origem_com_homonimo(self, numero='T366', tipo_documento='transcricao',
                             cartorio_escolhido=True):
        cartorio = Cartorios.objects.create(
            nome='CRI Origem 267', cns='CNS-267', cidade='X', estado='SP',
        )
        self.homonimo = Documento.objects.create(
            imovel=self.job.documento_digital.documento.imovel,
            tipo=DocumentoTipo.objects.create(tipo='matricula'),
            numero='M366', data=date(1990, 1, 1), cartorio=cartorio,
            livro='1', folha='1',
        )
        DocumentoTipo.objects.create(tipo='transcricao')
        payload = self._com_origem_numerada()
        origem = payload['acts'][0]['origem']
        origem['numero']['raw'] = origem['numero']['normalized'] = numero
        if tipo_documento:
            origem['tipo_documento'] = {
                'raw': tipo_documento, 'normalized': tipo_documento,
                'confianca': 0.95, 'requer_revisao': False,
                'evidencia': {'pagina': 1, 'trecho': 'MATRÍCULA Nº 42.718'},
            }
        self._persistir(payload)
        if cartorio_escolhido:
            self.extracao.campos.filter(chave='/acts/0/origem/cartorio').update(
                criar_novo=False, cartorio_escolhido_id=cartorio.pk,
            )
        return cartorio

    @staticmethod
    def _homonimo_avisado():
        return {
            'chave': '/acts/0/origem/numero',
            'motivo': 'origem_homonimo_outro_tipo', 'bloqueante': False,
        }

    def test_homonimo_de_outro_tipo_so_avisa_com_o_escopo_do_usuario(self):
        self._origem_com_homonimo()

        # Sem queryset a checagem é pulada: nada de outra TI vaza.
        self.assertNotIn(self._homonimo_avisado(), avisos(self.extracao))
        self.assertIn(
            self._homonimo_avisado(),
            avisos(self.extracao, documentos_queryset=Documento.objects.all()),
        )
        self.assertNotIn(
            self._homonimo_avisado(),
            avisos(
                self.extracao, documentos_queryset=Documento.objects.none(),
            ),
        )
        self.assertEqual(pendencias(self.extracao), [])

    def test_homonimo_so_com_cartorio_existente_escolhido(self):
        self._origem_com_homonimo(cartorio_escolhido=False)

        # "Criar novo": o cartório ainda não existe, não há o que comparar.
        self.assertNotIn(
            self._homonimo_avisado(),
            avisos(self.extracao, documentos_queryset=Documento.objects.all()),
        )

    def test_homonimo_usa_o_tipo_inferido_do_prefixo_do_numero(self):
        # Sem ``tipo_documento`` lido, 'T366' é transcrição — a mesma regra da
        # importação; o homônimo é a matrícula M366.
        self._origem_com_homonimo(tipo_documento=None)

        self.assertIn(
            self._homonimo_avisado(),
            avisos(self.extracao, documentos_queryset=Documento.objects.all()),
        )

    def test_numero_declarado_igual_ao_existente_nao_avisa(self):
        self._origem_com_homonimo(numero='M366', tipo_documento='matricula')

        self.assertNotIn(
            self._homonimo_avisado(),
            avisos(self.extracao, documentos_queryset=Documento.objects.all()),
        )

    def test_requer_origem_sem_numero_continua_como_antes(self):
        self.registro.requer_livro_origem = True
        self.registro.save()
        self._persistir(self._registro_completo())

        self.assertEqual(avisos(self.extracao), [{
            'chave': '/acts/0/origem/livro', 'motivo': 'requer_livro_origem',
            'bloqueante': False,
        }])

    def test_obrigatorio_descartado_bloqueia(self):
        linhas = self._persistir(self._registro_completo())
        self.assertEqual(pendencias(self.extracao), [])
        for chave in (
            '/document/tipo', '/document/data', '/document/cartorio',
            '/acts/0/data', '/acts/0/titulo', '/acts/0/origem/cartorio',
        ):
            with self.subTest(chave=chave):
                linha = linhas[chave]
                linha.status_revisao = 'descartado'
                linha.save()
                self.assertEqual(
                    pendencias(self.extracao), [self._obrigatorio(chave)]
                )
                linha.status_revisao = 'sugerido'
                linha.save()
        # P1-2 (rodada 7): o rótulo 'R-1' resolve o tipo — descartar o
        # tipo_sugerido deixa de ser bloqueante.
        tipo = linhas['/acts/0/tipo_sugerido']
        tipo.status_revisao = 'descartado'
        tipo.save()
        self.assertEqual(pendencias(self.extracao), [])
        tipo.status_revisao = 'sugerido'
        tipo.save()

    def test_data_nula_bloqueia(self):
        for chave in ('/document/data', '/acts/0/data'):
            with self.subTest(chave=chave):
                payload = self._registro_completo()
                ramo = payload['document'] if chave.startswith('/document') else (
                    payload['acts'][0]
                )
                ramo['data']['normalized'] = None
                linha = self._persistir(payload)[chave]
                linha.status_revisao = 'aceito'
                linha.save()
                self.assertEqual(
                    pendencias(self.extracao), [self._obrigatorio(chave)]
                )

                aplicar_linha(linha, incluir=True, valor='2020-01-11')
                linha.save()
                self.assertEqual(pendencias(self.extracao), [])

                linha.valor_final = ''
                linha.save()
                self.assertIn(self._obrigatorio(chave), pendencias(self.extracao))

                linha.normalized = '2020-01-11'
                linha.valor_final = 'data inválida'
                linha.save()
                self.assertEqual(pendencias(self.extracao), [{
                    'chave': chave, 'motivo': 'valor_incompativel_destino',
                    'bloqueante': True,
                }])

    def test_registro_exige_titulo_e_cartorio_origem(self):
        self._persistir(payload_registro(self.job.job_id))
        self.assertCountEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/titulo'),
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])
        self._persistir(self._registro_completo())
        self.assertEqual(pendencias(self.extracao), [])

    def test_cartorio_obrigatorio_sem_nome_nao_duplica_pendencia(self):
        self._persistir(payload_registro(self.job.job_id))
        chave = '/acts/0/origem/cartorio'

        self.assertEqual(
            [item for item in pendencias(self.extracao) if item['chave'] == chave],
            [self._obrigatorio(chave)],
        )

    def test_desnormalizar_cria_linha_para_campo_exigido_ausente(self):
        linhas = self._persistir(payload_registro(self.job.job_id))

        for chave in ('/acts/0/titulo', '/acts/0/origem/cartorio'):
            with self.subTest(chave=chave):
                linha = linhas[chave]
                self.assertIsNone(linha.raw)
                self.assertIsNone(linha.normalized)
                self.assertFalse(linha.requer_revisao)
        # A ausência continua bloqueando, mas agora há controle para resolver.
        self.assertCountEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/titulo'),
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])

    def test_desnormalizar_cria_descricao_exigida_pela_averbacao(self):
        payload = payload_averbacao(self.job.job_id)
        del payload['acts'][0]['descricao']

        linhas = self._persistir(payload)

        self.assertIn('/acts/0/descricao', linhas)
        self.assertIsNone(linhas['/acts/0/descricao'].normalized)
        self.assertEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/descricao'),
        ])

    def test_inicio_matricula_cria_cartorio_origem_mesmo_sem_flag(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['tipo_sugerido']['normalized'] = 'inicio_matricula'
        self.inicio.requer_cartorio_origem = False
        self.inicio.save()

        linhas = self._persistir(payload)
        self._sem_rotulo()

        self.assertIn('/acts/0/origem/cartorio', linhas)
        self.assertEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])

    def test_averbacao_exige_descricao(self):
        for estado in ('ausente', 'vazio', 'descartado'):
            with self.subTest(estado=estado):
                payload = payload_averbacao(self.job.job_id)
                if estado == 'ausente':
                    del payload['acts'][0]['descricao']
                elif estado == 'vazio':
                    payload['acts'][0]['descricao']['normalized'] = ''
                linhas = self._persistir(payload)
                if estado == 'descartado':
                    linha = linhas['/acts/0/descricao']
                    linha.status_revisao = 'descartado'
                    linha.save()
                self.assertEqual(pendencias(self.extracao), [
                    self._obrigatorio('/acts/0/descricao'),
                ])

    def test_inicio_matricula_exige_cartorio_origem(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['tipo_sugerido']['normalized'] = 'inicio_matricula'
        self._persistir(payload)
        self._sem_rotulo()
        for flag in (False, True):
            with self.subTest(requer_cartorio_origem=flag):
                self.inicio.requer_cartorio_origem = flag
                self.inicio.save()
                self.assertEqual(pendencias(self.extracao), [
                    self._obrigatorio('/acts/0/origem/cartorio'),
                ])
        payload['acts'][0]['origem'] = {
            'cartorio': payload['document']['cartorio'].copy(),
        }
        self._persistir(payload)
        self._sem_rotulo()  # R-1 volta no persistir; sem rótulo tipo_sugerido decide (#322)
        self.assertEqual(pendencias(self.extracao), [])

    def test_tipo_editado_recalcula_obrigacoes(self):
        payload = payload_registro(self.job.job_id)
        payload['acts'][0]['descricao'] = payload_averbacao(
            self.job.job_id
        )['acts'][0]['descricao']
        linhas = self._persistir(payload)
        self._sem_rotulo()
        self.assertCountEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/titulo'),
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])
        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='averbacao')
        tipo.save()
        self.assertEqual(tipo.normalized, 'registro')
        self.assertEqual(pendencias(self.extracao), [
            self._criar_novo_sem_nome('/acts/0/origem/cartorio'),
        ])

        descricao = linhas['/acts/0/descricao']
        aplicar_linha(descricao, incluir=True, valor='')
        descricao.save()
        self.assertEqual(pendencias(self.extracao), [
            self._criar_novo_sem_nome('/acts/0/origem/cartorio'),
            self._obrigatorio('/acts/0/descricao'),
        ])

        aplicar_linha(tipo, incluir=True, valor='inicio_matricula')
        tipo.save()
        self.assertEqual(pendencias(self.extracao), [
            self._obrigatorio('/acts/0/origem/cartorio'),
        ])

    def test_tipo_explicito_vence_rotulo_divergente(self):
        # (a) tipo explícito vence rótulo divergente (#322 rodada 7)
        payload = self._registro_completo()
        linhas = self._persistir(payload)
        tipo = linhas['/acts/0/tipo_sugerido']
        aplicar_linha(tipo, incluir=True, valor='averbacao')
        tipo.save()
        tipos_por_ato, _ = _tipos_efetivos(
            {campo.chave: campo for campo in self.extracao.campos.all()},
            [linhas['/acts/0']],
        )
        self.assertEqual(tipos_por_ato['/acts/0'], 'averbacao')
