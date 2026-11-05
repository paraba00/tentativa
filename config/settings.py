"""Configuração compartilhada entre desenvolvimento e implantação com MySQL."""
# Acessa variáveis de ambiente sem gravar credenciais no código-fonte.
import os
# Representa caminhos de arquivos de forma compatível com diferentes sistemas.
from pathlib import Path

# Permite interromper a inicialização quando falta configuração obrigatória.
from django.core.exceptions import ImproperlyConfigured
# Lê o arquivo local .env; variáveis já fornecidas pelo processo têm prioridade.
from dotenv import load_dotenv

# Localiza a raiz do projeto a partir deste arquivo, sem depender do diretório do terminal.
BASE_DIR = Path(__file__).resolve().parent.parent
# Carrega a configuração local; esse arquivo com segredos deve ficar fora do Git.
load_dotenv(BASE_DIR / ".env")


# Centraliza a conversão de texto do ambiente para valores booleanos.
def env_bool(name, default=False):
    # Aceita true, 1 e yes, sem diferenciar maiúsculas; outros textos resultam em False.
    return os.getenv(name, str(default)).lower() in {"true", "1", "yes"}


# Ativa detalhes de desenvolvimento por padrão; na implantação deve ser False.
DEBUG = env_bool("DJANGO_DEBUG", True)
# Obtém a chave de assinaturas Django; seu valor nunca deve aparecer em logs ou no Git.
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
# Trata explicitamente a ausência da chave secreta.
if not SECRET_KEY:
    # Em produção, aplica requisitos adicionais em vez das facilidades de desenvolvimento.
    if not DEBUG:
        # Impede iniciar produção com uma chave conhecida ou ausente.
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY antes de usar em produção.")
    # Chave pública de contingência exclusiva para desenvolvimento, bloqueada acima em produção.
    SECRET_KEY = "development-only-ouvidoria-never-use-in-production"
# Lista os hosts aceitos no cabeçalho Host; remove espaços e itens vazios da configuração.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",") if h.strip()]
# Origens adicionais confiáveis para formulários CSRF; exige esquema, como https://exemplo.
CSRF_TRUSTED_ORIGINS = [h.strip() for h in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if h.strip()]

