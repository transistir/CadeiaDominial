"""Pessoa da parte (decisão D): escolhida, reutilizada por CPF/RG ou nova."""
import re

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from dominial.models import Pessoas

from ..revisao import _normalizar_nome, _so_digitos


def _rg_normalizado(rg):
    """RG comparável: só alfanumérico, em caixa alta (o RG não é só dígito)."""
    return re.sub(r'[^A-Z0-9]', '', (rg or '').upper())


def _resolver_pessoa(parte, cache_pessoas, erros):
    """Pessoa da parte (decisão D): escolhida, reutilizada por identificação ou nova.

    Reuso exige IDENTIFICAÇÃO, nunca nome puro (homônimo existe): CPF por
    cache ou cadastro; RG por cache, e só com o nome igual. Sem CPF e sem
    RG cada ato grava o seu cadastro — não há evidência de mesma pessoa.
    Se o CPF e o RG da MESMA parte apontam para pessoas distintas, é
    conflito: erro na linha da parte, nunca fusão silenciosa (#263 rodada 2).

    Devolve ``(pessoa | None, criada_na_importacao)``.
    """
    chave_parte = parte.chave or ''
    if not parte.criar_novo:
        if parte.pessoa_id is None:
            erros.add(
                chave_parte, 'decisao_perdida',
                'A decisão de pessoa desta parte se perdeu; revise o ato.',
            )
            return None, False
        pessoa = Pessoas.objects.filter(pk=parte.pessoa_id).first()
        if pessoa is None:
            erros.add(
                chave_parte, 'decisao_perdida',
                'A pessoa escolhida para esta parte não existe mais.',
            )
            return None, False
        return pessoa, False

    nome = (parte.nome or '').strip()
    if not nome:
        erros.add(
            f'{chave_parte}/nome', 'valor_obrigatorio',
            'O nome da parte é obrigatório para criar a pessoa.',
        )
        return None, False
    cpf = _so_digitos(parte.cpf) if parte.cpf else ''
    rg = _rg_normalizado(parte.rg)
    chave_cpf = ('cpf', cpf) if cpf else None
    chave_rg = ('rg', _normalizar_nome(nome), rg) if rg else None

    pessoa_cpf = None
    if chave_cpf is not None:
        pessoa_cpf = cache_pessoas.get(chave_cpf)
        if pessoa_cpf is None:
            pessoa_cpf = Pessoas.objects.filter(cpf=cpf).first()
    pessoa_rg = cache_pessoas.get(chave_rg) if chave_rg is not None else None

    # Checagem DEFENSIVA (#263 rodada 3): ``dados_revisados`` entrega CPF
    # ou RG por parte, nunca os dois (a linha do documento tem um destino
    # só). Fica de guarda caso o contrato da parte passe a trazer ambos.
    if (
        pessoa_cpf is not None and pessoa_rg is not None
        and pessoa_cpf.pk != pessoa_rg.pk
    ):
        erros.add(
            f'{chave_parte}/documento_identificacao/valor',
            'decisao_conflitante',
            'O CPF e o RG desta parte apontam para pessoas cadastradas '
            'diferentes; revise a identificação da parte.',
        )
        return None, False

    pessoa = pessoa_cpf or pessoa_rg
    criada = False
    if pessoa is None:
        pessoa = Pessoas(
            nome=nome, cpf=cpf or None, rg=parte.rg,
        )
        try:
            pessoa.full_clean()
        except ValidationError as exc:
            # Corrida do full_clean (rodada 6, Codex): o cadastro concorrente
            # (outra importação ou o manual, que não passa pelas travas)
            # pode commitar o MESMO CPF entre o lookup acima e a checagem de
            # unicidade — o ValidationError de unique chega ANTES do INSERT
            # e o handler de IntegrityError nunca rodaria, rejeitando o
            # lote inteiro. Mesma decisão do savepoint: reler a vencedora e
            # REUTILIZAR. Qualquer outro ValidationError segue como erro de
            # linha — o full_clean não perde validação nenhuma.
            vencedora = _vencedora_da_unicidade_cpf(exc, cpf)
            if vencedora is None:
                erros.do_modelo(
                    exc, 'dominial.Pessoas', chave_parte=chave_parte,
                )
                return None, False
            pessoa = vencedora
        else:
            try:
                # Savepoint: o CPF pode ser gravado por OUTRA importação
                # (outro documento) entre o lookup e o INSERT — a trava do
                # Documento não cobre Pessoas. Decisão D: relê a linha
                # vencedora e REUTILIZA; a unicidade de CPF nunca sobe como
                # 500 (#263 rodada 4, Greptile P1).
                with transaction.atomic():
                    pessoa.save()
            except IntegrityError:
                vencedora = (
                    Pessoas.objects.filter(cpf=cpf).first() if cpf else None
                )
                if vencedora is None:
                    raise
                pessoa = vencedora
            else:
                criada = True
    if chave_cpf is not None:
        cache_pessoas[chave_cpf] = pessoa
    if chave_rg is not None:
        cache_pessoas[chave_rg] = pessoa
    return pessoa, criada


def _vencedora_da_unicidade_cpf(exc, cpf):
    """Pessoa que o cadastro concorrente commitou, se o erro for o do CPF.

    Reconhece SÓ a mensagem de unicidade do campo cpf (código ``unique``)
    com CPF não vazio: erro de formato, de outro campo ou de texto solto
    devolve None e segue como erro de linha. O código é lido do
    ``error_dict`` — o ``message_dict`` achata as mensagens para ``str`` e
    PERDE o ``code``. A devolvida é a linha já commitada com esse CPF —
    None quando ela não existe mais, e o erro original volta a valer
    (nada é mascarado).
    """
    if not cpf:
        return None
    dicionario = getattr(exc, 'error_dict', None)
    if not isinstance(dicionario, dict):
        return None
    mensagens = dicionario.get('cpf') or ()
    if not mensagens or any(
        getattr(mensagem, 'code', None) != 'unique' for mensagem in mensagens
    ):
        return None
    return Pessoas.objects.filter(cpf=cpf).first()
