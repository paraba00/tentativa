# Ponto de entrada ASGI: inicializa a aplicação sem executar comandos de terminal.
# Permite configurar o módulo de settings pela variável de ambiente do processo.
import os
# Importa a fábrica que adapta o Django ao protocolo ASGI do servidor.
from django.core.asgi import get_asgi_application

# Define nossos settings apenas se o processo ainda não escolheu outro módulo.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Carrega o Django e expõe o objeto que o servidor ASGI chamará para cada requisição.
application = get_asgi_application()
