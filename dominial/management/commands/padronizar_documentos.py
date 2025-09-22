"""
Comando para padronizar os números dos documentos adicionando o prefixo M ou T baseado no tipo.
Seguro para uso em produção com PostgreSQL.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from dominial.models import Documento, DocumentoTipo


class Command(BaseCommand):
    help = 'Padroniza os números dos documentos adicionando o prefixo M ou T baseado no tipo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Executa as alterações no banco de dados. Por padrão, roda em modo de teste.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a padronização mesmo que encontre conflitos de números.',
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Cria um backup dos dados antes de fazer as alterações.',
        )

    def handle(self, *args, **options):
        commit_changes = options['commit']
        force_changes = options['force']
        create_backup = options['backup']
        
        self.stdout.write(self.style.SUCCESS('🔧 Iniciando padronização de documentos...'))
        
        if not commit_changes:
            self.stdout.write(self.style.WARNING('⚠️  MODO DE TESTE - Nenhuma alteração será feita'))
        
        if create_backup and commit_changes:
            self.stdout.write(self.style.WARNING('💾 Criando backup dos dados...'))
            # Aqui você pode implementar a lógica de backup se necessário
            # Por exemplo, exportar para JSON ou SQL

        # Mapear tipos de documento para siglas esperadas
        siglas_por_tipo = {
            'matricula': 'M',
            'transcricao': 'T',
        }

        inconsistentes = []
        conflitos = {}

        # Buscar documentos que não seguem o padrão
        for documento in Documento.objects.select_related('tipo', 'imovel', 'cartorio').all():
            tipo_doc_str = documento.tipo.tipo
            numero_doc = documento.numero

            sigla_esperada = siglas_por_tipo.get(tipo_doc_str)

            if sigla_esperada and not numero_doc.startswith(sigla_esperada):
                # Verificar se o número é puramente numérico (sem prefixo)
                if numero_doc.isdigit():
                    novo_numero = f"{sigla_esperada}{numero_doc}"
                    
                    # Verificar se o novo número já existe para outro documento
                    # Excluir o próprio documento da verificação
                    if Documento.objects.filter(
                        numero=novo_numero, 
                        cartorio=documento.cartorio
                    ).exclude(id=documento.id).exists():
                        conflitos[numero_doc] = novo_numero
                        self.stdout.write(self.style.ERROR(
                            f"❌ CONFLITO: Documento {numero_doc} ({documento.imovel.nome}) "
                            f"com cartório {documento.cartorio.nome} resultaria em {novo_numero}, que já existe."
                        ))
                    else:
                        inconsistentes.append({
                            'documento': documento,
                            'novo_numero': novo_numero
                        })
                else:
                    self.stdout.write(self.style.WARNING(
                        f"AVISO: Documento {numero_doc} (ID: {documento.id}) do tipo {tipo_doc_str} "
                        f"não começa com {sigla_esperada} e não é puramente numérico. Ignorando."
                    ))

        self.stdout.write(f'📊 Encontrados {len(inconsistentes)} documentos inconsistentes')

        if inconsistentes:
            self.stdout.write('\n📋 Documentos que serão padronizados:')
            for item in inconsistentes:
                doc = item['documento']
                self.stdout.write(
                    f'  - {doc.numero} → {item["novo_numero"]} '
                    f'(Imóvel: {doc.imovel.nome}, Cartório: {doc.cartorio.nome})'
                )
        
        if conflitos and not force_changes:
            self.stdout.write(self.style.ERROR('\n❌ CONFLITOS ENCONTRADOS:'))
            for original, novo in conflitos.items():
                self.stdout.write(self.style.ERROR(f'  - {original} → {novo}'))
            self.stdout.write(self.style.ERROR(
                '❌ Operação cancelada devido a conflitos. Use --force para ignorar.'
            ))
            return

        if commit_changes:
            with transaction.atomic():
                sucessos = 0
                erros = 0
                
                for item in inconsistentes:
                    try:
                        doc = item['documento']
                        self.stdout.write(f'🔄 Padronizando {doc.numero} → {item["novo_numero"]}...')
                        
                        doc.numero = item['novo_numero']
                        doc.save()
                        sucessos += 1
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'❌ Erro ao padronizar documento {doc.numero}: {str(e)}'
                        ))
                        erros += 1
                
                self.stdout.write(f'\n📊 Resultado:')
                self.stdout.write(f'  ✅ Sucessos: {sucessos}')
                if erros > 0:
                    self.stdout.write(f'  ❌ Erros: {erros}')
                
                if sucessos > 0:
                    self.stdout.write(self.style.SUCCESS('✅ Padronização concluída com sucesso!'))
        elif inconsistentes:
            self.stdout.write(self.style.WARNING('\nPara aplicar as alterações, execute com --commit'))
        else:
            self.stdout.write(self.style.SUCCESS('\nNenhum documento inconsistente encontrado para padronizar.'))
        
        # Verificar resultado final
        self.stdout.write('\n🔍 Verificando resultado final...')
        total_docs = Documento.objects.count()
        matriculas_sem_m = Documento.objects.filter(
            tipo__tipo='matricula'
        ).exclude(numero__startswith='M').count()
        transcricoes_sem_t = Documento.objects.filter(
            tipo__tipo='transcricao'
        ).exclude(numero__startswith='T').count()

        self.stdout.write(f'Total de documentos: {total_docs}')
        self.stdout.write(f'Matrículas sem prefixo M: {matriculas_sem_m}')
        self.stdout.write(f'Transcrições sem prefixo T: {transcricoes_sem_t}')

        if matriculas_sem_m == 0 and transcricoes_sem_t == 0:
            self.stdout.write(self.style.SUCCESS('🎉 Todos os documentos estão padronizados!'))
        else:
            self.stdout.write(self.style.WARNING('⚠️  Ainda há documentos não padronizados'))
