import json
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from dominial.models import Lancamento, LancamentoOrigem
from dominial.utils.documento_identidade_utils import normalizar_numero_documento


PADROES_FIM_CADEIA = (
    'Destacamento Público:',
    'Outra:',
    'Sem Origem:',
    'FIM_CADEIA',
)


class Command(BaseCommand):
    help = (
        'Migra origens textuais históricas inequívocas para LancamentoOrigem, '
        'sem alterar o campo legado.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas relata o que seria convertido, sem executar escrita.',
        )
        parser.add_argument(
            '--lancamento-id',
            type=int,
            help='Restringe a análise a um lançamento.',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Emite o relatório em JSON.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        queryset = (
            Lancamento.objects.exclude(origem__isnull=True)
            .exclude(origem='')
            .prefetch_related('origens_estruturadas')
            .order_by('id')
        )
        if options.get('lancamento_id'):
            queryset = queryset.filter(pk=options['lancamento_id'])

        relatorio = self._novo_relatorio(dry_run)

        if dry_run:
            for lancamento in queryset:
                self._processar_lancamento(lancamento, relatorio, gravar=False)
        else:
            with transaction.atomic():
                for lancamento in queryset.select_for_update():
                    self._processar_lancamento(lancamento, relatorio, gravar=True)

        self._emitir_relatorio(relatorio, options['json'])

    @staticmethod
    def _novo_relatorio(dry_run):
        return {
            'modo': 'dry-run' if dry_run else 'execucao',
            'total_analisados': 0,
            'convertiveis': 0,
            'convertidos': 0,
            'ja_estruturados': 0,
            'ambiguos': 0,
            'invalidos': 0,
            'sem_cartorio': 0,
            'fim_cadeia': 0,
            'ids': {
                'convertiveis': [],
                'convertidos': [],
                'ja_estruturados': [],
                'ambiguos': [],
                'invalidos': [],
                'sem_cartorio': [],
                'fim_cadeia': [],
            },
        }

    def _processar_lancamento(self, lancamento, relatorio, gravar):
        relatorio['total_analisados'] += 1
        existentes = list(lancamento.origens_estruturadas.all())
        if existentes:
            self._registrar(relatorio, 'ja_estruturados', lancamento.pk)
            return

        partes = [parte.strip() for parte in lancamento.origem.split(';') if parte.strip()]
        if partes and all(self._is_fim_cadeia(parte) for parte in partes):
            self._registrar(relatorio, 'fim_cadeia', lancamento.pk)
            return
        if len(partes) != 1 or self._is_fim_cadeia(partes[0]):
            self._registrar(relatorio, 'ambiguos', lancamento.pk)
            return
        if not lancamento.cartorio_origem_id:
            self._registrar(relatorio, 'sem_cartorio', lancamento.pk)
            return

        identidade = self._extrair_identidade_direta(partes[0])
        if identidade is None:
            self._registrar(relatorio, 'invalidos', lancamento.pk)
            return

        tipo_documento, numero = identidade
        if not gravar:
            self._registrar(relatorio, 'convertiveis', lancamento.pk)
            return

        origem = LancamentoOrigem(
            lancamento=lancamento,
            indice_origem=0,
            tipo_documento=tipo_documento,
            numero=numero,
            cartorio_id=lancamento.cartorio_origem_id,
            livro=self._normalizar_metadado(lancamento.livro_origem),
            folha=self._normalizar_metadado(lancamento.folha_origem),
        )
        origem.full_clean(exclude=['numero_normalizado'])
        origem.save()
        self._registrar(relatorio, 'convertidos', lancamento.pk)

    @staticmethod
    def _extrair_identidade_direta(texto):
        numero = texto.strip()
        prefixado = re.match(r'^([MT])\s*\d', numero, re.IGNORECASE)
        if prefixado:
            tipo_documento = (
                'matricula'
                if prefixado.group(1).upper() == 'M'
                else 'transcricao'
            )
        elif re.fullmatch(r'\d+', numero):
            tipo_documento = 'matricula'
        else:
            return None

        try:
            normalizar_numero_documento(numero, tipo_documento)
        except (TypeError, ValueError):
            return None
        return tipo_documento, numero

    @staticmethod
    def _is_fim_cadeia(texto):
        return any(padrao in texto for padrao in PADROES_FIM_CADEIA)

    @staticmethod
    def _normalizar_metadado(valor):
        return valor.strip() if isinstance(valor, str) and valor.strip() else None

    @staticmethod
    def _registrar(relatorio, categoria, lancamento_id):
        relatorio[categoria] += 1
        relatorio['ids'][categoria].append(lancamento_id)

    def _emitir_relatorio(self, relatorio, como_json):
        if como_json:
            self.stdout.write(json.dumps(relatorio, ensure_ascii=False, sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Modo: {relatorio['modo']} | "
                f"analisados={relatorio['total_analisados']} | "
                f"convertíveis={relatorio['convertiveis']} | "
                f"convertidos={relatorio['convertidos']} | "
                f"já estruturados={relatorio['ja_estruturados']}"
            )
        )
        self.stdout.write(
            f"Não convertidos: ambíguos={relatorio['ambiguos']}, "
            f"inválidos={relatorio['invalidos']}, "
            f"sem cartório={relatorio['sem_cartorio']}, "
            f"fim de cadeia={relatorio['fim_cadeia']}"
        )
