"""Relatório somente-leitura de cartórios CRI suspeitos (issue #110)."""

import csv
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from itertools import combinations
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count, Q
from django.utils import timezone

from dominial.models import (
    Alteracoes,
    Cartorios,
    Documento,
    Imovel,
    Lancamento,
    LancamentoOrigem,
)
from dominial.utils.cns_utils import cns_eh_sintetico, normalizar_nome


ASSIS_BRASIL = 'ASSIS BRASIL'
CLASSIFICACOES = ('ATIVO', 'AMBIGUO', 'EM_CADEIA', 'ORFAO', 'DESCARTAVEL')

RELACOES_AUDITADAS = (
    (Imovel, 'cartorio'),
    (Documento, 'cartorio'),
    (Documento, 'cri_atual'),
    (Documento, 'cri_origem'),
    (Lancamento, 'cartorio_origem'),
    (LancamentoOrigem, 'cartorio'),
    (Alteracoes, 'cartorio'),
    (Alteracoes, 'cartorio_origem'),
)
RELACOES_FORA_ESCOPO = (
    (Lancamento, 'cartorio_transmissao'),
    (Lancamento, 'cartorio_transacao'),
)

CONSTRAINTS_IDENTIDADE = (
    (
        Documento,
        'unique_documento_identidade_canonica',
        ('tipo', 'numero_normalizado', 'cartorio'),
    ),
    (
        Imovel,
        'unique_imovel_identidade_registral',
        ('tipo_documento_principal', 'matricula_normalizada', 'cartorio'),
    ),
    (
        LancamentoOrigem,
        'unique_lancamento_origem_identidade',
        ('lancamento', 'tipo_documento', 'numero_normalizado', 'cartorio'),
    ),
)

SQL_ESCRITA = re.compile(
    r'^\s*(?:INSERT|UPDATE|DELETE|ALTER|DROP|CREATE|TRUNCATE|MERGE|COPY)\b',
    re.IGNORECASE | re.DOTALL,
)
SQL_CTE_ESCRITA = re.compile(
    r'^\s*WITH\b.*\b(?:INSERT|UPDATE|DELETE)\b',
    re.IGNORECASE | re.DOTALL,
)

CSV_FIELDS = (
    'record_type', 'id', 'nome', 'cns', 'cidade', 'estado', 'sinais',
    'severidade', 'numero', 'tipo', 'cartorio_id', 'tem_lancamentos',
    'qtd_lancamentos', 'criado_por_inicio_mat', 'referenciado_como_origem',
    'em_cadeia', 'classificacao', 'duplicata_id', 'documento_id',
    'cartorio_origem_id', 'lancamento_origem_id', 'documento_pai_id',
    'fantasma_id', 'candidato_id', 'metodo', 'source_id', 'target_id',
    'status', 'fk_counts', 'alertas', 'conflitos', 'cascade_pks',
    'cadeias_afetadas', 'constraint', 'model',
    'pks', 'descricao', 'chave', 'valor',
)


def _relacao_id(modelo, campo):
    return modelo._meta.label_lower, campo


def validar_relacoes_cartorio():
    """Falha se surgir uma FK para Cartorios sem decisão explícita de escopo."""
    esperadas = {
        _relacao_id(modelo, campo)
        for modelo, campo in RELACOES_AUDITADAS + RELACOES_FORA_ESCOPO
    }
    encontradas = {
        _relacao_id(relacao.related_model, relacao.field.name)
        for relacao in Cartorios._meta.related_objects
    }
    desconhecidas = encontradas - esperadas
    ausentes = esperadas - encontradas
    if desconhecidas or ausentes:
        partes = []
        if desconhecidas:
            partes.append(f'relações desconhecidas: {sorted(desconhecidas)}')
        if ausentes:
            partes.append(f'relações esperadas ausentes: {sorted(ausentes)}')
        raise CommandError(
            'Allowlist de FKs de Cartorios desatualizada; ' + '; '.join(partes)
        )


def _bloquear_sql_escrita(execute, sql, params, many, context):
    texto = str(sql)
    if SQL_ESCRITA.search(texto) or SQL_CTE_ESCRITA.search(texto):
        raise CommandError('SQL de escrita bloqueado pelo modo somente-leitura.')
    return execute(sql, params, many, context)


