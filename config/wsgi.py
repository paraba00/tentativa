# Ponto de entrada WSGI: inicializa a aplicação sem executar comandos de terminal.
# Permite configurar o módulo de settings pela variável de ambiente do processo.
import os
# Importa a fábrica que adapta o Django ao protocolo WSGI do servidor.
from django.core.wsgi import get_wsgi_application

# Define nossos settings apenas se o processo ainda não escolheu outro módulo.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
# Carrega o Django e expõe o objeto que o servidor WSGI chamará para cada requisição.
application = get_wsgi_application()
