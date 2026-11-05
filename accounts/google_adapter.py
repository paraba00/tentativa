"""Aplica a política Google Workspace depois da verificação OAuth.

O django-allauth valida o fluxo OAuth e os tokens conforme o protocolo. Na troca
direta com o Google, parte dessa confiança depende do HTTPS verificado. Estes
hooks acrescentam as regras da instituição e nunca devem receber claims de um
formulário enviado diretamente pelo navegador.
"""

# Disponibiliza avisos temporários para explicar ao usuário por que o acesso foi negado.
from django.contrib import messages
# Obtém o modelo de usuário configurado, sem depender do usuário padrão do Django.
from django.contrib.auth import get_user_model
# Cria a resposta HTTP que redireciona de volta à página de acesso.
from django.http import HttpResponseRedirect
# Resolve nomes de rotas em URLs, evitando caminhos fixos espalhados pelo código.
from django.urls import reverse

# Interrompe o fluxo allauth imediatamente devolvendo uma resposta HTTP controlada.
from allauth.core.exceptions import ImmediateHttpResponse
# Oferece pontos de extensão do OAuth sem reimplementar a comunicação e a validação do provedor.
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


# Domínio exato aceito; também precisa coincidir com a organização autenticada do Workspace.
INSTITUTIONAL_DOMAIN = "camporeal.edu.br"


# Especializa a política institucional aplicada após o allauth autenticar o provedor.
class InstitutionalGoogleAdapter(DefaultSocialAccountAdapter):
    # Centraliza a negação de acesso com explicação e redirecionamento seguro.
    def _deny(self, request, message):
        # Só registra mensagens quando o middleware está presente, permitindo testes com RequestFactory.
        if hasattr(request, "_messages"):
            # Adiciona a explicação para ser mostrada na próxima página.
            messages.error(request, message)
        # Aborta o login antes de criar sessão e retorna para a rota nomeada de acesso.
        raise ImmediateHttpResponse(HttpResponseRedirect(reverse("accounts:login")))

    # Valida claims autenticadas pelo Google; nunca aceita um e-mail enviado apenas pelo formulário.
    def _verified_email(self, request, sociallogin):
        # Recusa outros provedores mesmo se retornarem um endereço com o domínio da instituição.
        if sociallogin.account.provider != "google":
            # Explica que a identidade precisa ser autenticada pelo provedor institucional configurado.
            self._deny(request, "Utilize o Google institucional da Campo Real para entrar.")
        # Lê os dados do provedor após o fluxo OAuth, não parâmetros livres da URL.
        claims = sociallogin.account.extra_data
        # Usa texto vazio quando o Google não retorna o e-mail obrigatório.
        email = claims.get("email", "")
        # Garante o tipo antes de chamar operações de texto.
        if not isinstance(email, str):
            # Rejeita respostas sem um campo de e-mail textual válido.
            self._deny(request, "O Google não retornou um e-mail institucional válido.")
        # Normaliza espaços externos e maiúsculas para comparar com as contas locais.
        email = email.strip().lower()
        # O parâmetro hd da requisição é apenas sugestão visual; a claim autenticada
        # do Workspace e o domínio exato também são exigidos em cada login.
        # Agrupa as condições que invalidam o endereço ou sua organização institucional.
        if (
            # Exige exatamente um separador entre a parte local e o domínio.
            email.count("@") != 1
            # Recusa endereço sem identificação antes do arroba.
            or not email.split("@", 1)[0]
            # Compara o domínio completo, evitando aceitar subdomínios ou sufixos forjados.
            or email.split("@", 1)[1] != INSTITUTIONAL_DOMAIN
            # Confirma a organização Workspace na claim autenticada; o parâmetro hd de saída é só uma sugestão.
            or claims.get("hd") != INSTITUTIONAL_DOMAIN
        ):
            # Interrompe o fluxo quando o endereço ou a organização não pertencem à instituição.
            self._deny(request, "Entre com sua conta Google institucional @camporeal.edu.br.")
        # Exige uma das declarações de confirmação oferecidas pelos formatos de resposta Google.
        if not (
            # Aceita somente o booleano True do formato de ID token, não um texto como "true".
            claims.get("email_verified") is True
            # Também reconhece o nome de claim do endpoint legado de informações do Google.
            or claims.get("verified_email") is True
        ):
            # Não autentica e-mails cuja propriedade não foi confirmada pelo provedor.
            self._deny(request, "O Google precisa confirmar o e-mail institucional desta conta.")
        # Retorna o endereço normalizado somente após todas as verificações.
        return email

    # Hook allauth executado antes de concluir o login; revalida inclusive contas já vinculadas.
    def pre_social_login(self, request, sociallogin):
        # Aplica as mesmas restrições ao acesso existente e ao primeiro cadastro Google.
        email = self._verified_email(request, sociallogin)
        # Distingue uma identidade Google já vinculada pelo identificador do provedor.
        if sociallogin.is_existing:
            # Recupera a conta local que já pertence a essa identidade Google.
            user = sociallogin.user
            # Bloqueia contas desativadas mesmo que o Google ainda consiga autenticar o usuário.
            if not user.is_active:
                # A desativação administrativa local prevalece sobre o sucesso de autenticação externa.
                self._deny(request, "Esta conta está desativada. Entre em contato com a instituição.")
            # Detecta mudança de e-mail no provedor sem atualizar silenciosamente a identidade local.
            if user.email.lower() != email:
                # Exige intervenção institucional para reconciliar uma alteração de endereço.
                self._deny(request, "O e-mail da conta mudou. Solicite a atualização à instituição.")
            # Atualiza a confirmação local quando as claims verificadas do Google já comprovam a propriedade.
            if not user.email_verified:
                # Marca a confirmação no modelo que controla envio e permissões administrativas.
                user.email_verified = True
                # Persiste apenas a confirmação, sem alterar perfil ou outros campos da conta.
                user.save(update_fields=["email_verified"])
        # Procura coincidência com conta local ainda não vinculada; coincidência não prova que as contas são a mesma.
        elif get_user_model().objects.filter(email__iexact=email).exists():
            # Nunca vincula automaticamente contas locais/de demonstração só pelo e-mail.
            # Recusa a associação automática; um procedimento administrativo seguro deverá tratar a conta existente.
            self._deny(
                # Encaminha a requisição atual para que a negação possa mostrar uma mensagem.
                request,
                # Informa a necessidade de vinculação segura sem efetuar a operação automaticamente.
                "Já existe uma conta local com este e-mail. Solicite à administração a vinculação segura.",
            )

    # Hook usado para o primeiro cadastro social, preservando o salvamento padrão do allauth.
    def save_user(self, request, sociallogin, form=None):
        # Aplica as mesmas restrições ao acesso existente e ao primeiro cadastro Google.
        email = self._verified_email(request, sociallogin)
        # Grava exclusivamente o endereço validado, ignorando e-mails alternativos fornecidos pelo visitante.
        sociallogin.user.email = email
        # A confirmação resulta das claims validadas do Google, não de uma caixa de seleção.
        sociallogin.user.email_verified = True
        # Todo novo cadastro nasce como aluno; o login nunca concede perfil de ouvidoria ou direção.
        sociallogin.user.role = get_user_model().Role.STUDENT
        # Delega a persistência da conta e do vínculo Google ao allauth, que define senha inicial inutilizável.
        return super().save_user(request, sociallogin, form)