@contextmanager
def banco_somente_leitura():
    """Ativa e comprova o modo read-only no backend durante o diagnóstico."""
    vendor = connection.vendor
    if vendor not in {'sqlite', 'postgresql'}:
        raise CommandError(f'Backend não suportado para read-only: {vendor}')

    with connection.execute_wrapper(_bloquear_sql_escrita):
        if vendor == 'sqlite':
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA query_only')
                anterior = int(cursor.fetchone()[0])
                cursor.execute('PRAGMA query_only = ON')
                cursor.execute('PRAGMA query_only')
                if int(cursor.fetchone()[0]) != 1:
                    raise CommandError('SQLite não confirmou PRAGMA query_only=1.')
            try:
                yield
            finally:
                with connection.cursor() as cursor:
                    cursor.execute(f'PRAGMA query_only = {anterior}')
            return

        if connection.in_atomic_block or not connection.get_autocommit():
            raise CommandError(
                'PostgreSQL já está em transação; execute o command fora de atomic().'
            )
        connection.set_autocommit(False)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'
                )
                cursor.execute('SHOW transaction_read_only')
                if str(cursor.fetchone()[0]).lower() not in {'on', 'true', '1'}:
                    raise CommandError('PostgreSQL não confirmou transaction_read_only=on.')
            yield
        finally:
            connection.rollback()
            connection.set_autocommit(True)


def classificar_documento(tem_lancamentos, em_cadeia, duplicata_id):
    """Aplica os cinco estados na ordem de prioridade definida no plano."""
    if tem_lancamentos:
        return 'AMBIGUO' if duplicata_id is not None else 'ATIVO'
    if em_cadeia:
        return 'EM_CADEIA'
    return 'ORFAO' if duplicata_id is not None else 'DESCARTAVEL'


def calcular_severidade(*, sintetico, classificacoes, duplicidade_nome, total_vinculos):
    """Avalia todos os sinais e devolve a maior severidade aplicável."""
    niveis = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}
    candidatas = []
    conjunto = set(classificacoes)
    if total_vinculos == 0:
        candidatas.append('LOW')
    if duplicidade_nome and 'ATIVO' in conjunto:
        candidatas.append('MEDIUM')
    if sintetico and conjunto and conjunto <= {'ORFAO', 'DESCARTAVEL'}:
        candidatas.append('HIGH')
    if sintetico and conjunto.intersection({'ATIVO', 'EM_CADEIA'}):
        candidatas.append('CRITICAL')
    if not candidatas:
        candidatas.append('LOW')
    return max(candidatas, key=niveis.__getitem__)


def coletar_contagens_fks(cartorio_ids):
    """Executa exatamente uma agregação para cada uma das oito FKs CRI."""
    ids = set(cartorio_ids)
    resultado = {cartorio_id: {} for cartorio_id in ids}
    for modelo, campo in RELACOES_AUDITADAS:
        chave = f'{modelo._meta.model_name}.{campo}'
        coluna = f'{campo}_id'
        contagens = dict(
            modelo.objects.filter(**{f'{coluna}__in': ids})
            .values_list(coluna)
            .annotate(n=Count('pk'))
            .order_by()
        )
        for cartorio_id in ids:
            resultado[cartorio_id][chave] = contagens.get(cartorio_id, 0)
    return resultado


def _estado_preenchido(cartorio):
    return bool((cartorio.estado or '').strip())


def _cidade_assis_brasil(cartorio):
    return (cartorio.cidade or '').strip().casefold() == ASSIS_BRASIL.casefold()


def _ler_csv(caminho, colunas_obrigatorias):
    try:
        with open(caminho, encoding='utf-8-sig', newline='') as arquivo:
            leitor = csv.DictReader(arquivo)
            campos = set(leitor.fieldnames or ())
            faltantes = set(colunas_obrigatorias) - campos
            if faltantes:
                raise CommandError(
                    f'CSV {caminho} sem colunas obrigatórias: {sorted(faltantes)}'
                )
            return list(leitor)
    except OSError as erro:
        raise CommandError(f'Não foi possível ler {caminho}: {erro}') from erro


