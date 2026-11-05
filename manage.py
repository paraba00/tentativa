#!/usr/bin/env python3
# Permite informar ao Django onde encontrar a configuração do projeto.
import os
# Fornece os argumentos do terminal, como migrate, test ou runserver.
import sys

# Executa os comandos somente quando este arquivo é chamado diretamente, não ao importá-lo.
if __name__ == "__main__":
    # Seleciona o módulo padrão de configuração sem sobrescrever uma escolha externa.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # Importa o executor oficial de comandos depois de selecionar os settings.
    from django.core.management import execute_from_command_line
    # Delega ao Django a leitura dos argumentos e preserva o resultado do comando solicitado.
    execute_from_command_line(sys.argv)
