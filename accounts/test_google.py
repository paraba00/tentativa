# Captura a saída dos comandos em memória, evitando mensagens de teste no terminal.
from io import StringIO
# Divide URLs e seus parâmetros para inspecionar o redirecionamento OAuth.
from urllib.parse import parse_qs, urlsplit
# Substitui pontos controlados nos testes sem chamar serviços Google reais.
from unittest.mock import patch

# Usa o modelo institucional configurado, com perfil e confirmação de e-mail.
from django.contrib.auth import get_user_model
# Executa comandos Django dentro do teste, como set_role.
from django.core.management import call_command
# Permite verificar as recusas esperadas dos comandos administrativos.
from django.core.management.base import CommandError
# Importa cliente HTTP de teste, requisições isoladas, banco transacional de teste e substituição temporária de settings.
from django.test import Client, RequestFactory, TestCase, override_settings
# Resolve URLs pelos nomes registrados para testar as rotas efetivas.
from django.urls import reverse

# Representa a interrupção segura do login que o adapter deve lançar ao rejeitar uma conta.
from allauth.core.exceptions import ImmediateHttpResponse
# Cria representações controladas do vínculo Google e de uma tentativa de autenticação.
from allauth.socialaccount.models import SocialAccount, SocialLogin

# Importa a política de segurança institucional que será exercitada.
from .google_adapter import InstitutionalGoogleAdapter


