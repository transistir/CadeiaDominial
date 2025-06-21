# Sistema de Cadeia Dominial

Sistema web para gestão e visualização de cadeias dominiais de terras indígenas, desenvolvido em Django.

## 🚀 Versão Beta v1.0.0

Esta é a primeira versão beta do sistema, disponível para testes com clientes.

### Funcionalidades Implementadas

#### 📋 Gestão de Dados
- **TIs (Terras Indígenas)**: Cadastro e gestão de terras indígenas
- **Imóveis**: Registro de imóveis com matrícula, SNCR e SIGEF
- **Cartórios**: Base de dados de cartórios brasileiros
- **Pessoas**: Cadastro de proprietários e envolvidos
- **Documentos**: Gestão de matrículas e transcrições
- **Lançamentos**: Registro de averbações, registros e alterações

#### 🌳 Visualização em Árvore
- **Diagrama Interativo**: Visualização da cadeia dominial em formato de árvore
- **Zoom e Pan**: Navegação fluida com controles de zoom
- **Cards Dinâmicos**: Tamanho ajustável baseado na quantidade de documentos
- **Conexões Visuais**: Linhas conectando documentos relacionados
- **Origens Identificadas**: Detecção automática de documentos de origem

#### 🎨 Interface Moderna
- **Design Responsivo**: Adaptável a diferentes tamanhos de tela
- **Tema Consistente**: Interface unificada e profissional
- **Navegação Intuitiva**: Menu e botões organizados logicamente
- **Feedback Visual**: Efeitos de hover e transições suaves

#### 🔐 Segurança
- **Autenticação**: Sistema de login/logout
- **Autorização**: Controle de acesso baseado em permissões
- **Validação**: Verificação de dados e integridade

## 🛠️ Tecnologias Utilizadas

- **Backend**: Django 5.2.1
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Banco de Dados**: SQLite (desenvolvimento)
- **Geolocalização**: GeoDjango (PostGIS)
- **Autocomplete**: Django Autocomplete Light

## 📦 Instalação

### Pré-requisitos
- Python 3.8+
- pip
- Git

### Passos de Instalação

1. **Clone o repositório**
```bash
git clone https://github.com/transistir/CadeiaDominial.git
cd CadeiaDominial
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

4. **Configure o banco de dados**
```bash
python manage.py migrate
```

5. **Crie um superusuário**
```bash
python manage.py createsuperuser
```

6. **Execute os comandos de inicialização**
```bash
python manage.py criar_tipos_documento
python manage.py criar_tipos_lancamento
```

7. **Inicie o servidor**
```bash
python manage.py runserver
```

## 🎯 Como Usar

### Acesso ao Sistema
- URL: `http://localhost:8000`
- Use as credenciais do superusuário criado

### Fluxo Principal
1. **Cadastre uma TI** (Terra Indígena)
2. **Adicione Imóveis** à TI
3. **Cadastre Documentos** (matrículas/transcrições)
4. **Registre Lançamentos** nos documentos
5. **Visualize a Cadeia** na árvore dominial

### Visualização em Árvore
- Acesse um imóvel específico
- Clique em "Cadeia Dominial"
- Use os controles de zoom (+/-) para navegar
- Clique nos cards para ver detalhes
- Arraste para mover a visualização

## 🔄 Estratégia de Versionamento

### Branches
- **`main`**: Código estável e testado
- **`develop`**: Desenvolvimento ativo
- **`feature/*`**: Novas funcionalidades
- **`hotfix/*`**: Correções urgentes

### Tags
- **`v1.0.0-beta`**: Primeira versão para testes
- **`v1.0.0`**: Versão estável (futuro)
- **`v1.1.0`**: Novas funcionalidades (futuro)

## 📝 Próximas Versões

### v1.1.0 (Planejado)
- [ ] Relatórios em PDF
- [ ] Exportação de dados
- [ ] Notificações por email
- [ ] Dashboard com estatísticas

### v1.2.0 (Planejado)
- [ ] API REST
- [ ] Integração com sistemas externos
- [ ] Módulo de auditoria
- [ ] Backup automático

## 🤝 Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📞 Suporte

Para dúvidas, sugestões ou problemas:
- Abra uma [Issue](https://github.com/transistir/CadeiaDominial/issues)
- Entre em contato com a equipe de desenvolvimento

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

**Desenvolvido com ❤️ pela equipe Transistir**