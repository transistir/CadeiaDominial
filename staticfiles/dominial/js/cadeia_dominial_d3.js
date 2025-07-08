// JS para visualização D3 da cadeia dominial
// Busca os dados da árvore e renderiza usando d3.tree()

document.addEventListener('DOMContentLoaded', function() {
    const svg = d3.select('#arvore-d3-svg');
    const width = document.getElementById('arvore-d3-svg').clientWidth || 1000;
    const height = 600;
    svg.attr('width', width).attr('height', height);

    // Limpar SVG
    svg.selectAll('*').remove();

    // Grupo para zoom/pan
    const zoomGroup = svg.append('g').attr('id', 'zoom-group');

    // Comportamento de zoom/pan
    const zoom = d3.zoom()
        .scaleExtent([0.3, 2.5])
        .on('zoom', (event) => {
            zoomGroup.attr('transform', event.transform);
        });
    svg.call(zoom);

    // Guardar zoom para botões
    window._d3zoom = zoom;
    window._d3svg = svg;
    window._zoomGroup = zoomGroup;
    window._zoomTransform = d3.zoomIdentity;
    svg.on('wheel.zoom', null); // Desabilitar zoom na roda do mouse se quiser

    // Buscar dados da árvore (corrigido)
    fetch(`/dominial/cadeia-dominial/${window.tisId}/${window.imovelId}/arvore/`)
        .then(response => response.json())
        .then(data => {
            // Converter para formato de árvore
            const arvore = converterParaArvoreD3(data);
            renderArvoreD3(arvore, zoomGroup, width, height);
            // Enquadrar após renderizar
            setTimeout(() => enquadrarArvoreNoSVG(svg, zoomGroup, width, height), 100);
        })
        .catch(err => {
            svg.append('text')
                .attr('x', width/2)
                .attr('y', height/2)
                .attr('text-anchor', 'middle')
                .attr('fill', 'red')
                .text('Erro ao carregar dados da árvore');
        });
});

function ordenarFilhosPorNumeroDesc(nodo) {
    if (nodo.children && nodo.children.length > 0) {
        nodo.children.sort((a, b) => {
            // Extrair número ignorando prefixos não numéricos
            const numA = parseInt((a.numero || '').replace(/\D/g, ''));
            const numB = parseInt((b.numero || '').replace(/\D/g, ''));
            return numB - numA;
        });
        nodo.children.forEach(ordenarFilhosPorNumeroDesc);
    }
}

function converterParaArvoreD3(data) {
    // Mapear documentos por número
    const docMap = {};
    data.documentos.forEach(doc => {
        doc.children = [];
        docMap[doc.numero] = doc;
    });
    // Montar filhos a partir das conexões
    data.conexoes.forEach(con => {
        const from = docMap[con.from];
        const to = docMap[con.to];
        if (to && from) {
            to.children.push(from);
        }
    });
    // Encontrar a matrícula principal (raiz)
    let raiz = data.documentos.find(doc => doc.nivel === 0 || doc.origem === '' || doc.origem == null);
    if (!raiz) raiz = data.documentos[0];
    // Ordenar filhos recursivamente
    ordenarFilhosPorNumeroDesc(raiz);
    return raiz;
}

function centralizarArvore(width, height) {
    // Centraliza o grupo na tela
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    const zoomGroup = window._zoomGroup;
    // Centralizar em (width/2, height/2)
    const t = d3.zoomIdentity.translate(width/2, 60).scale(1);
    svg.transition().duration(400).call(zoom.transform, t);
    window._zoomTransform = t;
}