# Agrupa testes das claims Google e da associação entre identidade externa e conta local.
class InstitutionalGoogleTests(TestCase):
    # Prepara objetos novos antes de cada teste, impedindo dependência entre cenários.
    def setUp(self):
        # Cria a instância da política institucional, sem conexão com o Google.
        self.adapter = InstitutionalGoogleAdapter()
        # Monta uma requisição mínima para chamar o hook do adapter diretamente.
        self.request = RequestFactory().get("/autenticacao/google/login/callback/")

    # Fábrica de tentativa Google; os testes podem substituir uma claim para representar um caso inválido.
    def login(self, **claims):
        # Define um conjunto de claims fictícias que satisfaz a política institucional.
        data = {
            # E-mail fictício usado apenas no banco temporário de testes.
            "email": "aluno@camporeal.edu.br",
            # Representa a confirmação booleana devolvida pelo provedor autenticado.
            "email_verified": True,
            # Representa a organização Workspace informada pelo Google.
            "hd": "camporeal.edu.br",
        }
        # Sobrescreve os campos específicos do cenário, preservando os demais dados válidos.
        data.update(claims)
        # Devolve o objeto esperado pelo adapter; isso não efetua login real nem emite tokens.
        return SocialLogin(
            # Cria um usuário ainda não persistido com o e-mail do cenário.
            user=get_user_model()(email=data.get("email") or ""),
            # Identifica o provedor Google e anexa as claims simuladas ao vínculo.
            account=SocialAccount(provider="google", uid="google-subject", extra_data=data),
        )

    # Confirma que a política aceita uma conta institucional com organização e e-mail verificados.
    def test_verified_institutional_workspace_is_accepted(self):
        # Executa o hook; o teste falha se ele rejeitar um cenário que deveria ser válido.
        self.adapter.pre_social_login(self.request, self.login())

    # Confirma compatibilidade com o nome legado de claim Google verified_email.
    def test_legacy_verified_email_claim_is_accepted(self):
        # Fornece a confirmação somente no formato legado, que também é aceito.
        self.adapter.pre_social_login(self.request, self.login(email_verified=False, verified_email=True))

    # Verifica tentativas de contornar domínio, organização ou confirmação de e-mail.
    def test_external_unverified_and_spoofed_workspace_are_denied(self):
        # Lista cenários independentes de dados que devem ser recusados.
        invalid = [
            # Conta pessoal não pertence ao domínio da faculdade.
            {"email": "aluno@gmail.com"},
            # Um sufixo contendo o domínio não equivale ao domínio institucional exato.
            {"email": "aluno@camporeal.edu.br.evil.example"},
            # Subdomínio também não corresponde à organização explicitamente permitida.
            {"email": "aluno@sub.camporeal.edu.br"},
            # E-mail sem confirmação não é suficiente para autenticar.
            {"email_verified": False},
            # Texto parecido com booleano não deve passar pela comparação estrita is True.
            {"email_verified": "true"},
            # Organização Google diferente invalida mesmo um e-mail com aparência institucional.
            {"hd": "gmail.com"},
            # Ausência de organização autenticada não deve ser suprida pelo parâmetro de URL.
            {"hd": None},
            # Domínio sozinho, sem parte local do endereço, é inválido.
            {"email": "@camporeal.edu.br"},
        ]
        # Executa o mesmo requisito de segurança para cada vetor inválido da lista.
        for claims in invalid:
            # Identifica o cenário no relatório e exige que o login seja interrompido.
            with self.subTest(claims=claims), self.assertRaises(ImmediateHttpResponse):
                # Aplica as claims alteradas à mesma política utilizada pela aplicação.
                self.adapter.pre_social_login(self.request, self.login(**claims))

    # Exige revalidação de uma conta já vinculada e bloqueio após sua desativação local.
    def test_existing_account_revalidated_and_inactive_rejected(self):
        # Persiste uma conta de teste ainda sem confirmação para observar a atualização.
        user = get_user_model().objects.create_user("aluno@camporeal.edu.br")
        # Obtém uma tentativa institucional válida, sem consultar o Google.
        login = self.login()
        # Associa o objeto do teste à conta local existente, simulando vínculo OAuth reconhecido.
        login.user = user
        # Executa a política sobre a tentativa preparada neste cenário.
        self.adapter.pre_social_login(self.request, login)
        # Relê o banco para verificar persistência real, não apenas alteração em memória.
        user.refresh_from_db()
        # Confere que a confirmação verificada do provedor foi persistida.
        self.assertTrue(user.email_verified)
        # Simula bloqueio da conta pela administração institucional.
        user.is_active = False
        # Grava somente a alteração de ativação, preservando os demais dados.
        user.save(update_fields=["is_active"])
        # Exige que o adapter interrompa o login em vez de permitir uma sessão.
        with self.assertRaises(ImmediateHttpResponse):
            # Executa a política sobre a tentativa preparada neste cenário.
            self.adapter.pre_social_login(self.request, login)

    # Recusa alteração silenciosa de e-mail de uma identidade Google já vinculada.
    def test_existing_link_does_not_accept_changed_or_external_identity(self):
        # Prepara uma conta já confirmada para isolar a regra de consistência do endereço.
        user = get_user_model().objects.create_user("aluno@camporeal.edu.br", email_verified=True)
        # O provedor retorna outro e-mail válido, mas ele não é o endereço da conta vinculada.
        login = self.login(email="outro@camporeal.edu.br")
        # Associa o objeto do teste à conta local existente, simulando vínculo OAuth reconhecido.
        login.user = user
        # Exige que o adapter interrompa o login em vez de permitir uma sessão.
        with self.assertRaises(ImmediateHttpResponse):
            # Executa a política sobre a tentativa preparada neste cenário.
            self.adapter.pre_social_login(self.request, login)

    # Garante que coincidência de e-mail não vincula por si só uma conta local ao Google.
    def test_local_email_match_is_not_automatically_linked(self):
        # Cria a conta local preexistente, sem vínculo social autenticado.
        get_user_model().objects.create_user("aluno@camporeal.edu.br")
        # Exige que o adapter interrompa o login em vez de permitir uma sessão.
        with self.assertRaises(ImmediateHttpResponse):
            # Executa o hook; o teste falha se ele rejeitar um cenário que deveria ser válido.
            self.adapter.pre_social_login(self.request, self.login())

    # Confirma que o primeiro cadastro Google não concede perfil administrativo.
    def test_signup_cannot_create_privileged_role(self):
        # Obtém uma tentativa institucional válida, sem consultar o Google.
        login = self.login()
        # Simula um perfil privilegiado indevido no objeto antes da aplicação da política.
        login.user.role = get_user_model().Role.DIRECTOR
        # Isola o salvamento da biblioteca para inspecionar somente os campos definidos pelo nosso adapter.
        with patch("allauth.socialaccount.adapter.DefaultSocialAccountAdapter.save_user", return_value=login.user):
            # Executa o hook de cadastro institucional com o perfil indevido inicial.
            user = self.adapter.save_user(self.request, login)
        # Exige que um primeiro cadastro termine com o perfil mínimo de aluno.
        self.assertEqual(user.role, "student")
        # Confere que a confirmação verificada do provedor foi persistida.
        self.assertTrue(user.email_verified)

    # Garante que outro provedor não contorna a exigência de identidade Google.
    def test_non_google_provider_denied(self):
        # Obtém uma tentativa institucional válida, sem consultar o Google.
        login = self.login()
        # Troca apenas o provedor, mantendo as demais claims aparentemente válidas.
        login.account.provider = "github"
        # Exige que o adapter interrompa o login em vez de permitir uma sessão.
        with self.assertRaises(ImmediateHttpResponse):
            # Executa a política sobre a tentativa preparada neste cenário.
            self.adapter.pre_social_login(self.request, login)


