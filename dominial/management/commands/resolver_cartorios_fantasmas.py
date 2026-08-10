"""Resolver cartórios fantasmas (issue #110).

Aplica a decisão contida em um CSV gerado pelo `relatorio_cartorios_suspeitos`
(ou manualmente) e reatribui todas as FKs dos cartórios-fantasma para os
cartórios canônicos correspondentes. Marca os fantasmas como soft-deletados
(`deleted_at = now()`) e registra a operação em `CartorioMergeLog` (auditoria
irreversível por merge).

Decisões de segurança (plano v2, issue #110):
  - Advisory lock 0xCA21 (PostgreSQL) garante execução única.
  - Backup S3 é gate obrigatório para `--apply` em prod (validado por
    `BACKUP_VERIFIED` no env ou flag `--skip-backup-check`).
  - SHA-256 do `decisao.csv` é registrado em cada linha de log.
  - Validação CRI→CRI: cartórios-fantasma CRI só podem ser mergeados com CRI.
  - Sem `MAINTENANCE_MODE` ativo em prod fora da janela sáb 02:00–05:00 BRT.

Exemplo (DRY-RUN, homolog):

    docker-compose exec -T web python manage.py resolver_cartorios_fantasmas \\
        --decisao decisao.csv --decisao-sig decisao.csv.sha256

Exemplo (APPLY em prod, sábado 02:30 BRT, após backup S3 verificado):

    docker-compose exec -T web python manage.py resolver_cartorios_fantasmas \\
        --decisao decisao.csv --decisao-sig decisao.csv.sha256 \\
        --apply --maintenance-mode

Rollback (reverte os merges da fase N, lê de CartorioMergeLog):

    docker-compose exec -T web python manage.py resolver_cartorios_fantasmas \\
        --rollback-fase 1
"""
import csv
import getpass
import hashlib
import json
import os
import socket
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from dominial.models import (
    Alteracoes,
    CartorioMergeLog,
    Cartorios,
    Documento,
    Imovel,
    Lancamento,
    LancamentoOrigem,
)


# Relação (modelo, campo) a ser reatribuída em cada merge.
# Mantida em sincronia com `RELACOES_AUDITADAS` de relatorio_cartorios_suspeitos.
RELACOES_MERGE = (
    (Imovel, 'cartorio'),
    (Documento, 'cartorio'),
    (Documento, 'cri_atual'),
    (Documento, 'cri_origem'),
    (Lancamento, 'cartorio_origem'),
    (LancamentoOrigem, 'cartorio'),
    (Alteracoes, 'cartorio'),
    (Alteracoes, 'cartorio_origem'),
)

# Advisory lock 0xCA21 (cartórios issue 110). Constante de 32 bits.
ADVISORY_LOCK_KEY = 0xCA21
ADVISORY_LOCK_CLASS = 1  # 'merge' namespace

# BRT é UTC-3 (sem DST). Janela oficial: sábado 02:00–05:00 BRT.
JANELA_PROD_INICIO_UTC = 5  # 02:00 BRT = 05:00 UTC
JANELA_PROD_FIM_UTC = 8     # 05:00 BRT = 08:00 UTC

CSV_FIELDS = (
    'decisao', 'linha', 'ghost_id', 'cns_ghost', 'nome_ghost',
    'fk_count', 'target_id', 'cns_target', 'nome_target', 'tipo', 'justificativa',
)


def _normalizar_decisao_csv(linha):
    """Converte a linha do CSV para os tipos internos."""
    return {
        'decisao': linha['decisao'].strip().upper(),
        'linha': linha['linha'].strip(),
        'ghost_id': int(linha['ghost_id']),
        'cns_ghost': linha['cns_ghost'].strip(),
        'nome_ghost': linha['nome_ghost'].strip().strip('"'),
        'fk_count': int(linha.get('fk_count') or 0),
        'target_id': int(linha['target_id']) if linha.get('target_id', '').strip() else None,
        'cns_target': (linha.get('cns_target') or '').strip(),
        'nome_target': (linha.get('nome_target') or '').strip().strip('"'),
        'tipo': linha.get('tipo', 'CRI').strip().upper(),
        'justificativa': linha.get('justificativa', '').strip(),
    }


