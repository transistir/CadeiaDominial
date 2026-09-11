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

import re
from datetime import date

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..utils import abreviar_cartorio, normalizar_texto_opcional
from ..utils.formatacao_utils import formatar_area_ha, formatar_origem_completa

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

PREFIXOS_FORMULA_EXCEL = ('=', '+', '-', '@', '\t', '\r')
CARACTERES_INVALIDOS_ABA = re.compile(r'[:\\/?*\[\]\x00-\x1f]')
LIMITE_NOME_ABA = 31
NOMES_RESERVADOS_ABA = {'history'}

# Tokens visuais copiados dos CSS dos PDFs (`cadeia_dominial_pdf.css` e
# `cadeia_completa_pdf.css`). Manter os valores sincronizados com a fonte de
# referência aprovada pelo cliente.
COR_TEXTO = "333333"
COR_AZUL_TEXTO = "2C5AA0"
COR_CABECALHO = "F8F9FA"
COR_AGRUPAMENTO = "E1EDF7"
COR_BRANCO = "FFFFFF"
COR_BORDA = "DDDDDD"

FONTE_CORPO = Font(name="Arial", size=8, color=COR_TEXTO)


def escrever_celula_segura(ws, row, column, value):
    """
    Escreve um valor sem permitir que texto digitado pelo usuário vire
    fórmula no XLSX.

    O openpyxl infere strings iniciadas por ``=`` como fórmula. Os demais
    prefixos também são vetores conhecidos de formula injection em leitores
    de planilha, então todos são marcados explicitamente como texto. Valores
    não textuais mantêm a inferência original do openpyxl.
    """
    cell = ws.cell(row=row, column=column)
    cell.value = value
    cell.font = FONTE_CORPO
    if isinstance(value, str) and value.startswith(PREFIXOS_FORMULA_EXCEL):
        cell.data_type = 's'
    return cell


def criar_estilos():
    """
    Cria os estilos equivalentes ao PDF para título, informações do imóvel,
    cabeçalhos, dados e zebra. Centralizado aqui para que todos os exports
    XLS usem exatamente a mesma tipografia, cores, bordas e alturas.
    """
    borda = Side(style='thin', color=COR_BORDA)
    return {
        'title_font': Font(
            name="Arial", bold=True, size=18, color=COR_AZUL_TEXTO
        ),
        'body_font': FONTE_CORPO,
        'label_font': Font(name="Arial", bold=True, size=8, color=COR_TEXTO),
        'document_font': Font(
            name="Arial", bold=True, size=8, color=COR_AZUL_TEXTO
        ),
        'header_font': Font(
            name="Arial", bold=True, size=6, color=COR_TEXTO
        ),
        'data_font': Font(name="Arial", size=6, color=COR_TEXTO),
        'header_fill': PatternFill(
            start_color=COR_CABECALHO,
            end_color=COR_CABECALHO,
            fill_type="solid",
        ),
        'group_fill': PatternFill(
            start_color=COR_AGRUPAMENTO,
            end_color=COR_AGRUPAMENTO,
            fill_type="solid",
        ),
        'zebra_even_fill': PatternFill(
            start_color=COR_CABECALHO,
            end_color=COR_CABECALHO,
            fill_type="solid",
        ),
        'zebra_odd_fill': PatternFill(
            start_color=COR_BRANCO,
            end_color=COR_BRANCO,
            fill_type="solid",
        ),
        'border': Border(
            left=borda,
            right=borda,
            top=borda,
            bottom=borda,
        ),
        'title_alignment': Alignment(
            horizontal='center', vertical='center', wrap_text=False
        ),
        'center_alignment': Alignment(
            horizontal='center', vertical='center', wrap_text=True
        ),
        'data_alignment': Alignment(
            horizontal='left', vertical='top', wrap_text=True
        ),
        'body_alignment': Alignment(
            horizontal='left', vertical='top', wrap_text=False
        ),
        'title_row_height': 24,
        'body_row_height': 12,
        'document_row_height': 18,
        'header_row_height': 12,
        'spacer_row_height': 6,
    }


