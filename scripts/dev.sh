#!/usr/bin/env bash
# Encerra ao falhar um comando (-e), usar variável ausente (-u) ou falhar um pipeline.
set -euo pipefail
# Entra na raiz mesmo se o usuário executar o script a partir de outra pasta.
cd "$(dirname "$0")/.."
# Cria a configuração privada se necessário e preserva um .env que já existe.
python3 scripts/init_env.py
# O array guarda os argumentos do Compose sem quebrar caminhos ou espaços.
compose_args=(-f compose.yaml)
# A presença deste nome indica a confiança adicional do proxy da nuvem gerenciada.
if [[ -n "${CODEX_PROXY_CERT:-}" ]]; then
  # Acrescenta a montagem de certificados; não troca a configuração principal.
  compose_args+=(-f compose.cloud.yaml)
fi
# A função reaproveita os mesmos arquivos Compose em todos os comandos abaixo.
compose() { docker compose "${compose_args[@]}" "$@"; }
# No build da nuvem, o bundle de confiança entra como segredo temporário do Docker.
if [[ -n "${CODEX_PROXY_CERT:-}" && -f /etc/ssl/certs/ca-certificates.crt ]]; then
  # Constrói a imagem com TLS verificado; o certificado não vira arquivo da imagem.
  docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -t tentativa-ouvidoria:dev .
else
  # Fora desse ambiente, usa o build normal definido em compose.yaml.
  compose build web
fi
# Inicia apenas o MySQL em segundo plano e espera seu healthcheck passar.
compose up -d --wait db
# Cria ou atualiza as tabelas usando as migrations versionadas do Django.
compose run --rm web python manage.py migrate --noinput
# Cria a tabela do cache compartilhado, também usada nos limites de tentativas.
compose run --rm web python manage.py createcachetable
# Inicia o servidor Django/Gunicorn; não remove o volume persistente do banco.
compose up -d web
# Executa Python no container; o heredoc entre aspas evita expansão de variáveis do shell.
compose exec -T web python - <<'PY'
# time fornece a espera curta entre tentativas de prontidão.
import time
# urllib.request faz uma requisição HTTP sem exigir dependências adicionais.
import urllib.request
# Dá ao servidor até 30 tentativas para terminar a inicialização.
for attempt in range(30):
    # Uma falha temporária no início será tratada abaixo.
    try:
        # Consulta o servidor dentro do próprio container e limita o tempo de espera.
        with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=5) as response:
            # Uma porta aberta não basta: a página precisa responder com sucesso HTTP.
            assert response.status == 200
            # Confere um texto esperado para evitar validar uma página errada.
            assert "Sua voz importa" in response.read().decode()
        # Informa que as verificações anteriores passaram, sem expor credenciais.
        print("Ouvidoria respondendo. Banco MySQL e migrations preparados.")
        # Sai do laço assim que a página funcionar.
        break
    # Trata somente falha de comunicação ou conteúdo inesperado.
    except (OSError, AssertionError):
        # Na última tentativa, a falha precisa chegar ao usuário e ao shell.
        if attempt == 29:
            # Relança a exceção original, preservando seu diagnóstico.
            raise
        # Nas demais tentativas, aguarda um segundo antes de consultar novamente.
        time.sleep(1)
# Fim do bloco Python enviado ao container.
PY
