"""
Service para processamento de pessoas do lançamento
"""
from ..models import Pessoas

class LancamentoPessoaService:
    @staticmethod
    def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, pessoas_percentuais, tipo_pessoa):
        for i, nome in enumerate(pessoas_data):
            if nome and nome.strip():
                pessoa_id = pessoas_ids[i] if i < len(pessoas_ids) and pessoas_ids[i] else None
                percentual = pessoas_percentuais[i] if i < len(pessoas_percentuais) and pessoas_percentuais[i] else None
                if pessoa_id and pessoa_id.strip():
                    try:
                        pessoa = Pessoas.objects.get(id=pessoa_id)
                        if pessoa.nome != nome.strip():
                            pessoa.nome = nome.strip()
                            pessoa.save()
                    except Pessoas.DoesNotExist:
                        pessoa = Pessoas.objects.create(nome=nome.strip())
                else:
                    pessoa = Pessoas.objects.create(nome=nome.strip())
                lancamento.lancamentopessoa_set.create(
                    pessoa=pessoa,
                    tipo=tipo_pessoa,
                    percentual=float(percentual) if percentual and percentual.strip() else None
                ) 