# Registra os módulos cujos modelos, migrações, templates e integrações o Django carrega.
INSTALLED_APPS = [
    # Módulos de administração, usuários/permissões e metadados de modelos; não expõe uma URL admin.
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    # Habilita sessões, avisos temporários ao usuário e descoberta de CSS/JS locais.
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    # Carrega nossos apps e a infraestrutura de contas e autenticação social do allauth.
    "accounts", "ombudsman", "allauth", "allauth.account", "allauth.socialaccount",
    # Registra especificamente o provedor Google e seus endpoints OAuth.
    "allauth.socialaccount.providers.google",
]
# Define a sequência de camadas pelas quais passam requisições e respostas.
MIDDLEWARE = [
    # Aplica cabeçalhos de segurança e serve arquivos estáticos coletados pelo WhiteNoise.
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    # Recupera a sessão e aplica normalizações HTTP do Django.
    "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware",
    # Valida tokens CSRF e associa o usuário autenticado a request.user.
    "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Fornece o contexto de autenticação allauth e o armazenamento de mensagens de interface.
    "allauth.account.middleware.AccountMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    # Impede embutir as páginas em frames quando a política DENY está configurada.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
# Indica o módulo principal que distribui as URLs para os apps.
ROOT_URLCONF = "config.urls"
# Configura o mecanismo que transforma templates e contexto em HTML.
TEMPLATES = [{
    # Usa o interpretador padrão de templates Django, com escape automático de HTML.
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    # Procura templates na pasta compartilhada e também nas pastas de cada app instalado.
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    # Funções abaixo acrescentam informações comuns ao contexto das páginas.
    "OPTIONS": {"context_processors": [
        # Disponibiliza request, usuário autenticado e permissões nos templates.
        "django.template.context_processors.request", "django.contrib.auth.context_processors.auth",
        # Inclui avisos ao usuário e flags seguras de desenvolvimento/Google, sem expor segredos.
        "django.contrib.messages.context_processors.messages", "config.context_processors.environment",
    ]},
}]
# Ponto de entrada síncrono usado pelo Gunicorn neste projeto.
WSGI_APPLICATION = "config.wsgi.application"
# Ponto de entrada assíncrono compatível com servidores ASGI, se necessário futuramente.
ASGI_APPLICATION = "config.asgi.application"

# MySQL é o banco principal para apresentação e implantação.
# SQLite é uma alternativa opcional explícita para testes rápidos sem Docker.
# Só escolhe SQLite quando solicitado explicitamente; o padrão é MySQL.
if os.getenv("DB_ENGINE", "mysql") == "sqlite":
    # SQLite grava um arquivo local e serve como alternativa opcional de desenvolvimento.
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
# Quando a alternativa SQLite não foi selecionada, prepara a conexão MySQL.
else:
    # Define a conexão padrão usada pelo ORM e pelas migrações.
    DATABASES = {"default": {
        # Seleciona o driver MySQL e lê o nome do banco existente no servidor.
        "ENGINE": "django.db.backends.mysql", "NAME": os.getenv("DB_NAME", "ouvidoria"),
        # Lê as credenciais do usuário da aplicação; produção não deve usar root.
        "USER": os.getenv("DB_USER", "ouvidoria"), "PASSWORD": os.getenv("DB_PASSWORD", ""),
        # Informa endereço e porta do banco; no Compose o host é o nome do serviço db.
        "HOST": os.getenv("DB_HOST", "127.0.0.1"), "PORT": os.getenv("DB_PORT", "3306"),
        # Suporta Unicode completo e rejeita truncamentos silenciosos de dados inválidos.
        "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
        # Reutiliza conexões por até 60 segundos, reduzindo o custo entre requisições.
        "CONN_MAX_AGE": 60,
        # Mantém Unicode completo também no banco criado pelo executor de testes.
        "TEST": {"CHARSET": "utf8mb4"},
    }}

# Substitui o usuário padrão pelo modelo com e-mail, perfil e confirmação institucional.
AUTH_USER_MODEL = "accounts.User"
# Permite autenticação local de demonstração e integração allauth; as views limitam onde cada uma é aceita.
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend", "allauth.account.auth_backends.AuthenticationBackend"]
# Regras aplicadas ao definir senhas locais e à confirmação da direção.
AUTH_PASSWORD_VALIDATORS = [
    # Rejeita senhas muito parecidas com os dados pessoais da conta.
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    # Exige pelo menos dez caracteres na senha validada.
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    # Rejeita senhas presentes na lista de combinações comuns do Django.
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    # Rejeita senhas compostas somente por números.
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# Destino de quem tenta abrir uma página privada sem estar autenticado.
LOGIN_URL = "accounts:login"
# Destino padrão após autenticação; a view local pode escolher o painel da equipe.
LOGIN_REDIRECT_URL = "ombudsman:student_dashboard"
# Retorna à página inicial depois de encerrar a sessão.
LOGOUT_REDIRECT_URL = "ombudsman:home"
# Só libera login/cadastro local quando DEBUG também está ativo; produção permanece Google.
LOCAL_ACCOUNTS_ENABLED = DEBUG and env_bool("LOCAL_ACCOUNTS_ENABLED", True)

# Identificador do cliente OAuth autorizado no Google Cloud.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
# Segredo OAuth recebido por configuração segura e nunca exposto nos templates.
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
# A interface habilita o botão Google quando ambas as configurações estão presentes.
GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
# Aplica nossa validação obrigatória de domínio, organização e e-mail verificado.
SOCIALACCOUNT_ADAPTER = "accounts.google_adapter.InstitutionalGoogleAdapter"
# Informa ao allauth que o usuário não tem campo username.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# Define e-mail como identificador de conta em vez de nome de usuário.
ACCOUNT_LOGIN_METHODS = {"email"}
# Descreve campos obrigatórios do allauth; seu cadastro por senha fica bloqueado pelo modo social exclusivo.
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
# Impede cadastrar várias contas allauth com o mesmo e-mail.
ACCOUNT_UNIQUE_EMAIL = True
# Bloqueia os caminhos de senha/cadastro/reset do allauth para evitar contornar o login institucional.
SOCIALACCOUNT_ONLY = True
# Dispensa o fluxo de confirmação allauth, exigência do modo social exclusivo; nosso adapter valida a confirmação Google.
ACCOUNT_EMAIL_VERIFICATION = "none"
# Não envia segundo link de confirmação social; o Google precisa fornecer a claim verificada.
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
# Mantém o prazo de confirmação em um dia para recursos allauth que usem essa configuração.
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
# Cria a conta de aluno após um primeiro login Google válido, sem outro formulário.
SOCIALACCOUNT_AUTO_SIGNUP = True
# Não autentica uma conta local apenas porque o provedor retornou um e-mail igual.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
# Impede vincular automaticamente uma conta Google a uma conta local por coincidência de e-mail.
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
# Exige POST com CSRF para começar o login; acessar um link GET não inicia a autenticação automaticamente.
SOCIALACCOUNT_LOGIN_ON_GET = False
# Não armazena tokens de acesso Google no banco após autenticar.
SOCIALACCOUNT_STORE_TOKENS = False
# Configura somente o provedor institucional necessário à aplicação.
SOCIALACCOUNT_PROVIDERS = {"google": {
    # Solicita apenas perfil básico e e-mail, sem acesso a arquivos ou mensagens Google.
    "SCOPE": ["profile", "email"],
    # Sugere a organização e pede escolha de conta; hd será revalidado no retorno autenticado.
    "AUTH_PARAMS": {"hd": "camporeal.edu.br", "prompt": "select_account"},
    # Entrega as credenciais ao cliente OAuth sem colocá-las no HTML.
    "APP": {"client_id": GOOGLE_CLIENT_ID, "secret": GOOGLE_CLIENT_SECRET, "key": ""},
}}

# Por padrão imprime e-mails locais no console; SMTP real exige backend e credenciais configurados.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
# Endereço do servidor SMTP, quando o backend SMTP estiver selecionado.
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
# Converte a porta configurada para inteiro; 587 é comum para SMTP com STARTTLS.
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
# Usuário de autenticação SMTP, sem valor fixo no código.
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
# Senha SMTP obtida da configuração segura.
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
# Habilita STARTTLS no envio SMTP para proteger a conexão.
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
# Define o remetente; uma implantação precisa de endereço autorizado pelo servidor de envio.
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "ouvidoria@camporeal.edu.br")
# Limita a espera de conexão SMTP a dez segundos.
EMAIL_TIMEOUT = 10

# Usa traduções e formatos brasileiros na interface Django.
LANGUAGE_CODE = "pt-br"
# Exibe datas no fuso brasileiro escolhido para a faculdade.
TIME_ZONE = "America/Sao_Paulo"
# Ativa o sistema de tradução e internacionalização.
USE_I18N = True
# Armazena e manipula datas com fuso, evitando ambiguidade de horários.
USE_TZ = True
# Prefixo público das URLs de CSS, JavaScript e imagens locais.
STATIC_URL = "/static/"
# Pasta de origem dos recursos visuais mantidos no repositório.
STATICFILES_DIRS = [BASE_DIR / "static"]
# Destino gerado por collectstatic, servido pelo WhiteNoise na imagem Docker.
STATIC_ROOT = BASE_DIR / "staticfiles"
# Separa o armazenamento de arquivos comuns e o de recursos estáticos.
STORAGES = {
    # Arquivos comuns, se usados futuramente, ficam no sistema de arquivos local.
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Comprime recursos; produção também usa nomes com hash para controlar cache sem conteúdo antigo.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage" if DEBUG else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Usa chaves primárias inteiras de 64 bits nos modelos sem id explícito.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# O cache é compartilhado entre workers; dev.sh executa createcachetable.
# Compartilha limites de tentativas entre workers usando a tabela django_cache, criada no preparo.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

# Impede leitura do cookie de sessão por JavaScript no navegador.
SESSION_COOKIE_HTTPONLY = True
# Restringe envio de cookies entre sites preservando o retorno de navegação do OAuth.
SESSION_COOKIE_SAMESITE = "Lax"
# Aplica a mesma política ao cookie de proteção de formulários.
CSRF_COOKIE_SAMESITE = "Lax"
# Define duração máxima de quatro horas para a sessão.
SESSION_COOKIE_AGE = 60 * 60 * 4
# Marca o cookie como de sessão, com expiração ao fechar o navegador conforme seu comportamento.
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
# Instrui o navegador a respeitar o tipo declarado do conteúdo.
SECURE_CONTENT_TYPE_NOSNIFF = True
# Impede exibição das páginas dentro de frames de qualquer origem.
X_FRAME_OPTIONS = "DENY"
# Só envia o cabeçalho Referer para requisições da mesma origem.
SECURE_REFERRER_POLICY = "same-origin"
# Em produção, aplica requisitos adicionais em vez das facilidades de desenvolvimento.
if not DEBUG:
    # Em produção, envia o cookie de sessão apenas por HTTPS.
    SESSION_COOKIE_SECURE = True
    # Em produção, protege também o cookie CSRF com HTTPS.
    CSRF_COOKIE_SECURE = True
    # Redireciona HTTP para HTTPS em produção, salvo configuração explícita para a infraestrutura.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    # Solicita ao navegador usar HTTPS por um ano após receber uma resposta segura.
    SECURE_HSTS_SECONDS = 31536000
    # Estende a política HSTS aos subdomínios; a implantação precisa garantir HTTPS neles.
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Sinaliza compatibilidade com preload HSTS; a inclusão em listas de navegadores é um processo externo.
    SECURE_HSTS_PRELOAD = True
# Habilite apenas atrás de proxy confiável que substitua X-Forwarded-Proto.
# Só confia no cabeçalho do proxy quando o operador habilita expressamente essa opção.
if env_bool("DJANGO_TRUST_PROXY"):
    # Reconhece HTTPS encerrado no proxy; use apenas se ele substituir cabeçalhos recebidos do cliente.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
