# Ouvidoria Campo Real

Aplicação acadêmica para TCC: alunos registram manifestações e acompanham respostas; a ouvidoria organiza os atendimentos; a direção tem acesso excepcional e auditado à identificação de manifestações sigilosas.

Backend em **Python 3.12 e Django 5.2**, banco principal **MySQL 8.4** e interface responsiva em HTML, CSS e JavaScript, sem build de frontend. Identidade visual em branco, azul e detalhes amarelos.

O código está comentado em português para estudo no TCC, incluindo Python, templates Django, CSS, JavaScript, testes e configuração dos containers. Comece por [docs/GUIA_ESTUDO.md](docs/GUIA_ESTUDO.md), que explica a ordem de leitura e o caminho de uma manifestação entre as camadas.

## Funcionalidades

- Página inicial, área do aluno e administração da ouvidoria.
- Login Google institucional restrito a contas verificadas de `@camporeal.edu.br`.
- Reclamação, crítica, sugestão, elogio ou solicitação, com escolha de setor.
- Envio identificado ou sigiloso, protocolo único e histórico de situações.
- Acompanhamento autenticado: um protocolo não dá acesso às manifestações de outra conta.
- Painel administrativo com busca, filtros, indicadores e respostas ao aluno.
- Direção com consulta de identidade sigilosa mediante justificativa e senha de confirmação; cada consulta gera auditoria.
- Modo local de demonstração com contas e exemplos fictícios, desativado fora do desenvolvimento.

**Sigiloso não significa anonimato absoluto.** O aluno se autentica em qualquer modalidade. No envio sigiloso, sua identidade fica oculta da equipe comum de ouvidoria, mas pode ser consultada pela direção dentro da aplicação em situações justificadas e registradas. Administradores do banco e da infraestrutura mantêm acesso técnico aos dados. O site informa essa regra antes do envio.

## Executar com MySQL

Requisitos: Git, Docker e Docker Compose v2. Execute na raiz do repositório:

```bash
python3 scripts/init_env.py
./scripts/dev.sh
```

O inicializador prepara `.env` com segredos locais aleatórios e preserva configurações existentes. O script de desenvolvimento constrói a imagem, aguarda o banco, aplica migrações, prepara o cache compartilhado e inicia a aplicação. Os arquivos estáticos são coletados na construção da imagem. A primeira execução baixa imagens e dependências; as seguintes reutilizam o cache.

No computador local, a aplicação atende na porta `8000`. O banco permanece na rede interna do Compose. Em ambientes de nuvem, use a forma de acesso fornecida pela plataforma; uma porta local não é uma publicação pública.

```bash
docker compose ps
docker compose logs -f web
docker compose logs -f db
./scripts/check.sh
docker compose down
```

`check.sh` usa um MySQL descartável separado do banco da aplicação. `docker compose down` interrompe os serviços e preserva o volume do banco. Não use `down -v` em um banco que precise ser preservado: essa opção remove os dados locais do volume.

Equivalente manual: `docker compose build web`, `docker compose up -d --wait db`, `docker compose run --rm web python manage.py migrate`, `docker compose run --rm web python manage.py createcachetable` e `docker compose up -d web`. Prefira o script, que também verifica a resposta da aplicação.

## Demonstração do TCC

O modo de demonstração exige `DJANGO_DEBUG=true` e `LOCAL_ACCOUNTS_ENABLED=true`. Escolha uma senha com pelo menos 12 caracteres; ela será usada nas três contas fictícias, sem senha padrão no código.

Em Bash:

```bash
read -rsp 'Senha para as contas fictícias: ' DEMO_PASSWORD; echo
export DEMO_PASSWORD
docker compose run --rm -e DEMO_PASSWORD web python manage.py seed_demo
unset DEMO_PASSWORD
```

| Perfil | E-mail de demonstração |
| --- | --- |
| Aluno | `aluno.demo@camporeal.edu.br` |
| Ouvidoria | `ouvidoria.demo@camporeal.edu.br` |
| Direção | `direcao.demo@camporeal.edu.br` |

