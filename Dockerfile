# syntax=docker/dockerfile:1
# Usa Python 3.12 com Debian enxuto como base do ambiente isolado.
FROM python:3.12-slim-bookworm
# Evita .pyc, libera os logs imediatamente e dispensa o aviso de atualização do pip.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# Define a pasta padrão dos comandos e do código dentro do container.
WORKDIR /app
# Instala compilador, headers MySQL e certificados; remove só o cache do apt ao fim.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev ca-certificates && rm -rf /var/lib/apt/lists/*
# Copia primeiro as dependências para reutilizar esta camada se apenas o código mudar.
COPY requirements.txt .
# Monta opcionalmente a CA do proxy apenas durante este RUN; nunca desativa TLS.
# Se o arquivo existir, PIP_CERT aponta o pip para esse bundle antes da instalação.
# pip lê as versões fixadas e não mantém seu cache na imagem final.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
# Copia o projeto; .dockerignore exclui .env, senhas locais, Git e ambiente virtual.
COPY . .
# Cria um usuário sem privilégios e lhe entrega a pasta de trabalho.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
# Os comandos seguintes e o servidor deixam de usar o usuário root.
USER app
# Gera CSS/JS e seu manifesto antes de iniciar o site. SQLite evita depender do banco no build.
# A chave pública temporária serve somente a este comando; não é credencial de execução.
# Em produção, a inicialização exige uma DJANGO_SECRET_KEY própria e privada.
RUN DB_ENGINE=sqlite DJANGO_DEBUG=false DJANGO_SECRET_KEY=build-only-not-a-runtime-secret python manage.py collectstatic --noinput
# Documenta a porta usada pelo servidor dentro do container.
EXPOSE 8000
# Gunicorn carrega o Django via WSGI, usa dois processos e escreve acesso na saída padrão.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