def ler_merge_plan(caminho):
    if not caminho:
        return []
    linhas = _ler_csv(caminho, {'fantasma_id', 'correto_id'})
    pares = []
    for numero_linha, linha in enumerate(linhas, start=2):
        try:
            source_id = int((linha['fantasma_id'] or '').strip())
            target_id = int((linha['correto_id'] or '').strip())
        except (TypeError, ValueError) as erro:
            raise CommandError(
                f'IDs inválidos no merge plan, linha {numero_linha}.'
            ) from erro
        pares.append({'source_id': source_id, 'target_id': target_id, 'linha': numero_linha})
    return pares


def _ler_known_list(caminho):
    """Lê lista opcional de IDs ou mapeamentos fantasma/correto."""
    if not caminho:
        return None, {}
    try:
        with open(caminho, encoding='utf-8-sig', newline='') as arquivo:
            leitor = csv.DictReader(arquivo)
            campos = set(leitor.fieldnames or ())
            linhas = list(leitor)
    except OSError as erro:
        raise CommandError(f'Não foi possível ler {caminho}: {erro}') from erro

    if {'fantasma_id', 'correto_id'} <= campos:
        mapeamento = {}
        for linha in linhas:
            try:
                mapeamento[int(linha['fantasma_id'])] = int(linha['correto_id'])
            except (TypeError, ValueError) as erro:
                raise CommandError('known-list contém IDs inválidos.') from erro
        return set(mapeamento.values()), mapeamento

    coluna = next((nome for nome in ('id', 'cartorio_id', 'correto_id') if nome in campos), None)
    if coluna is None:
        raise CommandError(
            'known-list deve conter id/cartorio_id ou fantasma_id,correto_id.'
        )
    try:
        return {int(linha[coluna]) for linha in linhas}, {}
    except (TypeError, ValueError) as erro:
        raise CommandError('known-list contém IDs inválidos.') from erro


def _hash_arquivo(caminho):
    if not caminho:
        return None
    digest = hashlib.sha256()
    try:
        with open(caminho, 'rb') as arquivo:
            for bloco in iter(lambda: arquivo.read(65536), b''):
                digest.update(bloco)
    except OSError as erro:
        raise CommandError(f'Não foi possível calcular hash de {caminho}: {erro}') from erro
    return f'sha256:{digest.hexdigest()}'


def _git_commit():
    try:
        return subprocess.run(
            ['git', 'rev-parse', '--short=8', 'HEAD'],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'DESCONHECIDO'


def _schema_version():
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT name FROM django_migrations WHERE app = %s ORDER BY applied DESC, id DESC LIMIT 1',
            ['dominial'],
        )
        linha = cursor.fetchone()
    return linha[0] if linha else None


def _validar_entrada_merge(pares):
    ids = {par['source_id'] for par in pares} | {par['target_id'] for par in pares}
    cartorios = Cartorios.objects.in_bulk(ids)
    for par in pares:
        source = cartorios.get(par['source_id'])
        target = cartorios.get(par['target_id'])
        if source is None or target is None:
            raise CommandError(
                f'Merge plan linha {par["linha"]}: source ou target inexistente.'
            )
        if source.tipo != 'CRI' or target.tipo != 'CRI':
            raise CommandError(f'Merge plan linha {par["linha"]}: ambos devem ser CRI.')
        if source.pk == target.pk:
            raise CommandError(f'Merge plan linha {par["linha"]}: source = target.')
        # Mesmo critério de fantasma usado no diagnóstico (CRI sem estado):
        # fundir um fantasma em outro apenas move o problema de lugar.
        if not _estado_preenchido(source) and not _estado_preenchido(target):
            raise CommandError(
                f'Merge plan linha {par["linha"]}: source e target são fantasmas '
                '(CRI sem estado); o target deve ser um cartório correto.'
            )


