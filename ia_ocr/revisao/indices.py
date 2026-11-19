"""Índices em memória para o matching determinístico (I-5)."""

from dominial.models import Cartorios, Pessoas

from .estruturas import _normalizar_nome, _so_digitos


# ---------------------------------------------------------------------------
# Matching determinístico (I-5, §2.A): camada Python, nunca do modelo.
# ---------------------------------------------------------------------------

def _cpf_utilizavel(documento_tipo, documento_valor):
    """Dígitos do CPF quando o documento casa por documento; senão ``None``.

    Só CPF com EXATAMENTE 11 dígitos casa por documento. CPF mascarado
    (contém ``*``/``X``) ou com menos de 11 dígitos, e qualquer outro tipo
    (CNPJ, CGC, RG, OUTRO), nunca casam por documento — documento
    incompleto não é identidade (§party: nunca completar dígitos
    mascarados).
    """
    if documento_tipo != 'CPF' or not isinstance(documento_valor, str):
        return None
    if '*' in documento_valor or 'x' in documento_valor.lower():
        return None
    digitos = _so_digitos(documento_valor)
    return digitos if len(digitos) == 11 else None


class IndicePessoas:
    """Índice de ``Pessoas`` em memória: UMA query na construção.

    ``values_list('id', 'nome', 'cpf')`` uma única vez; todo ``match`` é
    puro, sem banco.
    """

    def __init__(self):
        self._por_nome = {}
        self._por_cpf = {}
        for pessoa_id, nome, cpf in Pessoas.objects.values_list(
            'id', 'nome', 'cpf'
        ):
            chave = _normalizar_nome(nome)
            if chave:
                self._por_nome.setdefault(chave, []).append(pessoa_id)
            digitos = _so_digitos(cpf)
            if len(digitos) == 11:
                self._por_cpf.setdefault(digitos, []).append(pessoa_id)

    def match(self, nome, documento_tipo=None, documento_valor=None):
        """``(escolhido_id|None, candidatos)``: CPF exato primeiro, nome depois.

        CPF utilizável (11 dígitos, sem máscara) casa por ``cpf`` exato:
        único → escolhido; vários → candidatos (humano decide). CPF que não
        casa ninguém — assim como CPF mascarado/incompleto ou
        CNPJ/CGC/OUTRO — cai no nome normalizado: 1 → escolhido; >1 →
        candidatos; 0 → ``(None, [])``. Matching sugere, nunca adivinha:
        a escolha é do revisor.
        """
        digitos = _cpf_utilizavel(documento_tipo, documento_valor)
        if digitos is not None:
            ids = self._por_cpf.get(digitos, [])
            if len(ids) == 1:
                return ids[0], []
            if ids:
                return None, ids
        chave = _normalizar_nome(nome)
        if not chave:
            return None, []
        ids = self._por_nome.get(chave, [])
        if len(ids) == 1:
            return ids[0], []
        return None, ids


class IndiceCartorios:
    """Índice de ``Cartorios`` em memória: UMA query na construção.

    ``values_list('id', 'nome', 'cidade', 'estado')`` uma única vez; todo
    ``match`` é puro, sem banco.
    """

    def __init__(self):
        self._por_nome = {}
        self._por_cidade = {}
        # Estágios de UF e lista completa do fallback (#315): (nome, id, uf).
        self._todos = []
        for cartorio_id, nome, cidade, estado in Cartorios.objects.values_list(
            'id', 'nome', 'cidade', 'estado'
        ):
            uf = (estado or '').strip().upper()
            cidade_chave = _normalizar_nome(cidade)
            if cidade_chave:
                self._por_cidade.setdefault(cidade_chave, []).append(
                    (nome or '', cartorio_id, uf)
                )
            chave = _normalizar_nome(nome)
            if chave:
                self._por_nome.setdefault(chave, []).append(
                    (cartorio_id, cidade_chave, uf)
                )
            self._todos.append((nome or '', cartorio_id, uf))

    def ids_da_cidade(self, cidade, uf=None, limite=None):
        """Ids dos cartórios da cidade (sem acento/caixa), por nome.

        ``uf`` informada exclui homônimos de outro estado.
        """
        entradas = sorted(
            (
                entrada
                for entrada in self._por_cidade.get(
                    _normalizar_nome(cidade), [],
                )
                if not uf or entrada[2] == uf
            ),
            key=lambda entrada: (entrada[0], entrada[1]),
        )
        ids = [cartorio_id for _nome, cartorio_id, _uf in entradas]
        return ids[:limite] if limite else ids

    def ids_da_uf(self, uf, limite=None):
        """Ids dos cartórios da UF, em ordem determinística de (nome, id).

        Estágio do fallback (#315) quando a cidade da comarca não está no
        índice. UF vazia/não informada não filtra ninguém: devolve ``[]``
        para o estágio cair para a lista completa.
        """
        uf_chave = (uf or '').strip().upper()
        if not uf_chave:
            return []
        entradas = sorted(
            (entrada for entrada in self._todos if entrada[2] == uf_chave),
            key=lambda entrada: (entrada[0], entrada[1]),
        )
        ids = [cartorio_id for _nome, cartorio_id, _uf in entradas]
        return ids[:limite] if limite else ids

    def ids_de_todos(self, limite=None):
        """Ids de todos os cartórios, em ordem determinística de (nome, id).

        Último estágio do fallback (#315): com o índice povoado, o seletor
        de cartório nunca fica vazio.
        """
        entradas = sorted(
            self._todos, key=lambda entrada: (entrada[0], entrada[1]),
        )
        ids = [cartorio_id for _nome, cartorio_id, _uf in entradas]
        return ids[:limite] if limite else ids

    def match(self, nome, cidade=None, uf=None):
        """``(escolhido_id|None, candidatos)`` por nome normalizado + cidade.

        ``uf`` informada descarta cartório de outro estado.

        Cidade informada filtra: cidade divergente — ou cartório sem cidade
        para confirmar — não casa (homônimo de outro município é outro
        cartório). Sem cidade, vale só o nome. 1 → escolhido; >1 →
        candidatos; 0 → ``(None, [])``.
        """
        chave = _normalizar_nome(nome)
        if not chave:
            return None, []
        entradas = self._por_nome.get(chave, [])
        cidade_chave = _normalizar_nome(cidade)
        if cidade_chave:
            entradas = [
                entrada for entrada in entradas
                if entrada[1] == cidade_chave
            ]
        if uf:
            entradas = [entrada for entrada in entradas if entrada[2] == uf]
        ids = [cartorio_id for cartorio_id, _cidade, _uf in entradas]
        if len(ids) == 1:
            return ids[0], []
        return None, ids
