# Guia de estudo do código comentado

Este projeto foi comentado em português para facilitar a explicação do TCC. Os comentários descrevem as instruções do código, os dados que elas recebem e o resultado esperado. Não substituem a execução dos testes nem a leitura das regras de negócio.

## Por onde começar

1. Leia `manage.py`: é a entrada para comandos como iniciar o servidor, migrar o banco e executar testes.
2. Leia `config/settings.py`: reúne banco, autenticação, arquivos estáticos e proteções do Django.
3. Abra `config/urls.py` e os `urls.py` dos aplicativos: eles ligam os endereços do navegador às funções de atendimento.
4. Leia `accounts/models.py` e `ombudsman/models.py`: os campos dessas classes correspondem aos dados persistidos no MySQL.
5. Siga o fluxo em `views.py`, `forms.py` e `services.py`: a requisição é autorizada, os dados são validados e só então são gravados ou consultados.
6. Veja `templates/` e `static/`: eles apresentam os dados e cuidam da aparência, sem substituir a autorização feita no servidor.
7. Consulte os arquivos de testes: cada cenário explica uma regra e verifica o comportamento esperado.

## Exemplo: o caminho de uma manifestação

O aluno acessa `/ouvidoria/nova/`. A rota chama a view de criação, que exige sessão autenticada e e-mail institucional confirmado. O formulário valida assunto, descrição, categoria, setor, modalidade de identificação e ciência das regras de privacidade.

Quando o formulário é válido, `create_complaint` grava a manifestação, a relação reservada com seu autor e o primeiro evento do histórico dentro de uma transação. Se uma gravação falhar, a transação evita deixar apenas uma parte do atendimento salva. O protocolo é criado no servidor e o navegador é redirecionado para o detalhe da manifestação.

Na consulta seguinte, o servidor filtra as manifestações pela conta conectada. Saber o protocolo de outra pessoa não concede acesso. Na administração, os dados exibidos são montados explicitamente sem a identidade sigilosa. A consulta excepcional da direção exige senha e justificativa; o registro de auditoria deve ser gravado antes da apresentação da identidade.

## O que os comentários significam

| Arquivo | Forma do comentário | O que estudar |
| --- | --- | --- |
| Python (`.py`) | `# explicação` ou uma docstring entre aspas triplas | Imports, variáveis, campos, validação, controle de fluxo e retorno. |
| Template Django (`.html`) | `{# explicação #}` | Estrutura HTML, blocos, variáveis e formulários; o Django remove estes comentários da resposta. |
| CSS (`.css`) | `/* explicação */` | Seletores, cores, dimensões, layout e adaptação à largura da tela. |
| JavaScript (`.js`) | `// explicação` | Eventos de menu, seleção e cópia de protocolo, com alternativas quando a API não está disponível. |
| YAML, shell e configuração | `# explicação` | Serviços, banco, variáveis, construção e execução dos containers. |
| SVG (`.svg`) | `<!-- explicação -->` | Elementos da ilustração e suas cores; não é uma logo oficial. |

Uma instrução pode ocupar várias linhas, por exemplo uma chamada com muitos argumentos. As explicações acompanham a instrução e os argumentos relevantes; linhas vazias apenas separam assuntos. Nomes reservados como `class`, `return`, `if` e `for` permanecem em inglês porque fazem parte da linguagem Python.

## Cores e logos

A paleta usa azul institucional `#003D59`, amarelo `#FFDF00` e branco. As variações claras e escuras são derivadas para manter a leitura de botões, textos, bordas e estados. O amarelo é usado como destaque, sem texto branco sobre amarelo.

O layout está preparado para os dois arquivos originais:

- `static/img/camporeal-azul.png`: versão de texto azul, exibida sobre o fundo branco do cabeçalho.
- `static/img/camporeal-branca.png`: versão de texto branco, exibida sobre o rodapé azul.

As imagens mostradas na conversa ainda precisam ser fornecidas como arquivos acessíveis ao projeto. Elas não foram redesenhadas nem substituídas por uma logo gerada. Enquanto os dois arquivos não estiverem presentes, o site usa a identificação textual, sem exibir uma imagem quebrada. Prefira os originais com fundo transparente e preserve suas proporções. Se os originais forem SVG, os caminhos dos dois templates e a verificação de presença devem acompanhar essa extensão.

Depois de adicionar os arquivos, rode `./scripts/dev.sh` para reconstruir os estáticos e reiniciar o servidor. A detecção dos arquivos é feita em `config/context_processors.py`; a apresentação está em `templates/base.html`.

## Reproduzir a validação

Use `./scripts/check.sh` para executar a suíte em um MySQL temporário separado do banco da aplicação. Os comentários dos testes explicam o objetivo de cada preparação, ação e verificação.

O teste opcional `scripts/browser_smoke.py` percorre as telas com dados fictícios e salva capturas de desktop e celular. O `README.md` contém os pré-requisitos e as instruções para preparar as contas de demonstração. O login Google real continua dependendo das credenciais institucionais; testes com dados controlados não representam uma autenticação real na faculdade.
