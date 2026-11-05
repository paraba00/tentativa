# Testes de contas: cada método test_ descreve um comportamento que deve permanecer verdadeiro.
# As senhas e contas abaixo são fictícias e pertencem somente ao banco isolado dos testes.

# Importa o relógio para criar um token com data passada e simular expiração.
import time
# Permite substituir temporariamente funções, como o relógio usado na assinatura.
from unittest.mock import patch

# Importa a autenticação real do Django, utilizada para conferir e-mail e senha.
from django.contrib.auth import authenticate
# Disponibiliza mail.outbox: caixa de saída em memória que recebe os e-mails do teste.
from django.core import mail
# Importa o cache onde são contadas tentativas de login e pedidos de reenvio.
from django.core.cache import cache
# TestCase isola o banco por teste; override_settings altera configurações só nesta execução.
from django.test import TestCase, override_settings
# Converte nomes de rotas em URLs, evitando depender de caminhos escritos manualmente.
from django.urls import reverse

# Importa o formulário que aplica as regras do cadastro institucional.
from .forms import RegistrationForm
# Importa o usuário personalizado para criar contas e conferir os registros persistidos.
from .models import User
# Importa a mesma geração de token assinada utilizada no envio de confirmação.
from .services import verification_token


# Usa armazenamento local e arquivos estáticos simples nos testes, sem exigir um manifesto de publicação.
TEST_STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


