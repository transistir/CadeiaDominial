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

## Instruções para Teste

### 1. Configuração Inicial

1. Clone o repositório:
```bash
git clone [URL_DO_REPOSITÓRIO]
cd CadeiaDominial
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

### 2. Configuração do Banco de Dados

1. Execute as migrações:
```bash
python manage.py migrate
```

2. Importe os dados das Terras Indígenas da FUNAI:
```bash
python manage.py importar_terras_indigenas
```

### 3. Criação de Usuário

1. Crie um usuário administrador:
```bash
python manage.py createsuperuser
```
- Siga as instruções para criar um usuário e senha
- Este usuário terá acesso total ao sistema

### 4. Executando o Sistema

1. Inicie o servidor de desenvolvimento:
```bash
python manage.py runserver
```

2. Acesse o sistema:
- Abra o navegador e acesse: http://localhost:8000/
- Faça login com o usuário criado no passo 3

### 5. Testando as Funcionalidades

1. **Cadastro de Terras Indígenas**
   - Após fazer login, você verá a lista de TIs disponíveis
   - Clique em "Cadastrar Nova Terra Indígena"
   - Selecione uma TI da lista importada da FUNAI

2. **Cadastro de Imóveis**
   - Dentro de uma TI, você pode cadastrar imóveis
   - Preencha os dados do imóvel (matrícula, área, etc.)

3. **Cadastro de Alterações**
   - Para cada imóvel, você pode registrar alterações
   - Escolha o tipo (registro, averbação ou não classificado)
   - Preencha os dados específicos de cada tipo

4. **Visualização de Cadeia Dominial**
   - Acesse um imóvel para ver sua cadeia dominial
   - O sistema mostrará todas as alterações em ordem cronológica

### 6. Dados de Teste

- O sistema já vem com dados de referência das TIs da FUNAI
- Você pode criar dados de teste para imóveis e alterações
- Use o painel administrativo (/admin) para gerenciar dados de referência

### 7. Solução de Problemas

Se encontrar algum erro:

1. Verifique se todas as migrações foram aplicadas:
```bash
python manage.py showmigrations
```

2. Verifique se os dados da FUNAI foram importados:
```bash
python manage.py importar_terras_indigenas
```

3. Verifique os logs do servidor para mensagens de erro

4. Certifique-se de que o usuário tem as permissões necessárias:
   - Acesse o painel administrativo
   - Verifique os grupos e permissões do usuário