"""
Layout de planilha compartilhado entre os exports em Excel da cadeia
dominial: o export por imóvel (issue #50, view `exportar_cadeia_dominial_excel`)
e o export consolidado por Terra Indígena (issue #179, view
`exportar_cadeia_dominial_excel_tis`).

Os dois exports representam a mesma estrutura de dados — o `cadeia_completa`
devolvido por `CadeiaCompletaService.get_cadeia_completa` — e têm de manter
exatamente o mesmo layout de colunas usado no PDF completo
(`cadeia_completa_pdf.html`): mesmos cabeçalhos, mesmas larguras de coluna,
mesmos estilos e a mesma lógica de escrita de cada documento/lançamento.

Este módulo concentra esse layout num único lugar (extraído da view
original de exportação por imóvel) justamente para que os dois exports não
divirjam ao longo do tempo: qualquer ajuste de coluna, cor ou formatação
deve ser feito aqui, uma única vez, e passa a valer para os dois.
"""

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..utils import abreviar_cartorio, normalizar_texto_opcional
from ..utils.formatacao_utils import formatar_area_ha

# 16 colunas (A até P). `ULTIMA_COLUNA` é derivada de `TOTAL_COLUNAS` para
# nunca ficarem dessincronizadas.
TOTAL_COLUNAS = 16
ULTIMA_COLUNA = get_column_letter(TOTAL_COLUNAS)

# Cabeçalho detalhado da tabela de lançamentos de cada documento. "CRI" nas
# posições 4 e 10 (cartório da matrícula e cartório da transmissão) é a
# sigla adotada nas exportações pela issue #166 — não alterar para "Cartório".
CABECALHOS_DETALHADOS = [
    'Nº', 'L', 'Fls.', 'CRI', 'Data',  # Matrícula
    'Transmitente', 'Adquirente',  # Pessoas
    'Forma', 'Título', 'CRI', 'L', 'Fls.', 'Data',  # Transmissão
    'Área (ha)', 'Origem', 'Observações'
]

# Larguras das 16 colunas, na mesma ordem de `CABECALHOS_DETALHADOS`.
LARGURAS_COLUNAS = [12, 8, 8, 20, 12, 20, 20, 15, 15, 20, 8, 8, 12, 12, 20, 30]


def criar_estilos():
    """
    Cria o conjunto de estilos usados na tabela de lançamentos de cada
    documento (cabeçalhos de agrupamento/detalhados, bordas e alinhamento).
    Centralizado aqui para que o export por imóvel e o consolidado por TI
    usem exatamente as mesmas cores e bordas.
    """
    return {
        'header_font': Font(bold=True, color="FFFFFF"),
        'header_fill': PatternFill(start_color="366092", end_color="366092", fill_type="solid"),
        'border': Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        ),
        'center_alignment': Alignment(horizontal='center', vertical='center'),
    }


def ajustar_larguras_colunas(ws):
    """Aplica `LARGURAS_COLUNAS` às `TOTAL_COLUNAS` colunas (A..P) da planilha."""
    for i, width in enumerate(LARGURAS_COLUNAS, 1):
        ws.column_dimensions[get_column_letter(i)].width = width