def ajustar_larguras_colunas(ws):
    """Aplica `LARGURAS_COLUNAS` às `TOTAL_COLUNAS` colunas (A..P) da planilha."""
    for i, width in enumerate(LARGURAS_COLUNAS, 1):
        ws.column_dimensions[get_column_letter(i)].width = width


def criar_nome_aba_imovel(matricula, nomes_usados, indice_imovel=None):
    """
    Gera um nome de aba válido e único a partir da matrícula.

    O Excel limita títulos a 31 caracteres, proíbe ``: \\ / ? * [ ]`` e
    compara títulos sem distinguir maiúsculas de minúsculas. Preservamos a
    grafia legível da matrícula (caixa, espaços, hífens e acentos), removendo
    somente caracteres inválidos. ``History`` é reservado pelo Excel.

    O sufixo ``~N`` fica dentro do limite e evita confundir uma duplicata com
    uma matrícula real terminada em ``-2``. Matrículas vazias recebem um nome
    estável baseado na posição do imóvel no arquivo.
    """
    nome_base = CARACTERES_INVALIDOS_ABA.sub(
        "", str(matricula) if matricula is not None else ""
    ).strip().strip("'")
    if not nome_base:
        nome_base = (
            f"imovel-{indice_imovel}"
            if indice_imovel is not None
            else "imovel"
        )
    nome_base = nome_base[:LIMITE_NOME_ABA].rstrip("'")
    nomes_normalizados = {
        nome.casefold() for nome in nomes_usados
    } | NOMES_RESERVADOS_ABA

    candidato = nome_base
    indice = 2
    while candidato.casefold() in nomes_normalizados:
        sufixo = f"~{indice}"
        candidato = f"{nome_base[:LIMITE_NOME_ABA - len(sufixo)]}{sufixo}"
        indice += 1

    return candidato


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

    Retorna a próxima linha livre após a separação do último documento.

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
    group_fill = estilos['group_fill']
    border = estilos['border']
    center_alignment = estilos['center_alignment']
    data_alignment = estilos['data_alignment']

    row = linha_inicial - 1

    for tronco in cadeia_completa:
        # Processar documentos do tronco
        for item in tronco['documentos']:
            documento = item['documento']
            lancamentos = item['lancamentos']
            prefixo_importado = (
                "[Importado] " if item.get('is_importado', False) else ""
            )
            # Título do documento
            row += 1
            ws.merge_cells(f'A{row}:{ULTIMA_COLUNA}{row}')
            escrever_celula_segura(
                ws,
                row,
                1,
                f"{prefixo_importado}"
                f"{documento.tipo.get_tipo_display()}: {documento.numero}",
            ).font = estilos['document_font']
            ws.cell(row=row, column=1).fill = group_fill
            ws.cell(row=row, column=1).alignment = data_alignment
            ws.row_dimensions[row].height = estilos['document_row_height']
            row += 1

            # Cabeçalho da tabela de lançamentos (igual ao template)
            # Primeira linha de cabeçalho (agrupamentos)
            ws.merge_cells(f'A{row}:E{row}')
            escrever_celula_segura(ws, row, 1, "MATRÍCULA").font = header_font
            ws.cell(row=row, column=1).fill = group_fill
            ws.cell(row=row, column=1).alignment = center_alignment

            ws.merge_cells(f'F{row}:G{row}')
            escrever_celula_segura(ws, row, 6, "").fill = group_fill

            ws.merge_cells(f'H{row}:M{row}')
            escrever_celula_segura(ws, row, 8, "TRANSMISSÃO").font = header_font
            ws.cell(row=row, column=8).fill = group_fill
            ws.cell(row=row, column=8).alignment = center_alignment

            escrever_celula_segura(ws, row, 14, "Área (ha)").font = header_font
            ws.cell(row=row, column=14).fill = header_fill
            ws.cell(row=row, column=14).alignment = center_alignment

            escrever_celula_segura(ws, row, 15, "Origem").font = header_font
            ws.cell(row=row, column=15).fill = header_fill
            ws.cell(row=row, column=15).alignment = center_alignment

            escrever_celula_segura(ws, row, 16, "Observações").font = header_font
            ws.cell(row=row, column=16).fill = header_fill
            ws.cell(row=row, column=16).alignment = center_alignment

            for col in range(1, TOTAL_COLUNAS + 1):
                ws.cell(row=row, column=col).border = border
            ws.row_dimensions[row].height = estilos['header_row_height']
            row += 1

            # Segunda linha de cabeçalho (colunas específicas)
            for col, header in enumerate(CABECALHOS_DETALHADOS, 1):
                cell = escrever_celula_segura(ws, row, col, header)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                cell.alignment = center_alignment
            ws.row_dimensions[row].height = estilos['header_row_height']
            row += 1

            # Adicionar lançamentos
            for indice_lancamento, lancamento in enumerate(lancamentos):
                # Nº (usando o filtro numero_documento_criado)
                from ..templatetags.dominial_extras import numero_documento_criado
                numero_formatado = numero_documento_criado(lancamento)
                escrever_celula_segura(ws, row, 1, numero_formatado).border = border

                # L, Fls., Cartório, Data (do documento)
                escrever_celula_segura(
                    ws, row, 2, documento.livro or "-"
                ).border = border
                folha_valor = "-" if documento.tipo and documento.tipo.tipo == 'matricula' else (documento.folha or "-")
                escrever_celula_segura(ws, row, 3, folha_valor).border = border
                escrever_celula_segura(
                    ws,
                    row,
                    4,
                    abreviar_cartorio(documento.cartorio.nome)
                    if documento.cartorio else "-",
                ).border = border
                escrever_celula_segura(
                    ws,
                    row,
                    5,
                    lancamento.data.strftime('%d/%m/%Y')
                    if lancamento.data else "-",
                ).border = border

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
                escrever_celula_segura(
                    ws,
                    row,
                    6,
                    ", ".join(transmitentes) if transmitentes else "-",
                ).border = border

                # Adquirente
                adquirentes = [
                    vinculo.pessoa.nome
                    for vinculo in pessoas_lancamento
                    if vinculo.tipo == 'adquirente'
                ]
                escrever_celula_segura(
                    ws,
                    row,
                    7,
                    ", ".join(adquirentes) if adquirentes else "-",
                ).border = border

                # Transmissão
                if lancamento.tipo.tipo == 'averbacao':
                    # Para averbação, mesclar colunas e mostrar descrição
                    ws.merge_cells(f'H{row}:M{row}')
                    escrever_celula_segura(
                        ws, row, 8, lancamento.descricao or "-"
                    ).border = border
                else:
                    # Para outros tipos, mostrar campos específicos
                    escrever_celula_segura(
                        ws, row, 8, lancamento.forma or "-"
                    ).border = border
                    escrever_celula_segura(
                        ws,
                        row,
                        9,
                        normalizar_texto_opcional(lancamento.titulo, "-"),
                    ).border = border
                    escrever_celula_segura(
                        ws,
                        row,
                        10,
                        abreviar_cartorio(
                            lancamento.cartorio_transmissao_compat.nome
                        ) if lancamento.cartorio_transmissao_compat else "-",
                    ).border = border
                    escrever_celula_segura(
                        ws, row, 11, lancamento.livro_transacao or "-"
                    ).border = border
                    escrever_celula_segura(
                        ws, row, 12, lancamento.folha_transacao or "-"
                    ).border = border
                    escrever_celula_segura(
                        ws,
                        row,
                        13,
                        lancamento.data_transacao.strftime('%d/%m/%Y')
                        if lancamento.data_transacao else "-",
                    ).border = border

                # Área, Origem, Observações
                # Issue #13: a área usa `formatar_area_ha`, que formata no
                # padrão pt-BR (4 casas decimais, ex. "1234,5678") e já
                # devolve "-" para None — por isso o `if ... is not None
                # else "-"` de antes não é mais necessário aqui. O export
                # por imóvel herda esta mesma formatação por compartilhar
                # este renderer.
                escrever_celula_segura(
                    ws, row, 14, formatar_area_ha(lancamento.area)
                ).border = border
                escrever_celula_segura(
                    ws, row, 15, formatar_origem_completa(lancamento)
                ).border = border
                escrever_celula_segura(
                    ws, row, 16, lancamento.observacoes or "-"
                ).border = border

                zebra_fill = (
                    estilos['zebra_even_fill']
                    if indice_lancamento % 2 == 0
                    else estilos['zebra_odd_fill']
                )
                for col in range(1, TOTAL_COLUNAS + 1):
                    cell = ws.cell(row=row, column=col)
                    cell.font = estilos['data_font']
                    cell.fill = zebra_fill
                    cell.border = border
                    cell.alignment = data_alignment
                # Não definir altura nas linhas de dados: Origem pode conter
                # várias linhas e Observações pode quebrar pela largura da
                # coluna. Uma altura explícita gera ``customHeight="1"`` no
                # XLSX e impede o auto-fit do Excel, ocultando parte do texto.

                row += 1

            # Adicionar linha em branco entre documentos
            ws.row_dimensions[row].height = estilos['spacer_row_height']
            row += 1

    return row


