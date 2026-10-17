"""Testes do matching determinístico de pessoas/cartórios (I-5, #262).

Um teste por regra: nome único, homônimos, CPF completo, CPF mascarado,
CNPJ (nunca casa por documento), cartório por nome+cidade, cidade
divergente e múltiplos candidatos — mais o enriquecimento do payload
(match do serviço sobrescrito, homônimos como candidatos, resultado
válido no A3 fora a extensão local, original intacto)
e o custo dos índices: UMA query por índice, matching sem banco.

Fixtures sintéticas: nenhum dado de documento/pessoa real.
"""

import copy
import uuid

from django.test import TestCase

from dominial.models import Cartorios, Pessoas
from ia_ocr.extracao_schema import validar_payload
from ia_ocr.revisao import (
    MATCH_PESSOA_CANDIDATOS, IndiceCartorios, IndicePessoas,
    enriquecer_payload,
)

from .payloads_extracao import payload_registro


def _criar_cartorio(nome, cns, cidade=None, estado='PR'):
    return Cartorios.objects.create(
        nome=nome, cns=cns, cidade=cidade, estado=estado
    )


class IndicePessoasTest(TestCase):
    def test_nome_unico(self):
        joao = Pessoas.objects.create(nome='JOÃO DA SILVA')

        escolhido, candidatos = IndicePessoas().match(
            '  joao   da silva ', None, None
        )

        # Normalização: NFKD sem acento, sem caixa, espaços colapsados.
        self.assertEqual(escolhido, joao.pk)
        self.assertEqual(candidatos, [])

    def test_nome_desconhecido_nao_casa(self):
        Pessoas.objects.create(nome='JOÃO DA SILVA')

        escolhido, candidatos = IndicePessoas().match(
            'FULANO DE TAL', None, None
        )

        self.assertIsNone(escolhido)
        self.assertEqual(candidatos, [])

    def test_homonimos(self):
        Pessoas.objects.create(nome='MARIA DA SILVA', cpf='11111111111')
        outra = Pessoas.objects.create(nome='Maria da Silva')

        escolhido, candidatos = IndicePessoas().match(
            'MARIA DA SILVA', None, None
        )

        # Homônimo nunca é escolha automática: humanos decidem.
        self.assertIsNone(escolhido)
        self.assertEqual(len(candidatos), 2)
        self.assertIn(outra.pk, candidatos)

    def test_cpf_completo(self):
        maria = Pessoas.objects.create(nome='MARIA DA SILVA', cpf='98765432100')
        Pessoas.objects.create(nome='MARIA DA SILVA')  # homônima sem cpf

        escolhido, candidatos = IndicePessoas().match(
            'MARIA DA SILVA', 'CPF', '987.654.321-00'
        )

        # CPF com exatamente 11 dígitos casa por documento, mesmo com
        # homônima pelo nome: o documento desempata.
        self.assertEqual(escolhido, maria.pk)
        self.assertEqual(candidatos, [])

    def test_cpf_completo_desconhecido_cai_no_nome(self):
        joao = Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='12345678900')

        indice = IndicePessoas()
        # CPF íntegro que não existe na base → nome decide.
        self.assertEqual(
            indice.match('JOÃO DA SILVA', 'CPF', '00000000000'), (joao.pk, [])
        )
        # Nem documento, nem nome → nenhuma sugestão.
        self.assertEqual(
            indice.match('FULANO', 'CPF', '00000000000'), (None, [])
        )

    def test_cpf_mascarado(self):
        joao = Pessoas.objects.create(nome='JOÃO DA SILVA', cpf='12345678900')
        indice = IndicePessoas()

        mascarados = (
            '***.456.789-**',  # máscara com *
            '123456789XX',     # máscara com X
            '1234567',         # menos de 11 dígitos
        )
        for valor in mascarados:
            with self.subTest(valor=valor):
                # Não casa por documento; o nome continua valendo.
                self.assertEqual(
                    indice.match('JOÃO DA SILVA', 'CPF', valor),
                    (joao.pk, []),
                )
                # Sem nome aproveitável → nenhuma sugestão (nunca adivinha).
                self.assertEqual(
                    indice.match('FULANO DE TAL', 'CPF', valor), (None, [])
                )

    def test_cnpj(self):
        empresa = Pessoas.objects.create(nome='AGROPECUÁRIA SANTA LUZIA')
        pessoa_com_cpf = Pessoas.objects.create(
            nome='OUTRA PESSOA', cpf='12345678900'
        )
        indice = IndicePessoas().match  # snapshot: criado DEPOIS das pessoas

        # CNPJ não casa por documento — mesmo com os dígitos de um cpf
        # indexado — mas o nome continua valendo.
        self.assertEqual(
            indice('AGROPECUARIA SANTA LUZIA', 'CNPJ', '12345678000190'),
            (empresa.pk, []),
        )
        self.assertEqual(
            indice('NOME QUALQUER', 'CNPJ', '12345678900'), (None, [])
        )
        # Outros tipos idem: só CPF íntegro casa por documento.
        for tipo in ('CGC', 'OUTRO'):
            with self.subTest(tipo=tipo):
                self.assertEqual(
                    indice('OUTRA PESSOA', tipo, '12345678900'),
                    (pessoa_com_cpf.pk, []),
                )