def _problemas_estrutura_merge(pares):
    fontes = Counter(par['source_id'] for par in pares)
    fontes_set = set(fontes)
    targets_set = {par['target_id'] for par in pares}
    intersecao = fontes_set & targets_set
    problemas = {}
    for indice, par in enumerate(pares):
        if par['source_id'] in intersecao or par['target_id'] in intersecao:
            problemas[indice] = 'CICLO'
        elif fontes[par['source_id']] > 1:
            problemas[indice] = 'FONTE_REPETIDA'
    return problemas


def _constraints_divergentes():
    divergencias = []
    with connection.cursor() as cursor:
        for modelo, nome, campos in CONSTRAINTS_IDENTIDADE:
            try:
                constraints = connection.introspection.get_constraints(
                    cursor, modelo._meta.db_table
                )
            except (IndexError, ValueError) as erro:
                # Django 5.2 pode falhar ao tokenizar CREATE TABLE do SQLite
                # quando há vírgulas na expressão de um GeneratedField. O
                # fallback continua introspectando o schema real, mas limita o
                # parser às três constraints nomeadas que precisamos conferir.
                if connection.vendor != 'sqlite':
                    raise CommandError(
                        f'Falha ao introspectar {modelo._meta.db_table}: {erro}'
                    ) from erro
                constraints = _constraints_sqlite_nomeadas(
                    cursor, modelo._meta.db_table
                )
            encontrada = constraints.get(nome)
            colunas_model = [modelo._meta.get_field(campo).column for campo in campos]
            if not encontrada:
                divergencias.append(f'{nome}: ausente')
                continue
            colunas_db = list(encontrada.get('columns') or ())
            if not encontrada.get('unique') or colunas_db != colunas_model:
                divergencias.append(
                    f'{nome}: banco={colunas_db}, models={colunas_model}, '
                    f'unique={bool(encontrada.get("unique"))}'
                )
    return divergencias


def _constraints_sqlite_nomeadas(cursor, tabela):
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = %s",
        [tabela],
    )
    linha = cursor.fetchone()
    ddl = linha[0] if linha else ''
    resultado = {}
    for _, nome, _ in CONSTRAINTS_IDENTIDADE:
        padrao = re.compile(
            r'CONSTRAINT\s+["`]' + re.escape(nome) +
            r'["`]\s+UNIQUE\s*\(([^)]*)\)',
            re.IGNORECASE,
        )
        encontrada = padrao.search(ddl)
        if encontrada:
            resultado[nome] = {
                'unique': True,
                'columns': re.findall(r'["`]([^"`]+)["`]', encontrada.group(1)),
            }
    return resultado


def _simular_conflitos(mapa):
    cartorios = set(mapa) | set(mapa.values())
    conflitos = []
    fontes_por_conflito = defaultdict(set)
    for modelo, nome, campos in CONSTRAINTS_IDENTIDADE:
        nomes_values = ['pk', 'cartorio_id']
        nomes_values.extend(
            modelo._meta.get_field(campo).attname
            for campo in campos
            if campo != 'cartorio'
        )
        linhas = list(
            modelo.objects.filter(cartorio_id__in=cartorios)
            .values(*dict.fromkeys(nomes_values))
            .order_by('pk')
        )
        grupos = defaultdict(list)
        for linha in linhas:
            cartorio_final = mapa.get(linha['cartorio_id'], linha['cartorio_id'])
            chave = tuple(
                cartorio_final if campo == 'cartorio'
                else linha[modelo._meta.get_field(campo).attname]
                for campo in campos
            )
            grupos[chave].append(linha)
        for chave, grupo in grupos.items():
            if len(grupo) < 2:
                continue
            for esquerda, direita in combinations(grupo, 2):
                fontes = {
                    linha['cartorio_id']
                    for linha in (esquerda, direita)
                    if linha['cartorio_id'] in mapa
                }
                if not fontes:
                    continue
                indice = len(conflitos)
                fontes_por_conflito[indice].update(fontes)
                conflitos.append({
                    'record_type': 'CONFLITO',
                    'constraint': nome,
                    'model': modelo._meta.label,
                    'pks': [esquerda['pk'], direita['pk']],
                    'descricao': 'Colisão após aplicar simultaneamente todo o mapa.',
                    'chave': list(chave),
                })
    return conflitos, fontes_por_conflito