def _calcular_sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, 'rb') as f:
        for bloco in iter(lambda: f.read(65536), b''):
            h.update(bloco)
    return h.hexdigest()


def _git_head():
    """SHA curto do HEAD; '' se não for repo ou git não disponível."""
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL, timeout=5,
        ).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return ''


def _advisory_lock_postgres(cursor, key, cls=ADVISORY_LOCK_CLASS):
    """Tenta pg_advisory_lock(cls, key). Retorna True se conseguiu."""
    cursor.execute('SELECT pg_try_advisory_lock(%s, %s)', [cls, key])
    return cursor.fetchone()[0]


def _advisory_unlock_postgres(cursor, key, cls=ADVISORY_LOCK_CLASS):
    cursor.execute('SELECT pg_advisory_unlock(%s, %s)', [cls, key])


def _hostname():
    return socket.gethostname() or 'unknown'


def _na_janela_prod_utc():
    """True se agora (UTC) está entre 05:00 e 08:00 de sábado."""
    agora = datetime.utcnow()
    # weekday(): segunda=0, ..., sábado=5
    if agora.weekday() != 5:
        return False
    return JANELA_PROD_INICIO_UTC <= agora.hour < JANELA_PROD_FIM_UTC


def _fk_breakdown_para(ghost_id, cartorios_alvo_ids=None):
    """Conta quantos registros em cada FK referenciam o ghost.

    Se `cartorios_alvo_ids` for fornecido, exclui da contagem de Documento
    aqueles que já apontam para o target (evita dupla contagem em logs
    sucessivos de homolog).
    """
    contagem = {}
    for modelo, campo in RELACOES_MERGE:
        coluna = f'{campo}_id'
        qs = modelo.objects.filter(**{coluna: ghost_id})
        contagem[f'{modelo._meta.model_name}.{campo}'] = qs.count()
    return contagem


def _reatribuir_fks(ghost_id, target_id, batch_size=200):
    """Reatribui cada FK em batches. Retorna {modelo.campo: count}."""
    if ghost_id == target_id:
        raise CommandError(f'ghost_id == target_id ({ghost_id}); merge idempotente.')
    breakdown = {}
    for modelo, campo in RELACOES_MERGE:
        coluna = f'{campo}_id'
        total = 0
        while True:
            ids = list(
                modelo.objects.filter(**{coluna: ghost_id})
                .values_list('pk', flat=True)[:batch_size]
            )
            if not ids:
                break
            modelo.objects.filter(pk__in=ids).update(**{coluna: target_id})
            total += len(ids)
            if len(ids) < batch_size:
                break
        breakdown[f'{modelo._meta.model_name}.{campo}'] = total
    return breakdown


def _soft_delete(cartorio_id, using=None):
    Cartorios.objects.filter(pk=cartorio_id).update(
        deleted_at=timezone.now(),
    )


def _is_prod_env():
    return os.environ.get('DJANGO_ENV', '').lower() == 'prod' or os.environ.get(
        'CADEIA_ENV', ''
    ).lower() == 'prod'


def _backup_verificado():
    """BACKUP_VERIFIED=1 (env) confirma que o dump S3 foi feito e validado."""
    return os.environ.get('BACKUP_VERIFIED', '').strip() in ('1', 'true', 'YES')


