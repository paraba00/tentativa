# Importa as funções para declarar rotas e obter seus endereços pelo nome.
from django.urls import path

# Importa as views deste pacote, responsáveis pelo comportamento de cada rota.
from . import views

# Cria o namespace accounts para distinguir os nomes destas rotas de outras aplicações.
app_name = "accounts"
# Declara as rotas relativas ao prefixo conta/, incluído pelo arquivo principal de URLs.
urlpatterns = [
    # Liga conta/entrar/ à classe de login; as_view transforma a classe em uma view HTTP.
    path("entrar/", views.InstitutionalLoginView.as_view(), name="login"),
    # Liga conta/sair/ ao encerramento de sessão, identificado pelo nome accounts:logout.
    path("sair/", views.InstitutionalLogoutView.as_view(), name="logout"),
    # Liga o cadastro local à view que verifica se esse modo está habilitado.
    path("cadastro/", views.register, name="register"),
    # Mostra a orientação posterior ao envio do e-mail de confirmação.
    path("confirmacao/", views.verify_sent, name="verify_sent"),
    # Registra a operação POST que solicita outro link de confirmação.
    path("reenviar-confirmacao/", views.resend_verification, name="resend_verification"),
    # Captura o token da URL como string e o entrega à view que valida sua assinatura e validade.
    path("confirmar/<str:token>/", views.verify_email, name="verify_email"),
]
