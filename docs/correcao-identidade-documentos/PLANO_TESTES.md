# Sistema de testes do desenvolvimento

## Objetivo

Impedir regressões em que coincidência numérica conecte documentos de cartórios ou tipos diferentes. Cada correção deve ser verificada no nível mais baixo possível e também no cenário integrado central.

## Pirâmide de testes

1. **Unitários:** normalização e identidade, sem banco quando possível.
2. **Modelo/banco:** constraints e combinações permitidas/proibidas.
3. **Serviços:** resolução, duplicata, importação, hierarquia e árvore.
4. **Views/formulários:** dados enviados pelo usuário e validação no backend.
5. **Integração:** cadeia completa com números coincidentes.
6. **Migração:** banco anterior, conflitos, avanço e reversibilidade suportada.
7. **Auditoria estática:** nenhuma consulta de relacionamento usa número sozinho.

## Dados-padrão dos testes

Todos os testes relevantes devem partir deste conjunto mínimo:

| Registro | Tipo | Número | Cartório | Resultado esperado |
|---|---|---|---|---|
| A | matrícula | `123` | Cartório A / CNS-A | identidade A |
| B | matrícula | `123` | Cartório B / CNS-B | identidade B, diferente de A |
| C | transcrição | `123` | Cartório A / CNS-A | identidade C, diferente de A |
| D | matrícula | `00123` | Cartório A / CNS-A | preservar como identidade distinta até decisão contrária |

Crie os registros em ordens diferentes nos testes que antes dependiam de `.first()`. O resultado deve ser igual em qualquer ordem.

## Portões de qualidade

### Por tarefa

Uma tarefa só pode ir para `EM REVISÃO` quando:

- seus testes específicos passam;
- testes do módulo alterado passam;
- nenhum teste existente foi removido ou afrouxado sem justificativa no diário;
- a evidência contém o comando e o resultado real.

### Por fase

- **Fundação:** todos os testes unitários e de serviço central passam.
- **Fluxos críticos:** CT-01 a CT-20 passam.
- **Banco:** auditoria sem conflitos não explicados e testes de migração passam.
- **Origens:** o modelo estruturado, a escrita dupla e o fallback são testados.
- **Entrega:** suíte completa, auditoria estática e teste manual de fumaça passam.

## Comandos

O projeto usa Django. Em um ambiente com dependências instaladas, prefira testes focados antes da suíte completa:

```bash
python manage.py test dominial.tests.test_identidade_documento
python manage.py test dominial.tests.test_duplicata_verificacao
python manage.py test dominial.tests
python manage.py check
python manage.py makemigrations --check --dry-run
```

Se os novos testes forem organizados em outros módulos, registre o caminho real em `DIARIO.md`. Não declare aprovação quando o comando não puder rodar por ausência de Django, banco ou variáveis de ambiente; registre como `NÃO EXECUTADO` e o motivo.

## Testes de migração

Cada alteração de constraint deve testar separadamente:

1. banco no estado da migração anterior;
2. avanço sem conflitos;
3. avanço com conflito e interrupção segura;
4. constraints efetivamente presentes no banco;
5. combinações permitidas e proibidas após a migração;
6. reversão, quando a migração declarar suporte real a ela.

Nunca use uma cópia única de produção como ambiente de teste. A auditoria deve rodar antes da migração.

## Auditoria estática

Ao fim de cada fase crítica, procure ocorrências suspeitas:

```bash
rg -n "Documento\.objects\.(filter|get|get_or_create)" dominial --glob '*.py'
rg -n "numero=.*\.first\(\)|filter\([^)]*numero[^)]*\)" dominial --glob '*.py'
rg -n "documentos_por_numero|processados.*numero" dominial --glob '*.py'
```

Cada ocorrência deve ser classificada como:

- `RELACIONAMENTO`: deve usar identidade completa;
- `PESQUISA TEXTUAL`: pode usar número, mas não pode criar vínculo;
- `FALSO POSITIVO`: justificar no relatório.

## Teste manual de fumaça em homologação

1. Criar matrícula `123` no Cartório A.
2. Criar matrícula `123` no Cartório B.
3. Confirmar que ambos os cadastros são aceitos.
4. Abrir cada cadeia e confirmar cartório e imóvel corretos.
5. Criar “Início de Matrícula” no Cartório B.
6. Confirmar que o documento do Cartório A não foi alterado.
7. Reutilizar/importar a origem do Cartório A explicitamente.
8. Confirmar que a interface mostra CNS, cidade/UF e imóvel.
9. Gerar tabela, árvore e PDF de ambas as cadeias.
10. Confirmar que nenhuma conexão ocorreu apenas pelo número.

Registre data, ambiente, usuário de teste, IDs criados e resultado na matriz. Remova os dados de homologação apenas pelo procedimento autorizado do ambiente.

## Política para falhas

- Falha em CT-01, CT-02, CT-13, CT-16, CT-18, CT-19 ou CT-20 bloqueia a entrega.
- Teste intermitente deve ser tratado como falha, não reexecutado até “passar”.
- Alterar expectativa para aceitar o comportamento antigo exige decisão registrada.
- Uma falha de migração não autoriza apagar ou consolidar dados automaticamente.