# Testa a atribuição de perfis pelo comando confiável do servidor.
class RoleAssignmentTests(TestCase):
    # Prepara objetos novos antes de cada teste, impedindo dependência entre cenários.
    def setUp(self):
        # Cria uma conta institucional confirmada, inicialmente aluno e sem senha utilizável.
        self.user = get_user_model().objects.create_user("diretor@camporeal.edu.br", email_verified=True)

    # Impede promover uma conta sem preparar a senha de confirmação sensível.
    def test_director_requires_confirmation_password(self):
        # Exige que uma condição administrativa inválida termine com erro explícito.
        with self.assertRaises(CommandError):
            # Tenta promover sem senha; a saída é capturada e nenhuma credencial é exibida.
            call_command("set_role", self.user.email, role="director", stdout=StringIO())
        # Relê o estado persistido após executar o comando administrativo.
        self.user.refresh_from_db()
        # Confirma que a tentativa negada não alterou o perfil no banco.
        self.assertEqual(self.user.role, "student")

    # Verifica promoção válida e armazenamento da senha pelo mecanismo de hash Django.
    def test_director_password_is_hashed_and_role_assigned(self):
        # Fornece senha fictícia exclusivamente ao processo de teste; ela não é uma credencial de implantação.
        with patch.dict("os.environ", {"DIRECTOR_CONFIRMATION_PASSWORD": "UmConfirmador-Forte!741"}):
            # Solicita a promoção junto com a configuração segura de senha por variável de ambiente.
            call_command("set_role", self.user.email, role="director", set_confirmation_password=True, stdout=StringIO())
        # Relê o estado persistido após executar o comando administrativo.
        self.user.refresh_from_db()
        # Confirma a persistência do perfil autorizado de direção.
        self.assertEqual(self.user.role, "director")
        # Verifica o hash com a API Django, sem esperar senha legível no banco.
        self.assertTrue(self.user.check_password("UmConfirmador-Forte!741"))

    # Impede atribuir privilégios antes da confirmação institucional da conta.
    def test_unconfirmed_account_cannot_be_promoted(self):
        # Simula a perda ou ausência de confirmação local.
        self.user.email_verified = False
        # Persiste somente a flag usada pela regra de promoção.
        self.user.save(update_fields=["email_verified"])
        # Exige que uma condição administrativa inválida termine com erro explícito.
        with self.assertRaises(CommandError):
            # Tenta conceder perfil de ouvidoria a uma conta não confirmada.
            call_command("set_role", self.user.email, role="ombudsman", stdout=StringIO())

    # Assegura que a senha da direção também segue os validadores de força do projeto.
    def test_password_validation_rejects_weak_confirmation(self):
        # Usa um valor propositalmente fraco como entrada negativa do teste.
        with patch.dict("os.environ", {"DIRECTOR_CONFIRMATION_PASSWORD": "123"}):
            # Exige que uma condição administrativa inválida termine com erro explícito.
            with self.assertRaises(CommandError):
                # Solicita a promoção junto com a configuração segura de senha por variável de ambiente.
                call_command("set_role", self.user.email, role="director", set_confirmation_password=True, stdout=StringIO())


