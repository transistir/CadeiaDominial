from django.core.management.base import BaseCommand
from dominial.models import Alteracoes, Documento, Lancamento, DocumentoTipo, LancamentoTipo
from django.utils import timezone

class Command(BaseCommand):
    help = 'Migra dados de Alteracoes para Documento e Lancamento'

    def handle(self, *args, **kwargs):
        # Criar tipos de documento e lançamento se não existirem
        doc_tipo, _ = DocumentoTipo.objects.get_or_create(tipo='transmissao')
        lanc_tipo, _ = LancamentoTipo.objects.get_or_create(tipo='registro')

        # Migrar dados
        for alteracao in Alteracoes.objects.all():
            # Gerar número único para o documento
            numero = f"DOC-{timezone.now().timestamp()}"

            # Criar Documento
            documento = Documento.objects.create(
                imovel=alteracao.imovel_id,
                tipo=doc_tipo,
                numero=numero,
                data=alteracao.data_alteracao or alteracao.data_cadastro,
                cartorio=alteracao.cartorio,
                livro=alteracao.livro or "",
                folha=alteracao.folha or "",
                observacoes=alteracao.observacoes
            )

            # Criar Lancamento
            Lancamento.objects.create(
                tipo=lanc_tipo,
                documento=documento,
                data=alteracao.data_alteracao or alteracao.data_cadastro,
                transmitente=alteracao.transmitente,
                adquirente=alteracao.adquirente,
                valor_transacao=alteracao.valor_transacao,
                area=alteracao.area,
                detalhes=alteracao.observacoes
            )

        self.stdout.write(self.style.SUCCESS('Migração concluída com sucesso!')) 