class IndiceCartoriosTest(TestCase):
    def test_nome_e_cidade(self):
        guaira = _criar_cartorio(
            'Cartório de Registro de Imóveis de Guaíra', '12.345-6',
            cidade='Guaíra',
        )

        escolhido, candidatos = IndiceCartorios().match(
            'CARTORIO DE REGISTRO DE IMOVEIS DE GUAIRA', 'Guaíra'
        )

        self.assertEqual(escolhido, guaira.pk)
        self.assertEqual(candidatos, [])

    def test_cidade_divergente(self):
        guaira = _criar_cartorio('CRI Central', '1', cidade='Guaíra')
        _criar_cartorio('CRI Central', '2', cidade='Umuarama')

        indice = IndiceCartorios()
        # Cidade informada confirma: a divergente sai, resta uma → escolhido.
        self.assertEqual(indice.match('CRI Central', 'Guaíra'), (guaira.pk, []))
        # Cidade que não é a de nenhum candidato → não casa, nem sugere.
        self.assertEqual(indice.match('CRI Central', 'Curitiba'), (None, []))
        # Sem cidade informada, o nome resolve sozinho: 2 → candidatos.
        escolhido, candidatos = indice.match('CRI Central', None)
        self.assertIsNone(escolhido)
        self.assertEqual(len(candidatos), 2)

    def test_multiplos(self):
        _criar_cartorio('CRI de Guaíra', '1', cidade='Guaíra')
        _criar_cartorio('CRI de Guaíra', '2', cidade='Guaíra')

        escolhido, candidatos = IndiceCartorios().match(
            'CRI de Guaíra', 'Guaíra'
        )

        self.assertIsNone(escolhido)
        self.assertEqual(len(candidatos), 2)


class EnriquecerPayloadTest(TestCase):
    def setUp(self):
        self.job_id = uuid.uuid4()
        self.joao = Pessoas.objects.create(
            nome='JOÃO DA SILVA', cpf='12345678900'
        )
        self.maria = Pessoas.objects.create(
            nome='MARIA DA SILVA', cpf='98765432100'
        )
        self.cri = _criar_cartorio(
            'CRI de Guaíra', '12.345-6', cidade='Guaíra'
        )
        self.indices = (IndicePessoas(), IndiceCartorios())

    def _enriquecer(self, payload):
        return enriquecer_payload(payload, *self.indices)

    def test_match_do_servico_sobrescrito(self):
        payload = payload_registro(self.job_id)
        payload['document']['cartorio']['match_sugerido'] = {
            'cartorio_id': 999999, 'candidatos': [999999],
        }
        payload['acts'][0]['partes'][0]['match_pessoa_id'] = 888888
        antes = copy.deepcopy(payload)

        enriquecido = self._enriquecer(payload)

        # O match que veio do serviço cede lugar ao determinístico.
        self.assertEqual(
            enriquecido['document']['cartorio']['match_sugerido'],
            {'cartorio_id': self.cri.pk, 'candidatos': []},
        )
        self.assertEqual(
            enriquecido['acts'][0]['partes'][0]['match_pessoa_id'],
            self.joao.pk,
        )
        # Enriquecer trabalha sobre cópia: o original fica intacto.
        self.assertEqual(payload, antes)

    def test_payload_enriquecido_valida_no_a3(self):
        payload = payload_registro(self.job_id)

        enriquecido = self._enriquecer(payload)

        # match_pessoa_candidatos é extensão local (a party do A3 não tem
        # lista de candidatos): sem ela, o resto do enriquecido é A3 válido.
        no_a3 = copy.deepcopy(enriquecido)
        for parte in no_a3['acts'][0]['partes']:
            self.assertEqual(parte.pop(MATCH_PESSOA_CANDIDATOS), [])
        validar_payload(no_a3, self.job_id, [1])  # não levanta
        partes = enriquecido['acts'][0]['partes']
        self.assertEqual(partes[0]['match_pessoa_id'], self.joao.pk)  # por CPF
        self.assertEqual(partes[1]['match_pessoa_id'], self.maria.pk)  # por CPF
        self.assertIsNone(partes[2]['match_pessoa_id'])  # PEDRO não existe
        self.assertEqual(
            enriquecido['document']['cartorio']['match_sugerido'],
            {'cartorio_id': self.cri.pk, 'candidatos': []},
        )
        # cri_atual não existe na base: sugestão vazia, nunca adivinhação.
        self.assertEqual(
            enriquecido['document']['cri_atual']['match_sugerido'],
            {'cartorio_id': None, 'candidatos': []},
        )

    def test_homonimos_viram_candidatos(self):
        pedro_b = Pessoas.objects.create(nome='Pedro Santos')
        pedro_a = Pessoas.objects.create(nome='PEDRO SANTOS')

        enriquecido = enriquecer_payload(
            payload_registro(self.job_id), IndicePessoas(), IndiceCartorios(),
        )

        # Homônimos: nenhum escolhido, todos candidatos em ordem de pk.
        pedro = enriquecido['acts'][0]['partes'][2]
        self.assertIsNone(pedro['match_pessoa_id'])
        self.assertEqual(
            pedro[MATCH_PESSOA_CANDIDATOS], sorted([pedro_a.pk, pedro_b.pk]),
        )
        # Match único: candidatos vazios, o id vai em match_pessoa_id.
        joao = enriquecido['acts'][0]['partes'][0]
        self.assertEqual(joao['match_pessoa_id'], self.joao.pk)
        self.assertEqual(joao[MATCH_PESSOA_CANDIDATOS], [])

    def test_uma_query_por_indice(self):
        with self.assertNumQueries(2):
            pessoas = IndicePessoas()
            cartorios = IndiceCartorios()

        # O índice é em memória: matching não toca o banco.
        with self.assertNumQueries(0):
            self.assertEqual(
                pessoas.match('JOÃO DA SILVA', 'CPF', '123.456.789-00'),
                (self.joao.pk, []),
            )
            self.assertEqual(
                cartorios.match('CRI de Guaíra', 'Guaíra'), (self.cri.pk, [])
            )