# Substitui credenciais e parâmetros somente nestes testes; não usa segredos Google reais.
@override_settings(SOCIALACCOUNT_PROVIDERS={"google": {
    # Credenciais fictícias suficientes para montar a URL de autorização, sem trocar códigos na rede.
    "APP": {"client_id": "test-client-id", "secret": "test-client-secret", "key": ""},
    # Mantém os mesmos escopos mínimos utilizados pelo fluxo institucional.
    "SCOPE": ["profile", "email"],
    # Inclui indicação de organização e escolha de conta na URL que será inspecionada.
    "AUTH_PARAMS": {"hd": "camporeal.edu.br", "prompt": "select_account"},
}})
# Testa requisições HTTP completas do início e das recusas do fluxo OAuth.
class GoogleLoginFlowTests(TestCase):
    # Um GET deve mostrar confirmação e não autenticar ou sair automaticamente do site.
    def test_get_requires_confirmation_before_leaving_site(self):
        # Abre a rota real do provedor com o cliente Django de teste.
        response = self.client.get(reverse("google_login"))
        # Exige resposta normal da página de confirmação.
        self.assertEqual(response.status_code, 200)
        # Garante que o GET não redirecionou o navegador ao provedor.
        self.assertNotIn("Location", response.headers)

    # Confere o redirecionamento OAuth criado após a ação explícita via POST.
    def test_post_starts_google_oauth_with_state_and_workspace_hint(self):
        # Solicita o início do login com POST; nenhuma chamada externa acontece nesta etapa.
        response = self.client.post(reverse("google_login"))
        # Exige o redirecionamento HTTP esperado para o Google.
        self.assertEqual(response.status_code, 302)
        # Decompõe o destino para inspecionar protocolo, host e parâmetros separadamente.
        target = urlsplit(response["Location"])
        # Não permite que a autorização Google use HTTP sem TLS.
        self.assertEqual(target.scheme, "https")
        # Confirma o host oficial do Google em vez de um destino arbitrário.
        self.assertEqual(target.hostname, "accounts.google.com")
        # Transforma a query string em listas de valores por nome de parâmetro.
        params = parse_qs(target.query)
        # Verifica que o início do login sugere a organização institucional correta.
        self.assertEqual(params["hd"], ["camporeal.edu.br"])
        # Confirma que a URL utiliza o cliente OAuth selecionado nas configurações de teste.
        self.assertEqual(params["client_id"], ["test-client-id"])
        # Exige estado OAuth não vazio para correlacionar autorização e sessão na volta.
        self.assertTrue(params["state"][0])

    # A proteção de formulário deve impedir iniciar login sem token CSRF.
    def test_csrf_is_required_to_start_google_login(self):
        # Usa um cliente que aplica CSRF de verdade e envia o POST sem token.
        response = Client(enforce_csrf_checks=True).post(reverse("google_login"))
        # Confirma acesso proibido para a operação sem pré-requisito de segurança.
        self.assertEqual(response.status_code, 403)

    # Um código sem estado de sessão correspondente não pode autenticar o visitante.
    def test_callback_without_oauth_state_cannot_authenticate(self):
        # Simula retorno malformado sem iniciar previamente uma autorização válida.
        response = self.client.get(reverse("google_callback"), {"code": "untrusted-code"})
        # Exige a recusa de autenticação do callback sem estado válido.
        self.assertEqual(response.status_code, 401)
        # Confirma que não foi criada uma sessão autenticada mesmo após a tentativa HTTP.
        self.assertNotIn("_auth_user_id", self.client.session)

    # Desativa o login local temporariamente para reproduzir a política de produção.
    @override_settings(LOCAL_ACCOUNTS_ENABLED=False)
    # Verifica que rotas alternativas não contornam o Google institucional.
    def test_production_has_no_alternate_password_login_or_signup(self):
        # Testa o login próprio e o caminho equivalente da biblioteca allauth.
        for url in (reverse("accounts:login"), reverse("account_login")):
            # Identifica qual URL violou a regra em caso de falha.
            with self.subTest(url=url):
                # Envia uma tentativa de senha que deve ser bloqueada antes de autenticar.
                response = self.client.post(url, {"login": "diretor@camporeal.edu.br", "password": "unused"})
                # Confirma acesso proibido para a operação sem pré-requisito de segurança.
                self.assertEqual(response.status_code, 403)
        # Verifica que cadastro e alteração/recuperação de senha allauth não são expostos.
        for url in ("/autenticacao/signup/", "/autenticacao/password/reset/", "/autenticacao/password/change/"):
            # Identifica qual URL violou a regra em caso de falha.
            with self.subTest(url=url):
                # Exige rota indisponível para os caminhos desabilitados pelo modo social exclusivo.
                self.assertEqual(self.client.get(url).status_code, 404)
        # Confirma que não foi criada uma sessão autenticada mesmo após a tentativa HTTP.
        self.assertNotIn("_auth_user_id", self.client.session)
