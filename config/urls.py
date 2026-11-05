# Importa o agrupamento de rotas (include) e o vínculo entre caminho e view (path).
from django.urls import include, path

# Lista de rotas examinadas em ordem pelo Django ao receber uma requisição.
urlpatterns = [
    # Encaminha login, logout e recursos locais de confirmação ao app de contas.
    path("conta/", include("accounts.urls")),
    # Inclui o OAuth Google; os caminhos de senha do allauth são bloqueados por SOCIALACCOUNT_ONLY.
    path("autenticacao/", include("allauth.urls")),
    # Entrega a página inicial e os portais de aluno/equipe ao app de ouvidoria.
    path("", include("ombudsman.urls")),
]
# Não há rota genérica Django Admin: a equipe usa o portal com autorização e auditoria.
