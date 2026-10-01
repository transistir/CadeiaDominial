import json

from django.conf import settings


def maintenance_status(request):
    """Injeta o status de manutenção no contexto de todos os templates."""
    file_path = getattr(settings, 'MANUTENCAO_FILE_PATH', None) or (settings.BASE_DIR / '.maintenance.json')

    config = None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    return {
        'manutencao_ativa': bool(config and config.get('ativo')),
        'manutencao_mensagem': config.get('mensagem', '') if config else '',
        'manutencao_fim': config.get('fim_estimado', '') if config else '',
    }
