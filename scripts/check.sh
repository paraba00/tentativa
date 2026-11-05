#!/usr/bin/env bash
# Qualquer comando que falhar deve fazer a verificação terminar com erro.
set -euo pipefail
# Resolve a raiz pelo caminho deste arquivo, sem depender do diretório do terminal.
cd "$(dirname "$0")/.."
# Usa um MySQL separado e descartável: os testes não usam o banco da aplicação.
docker compose -f compose.test.yaml up -d --wait db-test
# Ao sair, remove somente os recursos do projeto de testes; não o banco da aplicação.
trap 'docker compose -f compose.test.yaml down -v' EXIT
# Verifica se o Django detecta problemas na configuração e nos modelos.
docker compose -f compose.test.yaml run --rm test python manage.py check
# Detecta mudanças de modelos que precisariam de uma migration ainda não salva.
docker compose -f compose.test.yaml run --rm test python manage.py makemigrations --check --dry-run
# Executa a suíte; --noinput impede perguntas que travariam uma execução automática.
docker compose -f compose.test.yaml run --rm test python manage.py test --noinput
