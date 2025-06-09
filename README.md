# CadeiaDominial

Uma plataforma web para gerenciar e analisar cadeias dominiais de imóveis sobrepostos a terras indígenas. O sistema deve ser capaz de:
1. Inserir e sistematizar dados fundiários :
	- Registrar informações detalhadas de transações imobiliárias (compra, venda, transferência, etc.).
	- Armazenar dados como matrícula, transmitente, adquirente, forma de transmissão, área, origem, observações, etc.
2. Processar e analisar cadeias dominiais :
	- Construir diagramas que representem as relações entre as transações.
3. Emitir fichas automatizadas e relatórios :
	- Gerar fichas por imóvel em formatos compatíveis com planilhas já utilizadas pela equipe técnica.
	- Emitir relatórios sintetizando informações por terra indígena.
4. Autenticação e controle de acesso :
	- Implementar um sistema de autenticação e controle de acesso para garantir segurança.
5. Banco de dados estruturado :
	- Armazenar todas as informações de forma organizada e acessível.
6. Exportação de resultados :
	- Permitir exportação dos resultados em formatos abertos (por exemplo, CSV, JSON).
7. Diagrama de rede :
	- Criar visualizações gráficas das cadeias dominiais para facilitar a análise.

## Fluxo do Usuario
### ANALISAR CADEIA DOMINIAL DE MATRÍCULAS SOBREPOSTAS A UMA TI
1. O usuário entra no sistema e escolhe uma terra indígena .
2. Dentro da terra, ele vê uma lista de propriedades já cadastradas ou pode cadastrar uma nova.
3. Para cada propriedade, ele pode ver uma lista de alterações ou adicionar uma nova.
4. Ao cadastrar uma alteração, ele seleciona o tipo :
	- Se for registro , preenche transmitente e adquirente .
	- Se for averbação , seleciona o tipo específico.
	- Se for não classificado , precisa preencher área e origem obrigatoriamente.
5. Sempre há campos comuns: forma, título, cartório, livro, folha, data_alteracao, observação .


### 🔗 Relacionamentos entre tabelas
- Uma terra indígena pode ter muitas propriedades
- Uma propriedade pode ter muitas alterações
- Cada alteração tem um tipo (registro, averbação ou não classificado)
- Se for registro , ela tem uma forma de registro
- Se for averbação , ela tem uma forma de averbação
- As formas de registro e averbação são listas fixas, mas editáveis pelo admin