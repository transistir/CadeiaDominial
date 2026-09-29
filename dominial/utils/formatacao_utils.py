"""
Utilitários para formatação de dados
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.utils.html import escape
from django.utils.safestring import mark_safe


_PREFIXO_CRI = "cartorio de registro de imoveis"

_PADROES_FIM_CADEIA = (
    'Destacamento Público:',
    'Outra:',
    'Sem Origem:',
    'FIM_CADEIA',
)


def _eh_fim_cadeia(parte):
    """Mesmo critério usado no laço de formatação, para não duplicar a lista."""
    return any(padrao in parte for padrao in _PADROES_FIM_CADEIA)


def _chaves_texto_livre(parte):
    """
    Identidades (tipo, número normalizado) que um texto sem prefixo M/T
    citaria, uma por número presente no texto.

    Espelho deliberado da VALIDAÇÃO 4 (hierarquia_utils.py); se a VALIDAÇÃO 4
    mudar, divergir aqui pode casar menos ou de forma diferente — manter os
    dois em sincronia.
    """
    # Import tardio evita o ciclo models -> utils -> services -> utils.
    from .documento_identidade_utils import normalizar_numero_documento

    tipo = (
        'transcricao'
        if 'transcrição' in parte.lower() or 'transcricao' in parte.lower()
        else 'matricula'
    )
    chaves = set()
    for numero in re.findall(r'\d+', parte):
        try:
            chaves.add((tipo, normalizar_numero_documento(numero, tipo)))
        except (TypeError, ValueError):
            continue
    return chaves


def _cartorios_por_posicao(lancamento, origens):
    """
    Cartório de cada origem normal de ``origens`` (mesma lista e mesmos
    índices do laço de ``formatar_origem_completa``), resolvido pelas linhas
    ``LancamentoOrigem`` da posição — nunca por ``lancamento.cartorio_origem``,
    que é o cartório da PRIMEIRA origem válida do formulário, não o da
    posição 0 (#229).

    Devolve ``None`` (sinal para o legado) quando o lançamento não está
    salvo, quando todas as partes são fim de cadeia ou quando não há nenhuma
    linha estruturada. Nos outros casos devolve uma lista alinhada a
    ``origens``: cartório resolvido ou ``None`` em cada posição.
    """
    # Imports tardios evitam o ciclo models -> utils -> services -> utils
    # (mesmo padrão de hierarquia_utils.py:21-28).
    from ..models import Lancamento
    from ..services.lancamento_origem_leitura_service import (
        LancamentoOrigemLeituraService,
    )
    from ..services.lancamento_origem_service import LancamentoOrigemService

    if not isinstance(lancamento, Lancamento) or lancamento.pk is None:
        return None
    if all(_eh_fim_cadeia(origem) for origem in origens):
        return None

    linhas = LancamentoOrigemLeituraService.linhas_estruturadas(lancamento)
    if not linhas:
        return None

    linhas_por_posicao = {linha.indice_origem: linha for linha in linhas}

    cartorios = []
    for indice, parte in enumerate(origens):
        if _eh_fim_cadeia(parte):
            cartorios.append(None)
            continue

        chave = LancamentoOrigemService._chave_identidade_texto(parte)
        if chave:
            linha, _ambiguo, _ambiguo_registrada = (
                LancamentoOrigemService.resolver_linha_por_posicao(
                    linhas, parte, indice, origens
                )
            )
        else:
            linha = linhas_por_posicao.get(indice)
            if linha and (
                linha.tipo_documento, linha.numero_normalizado
            ) not in _chaves_texto_livre(parte):
                linha = None

        cartorios.append(linha.cartorio if linha else None)

    return cartorios


def _classificacao_fim_cadeia_display(classificacao):
    """Converte classificações persistidas no rótulo vigente."""
    chave = ''.join(
        caractere
        for caractere in unicodedata.normalize('NFD', classificacao)
        if unicodedata.category(caractere) != 'Mn'
    ).lower().replace(' ', '_')
    labels = {
        'origem_lidima': 'Origem Lídima',
        'origem_identificada': 'Origem Lídima',
        'sem_origem': 'Sem Origem',
        'situacao_inconclusa': 'Situação Inconclusa',
        'inconclusa': 'Situação Inconclusa',
    }
    return labels.get(chave, classificacao)


def formatar_origem_completa(
    lancamento, separador='\n', escapar_html=False
):
    """
    Formata a origem de um lançamento para exibição em exportações.

    A regra é compartilhada pelo PDF/HTML e pelo Excel. O chamador informa
    o separador adequado ao meio: ``<br>`` no filtro de template e quebra de
    linha real (o padrão) no XLSX. Com ``escapar_html=True``, cada texto
    montado é escapado antes que somente o resultado final seja marcado como
    seguro; o separador é tratado como markup interno confiável.
    """
    if not lancamento.origem:
        return '-'

    origens_formatadas = []
    origens = [o.strip() for o in lancamento.origem.split(';') if o.strip()]
    cartorios_por_posicao = _cartorios_por_posicao(lancamento, origens)

    for indice, origem in enumerate(origens):
        is_fim_cadeia = _eh_fim_cadeia(origem)

        if is_fim_cadeia:
            if 'Destacamento Público:' in origem:
                # Formato: Destacamento Público:Sigla:Classificação
                partes = origem.split(':')
                if len(partes) >= 2:
                    sigla = partes[1].strip() if len(partes) > 1 else ''
                    classificacao = partes[2].strip() if len(partes) > 2 else ''
                    classificacao = _classificacao_fim_cadeia_display(classificacao)
                    if sigla:
                        origem_formatada = f"Destacamento Público : {sigla}"
                        if classificacao:
                            origem_formatada += f" ({classificacao})"
                    else:
                        origem_formatada = "Destacamento Público"
                else:
                    origem_formatada = origem
            elif 'Outra:' in origem:
                # Formato: Outra:Especificação:Classificação
                partes = origem.split(':')
                if len(partes) >= 2:
                    especificacao = partes[1].strip() if len(partes) > 1 else ''
                    classificacao = partes[2].strip() if len(partes) > 2 else ''
                    classificacao = _classificacao_fim_cadeia_display(classificacao)
                    if especificacao:
                        origem_formatada = f"Outra : {especificacao}"
                        if classificacao:
                            origem_formatada += f" ({classificacao})"
                    else:
                        origem_formatada = "Outra"
                else:
                    origem_formatada = origem
            elif 'Sem Origem:' in origem:
                # Formato: Sem Origem::Classificação
                partes = origem.split(':')
                if len(partes) >= 3:
                    classificacao = partes[2].strip() if len(partes) > 2 else ''
                    classificacao = _classificacao_fim_cadeia_display(classificacao)
                    origem_formatada = "Sem Origem"
                    if classificacao:
                        origem_formatada += f" ({classificacao})"
                else:
                    origem_formatada = "Sem Origem"
            else:
                # O formato legado FIM_CADEIA permanece inalterado.
                origem_formatada = origem

            origens_formatadas.append(origem_formatada)
        else:
            if cartorios_por_posicao is not None:
                cartorio = cartorios_por_posicao[indice]
                cartorio_nome = cartorio.nome if cartorio else ''
            else:
                cartorio_nome = (
                    lancamento.cartorio_origem.nome
                    if lancamento.cartorio_origem
                    else ''
                )
            if cartorio_nome:
                origem_formatada = f"{origem} ({cartorio_nome})"
            else:
                origem_formatada = origem
            origens_formatadas.append(origem_formatada)

    if escapar_html:
        partes_escapadas = [str(escape(origem)) for origem in origens_formatadas]
        return mark_safe(separador.join(partes_escapadas))

    return separador.join(origens_formatadas)


def _remover_acentos_preservando_posicao(texto):
    """
    Remove acentos mantendo o mapeamento de posição: cada caractere do texto
    de entrada vira exatamente um caractere no resultado. Assim o índice de
    fim de um prefixo casado no texto sem acento vale também no texto de
    entrada (evitando o descasamento de comprimento de uma normalização NFKD
    ingênua).

    Espera receber texto já em NFC — ver `abreviar_cartorio`. Sequências
    combinantes (base + marca) que sobrarem são tratadas como uma unidade:
    a marca combinante isolada é mantida na saída (preservando a posição),
    mas o `.startswith` do prefixo já terá casado pelo caractere base.
    """
    resultado = []
    for caractere in texto:
        base = ''.join(
            c
            for c in unicodedata.normalize("NFKD", caractere)
            if not unicodedata.combining(c)
        )
        resultado.append(base if len(base) == 1 else caractere)
    return ''.join(resultado)


def abreviar_cartorio(nome):
    """
    Substitui o prefixo "Cartório de Registro de Imóveis" pela sigla "CRI".

    Usado APENAS nas exportações (Excel e PDF completo) — a UI de cadastro
    mantém o nome por extenso (issue #50).

    - Falsy (None, "") retorna inalterado.
    - Só o prefixo exato casa (variantes como "do Registro" não são tocadas).
    - NFC e NFD do mesmo texto produzem o mesmo resultado (o texto é
      normalizado para NFC antes de comparar).
    - Exige fronteira de palavra após "Imóveis" (fim da string ou caractere
      não-alfabético): "...ImóveisXYZ" NÃO é abreviado.
    - A caixa e os acentos do restante do nome são preservados.
    """
    if not nome:
        return nome

    nome_nfc = unicodedata.normalize("NFC", nome)
    normalizado = _remover_acentos_preservando_posicao(nome_nfc).lower()
    if not normalizado.startswith(_PREFIXO_CRI):
        return nome

    fim = len(_PREFIXO_CRI)
    if fim < len(normalizado) and normalizado[fim].isalpha():
        # Sem fronteira de palavra depois de "Imóveis" — não abrevia.
        return nome

    resto = nome_nfc[fim:].lstrip()
    return f"CRI {resto}".rstrip()


def formatar_cpf(cpf):
    """
    Formata um CPF no padrão XXX.XXX.XXX-XX
    """
    if not cpf:
        return ""
    
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        return cpf
    
    # Formata o CPF
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def formatar_telefone(telefone):
    """
    Formata um telefone no padrão (XX) XXXXX-XXXX
    """
    if not telefone:
        return ""
    
    # Remove caracteres não numéricos
    telefone = ''.join(filter(str.isdigit, telefone))
    
    # Verifica se tem 10 ou 11 dígitos
    if len(telefone) == 10:
        return f"({telefone[:2]}) {telefone[2:6]}-{telefone[6:]}"
    elif len(telefone) == 11:
        return f"({telefone[:2]}) {telefone[2:7]}-{telefone[7:]}"
    else:
        return telefone


def formatar_valor_monetario(valor):
    """
    Formata um valor monetário no padrão brasileiro
    """
    if valor is None:
        return "R$ 0,00"
    
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def formatar_area(area):
    """
    Formata uma área em hectares
    """
    if area is None:
        return "0,00 ha"

    try:
        return f"{area:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00 ha"


def formatar_area_ha(area, padrao="-"):
    """
    Formata o campo `Lancamento.area` no padrão brasileiro, com 4 casas
    decimais, vírgula como separador decimal e sem separador de milhar
    (ex.: "1234,5678"). NÃO adiciona sufixo " ha" — usada na coluna
    "Área (ha)" das tabelas HTML da Cadeia Dominial Geral e do Documento
    Detalhado (issue #13), cujo cabeçalho já indica a unidade. É só
    formatação de exibição: o valor persistido no banco não é alterado.

    - `None` ou string vazia retornam `padrao` (default "-").
    - Valor que, convertido, é igual a zero (ex.: `Decimal("0")`,
      `Decimal("0.0000")`, `0`, `0.0`, `"0"`) também retorna `padrao`:
      por decisão de produto (Hiure, 10/09/2026) área zerada é exibida
      como "-", e não como "0,0000" (issue #13).
    - Valor não convertível para número (ex.: texto não numérico) também
      retorna `padrao`, sem levantar exceção.
    - A conversão usa `Decimal(str(valor))` para evitar ruído binário de
      `float` (mesma técnica de `formatar_area`/`formatar_valor_monetario`,
      acima).
    """
    if area is None or area == "":
        return padrao

    try:
        valor = Decimal(str(area))
    except (InvalidOperation, TypeError, ValueError):
        return padrao

    if not valor.is_finite() or valor == 0:
        return padrao

    return f"{valor:.4f}".replace(".", ",")


def normalizar_texto_opcional(valor, padrao=None):
    """Substitui valores textuais ausentes ou o sentinela legado 'None'."""
    if valor is None:
        return padrao

    if isinstance(valor, str):
        valor_comparacao = valor.strip()
        if not valor_comparacao or valor_comparacao == "None":
            return padrao

    return valor
