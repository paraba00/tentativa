#!/usr/bin/env python3
"""Prepara o arquivo local de configuração sem imprimir ou reutilizar senhas padrão."""
# secrets gera valores aleatórios próprios para chaves e senhas, ao contrário de random.
import secrets
# Path permite montar e manipular caminhos de arquivo de forma portável.
from pathlib import Path

# __file__ é este script; dois níveis acima fica a raiz do projeto.
ROOT = Path(__file__).resolve().parent.parent
# O arquivo .env guarda a configuração privada desta instalação e fica fora do Git.
target = ROOT / ".env"
# Se o usuário já configurou o projeto, não substituímos suas credenciais.
if target.exists():
    # A mensagem informa apenas a existência do arquivo, nunca o conteúdo.
    print(".env existente preservado.")
else:
    # O modelo contém nomes e exemplos públicos, com os segredos ainda vazios.
    content = (ROOT / ".env.example").read_text()
    # Cada configuração sensível recebe um valor diferente e imprevisível.
    for name in ("DJANGO_SECRET_KEY", "DB_PASSWORD", "DB_ROOT_PASSWORD"):
        # Substitui somente a atribuição vazia do modelo; os demais exemplos permanecem.
        content = content.replace(f"{name}=\n", f"{name}={secrets.token_urlsafe(48)}\n")
    # O modo x cria um arquivo novo e recusa sobrescrever um que apareça nesse intervalo.
    with target.open("x") as handle:
        # Em sistemas Unix, 0600 permite leitura e escrita apenas ao dono do arquivo.
        target.chmod(0o600)
        # Grava as opções e as chaves geradas no arquivo local protegido.
        handle.write(content)
    # O usuário recebe uma confirmação sem que as chaves sejam exibidas no terminal.
    print(".env criado com chaves aleatórias. Não compartilhe nem envie ao Git.")