def _riscos_cascade(source_ids):
    riscos = defaultdict(lambda: {'cartorio': [], 'cartorio_origem': []})
    for campo in ('cartorio', 'cartorio_origem'):
        for pk, cartorio_id in (
            Alteracoes.objects.filter(**{f'{campo}_id__in': source_ids})
            .values_list('pk', f'{campo}_id')
            .order_by('pk')
        ):
            riscos[cartorio_id][campo].append(pk)
    return riscos


def _cadeias_afetadas(source_ids):
    documentos = list(
        Documento.objects.filter(cartorio_id__in=source_ids)
        .values_list('pk', 'cartorio_id')
        .order_by('pk')
    )
    source_por_documento = dict(documentos)
    if not source_por_documento:
        return defaultdict(list)
    docs_com_lancamento = set(
        Lancamento.objects.filter(documento_id__in=source_por_documento)
        .values_list('documento_id', flat=True)
        .distinct()
    )
    riscos = defaultdict(list)
    referencias = (
        Lancamento.objects.filter(documento_origem_id__in=source_por_documento)
        .values('pk', 'documento_id', 'documento_origem_id')
        .order_by('pk')
    )
    for referencia in referencias:
        documento_id = referencia['documento_origem_id']
        if (
            documento_id not in docs_com_lancamento
            and referencia['documento_id'] != documento_id
        ):
            riscos[source_por_documento[documento_id]].append({
                'documento_id': documento_id,
                'lancamento_origem_id': referencia['pk'],
                'documento_pai_id': referencia['documento_id'],
            })
    return riscos


def simular_merges(pares, fk_counts=None):
    """Valida e simula o mapa inteiro sem executar nenhuma alteração."""
    if not pares:
        return [], []
    _validar_entrada_merge(pares)
    problemas = _problemas_estrutura_merge(pares)
    if problemas:
        resultados = []
        for indice, par in enumerate(pares):
            status = problemas.get(indice, 'NAO_SIMULADO')
            resultados.append({
                'record_type': 'MERGE_SIMULADO',
                'source_id': par['source_id'],
                'target_id': par['target_id'],
                'status': status,
                'fk_counts': (fk_counts or {}).get(par['source_id'], {}),
                'alertas': [status],
                'conflitos': [],
            })
        return resultados, []

    divergencias = _constraints_divergentes()
    if divergencias:
        return [
            {
                'record_type': 'MERGE_SIMULADO',
                'source_id': par['source_id'],
                'target_id': par['target_id'],
                'status': 'SCHEMA_DIVERGENTE',
                'fk_counts': (fk_counts or {}).get(par['source_id'], {}),
                'alertas': divergencias,
                'conflitos': [],
            }
            for par in pares
        ], []

    mapa = {par['source_id']: par['target_id'] for par in pares}
    conflitos, fontes_por_conflito = _simular_conflitos(mapa)
    conflito_ids_por_source = defaultdict(list)
    for indice, fontes in fontes_por_conflito.items():
        for source_id in fontes:
            conflito_ids_por_source[source_id].append(indice)
    cascades = _riscos_cascade(set(mapa))
    cadeias = _cadeias_afetadas(set(mapa))

    resultados = []
    for par in pares:
        source_id = par['source_id']
        alertas = []
        if cascades[source_id]['cartorio'] or cascades[source_id]['cartorio_origem']:
            alertas.append('CASCADE_RISCO')
        if cadeias[source_id]:
            alertas.append('CADEIA_AFETADA')
        if conflito_ids_por_source[source_id]:
            alertas.append('CONFLITO')
        if 'CONFLITO' in alertas:
            status = 'CONFLITO'
        elif 'CASCADE_RISCO' in alertas:
            status = 'CASCADE_RISCO'
        elif 'CADEIA_AFETADA' in alertas:
            status = 'CADEIA_AFETADA'
        else:
            status = 'SEGURO'
        resultados.append({
            'record_type': 'MERGE_SIMULADO',
            'source_id': source_id,
            'target_id': par['target_id'],
            'status': status,
            'fk_counts': (fk_counts or {}).get(source_id, {}),
            'alertas': alertas,
            'cascade_pks': dict(cascades[source_id]),
            'cadeias_afetadas': cadeias[source_id],
            'conflitos': conflito_ids_por_source[source_id],
        })
    return resultados, conflitos


