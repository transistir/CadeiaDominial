# Entendendo a Cadeia Dominial

Imagine a **Cadeia Dominial** como a "árvore genealógica" de um pedaço de terra. Assim como pesquisamos nossos antepassados para saber de onde viemos, a cadeia dominial reconta a história de um imóvel para garantir que o dono atual é, de fato, o dono legítimo.

Este documento explica de forma simples como o sistema transforma dados de cartório em um mapa visual compreensível.

---

### 1. A Matéria-Prima (Os Dados no Banco)
Tudo começa nos cartórios. O banco de dados guarda o que está escrito nos livros de registro (**Matrículas** e **Transcrições**). 

Para o sistema, cada pedaço dessa história é como uma peça de um quebra-cabeça:
*   **O Imóvel:** É o protagonista. Ele tem um "RG" (o número da matrícula).
*   **Os Eventos (Lançamentos):** São as coisas que acontecem com a terra. Alguém comprou? Alguém herdou? O dono resolveu dividir a fazenda em três? Ou juntou dois lotes para fazer um shopping?
*   **O "DNA" da Origem:** Este é o ponto mais importante. Quase todo registro novo diz de onde ele veio (ex: "este lote nasceu do desmembramento da Fazenda X"). O banco de dados captura essa "ponte" entre o passado e o presente.

### 2. Construindo a História
Para montar a cadeia, o sistema faz o papel de um historiador:
1.  Ele escolhe um ponto de partida (um imóvel).
2.  Ele olha para trás: "Quem era o dono antes?" e "De qual terra este lugar nasceu?".
3.  Ele olha para frente: "Esta terra ainda existe ou foi dividida em outras novas?".
4.  O sistema vai ligando esses pontos através dos **Tipos de Lançamento**. Se foi uma "Venda", a linha segue contínua. Se foi um "Desmembramento", uma caixa se transforma em várias outras menores.

### 3. Transformando Texto em Mapa (Visualização)
Ler centenas de páginas de cartório é exaustivo. É aqui que entra a tecnologia (ReactFlow), que funciona como um "tradutor visual". Ele transforma dados áridos em um mapa vivo:

*   **As Caixinhas (Nodos):** Cada uma representa um momento ou um estado da terra. Pense nelas como "retratos no tempo". Nelas, você vê o nome do dono, o tamanho da área e o número do documento.
*   **As Setas (Conexões):** Elas mostram o fluxo do tempo e da propriedade. 
    *   Uma seta única indica que a terra apenas mudou de mãos.
    *   Várias setas saindo de uma única caixa mostram uma **divisão** (como galhos de uma árvore).
    *   Várias setas entrando em uma única caixa mostram uma **fusão** de terras.
*   **As Cores e Formas:** O gráfico usa cores diferentes para você bater o olho e saber o que é uma matrícula ativa, o que é uma transcrição antiga ou onde a história "termina" (quando a terra não foi mais mexida).

---

### Em resumo
O sistema pega milhares de frases técnicas escritas em livros de cartório, identifica quem "nasceu" de quem, e desenha um mapa onde você pode navegar com o mouse. É como sair de uma lista de nomes em uma planilha e entrar em um mapa do tesouro, onde você segue as setas para entender exatamente como aquela fazenda de 1920 se transformou nos bairros de hoje.