Entre pelo formulário de acesso local da página de login. As contas fictícias já têm confirmação local; não representam autenticação real pelo Google e não enviam e-mails para esses endereços. O comando pode ser repetido sem duplicar exemplos; senhas existentes são preservadas.

Sugestão de apresentação: entre como aluno, envie uma manifestação sigilosa e guarde o protocolo; entre como ouvidoria, responda e altere a situação; volte ao aluno para acompanhar; entre como direção e consulte a identidade com uma justificativa. A consulta aparece na auditoria da direção. O ouvidor comum não recebe essa identificação.

## Google institucional

A integração usa OAuth 2.0 via `django-allauth`. **O login real Google exige credenciais autorizadas pela instituição.** Não basta preencher um e-mail institucional em um formulário.

1. No Google Cloud da instituição, configure o consentimento para a organização Google Workspace e crie um cliente OAuth do tipo **Aplicativo da Web**. O administrador da organização pode precisar autorizar o aplicativo.
2. Cadastre o redirecionamento exato. Desenvolvimento: `http://localhost:8000/autenticacao/google/login/callback/`. Implantação: `https://SEU-DOMINIO/autenticacao/google/login/callback/`.
3. Preencha `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` em `.env` ou no gerenciador de segredos da hospedagem. Nunca publique esses valores em Git, imagens ou capturas.
4. Reinicie a aplicação: `docker compose up -d --force-recreate web`.
5. Faça um login com conta institucional real autorizada e confira o fluxo completo no domínio configurado.

O servidor exige e-mail verificado, domínio exato `camporeal.edu.br` e declaração autenticada `hd=camporeal.edu.br` do Google Workspace. Contas pessoais, subdomínios e e-mails sem verificação são recusados. O parâmetro `hd` enviado ao Google é apenas uma indicação de interface; a validação também acontece no retorno autenticado.

Na nuvem gerenciada, `dev.sh` detecta o certificado do proxy e acrescenta `compose.cloud.yaml`, montando o bundle de confiança somente para leitura no servidor. Para comandos manuais que recriem serviços nesse ambiente, use `docker compose -f compose.yaml -f compose.cloud.yaml ...` ou prefira `dev.sh`. A rede deve permitir `accounts.google.com`, `oauth2.googleapis.com` e `www.googleapis.com`; o rascunho do ambiente inclui essas adições, que ainda precisam ser salvas/publicadas pela interface. A configuração da integração não foi validada com uma conta Google real.

Não há vinculação automática por coincidência de e-mail entre contas locais e Google. Faça o primeiro acesso Google antes de atribuir o perfil. Não reutilize contas fictícias como contas institucionais.

## Perfis da equipe

Novas contas Google recebem o perfil de aluno. A promoção é feita por quem administra o servidor, após o primeiro acesso institucional:

```bash
docker compose run --rm web python manage.py set_role pessoa@camporeal.edu.br --role ombudsman
docker compose run --rm web python manage.py set_role diretor@camporeal.edu.br --role director --set-confirmation-password
```

O segundo comando solicita uma senha de confirmação sem exibi-la. Ela deve atender às regras do Django e é armazenada como hash. Essa senha confirma a ação excepcional da direção; o acesso normal de produção continua sendo pelo Google. Para automação, o comando aceita `DIRECTOR_CONFIRMATION_PASSWORD` no ambiente, sem receber seu valor como argumento nem registrá-lo no repositório.

Somente contas ativas e confirmadas recebem perfis. Para retornar ao perfil de aluno, use `--role student`. Não há criação de perfis privilegiados no cadastro público e o Django Admin genérico não é exposto.

## Variáveis e implantação

Consulte `.env.example`. As principais configurações são:

