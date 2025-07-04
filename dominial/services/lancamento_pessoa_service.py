"""
Service para processamento de pessoas do lançamento
"""
from ..models import Pessoas

class LancamentoPessoaService:
    @staticmethod
    def processar_pessoas_lancamento(lancamento, pessoas_data, pessoas_ids, tipo_pessoa):
        for i, nome in enumerate(pessoas_data):
            if nome and nome.strip():
                pessoa_id = pessoas_ids[i] if i < len(pessoas_ids) and pessoas_ids[i] else None
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
                
                # Usar lancamento.pessoas.create() em vez de lancamentopessoa_set.create()
                lancamento.pessoas.create(
                    pessoa=pessoa,
                    tipo=tipo_pessoa,
                    nome_digitado=nome.strip() if not pessoa_id else None
                ) 