# Importa as configurações carregadas pelo projeto, sem fixar valores de implantação neste módulo.
from django.conf import settings
# Importa os recursos de assinatura criptográfica usados nos links de confirmação.
from django.core import signing
# Importa a função que envia mensagens pelo backend de e-mail configurado.
from django.core.mail import send_mail
# Importa as funções para declarar rotas e obter seus endereços pelo nome.
from django.urls import reverse

# Separa o propósito desta assinatura de outros tokens que usem a mesma chave secreta do Django.
VERIFICATION_SALT = "accounts.verify-email.v1"


# Produz um token assinado e datado vinculado ao usuário e ao e-mail que ele precisa confirmar.
def verification_token(user):
    # Assina identificador e e-mail; a assinatura detecta alterações, mas não é criptografia do conteúdo.
    return signing.dumps({"user_id": user.pk, "email": user.email}, salt=VERIFICATION_SALT)


# Monta o endereço de confirmação e o envia à caixa postal institucional do cadastro.
def send_verification_email(request, user):
    # Resolve a rota nomeada e inclui o token recém-gerado no endereço relativo.
    path = reverse("accounts:verify_email", args=[verification_token(user)])
    # Usa a URL pública configurada quando existir e remove a barra final para evitar duplicidade.
    base_url = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    # Prefere a URL pública; na ausência dela, usa o host da requisição validado pelo Django.
    url = f"{base_url}{path}" if base_url else request.build_absolute_uri(path)
    # Pede ao backend configurado para enviar a confirmação; no modo console, a mensagem aparece no terminal.
    send_mail(
        # Define o assunto da mensagem de confirmação.
        "Confirme seu e-mail • Ouvidoria Campo Real",
        # Inicia o corpo da mensagem; as sequências \n representam quebras de linha no e-mail.
        "Olá!\n\nConfirme seu e-mail institucional para acessar a Ouvidoria Campo Real:\n\n"
        # Acrescenta o link e orienta sobre validade e cadastros não reconhecidos.
        f"{url}\n\nO link vale por 24 horas. Se não fez este cadastro, ignore esta mensagem.\n",
        # Obtém o remetente das configurações, evitando fixar credenciais neste código.
        settings.DEFAULT_FROM_EMAIL,
        # Envia apenas para o e-mail pertencente à conta que está sendo confirmada.
        [user.email],
        # Permite que falhas de envio sejam tratadas pela view, em vez de fingir sucesso.
        fail_silently=False,
    )
