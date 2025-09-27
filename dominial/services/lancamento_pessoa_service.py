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
        Processa pessoas do lançamento
        """
        for i, nome in enumerate(pessoas_data):
            if nome and nome.strip():
                nome_clean = nome.strip()
                pessoa_id = pessoas_ids[i] if i < len(pessoas_ids) and pessoas_ids[i] else None
                
                if pessoa_id and pessoa_id.strip():
                    # Se foi selecionada uma pessoa existente via autocomplete
                    try:
                        pessoa = Pessoas.objects.get(id=pessoa_id)
                        # Atualizar nome se foi alterado
                        if pessoa.nome != nome_clean:
                            pessoa.nome = nome_clean
                            pessoa.save()
                    except Pessoas.DoesNotExist:
                        # Se o ID não existe, procurar por nome ou criar nova
                        pessoa = Pessoas.objects.filter(nome__iexact=nome_clean).first()
                        if not pessoa:
                            pessoa = Pessoas.objects.create(nome=nome_clean)
                else:
                    # Se não foi selecionada pessoa existente, procurar por nome ou criar nova
                    pessoa = Pessoas.objects.filter(nome__iexact=nome_clean).first()
                    if not pessoa:
                        pessoa = Pessoas.objects.create(nome=nome_clean)
                
                # Criar ou atualizar relacionamento LancamentoPessoa
                lancamento_pessoa, created = LancamentoPessoa.objects.get_or_create(
                    lancamento=lancamento,
                    pessoa=pessoa,
                    tipo=tipo_pessoa,
                    defaults={'nome_digitado': nome_clean}
                )
                
                if not created:
                    # Atualizar nome digitado se já existe
                    lancamento_pessoa.nome_digitado = nome_clean
                    lancamento_pessoa.save()