def escrever_secao_documentos(ws, cadeia_completa, linha_inicial, estilos=None):
    """
    Escreve, a partir de `linha_inicial`, a sequência de documentos e
    lançamentos de uma cadeia dominial completa (o `cadeia_completa`
    devolvido por `CadeiaCompletaService.get_cadeia_completa`), no mesmo
    formato usado pelo PDF: título mesclado do documento, cabeçalho de
    agrupamento (MATRÍCULA / TRANSMISSÃO / Área / Origem / Observações),
    cabeçalho detalhado (`CABECALHOS_DETALHADOS`) e uma linha por
    lançamento, com uma linha em branco separando um documento do próximo.

    `linha_inicial` é a primeira linha efetivamente escrita (o título do
    primeiro documento) — quem chama decide onde a seção começa.

    Retorna a próxima linha livre: a linha em branco deixada após o último
    documento. Quem chama decide o que fazer com ela (o export por imóvel
    soma +1 antes do bloco de estatísticas; o export consolidado por TI soma
    +1 para separar o próximo imóvel).

    ATENÇÃO: os acessos a `documento.livro`/`documento.folha`/
    `documento.cartorio` ficam DENTRO do loop `for lancamento in
    lancamentos`, de propósito — `test_exportacao_cadeia.py` exercita esta
    função com documentos falsos (`SimpleNamespace`) sem esses atributos,
    mas cuja lista de lançamentos é vazia. Não promova esses acessos para
    fora do loop.
    """
    if estilos is None:
        estilos = criar_estilos()
    header_font = estilos['header_font']
    header_fill = estilos['header_fill']
    border = estilos['border']
    center_alignment = estilos['center_alignment']

    row = linha_inicial - 1

    for tronco in cadeia_completa:
        # Processar documentos do tronco
        for item in tronco['documentos']:
            documento = item['documento']
            lancamentos = item['lancamentos']
            is_importado = item.get('is_importado', False)

            # Título do documento
            row += 1
            prefixo_importado = "📥 " if is_importado else ""
            ws.merge_cells(f'A{row}:{ULTIMA_COLUNA}{row}')
            ws.cell(row=row, column=1, value=f"{prefixo_importado}{documento.tipo.get_tipo_display()}: {documento.numero}").font = Font(bold=True, size=12)
            ws.cell(row=row, column=1).fill = PatternFill(start_color="e3f2fd", end_color="e3f2fd", fill_type="solid")
            ws.cell(row=row, column=1).alignment = center_alignment
            row += 1

            # Cabeçalho da tabela de lançamentos (igual ao template)
            # Primeira linha de cabeçalho (agrupamentos)
            ws.merge_cells(f'A{row}:E{row}')
            ws.cell(row=row, column=1, value="MATRÍCULA").font = header_font
            ws.cell(row=row, column=1).fill = header_fill
            ws.cell(row=row, column=1).alignment = center_alignment

            ws.merge_cells(f'F{row}:G{row}')
            ws.cell(row=row, column=6, value="").fill = header_fill

            ws.merge_cells(f'H{row}:M{row}')
            ws.cell(row=row, column=8, value="TRANSMISSÃO").font = header_font
            ws.cell(row=row, column=8).fill = header_fill
            ws.cell(row=row, column=8).alignment = center_alignment

            ws.cell(row=row, column=14, value="Área (ha)").font = header_font
            ws.cell(row=row, column=14).fill = header_fill
            ws.cell(row=row, column=14).alignment = center_alignment

            ws.cell(row=row, column=15, value="Origem").font = header_font
            ws.cell(row=row, column=15).fill = header_fill
            ws.cell(row=row, column=15).alignment = center_alignment

            ws.cell(row=row, column=16, value="Observações").font = header_font
            ws.cell(row=row, column=16).fill = header_fill
            ws.cell(row=row, column=16).alignment = center_alignment
            row += 1

            # Segunda linha de cabeçalho (colunas específicas)
            for col, header in enumerate(CABECALHOS_DETALHADOS, 1):
                cell = ws.cell(row=row, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                cell.alignment = center_alignment
            row += 1

            # Adicionar lançamentos
            for lancamento in lancamentos:
                # Nº (usando o filtro numero_documento_criado)
                from ..templatetags.dominial_extras import numero_documento_criado
                numero_formatado = numero_documento_criado(lancamento)
                ws.cell(row=row, column=1, value=numero_formatado).border = border

                # L, Fls., Cartório, Data (do documento)
                ws.cell(row=row, column=2, value=documento.livro or "-").border = border
                folha_valor = "-" if documento.tipo and documento.tipo.tipo == 'matricula' else (documento.folha or "-")
                ws.cell(row=row, column=3, value=folha_valor).border = border
                ws.cell(row=row, column=4, value=abreviar_cartorio(documento.cartorio.nome) if documento.cartorio else "-").border = border
                ws.cell(row=row, column=5, value=lancamento.data.strftime('%d/%m/%Y') if lancamento.data else "-").border = border

                # `transmitentes`/`adquirentes` são properties que chamam
                # `.filter()` e, por isso, ignoram o cache montado por
                # `prefetch_related('pessoas__pessoa')`. Particionar a relação
                # já prefetched evita duas queries extras por lançamento.
                pessoas_lancamento = list(lancamento.pessoas.all())

                # Transmitente
                transmitentes = [
                    vinculo.pessoa.nome
                    for vinculo in pessoas_lancamento
                    if vinculo.tipo == 'transmitente'
                ]
                ws.cell(row=row, column=6, value=", ".join(transmitentes) if transmitentes else "-").border = border

                # Adquirente
                adquirentes = [
                    vinculo.pessoa.nome
                    for vinculo in pessoas_lancamento
                    if vinculo.tipo == 'adquirente'
                ]
                ws.cell(row=row, column=7, value=", ".join(adquirentes) if adquirentes else "-").border = border

                # Transmissão
                if lancamento.tipo.tipo == 'averbacao':
                    # Para averbação, mesclar colunas e mostrar descrição
                    ws.merge_cells(f'H{row}:M{row}')
                    ws.cell(row=row, column=8, value=lancamento.descricao or "-").border = border
                else:
                    # Para outros tipos, mostrar campos específicos
                    ws.cell(row=row, column=8, value=lancamento.forma or "-").border = border
                    ws.cell(row=row, column=9, value=normalizar_texto_opcional(lancamento.titulo, "-")).border = border
                    ws.cell(row=row, column=10, value=abreviar_cartorio(lancamento.cartorio_transmissao_compat.nome) if lancamento.cartorio_transmissao_compat else "-").border = border
                    ws.cell(row=row, column=11, value=lancamento.livro_transacao or "-").border = border
                    ws.cell(row=row, column=12, value=lancamento.folha_transacao or "-").border = border
                    ws.cell(row=row, column=13, value=lancamento.data_transacao.strftime('%d/%m/%Y') if lancamento.data_transacao else "-").border = border

                # Área, Origem, Observações
                # Issue #13: a área usa `formatar_area_ha`, que formata no
                # padrão pt-BR (4 casas decimais, ex. "1.234,5678") e já
                # devolve "-" para None — por isso o `if ... is not None
                # else "-"` de antes não é mais necessário aqui. O export
                # por imóvel herda esta mesma formatação por compartilhar
                # este renderer.
                ws.cell(row=row, column=14, value=formatar_area_ha(lancamento.area)).border = border
                ws.cell(row=row, column=15, value=lancamento.origem or "-").border = border
                ws.cell(row=row, column=16, value=lancamento.observacoes or "-").border = border

                row += 1

            # Adicionar linha em branco entre documentos
            row += 1

    return row