def _coletar_diagnostico(pares, known_ids, known_map):
    fantasmas = list(
        Cartorios.objects.filter(tipo='CRI')
        .filter(Q(estado__isnull=True) | Q(estado='') | Q(estado__regex=r'^\s+$'))
        .order_by('pk')
    )
    fantasma_ids = [cartorio.pk for cartorio in fantasmas]
    fk_counts = coletar_contagens_fks(fantasma_ids)

    corretos = [
        cartorio
        for cartorio in Cartorios.objects.filter(tipo='CRI').order_by('pk')
        if _estado_preenchido(cartorio) and not _cidade_assis_brasil(cartorio)
        and (known_ids is None or cartorio.pk in known_ids)
    ]
    corretos_por_nome = defaultdict(list)
    for cartorio in corretos:
        corretos_por_nome[normalizar_nome(cartorio.nome)].append(cartorio)

    mapa_manual = dict(known_map)
    mapa_manual.update({par['source_id']: par['target_id'] for par in pares})
    sugestoes = []
    candidatos_por_fantasma = {}
    corretos_por_id = {cartorio.pk: cartorio for cartorio in corretos}
    for fantasma in fantasmas:
        if fantasma.pk in mapa_manual:
            candidato_id = mapa_manual[fantasma.pk]
            candidatos_por_fantasma[fantasma.pk] = [candidato_id]
            sugestoes.append({
                'record_type': 'SUGESTAO',
                'fantasma_id': fantasma.pk,
                'candidato_id': candidato_id,
                'metodo': 'manual',
                'status': 'CONFIRMADO',
            })
            continue
        candidatos = corretos_por_nome.get(normalizar_nome(fantasma.nome), [])
        candidatos_por_fantasma[fantasma.pk] = [item.pk for item in candidatos]
        if candidatos:
            for candidato in candidatos:
                sugestoes.append({
                    'record_type': 'SUGESTAO',
                    'fantasma_id': fantasma.pk,
                    'candidato_id': candidato.pk,
                    'metodo': 'normalizacao',
                    'status': 'NAO_VERIFICADO',
                })
        else:
            sugestoes.append({
                'record_type': 'SUGESTAO',
                'fantasma_id': fantasma.pk,
                'candidato_id': None,
                'metodo': 'normalizacao',
                'status': 'SEM_CANDIDATO',
            })

    documentos_obj = list(
        Documento.objects.filter(cartorio_id__in=fantasma_ids)
        .select_related('tipo')
        .order_by('pk')
    )
    documentos_por_id = {documento.pk: documento for documento in documentos_obj}
    lancamentos_obj = list(
        Lancamento.objects.filter(documento_id__in=documentos_por_id)
        .select_related('tipo')
        .order_by('pk')
    )
    lancamentos_por_documento = defaultdict(list)
    for lancamento in lancamentos_obj:
        lancamentos_por_documento[lancamento.documento_id].append(lancamento)

    referencias_obj = list(
        Lancamento.objects.filter(documento_origem_id__in=documentos_por_id)
        .select_related('tipo')
        .order_by('pk')
    )
    referencias_por_documento = defaultdict(list)
    for lancamento in referencias_obj:
        referencias_por_documento[lancamento.documento_origem_id].append(lancamento)

    todos_candidatos = {
        candidato_id
        for candidatos in candidatos_por_fantasma.values()
        for candidato_id in candidatos
    }
    duplicatas = defaultdict(list)
    if todos_candidatos:
        for duplicata in (
            Documento.objects.filter(cartorio_id__in=todos_candidatos)
            .values('pk', 'tipo_id', 'numero_normalizado', 'cartorio_id')
            .order_by('pk')
        ):
            duplicatas[
                (
                    duplicata['cartorio_id'],
                    duplicata['tipo_id'],
                    duplicata['numero_normalizado'],
                )
            ].append(duplicata['pk'])

    documentos = []
    lancamentos = []
    cadeias = []
    classificacoes_por_fantasma = defaultdict(list)
    lancamentos_afetados = 0
    for documento in documentos_obj:
        candidatos = candidatos_por_fantasma.get(documento.cartorio_id, [])
        ids_duplicata = []
        for candidato_id in candidatos:
            ids_duplicata.extend(
                duplicatas.get(
                    (candidato_id, documento.tipo_id, documento.numero_normalizado),
                    (),
                )
            )
        duplicata_id = min(ids_duplicata) if ids_duplicata else None
        proprios = lancamentos_por_documento[documento.pk]
        referencias = referencias_por_documento[documento.pk]
        referencias_externas = [
            item for item in referencias if item.documento_id != documento.pk
        ]
        em_cadeia = bool(referencias_externas) and not proprios
        classificacao = classificar_documento(bool(proprios), em_cadeia, duplicata_id)
        classificacoes_por_fantasma[documento.cartorio_id].append(classificacao)
        lancamentos_afetados += len(proprios)
        criadores = [item for item in referencias if item.tipo.tipo == 'inicio_matricula']
        documentos.append({
            'record_type': 'DOCUMENTO',
            'id': documento.pk,
            'numero': documento.numero,
            'tipo': documento.tipo.tipo,
            'cartorio_id': documento.cartorio_id,
            'tem_lancamentos': bool(proprios),
            'qtd_lancamentos': len(proprios),
            'criado_por_inicio_mat': [
                {'lancamento_id': item.pk, 'documento_id': item.documento_id}
                for item in criadores
            ],
            'referenciado_como_origem': bool(referencias_externas),
            'em_cadeia': em_cadeia,
            'classificacao': classificacao,
            'duplicata_id': duplicata_id,
        })
        if classificacao in {'ATIVO', 'AMBIGUO'}:
            for lancamento in proprios:
                lancamentos.append({
                    'record_type': 'LANCAMENTO',
                    'id': lancamento.pk,
                    'documento_id': documento.pk,
                    'tipo': lancamento.tipo.tipo,
                    'cartorio_origem_id': lancamento.cartorio_origem_id,
                })
        if classificacao == 'EM_CADEIA':
            for referencia in referencias_externas:
                cadeias.append({
                    'record_type': 'CADEIA',
                    'documento_id': documento.pk,
                    'lancamento_origem_id': referencia.pk,
                    'documento_pai_id': referencia.documento_id,
                })

    fantasmas_saida = []
    for fantasma in fantasmas:
        sintetico = cns_eh_sintetico(fantasma.cns)
        sinais = ['ESTADO_AUSENTE']
        if sintetico:
            sinais.append('CNS_SINTETICO')
        if sintetico and _cidade_assis_brasil(fantasma):
            sinais.append('LOCALIDADE_COPIADA')
        total_vinculos = sum(fk_counts[fantasma.pk].values())
        if total_vinculos == 0:
            sinais.append('SEM_VINCULOS')
        classificacoes = classificacoes_por_fantasma[fantasma.pk]
        duplicidade_nome = bool(candidatos_por_fantasma.get(fantasma.pk))
        fantasmas_saida.append({
            'record_type': 'FANTASMA',
            'id': fantasma.pk,
            'nome': fantasma.nome,
            'cns': fantasma.cns,
            'cidade': fantasma.cidade,
            'estado': fantasma.estado,
            'sinais': sinais,
            'severidade': calcular_severidade(
                sintetico=sintetico,
                classificacoes=classificacoes,
                duplicidade_nome=duplicidade_nome,
                total_vinculos=total_vinculos,
            ),
            'fk_counts': fk_counts[fantasma.pk],
        })

    totais = Counter(item['classificacao'] for item in documentos)
    resumo = {
        'fantasmas_cri': len(fantasmas_saida),
        'documentos_total': len(documentos),
        'documentos_ativos': totais['ATIVO'],
        'documentos_ambiguos': totais['AMBIGUO'],
        'documentos_em_cadeia': totais['EM_CADEIA'],
        'documentos_orfaos': totais['ORFAO'],
        'documentos_descartaveis': totais['DESCARTAVEL'],
        'lancamentos_afetados': lancamentos_afetados,
    }
    return {
        'fantasmas': fantasmas_saida,
        'documentos': documentos,
        'lancamentos': lancamentos,
        'cadeias': cadeias,
        'sugestoes': sugestoes,
        'resumo': resumo,
    }, fk_counts