function renderArvoreD3(data, svgGroup, width, height) {
    // Converter para d3.hierarchy
    const root = d3.hierarchy(data);
    // Aumentar espaçamento vertical e horizontal
    const treeLayout = d3.tree().size([height * 1.8, width - 200]);
    treeLayout(root);

    // Desenhar links
    svgGroup.selectAll('path.link')
        .data(root.links())
        .enter()
        .append('path')
        .attr('class', 'link')
        .attr('fill', 'none')
        .attr('stroke', '#28a745')
        .attr('stroke-width', 2)
        .attr('d', d3.linkHorizontal()
            .x(d => d.y + 100)
            .y(d => d.x + 20)
        );

    // Desenhar nós (cards)
    const node = svgGroup.selectAll('g.node')
        .data(root.descendants())
        .enter()
        .append('g')
        .attr('class', 'node')
        .attr('transform', d => `translate(${d.y + 100},${d.x + 20})`)
        .style('cursor', 'pointer');

    // Card base
    node.append('rect')
        .attr('width', 120)
        .attr('height', 60)
        .attr('x', -60)
        .attr('y', -30)
        .attr('rx', 12)
        .attr('fill', d => d.data.tipo === 'transcricao' ? '#6f42c1' : '#007bff')
        .attr('stroke', d => d.data.tipo === 'transcricao' ? '#5a32a3' : '#0056b3')
        .attr('stroke-width', 2)
        .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.10))')
        .on('mouseover', function() {
            d3.select(this)
                .transition().duration(120)
                .attr('stroke-width', 3)
                .attr('filter', 'drop-shadow(0 6px 20px rgba(0,0,0,0.25))')
                .attr('transform', 'scale(1.06)');
        })
        .on('mouseout', function() {
            d3.select(this)
                .transition().duration(120)
                .attr('stroke-width', 2)
                .attr('filter', 'drop-shadow(0 2px 8px rgba(0,0,0,0.10))')
                .attr('transform', 'scale(1)');
        });

    // Número do documento
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', -6)
        .attr('fill', 'white')
        .attr('font-size', 20)
        .attr('font-weight', 700)
        .text(d => d.data.numero || d.data.name || '');

    // Total de lançamentos
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('y', 14)
        .attr('fill', 'white')
        .attr('font-size', 11)
        .attr('opacity', 0.7)
        .text(d => d.data.total_lancamentos !== undefined ? `${d.data.total_lancamentos} lançamentos` : '');

    // Botões SVG
    const btnGroup = node.append('g')
        .attr('class', 'card-buttons')
        .attr('transform', 'translate(0,28)');

    // 👁️ Ver lançamentos
    btnGroup.append('text')
        .attr('x', -20)
        .attr('y', 0)
        .attr('font-size', 18)
        .attr('cursor', 'pointer')
        .attr('opacity', 0.85)
        .text('👁️')
        .on('click', (event, d) => {
            event.stopPropagation();
            window.location.href = `/dominial/documento/${d.data.id}/lancamentos/${window.tisId}/${window.imovelId}/`;
        });

    // ➕ Novo lançamento
    btnGroup.append('text')
        .attr('x', 20)
        .attr('y', 0)
        .attr('font-size', 18)
        .attr('cursor', 'pointer')
        .attr('opacity', 0.85)
        .text('➕')
        .on('click', (event, d) => {
            event.stopPropagation();
            window.location.href = `/dominial/tis/${window.tisId}/imovel/${window.imovelId}/novo-lancamento/${d.data.id}/`;
        });
}

// Controle de zoom para o SVG D3
let currentZoom = 1;
const minZoom = 0.3;
const maxZoom = 2.5;
const zoomStep = 0.2;

function applyZoom() {
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    const t = window._zoomTransform.rescaleY ? window._zoomTransform : d3.zoomTransform(svg.node());
    svg.transition().duration(200).call(zoom.scaleBy, currentZoom / t.k);
}

window.zoomIn = function() {
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    svg.transition().duration(200).call(zoom.scaleBy, 1.2);
    currentZoom = Math.min(currentZoom * 1.2, maxZoom);
}

window.zoomOut = function() {
    const svg = window._d3svg;
    const zoom = window._d3zoom;
    svg.transition().duration(200).call(zoom.scaleBy, 0.8);
    currentZoom = Math.max(currentZoom * 0.8, minZoom);
}

window.resetZoom = function() {
    const svg = window._d3svg;
    centralizarArvore(svg.attr('width'), svg.attr('height'));
    currentZoom = 1;
}

function enquadrarArvoreNoSVG(svg, zoomGroup, width, height) {
    // Pega o bounding box do grupo de nós
    const nodes = zoomGroup.selectAll('.node');
    if (nodes.size() === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    nodes.each(function() {
        const bbox = this.getBBox();
        const x = +this.getAttribute('transform').split('(')[1].split(',')[0];
        const y = +this.getAttribute('transform').split(',')[1].split(')')[0];
        minX = Math.min(minX, x + bbox.x);
        maxX = Math.max(maxX, x + bbox.x + bbox.width);
        minY = Math.min(minY, y + bbox.y);
        maxY = Math.max(maxY, y + bbox.y + bbox.height);
    });
    const treeWidth = maxX - minX;
    const treeHeight = maxY - minY;
    // Calcular escala para caber tudo
    const scale = Math.min((width - 60) / treeWidth, (height - 60) / treeHeight, 1);
    // Centralizar
    const tx = (width - treeWidth * scale) / 2 - minX * scale;
    const ty = (height - treeHeight * scale) / 2 - minY * scale;
    const t = d3.zoomIdentity.translate(tx, ty).scale(scale);
    svg.transition().duration(400).call(window._d3zoom.transform, t);
    window._zoomTransform = t;
} 