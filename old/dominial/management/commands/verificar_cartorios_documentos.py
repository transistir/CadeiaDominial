from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Documento, Lancamento
from dominial.services.lancamento_origem_service import LancamentoOrigemService


class Command(BaseCommand):
    help = 'Verifica se os cartórios dos documentos correspondem aos cartórios dos lançamentos de início de matrícula que os criaram'

    def add_arguments(self, parser):
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help='Corrigir automaticamente os cartórios inconsistentes',
        )
        parser.add_argument(
            '--documento-id',
            type=int,
            help='Verificar apenas um documento específico por ID',
        )

    def handle(self, *args, **options):
        corrigir = options['corrigir']
        documento_id = options['documento_id']
        
        self.stdout.write(self.style.SUCCESS('🔍 Iniciando verificação de cartórios dos documentos...'))
        
        # Buscar documentos para verificar
        if documento_id:
            documentos = Documento.objects.filter(id=documento_id)
            self.stdout.write(f'Verificando apenas documento ID: {documento_id}')
        else:
            documentos = Documento.objects.all()
            self.stdout.write(f'Verificando todos os {documentos.count()} documentos')
        
        documentos_inconsistentes = []
        documentos_verificados = 0
        
        for documento in documentos:
            documentos_verificados += 1
            
            # Buscar o lançamento de início de matrícula em outro documento que criou este documento
            # O lançamento deve ter origem que contenha o número deste documento
            lancamento_criador = Lancamento.objects.filter(
                tipo__tipo='inicio_matricula',
                origem__icontains=documento.numero
            ).exclude(documento=documento).select_related('documento').first()
            
            if not lancamento_criador:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Documento {documento.id} ({documento.numero}) - não encontrou lançamento de início de matrícula que o criou')
                )
                continue
            
            # Verificar se o cartório do documento corresponde ao cartório de origem do lançamento criador
            cartorio_lancamento = lancamento_criador.cartorio_origem
            cartorio_documento = documento.cartorio
            
            # Debug: mostrar informações do lançamento criador
            self.stdout.write(
                f'🔍 Debug: Documento {documento.id} ({documento.numero}) criado por lançamento {lancamento_criador.id} '
                f'do documento {lancamento_criador.documento.id} ({lancamento_criador.documento.numero}) '
                f'com origem={lancamento_criador.origem} e cartório={cartorio_lancamento}'
            )
            
            # Verificar se o cartório do documento corresponde ao cartório de origem do lançamento criador
            cartorio_lancamento = lancamento_criador.cartorio_origem
            cartorio_documento = documento.cartorio
            
            if cartorio_lancamento != cartorio_documento:
                inconsistencia = {
                    'documento_id': documento.id,
                    'documento_numero': documento.numero,
                    'cartorio_documento': cartorio_documento,
                    'cartorio_lancamento': cartorio_lancamento,
                    'lancamento_id': lancamento_criador.id,
                    'lancamento_criador': lancamento_criador
                }
                documentos_inconsistentes.append(inconsistencia)
                
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Documento {documento.id} ({documento.numero}): '
                        f'Cartório do documento: {cartorio_documento} | '
                        f'Cartório do lançamento: {cartorio_lancamento}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Documento {documento.id} ({documento.numero}): Cartório correto ({cartorio_documento})'
                    )
                )
        
        # Resumo
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'📊 RESUMO DA VERIFICAÇÃO:'))
        self.stdout.write(f'   • Documentos verificados: {documentos_verificados}')
        self.stdout.write(f'   • Documentos consistentes: {documentos_verificados - len(documentos_inconsistentes)}')
        self.stdout.write(f'   • Documentos inconsistentes: {len(documentos_inconsistentes)}')
        
        if documentos_inconsistentes:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(self.style.ERROR('📋 DOCUMENTOS INCONSISTENTES:'))
            
            for inconsistencia in documentos_inconsistentes:
                self.stdout.write(
                    f'   • Documento {inconsistencia["documento_id"]} ({inconsistencia["documento_numero"]}): '
                    f'{inconsistencia["cartorio_documento"]} → {inconsistencia["cartorio_lancamento"]}'
                )
            
            # Correção automática
            if corrigir:
                self.stdout.write('\n' + '='*80)
                self.stdout.write(self.style.WARNING('🔧 INICIANDO CORREÇÃO AUTOMÁTICA...'))
                
                with transaction.atomic():
                    documentos_corrigidos = 0
                    
                    for inconsistencia in documentos_inconsistentes:
                        documento = Documento.objects.get(id=inconsistencia['documento_id'])
                        cartorio_correto = inconsistencia['cartorio_lancamento']
                        
                        try:
                            # Verificar se já existe outro documento com o mesmo número e cartório para o mesmo imóvel
                            documento_existente = Documento.objects.filter(
                                numero=documento.numero,
                                cartorio=cartorio_correto,
                                imovel=documento.imovel
                            ).exclude(id=documento.id).first()
                            
                            if documento_existente:
                                self.stdout.write(
                                    self.style.ERROR(
                                        f'❌ ERRO: Já existe documento {documento_existente.id} ({documento.numero}) '
                                        f'com cartório {cartorio_correto} para o imóvel {documento.imovel.id}. '
                                        f'Não é possível corrigir documento {documento.id}.'
                                    )
                                )
                                continue
                            
                            # Atualizar o cartório do documento
                            documento.cartorio = cartorio_correto
                            documento.save()
                            
                            documentos_corrigidos += 1
                            
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'✅ Corrigido: Documento {documento.id} ({documento.numero}) → {cartorio_correto}'
                                )
                            )
                            
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'❌ ERRO ao corrigir documento {documento.id} ({documento.numero}): {str(e)}'
                                )
                            )
                    
                    self.stdout.write(f'\n🎉 Correção concluída! {documentos_corrigidos} documentos corrigidos.')
            else:
                self.stdout.write(
                    self.style.WARNING(
                        '\n💡 Para corrigir automaticamente, execute: '
                        'python manage.py verificar_cartorios_documentos --corrigir'
                    )
                )
        else:
            self.stdout.write(self.style.SUCCESS('\n🎉 Todos os documentos estão com cartórios consistentes!')) 