def renderizar_planilha_imovel(
    ws,
    tis,
    imovel,
    cadeia_completa,
    estilos=None,
    usar_cri_abreviado=False,
):
    """
    Renderiza uma planilha completa de um imóvel.

    É a única implementação do layout usado tanto pelo XLS individual quanto
    por cada aba de imóvel do XLS consolidado da TI. O bloco narrativo mantém
    ``Cartório:`` e o nome por extenso no individual (#50); no consolidado,
    ``usar_cri_abreviado`` aplica ``CRI:`` e a sigla definida pela #166.
    """
    if estilos is None:
        estilos = criar_estilos()

    ws.merge_cells(f'A1:{ULTIMA_COLUNA}1')
    titulo = escrever_celula_segura(
        ws, 1, 1, f"CADEIA DOMINIAL GERAL - {imovel.nome}"
    )
    titulo.font = estilos['title_font']
    # O título ocupa A:P e deve permanecer em uma única linha. Wrap junto
    # da altura fixa de 24 pontos ocultava nomes longos de imóveis.
    titulo.alignment = estilos['title_alignment']
    ws.row_dimensions[1].height = estilos['title_row_height']

    nome_cartorio = imovel.cartorio.nome if imovel.cartorio else ""
    rotulo_cartorio = "Cartório:"
    if usar_cri_abreviado:
        rotulo_cartorio = "CRI:"
        nome_cartorio = abreviar_cartorio(nome_cartorio)

    informacoes = (
        ("TIS:", tis.nome),
        ("Matrícula:", imovel.matricula),
        ("Nome:", imovel.nome),
        (
            "Proprietário:",
            imovel.proprietario.nome if imovel.proprietario else "",
        ),
        (rotulo_cartorio, nome_cartorio),
        ("Data de Exportação:", date.today().strftime('%d/%m/%Y')),
    )
    for linha, (rotulo, valor) in enumerate(informacoes, start=3):
        celula_rotulo = escrever_celula_segura(ws, linha, 1, rotulo)
        celula_rotulo.font = estilos['label_font']
        celula_rotulo.fill = estilos['header_fill']
        celula_valor = escrever_celula_segura(ws, linha, 2, valor)
        for celula in (celula_rotulo, celula_valor):
            celula.border = estilos['border']
            # O valor ocupa B e transborda pelas células vazias seguintes,
            # como no layout histórico do export individual (#50). Wrap com
            # altura fixa confinava nomes longos à largura reduzida de B.
            celula.alignment = estilos['body_alignment']

    if cadeia_completa:
        escrever_secao_documentos(ws, cadeia_completa, 11, estilos)
    else:
        celula_vazia = escrever_celula_segura(
            ws, 11, 1, "Sem documentos cadastrados."
        )
        celula_vazia.alignment = estilos['body_alignment']
        ws.row_dimensions[11].height = estilos['body_row_height']

    ajustar_larguras_colunas(ws)
