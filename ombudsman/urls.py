# Importa as funções para declarar rotas e obter seus endereços pelo nome.
from django.urls import path

# Importa as views deste pacote, responsáveis pelo comportamento de cada rota.
from . import views

# Define o namespace ombudsman para os nomes de rotas da ouvidoria.
app_name = "ombudsman"
# Relaciona cada caminho público ou privado à sua view; a proteção de acesso fica nas próprias views.
urlpatterns = [
    # Entrega a página inicial pública na raiz do portal.
    path("", views.home, name="home"),
    # Apresenta a lista privada das manifestações pertencentes ao usuário autenticado.
    path("ouvidoria/", views.student_dashboard, name="student_dashboard"),
    # Abre e processa o formulário de uma nova manifestação antes da rota dinâmica de protocolo.
    path("ouvidoria/nova/", views.create, name="create"),
    # Apresenta a busca por protocolo, sempre limitada à conta autenticada.
    path("acompanhar/", views.track, name="track"),
    # Captura o protocolo como string para exibir o detalhe ao autor autorizado.
    path("ouvidoria/<str:protocol>/", views.detail, name="detail"),
    # Liga a listagem administrativa à view que exige perfil de equipe.
    path("gestao/", views.staff_dashboard, name="staff_dashboard"),
    # Abre o relato para análise e recebimento de respostas administrativas.
    path("gestao/<str:protocol>/", views.staff_detail, name="staff_detail"),
    # Encaminha a solicitação excepcional de identidade à view exclusiva da direção, restrita a POST.
    path("gestao/<str:protocol>/identidade/", views.reveal_identity, name="reveal_identity"),
]
