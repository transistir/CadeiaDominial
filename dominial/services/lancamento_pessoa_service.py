"""
Service para processamento de pessoas em lançamentos
"""

from ..models import Lancamento, LancamentoPessoa, Pessoas


class LancamentoPessoaService:
    """
    Service para processar pessoas em lançamentos
    """

    @staticmethod
    def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, tipo_pessoa):
        """
        Processa pessoas do lançamento.

        Importante (issue #213): este método NUNCA altera o cadastro global de
        `Pessoas`. Quando o texto digitado diverge do nome da pessoa vinculada
        pelo autocomplete (caso típico de um registro `Pessoas` com nome
        composto, ex. "João, José e Paulo"), a linha passa a apontar para o
        registro de nome exato (`nome__iexact`), criando-o se necessário — o
        registro composto original permanece intocado. Cada nome digitado
        gera sua própria linha de `LancamentoPessoa`.
        """
        for i, nome in enumerate(pessoas_data):
            if not (nome and nome.strip()):
                continue

            nome_clean = nome.strip()
            pessoa_id = pessoas_ids[i] if i < len(pessoas_ids) and pessoas_ids[i] else None

            pessoa_vinculada = None
            if pessoa_id and str(pessoa_id).strip():
                try:
                    pessoa_vinculada = Pessoas.objects.filter(id=pessoa_id).first()
                except (ValueError, TypeError):
                    # pessoa_id não numérico/inválido: trata como "não encontrado".
                    pessoa_vinculada = None

            if pessoa_vinculada is not None and pessoa_vinculada.nome.strip().lower() == nome_clean.lower():
                # Nome digitado igual ao nome vinculado: reaproveita o registro existente.
                pessoa = pessoa_vinculada
            else:
                # Sem pessoa_id, id inexistente, ou texto divergente do vínculo
                # (registro composto): resolve pelo nome exato digitado.
                pessoa = Pessoas.objects.filter(nome__iexact=nome_clean).first()
                if not pessoa:
                    pessoa = Pessoas.objects.create(nome=nome_clean)

            # Uma linha própria por nome digitado.
            LancamentoPessoa.objects.update_or_create(
                lancamento=lancamento,
                pessoa=pessoa,
                tipo=tipo_pessoa,
                defaults={'nome_digitado': nome_clean}
            )