def _metadata(known_list):
    return {
        'timestamp': timezone.now().isoformat().replace('+00:00', 'Z'),
        'git_commit': _git_commit(),
        'db_vendor': connection.vendor,
        'schema_version': _schema_version(),
        'total_cartorios': Cartorios.objects.count(),
        'known_list_hash': _hash_arquivo(known_list),
        'ordenacao': 'id ASC em todas as seções',
        'somente_leitura': True,
    }


def _records_csv(relatorio):
    for secao in (
        'fantasmas', 'documentos', 'lancamentos', 'cadeias', 'sugestoes',
        'merges_simulados', 'conflitos',
    ):
        yield from relatorio.get(secao, ())
    for chave, valor in relatorio['resumo'].items():
        yield {'record_type': 'RESUMO', 'chave': chave, 'valor': valor}


def serializar_relatorio(relatorio, formato):
    if formato == 'json':
        return json.dumps(relatorio, ensure_ascii=False, indent=2, sort_keys=True) + '\n'
    saida = io.StringIO(newline='')
    escritor = csv.DictWriter(saida, fieldnames=CSV_FIELDS, extrasaction='ignore')
    escritor.writeheader()
    for registro in _records_csv(relatorio):
        linha = {}
        for chave, valor in registro.items():
            if isinstance(valor, (dict, list)):
                linha[chave] = json.dumps(valor, ensure_ascii=False, sort_keys=True)
            elif isinstance(valor, bool):
                linha[chave] = 'SIM' if valor else 'NAO'
            elif valor is None:
                linha[chave] = ''
            else:
                linha[chave] = valor
        escritor.writerow(linha)
    return saida.getvalue()


