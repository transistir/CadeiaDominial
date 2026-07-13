from django.core.management.base import BaseCommand
from dominial.models import Lancamento


class Command(BaseCommand):
    help = 'Corrige lançamentos de início de matrícula para produção (SEGURO)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa em modo de teste sem fazer alterações',
        )

    def handle(self, *args, **kwargs):
        dry_run = kwargs['dry_run']
        
        if dry_run:
            self.stdout.write('=== MODO DE TESTE - NENHUMA ALTERAÇÃO SERÁ FEITA ===')
        
        self.stdout.write('=== CORREÇÃO DE LANÇAMENTOS DE INÍCIO DE MATRÍCULA ===')
        
        # Buscar lançamentos de início de matrícula que precisam ser corrigidos
        lancamentos_inicio = Lancamento.objects.filter(tipo__tipo='inicio_matricula')
        
        corrigidos = 0
        for lancamento in lancamentos_inicio:
            numero_atual = lancamento.numero_lancamento
            documento_numero = lancamento.documento.numero
            documento_tipo = lancamento.documento.tipo.tipo
            
            # Determinar o número correto baseado no tipo do documento
            if documento_tipo == 'matricula':
                # Para matrículas, se o documento não tem M, adicionar M
                if not documento_numero.startswith('M'):
                    numero_correto = f'M{documento_numero}'
                else:
                    numero_correto = documento_numero
            elif documento_tipo == 'transcricao':
                # Para transcrições, se o documento não tem T, adicionar T
                if not documento_numero.startswith('T'):
                    numero_correto = f'T{documento_numero}'
                else:
                    numero_correto = documento_numero
            else:
                # Para outros tipos, usar o número do documento como está
                numero_correto = documento_numero
            
            # Corrigir se necessário
            if numero_atual != numero_correto:
                if dry_run:
                    self.stdout.write(f'[TESTE] Corrigiria lançamento {lancamento.id}: {numero_atual} -> {numero_correto} (Documento: {documento_numero}, Tipo: {documento_tipo})')
                else:
                    self.stdout.write(f'Corrigindo lançamento {lancamento.id}: {numero_atual} -> {numero_correto} (Documento: {documento_numero}, Tipo: {documento_tipo})')
                    lancamento.numero_lancamento = numero_correto
                    lancamento.save()
                corrigidos += 1
        
        if dry_run:
            self.stdout.write(f'\n[TESTE] Total de lançamentos que seriam corrigidos: {corrigidos}')
            self.stdout.write(self.style.WARNING('Execute sem --dry-run para aplicar as correções'))
        else:
            self.stdout.write(f'\nTotal de lançamentos corrigidos: {corrigidos}')
        
        # Verificação final
        self.stdout.write('\n=== VERIFICAÇÃO FINAL ===')
        
        # Verificar lançamentos de matrícula
        lancamentos_matricula = Lancamento.objects.filter(
            tipo__tipo='inicio_matricula',
            documento__tipo__tipo='matricula'
        )
        
        self.stdout.write(f'Lançamentos de início de matrícula (documentos tipo matrícula): {lancamentos_matricula.count()}')
        for lancamento in lancamentos_matricula[:10]:  # Mostrar apenas os primeiros 10
            self.stdout.write(f'  ID: {lancamento.id}, Número: {lancamento.numero_lancamento}, Documento: {lancamento.documento.numero}')
        
        # Verificar lançamentos de transcrição
        lancamentos_transcricao = Lancamento.objects.filter(
            tipo__tipo='inicio_matricula',
            documento__tipo__tipo='transcricao'
        )
        
        self.stdout.write(f'\nLançamentos de início de matrícula (documentos tipo transcrição): {lancamentos_transcricao.count()}')
        for lancamento in lancamentos_transcricao:
            self.stdout.write(f'  ID: {lancamento.id}, Número: {lancamento.numero_lancamento}, Documento: {lancamento.documento.numero}')
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'\n[TESTE] Verificação concluída! {corrigidos} lançamentos seriam corrigidos.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'\nCorreção concluída! {corrigidos} lançamentos corrigidos.')
            ) 