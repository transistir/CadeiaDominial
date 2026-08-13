"""
Management command para controlar o modo de manutenção.

Uso:
    python manage.py manutencao --on --mensagem "Voltamos às 15h" --duracao 2
    python manage.py manutencao --off
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Liga ou desliga o modo de manutenção do sistema'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--on',
            action='store_true',
            help='Liga o modo de manutenção',
        )
        group.add_argument(
            '--off',
            action='store_true',
            help='Desliga o modo de manutenção',
        )
        parser.add_argument(
            '--mensagem',
            type=str,
            default='Sistema em manutenção. Tente novamente em alguns minutos.',
            help='Mensagem exibida para os usuários',
        )
        parser.add_argument(
            '--duracao',
            type=float,
            default=1.0,
            help='Duração estimada da manutenção em horas (default: 1)',
        )

    def handle(self, *args, **options):
        file_path = Path(getattr(
            settings,
            'MANUTENCAO_FILE_PATH',
            settings.BASE_DIR / '.maintenance.json'
        ))

        if options['on']:
            inicio = datetime.now()
            fim = inicio + timedelta(hours=options['duracao'])

            config = {
                'ativo': True,
                'mensagem': options['mensagem'],
                'inicio': inicio.isoformat(),
                'fim_estimado': fim.strftime('%H:%M'),
            }
            file_path.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ Modo de manutenção ATIVADO.\n'
                f'  Mensagem: {config["mensagem"]}\n'
                f'  Fim estimado: {config["fim_estimado"]}\n'
                f'  Arquivo: {file_path}\n'
                f'  Usuários comuns não podem criar/editar/excluir registros.\n'
                f'  Superusers mantêm acesso total.\n'
                f'  Para desligar: python manage.py manutencao --off'
            ))

        elif options['off']:
            if file_path.exists():
                file_path.unlink()
                self.stdout.write(self.style.SUCCESS(
                    '✓ Modo de manutenção DESATIVADO.\n'
                    f'  Arquivo removido: {file_path}\n'
                    f'  Sistema voltou ao funcionamento normal.'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    'Modo de manutenção já estava desativado (arquivo não encontrado).'
                ))