| Variáveis | Uso |
| --- | --- |
| `DJANGO_SECRET_KEY` | Segredo exclusivo da instalação, gerado localmente. |
| `DJANGO_DEBUG`, `LOCAL_ACCOUNTS_ENABLED` | Desenvolvimento e acesso local de demonstração; desativar na implantação. |
| `DJANGO_ALLOWED_HOSTS` | Domínios da aplicação, separados por vírgula. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origens HTTPS autorizadas para formulários, quando necessárias. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ROOT_PASSWORD` | Credenciais MySQL exclusivas; o usuário da aplicação deve ter privilégios limitados. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Cliente OAuth da instituição. |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Envio de confirmação para o cadastro local, se configurado. |

Na implantação, defina `DJANGO_DEBUG=false`, `LOCAL_ACCOUNTS_ENABLED=false`, uma chave forte e os domínios corretos. O sistema passa a exigir cookies seguros e HTTPS. Use um proxy HTTPS confiável; habilite `DJANGO_TRUST_PROXY=true` somente se ele substituir corretamente `X-Forwarded-Proto`. O Gunicorn não fornece certificado HTTPS por conta própria.

Mantenha backups protegidos do MySQL e teste a restauração. Limite acesso a `.env`, logs e infraestrutura. O projeto demonstra o TCC; uso com dados reais exige revisão da instituição, definição de responsáveis, retenção e descarte, procedimento para consultas excepcionais e avaliação de privacidade/LGPD. Não há exclusão automática por prazo nesta versão.

## Alternativa sem Docker

O MySQL é o banco principal. SQLite é uma alternativa explícita para trabalhar na interface ou executar testes rápidos sem servidor MySQL:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DB_ENGINE=sqlite
python manage.py migrate
python manage.py createcachetable
python manage.py runserver
python manage.py test
```

O pacote `mysqlclient` pode exigir compilador, `pkg-config` e bibliotecas de desenvolvimento MySQL/MariaDB, mesmo nesta alternativa. O Dockerfile já inclui esses pré-requisitos. Testes apenas em SQLite não validam o requisito MySQL.

No cadastro local de desenvolvimento, o backend padrão imprime o link de confirmação no console e não entrega mensagens em uma caixa postal. Esse fluxo é separado do Google institucional.

## Testes e organização

`./scripts/check.sh` executa verificações e testes com banco MySQL separado. A cobertura inclui permissões, isolamento entre alunos, formulários e protocolos, respostas, sigilo, auditoria, regras Google, estado OAuth e CSRF. Os testes Google usam dados controlados; não substituem o teste com credenciais institucionais reais.

Validação desta versão: **52 testes passaram em MySQL 8.4**, além de verificação de migrations e do fluxo no navegador. O MySQL emite dois avisos `models.W036` para índices condicionais do `django-allauth`, que ele não suporta; a unicidade do e-mail de acesso é garantida pelo campo único de `accounts.User`. Não foram silenciados avisos nem desativadas verificações para executar os testes.

O teste opcional de navegador exige Playwright (`requirements-dev.txt`), Chromium e as contas de demonstração já preparadas. Exporte `DEMO_PASSWORD` e rode `python scripts/browser_smoke.py`. Ele cria uma manifestação fictícia, testa aluno → ouvidoria → direção e salva capturas em `artifacts/` (ignorado pelo Git). Se o navegador não estiver instalado, use `python -m playwright install chromium`; `CHROMIUM_PATH` permite selecionar uma instalação existente. Este teste é apenas para o ambiente de demonstração.

| Caminho | Responsabilidade |
| --- | --- |
| `accounts/` | Usuários, acesso, confirmação local, política Google e perfis. |
| `ombudsman/` | Manifestações, identidade reservada, respostas, situações e auditoria. |
| `config/` | Configurações, rotas e inicialização Django. |
| `templates/`, `static/` | Páginas, estilos e melhorias de interface. |
| `scripts/` | Preparação, inicialização e verificações. |
| `docs/ARQUITETURA.md` | Modelo de dados, fluxos, decisões e limites. |

A paleta foi ajustada para azul `#003D59`, amarelo `#FFDF00` e branco. O cabeçalho está preparado para `static/img/camporeal-azul.png`, e o rodapé azul para `static/img/camporeal-branca.png`, preservando proporções e textos alternativos. Os arquivos originais das imagens mostradas na conversa ainda precisam ser anexados ao projeto; até que ambos existam, a identificação textual continua visível, sem imagens quebradas. As logos não foram recriadas. Veja o guia de estudo para completar a inclusão dos arquivos e reconstruir os estáticos.