class Command(BaseCommand):
    help = (
        'Resolve cartórios fantasmas via CSV de decisão. '
        'Por padrão executa em DRY-RUN (apenas loga). Use --apply para efetivar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--decisao', required=True,
            help='Caminho do decisao.csv (gerado pelo relatorio_cartorios_suspeitos).',
        )
        parser.add_argument(
            '--decisao-sig', default=None,
            help='Caminho do arquivo .sha256 com o hash do CSV. Validado antes de aplicar.',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='Efetiva os merges. Sem este flag é dry-run.',
        )
        parser.add_argument(
            '--batch-size', type=int, default=200,
            help='Tamanho do batch de UPDATE em cada FK (padrão 200).',
        )
        parser.add_argument(
            '--max-fk-count', type=int, default=0,
            help='Falha se algum ghost tiver mais FKs que este valor. 0 = sem limite.',
        )
        parser.add_argument(
            '--allow-outro', action='store_true',
            help='Permite MERGE de cartórios OUTRO (Tabelionato). Default: só CRI.',
        )
        parser.add_argument(
            '--maintenance-mode', action='store_true',
            help='Assume que MAINTENANCE_MODE está ativo (passa o gate de janela prod).',
        )
        parser.add_argument(
            '--skip-backup-check', action='store_true',
            help='Pula o gate de BACKUP_VERIFIED (use só em homolog).',
        )
        parser.add_argument(
            '--rollback-fase', type=int, default=None,
            help='Restaura os soft-deletes da fase N lendo CartorioMergeLog.',
        )
        parser.add_argument(
            '--pg-advisory-lock-key', type=int, default=ADVISORY_LOCK_KEY,
            help='Chave do pg_advisory_lock (padrão 0xCA21 = 51745).',
        )

    # ---------- helpers de output ----------

    def _out(self, msg, style=None):
        if style:
            self.stdout.write(style(msg))
        else:
            self.stdout.write(msg)

    def _ok(self, msg):
        self._out(msg, self.style.SUCCESS)

    def _warn(self, msg):
        self._out(msg, self.style.WARNING)

    def _err(self, msg):
        self._out(msg, self.style.ERROR)

    # ---------- handler principal ----------

    def handle(self, *args, **options):
        if options['rollback_fase'] is not None:
            return self._rollback(options)
        return self._apply_or_dry_run(options)

    # ---------- apply / dry-run ----------

    def _apply_or_dry_run(self, options):
        decisao_path = Path(options['decisao'])
        if not decisao_path.exists():
            raise CommandError(f'decisao.csv não encontrado: {decisao_path}')

        # Validação de assinatura (SHA-256).
        sig_path = Path(options['decisao_sig']) if options['decisao_sig'] else None
        if sig_path:
            if not sig_path.exists():
                raise CommandError(f'Arquivo de assinatura não encontrado: {sig_path}')
            esperado = sig_path.read_text().split()[0].strip()
            calculado = _calcular_sha256(decisao_path)
            if esperado != calculado:
                raise CommandError(
                    f'SHA-256 mismatch.\n  esperado: {esperado}\n  calculado: {calculado}'
                )
            self._ok(f'✓ Assinatura SHA-256 validada: {calculado[:16]}...')

        # Carrega CSV.
        with open(decisao_path, newline='', encoding='utf-8') as f:
            leitor = csv.DictReader(f)
            if not leitor.fieldnames:
                raise CommandError('CSV vazio.')
            faltando = set(CSV_FIELDS) - set(leitor.fieldnames)
            if faltando:
                raise CommandError(f'CSV faltando colunas: {sorted(faltando)}')
            linhas = [_normalizar_decisao_csv(l) for l in leitor]

        if not linhas:
            raise CommandError('CSV sem linhas de decisão.')

        # Filtra e separa.
        merges = [l for l in linhas if l['decisao'] == 'MERGE']
        bloqueados = [l for l in linhas if l['decisao'] == 'BLOCKED']
        outros = [l for l in linhas if l['decisao'] not in ('MERGE', 'BLOCKED')]
        if outros:
            self._warn(
                f'⚠ {len(outros)} linha(s) com decisao desconhecida — ignoradas: '
                f'{[l["linha"] for l in outros]}'
            )

        # Validação OUTRO (gate padrão é só CRI).
        if not options['allow_outro']:
            for l in merges:
                ghost = Cartorios.objects.filter(pk=l['ghost_id']).first()
                if not ghost:
                    raise CommandError(
                        f'Ghost id={l["ghost_id"]} (linha {l["linha"]}) não existe no banco.'
                    )
                target = Cartorios.objects.filter(pk=l['target_id']).first()
                if not target:
                    raise CommandError(
                        f'Target id={l["target_id"]} (linha {l["linha"]}) não existe no banco.'
                    )
                if ghost.tipo != 'CRI' and not options['allow_outro']:
                    raise CommandError(
                        f'Ghost {l["ghost_id"]} é tipo {ghost.tipo!r} (não-CRI). '
                        f'Use --allow-outro para forçar. (linha {l["linha"]})'
                    )
                if target.tipo != 'CRI' and not options['allow_outro']:
                    raise CommandError(
                        f'Target {l["target_id"]} é tipo {target.tipo!r} (não-CRI). '
                        f'Validação CRI→CRI falhou. (linha {l["linha"]})'
                    )

        # Validação de magnitude.
        max_fk = options['max_fk_count']
        if max_fk:
            for l in merges:
                if l['fk_count'] > max_fk:
                    raise CommandError(
                        f'Ghost {l["ghost_id"]} tem {l["fk_count"]} FKs > limite {max_fk}. '
                        f'Revisar decisao.csv. (linha {l["linha"]})'
                    )

        # Gate de prod.
        apply = options['apply']
        if apply and _is_prod_env():
            if not options['maintenance_mode'] and not _na_janela_prod_utc():
                raise CommandError(
                    'Prod: --apply só permitido dentro da janela sáb 02:00–05:00 BRT '
                    '(05:00–08:00 UTC) ou com --maintenance-mode.'
                )
            if not options['skip_backup_check'] and not _backup_verificado():
                raise CommandError(
                    'Prod: BACKUP_VERIFIED=1 não está no env. '
                    'Faça o backup S3 e set a env var, ou use --skip-backup-check (homolog).'
                )

        modo = 'APPLY' if apply else 'DRY-RUN'
        self._out('')
        self._out(f'=== resolver_cartorios_fantasmas — {modo} ===')
        self._out(f'CSV: {decisao_path}  ({len(linhas)} linhas)')
        self._out(f'  MERGE: {len(merges)}')
        self._out(f'  BLOCKED: {len(bloqueados)}')
        self._out(f'batch_size={options["batch_size"]}, max_fk_count={max_fk or "sem limite"}')
        self._out(f'host={_hostname()}, git={_git_head()[:12] or "(sem git)"}')
        self._out('')

        if not apply:
            self._warn('Modo DRY-RUN — nada será alterado. Use --apply para efetivar.')
            self._out('')
            for l in merges:
                self._dry_run_linha(l)
            for l in bloqueados:
                self._out(
                    f'  [linha {l["linha"]}] BLOCKED ghost={l["ghost_id"]} ({l["nome_ghost"][:40]}) — '
                    f'pulado'
                )
            self._out('')
            self._ok('Dry-run concluído sem alterações.')
            return

        # APPLY: pega advisory lock e processa linha a linha.
        with connection.cursor() as cursor:
            conseguiu = _advisory_lock_postgres(cursor, options['pg_advisory_lock_key'])
            if not conseguiu:
                raise CommandError(
                    f'Advisory lock {options["pg_advisory_lock_key"]:#x} ocupado. '
                    f'Outro merge em andamento?'
                )
            try:
                self._out(f'✓ pg_advisory_lock({ADVISORY_LOCK_CLASS}, '
                          f'{options["pg_advisory_lock_key"]:#x}) adquirido')
                sha = _calcular_sha256(decisao_path)
                git_sha = _git_head()
                for l in merges:
                    self._apply_linha(l, sha, git_sha, options)
                for l in bloqueados:
                    self._out(
                        f'  [linha {l["linha"]}] BLOCKED ghost={l["ghost_id"]} — pulado, '
                        f'sem destino definido'
                    )
            finally:
                _advisory_unlock_postgres(cursor, options['pg_advisory_lock_key'])
                self._out(f'✓ Advisory lock liberado')

        self._out('')
        self._ok(f'Apply concluído. {len(merges)} merge(s), {len(bloqueados)} bloqueado(s).')

    def _dry_run_linha(self, l):
        ghost = Cartorios.objects.filter(pk=l['ghost_id']).first()
        target = Cartorios.objects.filter(pk=l['target_id']).first() if l['target_id'] else None
        ghost_label = f'#{l["ghost_id"]} "{l["nome_ghost"][:50]}" (cns={l["cns_ghost"]})'
        target_label = (
            f'#{l["target_id"]} "{l["nome_target"][:50]}" (cns={l["cns_target"]})'
            if target else '?'
        )
        if not ghost:
            self._err(f'  [linha {l["linha"]}] MERGE ghost={ghost_label} → {target_label} — '
                      f'FALHA: ghost não existe no banco')
            return
        if not target:
            self._err(f'  [linha {l["linha"]}] MERGE ghost={ghost_label} → {target_label} — '
                      f'FALHA: target não existe no banco')
            return
        # Breakdown real no banco (sem aplicar).
        breakdown = _fk_breakdown_para(l['ghost_id'])
        total = sum(breakdown.values())
        self._out(
            f'  [linha {l["linha"]}] MERGE ghost={ghost_label}'
        )
        self._out(f'          → target={target_label}')
        self._out(f'          fk_count declarado={l["fk_count"]}, real no banco={total}')
        for k, v in breakdown.items():
            if v:
                self._out(f'            {k}: {v}')
        if total == 0 and l['fk_count'] > 0:
            self._warn(
                f'            ⚠ divergência: CSV diz {l["fk_count"]} mas banco diz 0. '
                f'Re-verificar antes de --apply.'
            )

    def _apply_linha(self, l, decisao_sha, git_sha, options):
        ghost = Cartorios.objects.filter(pk=l['ghost_id']).first()
        target = Cartorios.objects.filter(pk=l['target_id']).first() if l['target_id'] else None
        ghost_label = f'#{l["ghost_id"]} "{l["nome_ghost"][:50]}"'
        target_label = (
            f'#{l["target_id"]} "{l["nome_target"][:50]}"' if target else '?'
        )

        if not ghost or not target:
            self._err(
                f'  [linha {l["linha"]}] MERGE ghost={ghost_label} → {target_label} — '
                f'FALHA: ghost ou target inexistente. Log: SKIPPED_CONFLICT'
            )
            CartorioMergeLog.objects.create(
                ghost_id=l['ghost_id'],
                target_id=l.get('target_id') or 0,
                fase=self._fase_da_linha(l),
                fk_breakdown_json={},
                decisao_csv_sha256=decisao_sha,
                applied_by=getpass.getuser() or 'unknown',
                git_commit=git_sha,
                status='SKIPPED_CONFLICT',
                detalhes_json={'motivo': 'ghost ou target não encontrado', 'linha': l['linha']},
            )
            return

        # Transação por linha: ou reatribui tudo + soft-deleta, ou nada.
        try:
            with transaction.atomic():
                breakdown = _reatribuir_fks(
                    l['ghost_id'], l['target_id'],
                    batch_size=options['batch_size'],
                )
                _soft_delete(l['ghost_id'])
                CartorioMergeLog.objects.create(
                    ghost_id=l['ghost_id'],
                    target_id=l['target_id'],
                    fase=self._fase_da_linha(l),
                    fk_breakdown_json=breakdown,
                    decisao_csv_sha256=decisao_sha,
                    applied_by=getpass.getuser() or 'unknown',
                    git_commit=git_sha,
                    status='SUCCESS',
                )
            total = sum(breakdown.values())
            self._ok(
                f'  [linha {l["linha"]}] MERGE {ghost_label} → {target_label} — '
                f'OK ({total} FKs reatribuídas, soft-delete aplicado)'
            )
        except Exception as e:
            self._err(
                f'  [linha {l["linha"]}] MERGE {ghost_label} → {target_label} — '
                f'ERRO: {e!r}. Log: ERROR'
            )
            CartorioMergeLog.objects.create(
                ghost_id=l['ghost_id'],
                target_id=l['target_id'],
                fase=self._fase_da_linha(l),
                fk_breakdown_json={},
                decisao_csv_sha256=decisao_sha,
                applied_by=getpass.getuser() or 'unknown',
                git_commit=git_sha,
                status='ERROR',
                detalhes_json={'erro': repr(e), 'linha': l['linha']},
            )

    def _fase_da_linha(self, l):
        """Mapeia fk_count → fase do plano (1=órfãos, 2=secundários, 3=críticos)."""
        if l['fk_count'] == 0:
            return 1
        if l['fk_count'] < 100:
            return 2
        return 3

    # ---------- rollback ----------

    def _rollback(self, options):
        """Reverte os merges de uma fase lendo CartorioMergeLog."""
        fase = options['rollback_fase']
        if options['apply'] or not options['decisao']:
            # Rollback não precisa de CSV — só da fase.
            pass

        self._out(f'=== rollback fase {fase} ===')
        logs = CartorioMergeLog.objects.filter(fase=fase).order_by('applied_at')
        total = logs.count()
        if not total:
            self._warn(f'Nenhum log encontrado para fase {fase}.')
            return
        self._out(f'Encontrados {total} log(s) para fase {fase}.')

        if not options['apply']:
            self._warn('Rollback em DRY-RUN — nada será alterado. Use --apply para efetivar.')
            for log in logs[:20]:
                self._out(
                    f'  log id={log.id} ghost={log.ghost_id} → target={log.target_id} '
                    f'status={log.status} when={log.applied_at}'
                )
            if total > 20:
                self._out(f'  ... e mais {total - 20}')
            return

        # APPLY rollback: reativa cartórios e des-reatribui FKs lendo o breakdown.
        for log in logs:
            if log.status != 'SUCCESS':
                self._warn(
                    f'  pulando log id={log.id} (status={log.status})'
                )
                continue
            try:
                with transaction.atomic():
                    # Reverte cada FK do breakdown_json.
                    for chave, count in (log.fk_breakdown_json or {}).items():
                        if not count:
                            continue
                        model_name, campo = chave.split('.')
                        coluna = f'{campo}_id'
                        # Reverte os N mais recentes do target de volta para ghost.
                        # Limitamos a `count` para não reatribuir mais que o original.
                        for modelo, _ in RELACOES_MERGE:
                            if modelo._meta.model_name == model_name:
                                ids = list(
                                    modelo.objects.filter(**{coluna: log.target_id})
                                    .order_by('-pk')
                                    .values_list('pk', flat=True)[:count]
                                )
                                modelo.objects.filter(pk__in=ids).update(
                                    **{coluna: log.ghost_id}
                                )
                                break
                    # Reativa o cartório.
                    Cartorios.objects.filter(pk=log.ghost_id).update(deleted_at=None)
                    log.status = 'ROLLED_BACK'
                    log.save(update_fields=['status'])
                self._ok(
                    f'  log id={log.id} ghost={log.ghost_id} ← target={log.target_id} — '
                    f'rollback OK'
                )
            except Exception as e:
                self._err(
                    f'  log id={log.id} — ERRO no rollback: {e!r}'
                )