def escrever_atomicamente(caminho, conteudo, force=False):
    destino = Path(caminho)
    if destino.exists() and not force:
        raise CommandError(
            f'O arquivo {destino} já existe; use --force para sobrescrever.'
        )
    if not destino.parent.exists():
        raise CommandError(f'Diretório de saída não existe: {destino.parent}')
    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', newline='',
            dir=destino.parent, prefix=f'.{destino.name}.', delete=False,
        ) as arquivo:
            temporario = Path(arquivo.name)
            arquivo.write(conteudo)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, destino)
    except OSError as erro:
        if temporario and temporario.exists():
            temporario.unlink()
        raise CommandError(f'Falha ao escrever {destino}: {erro}') from erro


class Command(BaseCommand):
    help = 'Relata cartórios CRI suspeitos e simula merges sem alterar o banco.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Arquivo de saída; omita para stdout.')
        parser.add_argument('--format', choices=('csv', 'json'), default='csv')
        parser.add_argument('--known-list', help='CSV opcional de cartórios conhecidos.')
        parser.add_argument('--merge-plan', help='CSV fantasma_id,correto_id para simulação.')
        parser.add_argument('--force', action='store_true', help='Sobrescreve a saída existente.')

    def handle(self, *args, **options):
        validar_relacoes_cartorio()
        pares = ler_merge_plan(options['merge_plan'])
        known_ids, known_map = _ler_known_list(options['known_list'])
        with banco_somente_leitura():
            diagnostico, fk_counts = _coletar_diagnostico(pares, known_ids, known_map)
            merges, conflitos = simular_merges(pares, fk_counts)
            relatorio = {
                'metadata': _metadata(options['known_list']),
                **diagnostico,
                'merges_simulados': merges,
                'conflitos': conflitos,
            }
        conteudo = serializar_relatorio(relatorio, options['format'])
        if options['output']:
            escrever_atomicamente(options['output'], conteudo, options['force'])
            self.stdout.write(self.style.SUCCESS(f'Relatório gravado em {options["output"]}'))
        else:
            self.stdout.write(conteudo, ending='')