# Habilita cadastro local só nesta classe; e-mails ficam em memória.
# O hash MD5 acelera estes testes isolados e nunca substitui o hash seguro da aplicação em execução.
@override_settings(LOCAL_ACCOUNTS_ENABLED=True, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], STORAGES=TEST_STORAGES)
# Agrupa os cenários automatizados de cadastro, confirmação, autenticação e encerramento de sessão.
class InstitutionalAccountsTests(TestCase):
    # Executa esta preparação antes de cada cenário para impedir dependência entre testes.
    def setUp(self):
        # Limpa contadores de tentativas e reenvios deixados pelo cenário anterior.
        cache.clear()

    # Produz dados válidos de cadastro e permite trocar campos para testar casos específicos.
    def registration_data(self, **changes):
        # Monta nome, sobrenome, e-mail institucional e duas cópias iguais da senha fictícia.
        data = {"first_name": "Aluno", "last_name": "Teste", "email": "aluno@camporeal.edu.br", "password1": "Uma-Senha-Institucional-123", "password2": "Uma-Senha-Institucional-123"}
        # Aplica somente as alterações solicitadas pelo cenário sobre os dados padrão.
        data.update(changes)
        # Entrega o dicionário pronto para enviar ao formulário ou à requisição POST.
        return data

    # Verifica a rejeição de domínios externos e de endereços que apenas imitam o domínio institucional.
    def test_only_exact_institutional_domain_is_accepted(self):
        # Percorre exemplos de domínio externo, prefixo parecido, sufixo malicioso e subdomínio não permitido.
        for email in ["aluno@gmail.com", "aluno@evilcamporeal.edu.br", "aluno@camporeal.edu.br.evil.com", "aluno@sub.camporeal.edu.br"]:
            # Submete cada endereço ao formulário real, mantendo os demais campos válidos.
            form = RegistrationForm(data=self.registration_data(email=email))
            # Exige que o formulário seja inválido; o endereço aparece na mensagem caso a verificação falhe.
            self.assertFalse(form.is_valid(), email)
            # Confirma que a rejeição foi associada ao campo e-mail, e não a outro dado.
            self.assertIn("email", form.errors)

    # Testa a normalização do e-mail e uma tentativa de forjar privilégios durante o cadastro público.
    def test_registration_normalizes_email_and_ignores_privilege_fields(self):
        # Envia e-mail em maiúsculas junto de campos administrativos indevidos no POST.
        response = self.client.post(reverse("accounts:register"), self.registration_data(email="ALUNO@CAMPOREAL.EDU.BR", role="director", email_verified="true", is_staff="true", is_superuser="true"))
        # Confirma o redirecionamento para as instruções de confirmação de e-mail.
        self.assertRedirects(response, reverse("accounts:verify_sent"))
        # Lê a única conta criada no banco isolado para inspecionar seus valores efetivos.
        user = User.objects.get()
        # Exige que o endereço tenha sido persistido em letras minúsculas.
        self.assertEqual(user.email, "aluno@camporeal.edu.br")
        # Confirma que o perfil continua sendo aluno, mesmo após o envio forjado de director.
        self.assertEqual(user.role, User.Role.STUDENT)
        # Confirma que o aluno não conseguiu marcar seu próprio e-mail como verificado.
        self.assertFalse(user.email_verified)
        # Confirma que o campo forjado is_staff não concedeu acesso administrativo.
        self.assertFalse(user.is_staff)
        # Confirma que o campo forjado is_superuser não concedeu permissões de superusuário.
        self.assertFalse(user.is_superuser)
        # Verifica que o cadastro gerou exatamente uma mensagem de confirmação.
        self.assertEqual(len(mail.outbox), 1)
        # Confirma que a mensagem foi destinada exclusivamente ao e-mail cadastrado.
        self.assertEqual(mail.outbox[0].to, [user.email])
        # Confirma que o corpo contém o caminho do link para confirmar a conta.
        self.assertIn("/conta/confirmar/", mail.outbox[0].body)

    # Verifica que trocar maiúsculas e minúsculas não permite cadastrar duas vezes o mesmo endereço.
    def test_duplicate_email_is_case_insensitive(self):
        # Cria primeiro uma conta que já ocupa o endereço institucional em minúsculas.
        User.objects.create_user("aluno@camporeal.edu.br", "secure-password")
        # Tenta cadastrar o mesmo endereço com o nome local escrito em maiúsculas.
        form = RegistrationForm(data=self.registration_data(email="ALUNO@camporeal.edu.br"))
        # Exige que o segundo cadastro seja considerado inválido.
        self.assertFalse(form.is_valid())
        # Confirma que o formulário informa a duplicidade no próprio campo e-mail.
        self.assertIn("email", form.errors)

    # Verifica que o link confirma a conta sem autenticar automaticamente o navegador que o abriu.
    def test_valid_email_link_verifies_but_does_not_login(self):
        # Cria um usuário ainda não verificado para receber a confirmação.
        user = User.objects.create_user("aluno@camporeal.edu.br", "secure-password")
        # Gera um token válido e acessa a rota pública de confirmação como faria o destinatário.
        response = self.client.get(reverse("accounts:verify_email", args=[verification_token(user)]))
        # Confirma que o visitante é encaminhado à tela de login após validar o e-mail.
        self.assertRedirects(response, reverse("accounts:login"))
        # Recarrega os dados do banco porque a requisição alterou outra instância do usuário.
        user.refresh_from_db()
        # Exige que a confirmação tenha sido gravada em email_verified.
        self.assertTrue(user.email_verified)
        # Confirma que a sessão não ganhou a chave de autenticação do Django.
        self.assertNotIn("_auth_user_id", self.client.session)

    # Testa separadamente um token adulterado e um token emitido além do prazo permitido.
    def test_tampered_and_expired_tokens_do_not_verify(self):
        # Cria uma conta sem confirmação para verificar que as tentativas inválidas não a alteram.
        user = User.objects.create_user("aluno@camporeal.edu.br", "secure-password")
        # Gera um token original, com conteúdo e instante protegidos pela assinatura.
        token = verification_token(user)
        # Acrescenta texto ao token e tenta usá-lo; a assinatura deve deixar de conferir.
        self.client.get(reverse("accounts:verify_email", args=[token + "tampered"]))
        # Busca novamente o usuário para observar o estado persistido após a tentativa.
        user.refresh_from_db()
        # Exige que o token adulterado não tenha confirmado o e-mail.
        self.assertFalse(user.email_verified)
        # Substitui o relógio do assinador por um instante de 90.000 segundos atrás, superior a 24 horas.
        with patch("django.core.signing.time.time", return_value=time.time() - 90000):
            # Emite o token enquanto o relógio simulado está no passado.
            expired = verification_token(user)
        # Tenta confirmar o token com o relógio normal, quando seu prazo já expirou.
        self.client.get(reverse("accounts:verify_email", args=[expired]))
        # Recarrega o estado da conta após a verificação do token expirado.
        user.refresh_from_db()
        # Confirma que o token vencido também não validou o e-mail.
        self.assertFalse(user.email_verified)

    # Verifica login indiferente a maiúsculas e o destino correto para uma conta da ouvidoria.
    def test_login_accepts_uppercase_email_and_routes_staff(self):
        # Cria uma conta de ouvidor ativa e com e-mail previamente confirmado.
        user = User.objects.create_user("ouvidor@camporeal.edu.br", "secure-password", role=User.Role.OMBUDSMAN, email_verified=True)
        # Confere diretamente que o backend encontra a mesma conta usando e-mail em maiúsculas.
        self.assertEqual(authenticate(username="OUVIDOR@CAMPOREAL.EDU.BR", password="secure-password"), user)
        # Envia as mesmas credenciais à página real de login.
        response = self.client.post(reverse("accounts:login"), {"email": "OUVIDOR@CAMPOREAL.EDU.BR", "password": "secure-password"})
        # Exige que um ouvidor autenticado seja encaminhado ao painel administrativo.
        self.assertRedirects(response, reverse("ombudsman:staff_dashboard"))

    # Verifica que desabilitar contas locais realmente bloqueia cadastro e senha pela interface pública.
    def test_local_accounts_cannot_bypass_google_only_setting(self):
        # Aplica temporariamente a configuração que permite somente o acesso institucional Google.
        with self.settings(LOCAL_ACCOUNTS_ENABLED=False):
            # Confirma que uma tentativa de cadastro local volta à página de entrada.
            self.assertRedirects(self.client.post(reverse("accounts:register"), self.registration_data()), reverse("accounts:login"))
            # Exige HTTP 403, acesso negado, para uma tentativa de autenticação local por senha.
            self.assertEqual(self.client.post(reverse("accounts:login"), {"email": "aluno@camporeal.edu.br", "password": "secure-password"}).status_code, 403)
            # Confirma que a tentativa bloqueada não criou qualquer usuário no banco.
            self.assertFalse(User.objects.exists())

    # Verifica a proteção contra redirecionamento do login para um site externo controlado por terceiros.
    def test_login_does_not_accept_external_redirect(self):
        # Cria uma conta válida para que a autenticação em si seja bem-sucedida.
        User.objects.create_user("aluno@camporeal.edu.br", "secure-password")
        # Tenta impor um destino externo pelo parâmetro next durante o login.
        response = self.client.post(reverse("accounts:login") + "?next=https://evil.example", {"email": "aluno@camporeal.edu.br", "password": "secure-password"})
        # Confirma que o endereço externo foi ignorado e o aluno seguiu para o painel interno.
        self.assertRedirects(response, reverse("ombudsman:student_dashboard"))

    # Verifica o bloqueio temporário após o limite de tentativas de login malsucedidas.
    def test_failed_login_attempts_are_rate_limited(self):
        # Repete dez tentativas para atingir o limite configurado para o endereço informado.
        for _ in range(10):
            # Envia uma senha inválida; cada falha deve aumentar o contador no cache.
            self.client.post(reverse("accounts:login"), {"email": "nobody@camporeal.edu.br", "password": "wrong-password"})
        # Faz a tentativa seguinte, quando o limite já foi alcançado.
        response = self.client.post(reverse("accounts:login"), {"email": "nobody@camporeal.edu.br", "password": "wrong-password"})
        # Exige HTTP 429, que indica excesso de tentativas e necessidade de aguardar.
        self.assertEqual(response.status_code, 429)

    # Verifica autenticação, método POST e intervalo mínimo para reenviar a confirmação.
    def test_resend_requires_login_and_post(self):
        # Confirma que um visitante sem sessão é redirecionado antes de solicitar o reenvio.
        self.assertEqual(self.client.post(reverse("accounts:resend_verification")).status_code, 302)
        # Cria uma conta ainda não confirmada para testar o botão de reenvio.
        user = User.objects.create_user("aluno@camporeal.edu.br", "secure-password")
        # Autentica diretamente o cliente de teste, isolando o cenário do formulário de login.
        self.client.force_login(user)
        # Exige HTTP 405 para GET; abrir uma página não pode disparar o envio de e-mail.
        self.assertEqual(self.client.get(reverse("accounts:resend_verification")).status_code, 405)
        # Solicita o primeiro reenvio válido com uma requisição POST.
        self.client.post(reverse("accounts:resend_verification"))
        # Repete a solicitação imediatamente, antes do intervalo mínimo de um minuto.
        self.client.post(reverse("accounts:resend_verification"))
        # Confirma que só a primeira solicitação produziu um e-mail.
        self.assertEqual(len(mail.outbox), 1)

    # Verifica que sair da conta exige POST e remove a autenticação da sessão.
    def test_logout_requires_post(self):
        # Cria uma conta que será usada apenas para este cenário de encerramento de sessão.
        user = User.objects.create_user("aluno@camporeal.edu.br", "secure-password")
        # Inicia uma sessão autenticada para que o teste possa encerrá-la.
        self.client.force_login(user)
        # Exige HTTP 405 para GET, impedindo o logout por simples acesso a um link.
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        # Envia o POST permitido para encerrar a sessão.
        self.client.post(reverse("accounts:logout"))
        # Confirma a remoção da chave que identificava o usuário autenticado.
        self.assertNotIn("_auth_user_id", self.client.session)
