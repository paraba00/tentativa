# Testes da ouvidoria: verificam o fluxo completo e os limites de acesso aos dados dos alunos.
# As senhas e contas abaixo são fictícias e pertencem somente ao banco isolado dos testes.

# Importa um buffer de texto para capturar a saída do comando de demonstração sem poluir os testes.
from io import StringIO
# Permite fornecer variáveis de ambiente fictícias só durante um bloco do teste.
from unittest.mock import patch

# Obtém o modelo de usuário configurado em AUTH_USER_MODEL, sem depender de um usuário padrão.
from django.contrib.auth import get_user_model
# Importa o cache que guarda os contadores de tentativas de revelação de identidade.
from django.core.cache import cache
# Permite executar comandos manage.py, como seed_demo, a partir do próprio teste.
from django.core.management import call_command
# Importa a exceção esperada quando um comando é solicitado fora das condições permitidas.
from django.core.management.base import CommandError
# Client simula requisições; TestCase isola o banco; override_settings restringe ajustes aos testes.
from django.test import Client, TestCase, override_settings
# Resolve os nomes das rotas para seus caminhos atuais.
from django.urls import reverse

# Importa a validação usada no envio de uma manifestação pelo aluno.
from .forms import ComplaintForm
# Importa os registros operacionais, a identidade separada, a auditoria, as respostas e o histórico.
from .models import Complaint, ComplaintIdentity, IdentityAccessAudit, Reply, StatusEvent
# Importa a projeção segura dos dados e o serviço transacional de criação da manifestação.
from .services import case_payload, create_complaint

# Guarda o modelo de usuário ativo para criar as contas fictícias dos cenários.
User = get_user_model()
# Usa arquivos locais e estáticos simples, evitando exigir o manifesto de publicação nesta suíte.
TEST_STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


# Acelera o hash de senhas fictícias com MD5 apenas nestes testes e aplica os armazenamentos de teste.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"], STORAGES=TEST_STORAGES)
# Agrupa os cenários de manifestação, acompanhamento, administração e privacidade.
class OmbudsmanWorkflowTests(TestCase):
    # Declara a preparação compartilhada como método de classe, recebendo cls em vez de self.
    @classmethod
    # Prepara os dados de referência uma vez por classe; TestCase mantém o isolamento entre cenários.
    def setUpTestData(cls):
        # Cria o aluno titular com nome e e-mail reconhecíveis para detectar vazamentos no HTML.
        cls.student = User.objects.create_user("particular@camporeal.edu.br", "student-password", first_name="Identidade", last_name="Protegida", email_verified=True)
        # Cria outro aluno para simular alguém que conhece um protocolo, mas não é seu autor.
        cls.other_student = User.objects.create_user("outro@camporeal.edu.br", "student-password", email_verified=True)
        # Cria uma conta com perfil de ouvidoria e e-mail confirmado.
        cls.staff = User.objects.create_user("ouvidor@camporeal.edu.br", "staff-password", role=User.Role.OMBUDSMAN, email_verified=True)
        # Cria uma conta de direção com senha de confirmação e e-mail confirmado.
        cls.director = User.objects.create_user("diretor@camporeal.edu.br", "director-password", role=User.Role.DIRECTOR, email_verified=True)
        # Monta o formulário da manifestação inicial a partir dos dados fictícios válidos.
        form = ComplaintForm(data=cls.case_data())
        # Interrompe a preparação com os erros do formulário se os dados de referência deixarem de ser válidos.
        assert form.is_valid(), form.errors
        # Cria a manifestação inicial usando o mesmo serviço que a aplicação utiliza.
        cls.case = create_complaint(user=cls.student, form=form)

    # Marca o gerador de dados como função auxiliar sem dependência de uma instância da classe.
    @staticmethod
    # Permite montar manifestações válidas e trocar somente os campos relevantes para cada teste.
    def case_data(**changes):
        # Define uma reclamação acadêmica sigilosa, com título, descrição e ciência de privacidade.
        data = {"category": Complaint.Category.COMPLAINT, "sector": Complaint.Sector.ACADEMIC, "title": "Laboratório sem acesso", "description": "Gostaria de informar que o laboratório está fechado durante o intervalo.", "visibility": Complaint.Visibility.CONFIDENTIAL, "privacy_ack": True}
        # Substitui os valores padrão pelos campos enviados pelo cenário atual.
        data.update(changes)
        # Retorna o dicionário pronto para alimentar um formulário ou uma requisição POST.
        return data

    # Executa esta preparação antes de cada teste individual.
    def setUp(self):
        # Zera contadores para que bloqueios de um cenário não influenciem o seguinte.
        cache.clear()

    # Centraliza a construção do endereço de acompanhamento da manifestação inicial.
    def own_detail_url(self):
        # Gera a rota do aluno usando o protocolo real criado na preparação.
        return reverse("ombudsman:detail", args=[self.case.protocol])

    # Centraliza o endereço administrativo usado para ler e responder à manifestação inicial.
    def staff_detail_url(self):
        # Gera a rota de detalhe administrativo com o protocolo, sem escrever o caminho manualmente.
        return reverse("ombudsman:staff_detail", args=[self.case.protocol])

    # Centraliza o endereço da ação sensível de consulta da identidade sigilosa.
    def reveal_url(self):
        # Gera a URL que exige perfil de direção, POST e confirmação de senha.
        return reverse("ombudsman:reveal_identity", args=[self.case.protocol])

    # Verifica que a página inicial é pública e as demais áreas exigem autenticação.
    def test_public_home_and_login_protection(self):
        # Exige HTTP 200 para a página inicial aberta por um visitante sem sessão.
        self.assertEqual(self.client.get(reverse("ombudsman:home")).status_code, 200)
        # Percorre os nomes das áreas protegidas de aluno e administração.
        for name in ["student_dashboard", "create", "track", "staff_dashboard"]:
            # Exige redirecionamento HTTP 302 para login quando o visitante tenta cada área protegida.
            self.assertEqual(self.client.get(reverse(f"ombudsman:{name}")).status_code, 302)
        # Confirma que saber o endereço de uma manifestação também não dispensa o login.
        self.assertEqual(self.client.get(self.own_detail_url()).status_code, 302)

    # Verifica a persistência conjunta da manifestação, de sua autoria reservada e do histórico inicial.
    def test_submission_persists_identity_protocol_and_timeline(self):
        # Autentica o cliente como o aluno verificado que enviará uma nova manifestação.
        self.client.force_login(self.student)
        # Envia uma manifestação válida com título próprio para localizá-la no banco.
        response = self.client.post(reverse("ombudsman:create"), self.case_data(title="Nova manifestação do aluno"))
        # Busca a manifestação recém-criada pelo título exclusivo deste cenário.
        case = Complaint.objects.get(title="Nova manifestação do aluno")
        # Confirma o redirecionamento para o acompanhamento da manifestação enviada.
        self.assertRedirects(response, reverse("ombudsman:detail", args=[case.protocol]))
        # Exige o formato CR-ano-12 dígitos hexadecimais no protocolo gerado.
        self.assertRegex(case.protocol, r"^CR-\d{4}-[0-9A-F]{12}$")
        # Confirma que o novo protocolo é diferente do protocolo da manifestação de referência.
        self.assertNotEqual(case.protocol, self.case.protocol)
        # Confirma que a identidade reservada aponta para o aluno autenticado que fez o envio.
        self.assertEqual(case.identity.user, self.student)
        # Exige que a nova manifestação comece na situação Recebida.
        self.assertEqual(case.status, Complaint.Status.RECEIVED)
        # Confirma que foi criado exatamente o evento inicial do histórico.
        self.assertEqual(case.events.count(), 1)

    # Verifica que uma sessão autenticada sem e-mail confirmado não pode registrar manifestações.
    def test_unverified_student_cannot_submit(self):
        # Simula uma conta que ainda não confirmou o endereço institucional.
        self.student.email_verified = False
        # Grava apenas o campo alterado para que a próxima requisição veja o novo estado.
        self.student.save(update_fields=["email_verified"])
        # Autentica essa conta sem transformar seu e-mail em confirmado.
        self.client.force_login(self.student)
        # Tenta enviar dados de manifestação válidos para isolar a regra de confirmação do e-mail.
        response = self.client.post(reverse("ombudsman:create"), self.case_data())
        # Confirma o encaminhamento para as instruções de confirmação institucional.
        self.assertRedirects(response, reverse("accounts:verify_sent"))
        # Exige que permaneça somente a manifestação inicial, sem criar outra indevidamente.
        self.assertEqual(Complaint.objects.count(), 1)

    # Verifica a categoria sugerida pelos links da página inicial e a prioridade da escolha feita no POST.
    def test_creation_preselects_only_valid_category_from_home_link(self):
        # Autentica o aluno que acessará o formulário de envio.
        self.client.force_login(self.student)
        # Abre o formulário com uma categoria válida enviada pela URL.
        response = self.client.get(reverse("ombudsman:create"), {"category": Complaint.Category.SUGGESTION})
        # Confirma que Sugestão aparece previamente selecionada no campo do formulário.
        self.assertEqual(response.context["form"]["category"].value(), Complaint.Category.SUGGESTION)
        # Abre o formulário com um valor inexistente na lista de categorias permitidas.
        response = self.client.get(reverse("ombudsman:create"), {"category": "invalid-category"})
        # Confirma que o valor inválido da URL não foi usado como seleção inicial.
        self.assertIsNone(response.context["form"]["category"].value())
        # Envia Elogio no formulário, embora a URL ainda sugira Sugestão.
        response = self.client.post(reverse("ombudsman:create") + "?category=suggestion", self.case_data(title="Categoria explícita do formulário", category=Complaint.Category.PRAISE))
        # Exige o redirecionamento que confirma um envio bem-sucedido.
        self.assertEqual(response.status_code, 302)
        # Confirma que o banco guardou Elogio, a escolha explícita do POST, e não a sugestão da URL.
        self.assertEqual(Complaint.objects.get(title="Categoria explícita do formulário").category, Complaint.Category.PRAISE)

    # Verifica os tamanhos mínimos do texto e a obrigatoriedade de compreender as condições de privacidade.
    def test_privacy_acknowledgement_and_minimum_details_are_required(self):
        # Monta dados inválidos: assunto curto, descrição curta e ciência de privacidade desmarcada.
        form = ComplaintForm(data=self.case_data(privacy_ack=False, title="abc", description="curto"))
        # Confirma que o formulário rejeita o conjunto de dados incompleto.
        self.assertFalse(form.is_valid())
        # Exige erros exatamente nos três campos que foram tornados inválidos.
        self.assertEqual(set(form.errors), {"title", "description", "privacy_ack"})

    # Testa a tentativa de escolher situação, autor e protocolo por campos extras no POST.
    def test_forged_status_and_identity_fields_are_ignored(self):
        # Inicia uma sessão do aluno verdadeiro que fará o envio forjado.
        self.client.force_login(self.student)
        # Envia campos extras tentando concluir a manifestação, atribuí-la a outro aluno e fixar seu protocolo.
        self.client.post(reverse("ombudsman:create"), self.case_data(title="Somente campos permitidos", status="closed", user=self.other_student.pk, protocol="CR-FORGED"))
        # Busca o registro efetivamente criado para conferir os valores persistidos pelo servidor.
        case = Complaint.objects.get(title="Somente campos permitidos")
        # Confirma que a situação continua Recebida, ignorando o valor closed forjado.
        self.assertEqual(case.status, Complaint.Status.RECEIVED)
        # Confirma que o protocolo foi gerado pelo servidor e não aceitou o texto imposto pelo cliente.
        self.assertNotEqual(case.protocol, "CR-FORGED")
        # Confirma que a autoria continua ligada à conta autenticada, não ao usuário indicado no POST.
        self.assertEqual(case.identity.user, self.student)

    # Verifica que conhecer o número de protocolo não concede acesso à manifestação de outra conta.
    def test_protocol_alone_does_not_grant_access(self):
        # Autentica o cliente como o aluno que não é autor da manifestação inicial.
        self.client.force_login(self.other_student)
        # Exige HTTP 404 ao tentar abrir o detalhe de uma manifestação pertencente a outra conta.
        self.assertEqual(self.client.get(self.own_detail_url()).status_code, 404)
        # Tenta localizar a mesma manifestação pelo formulário de consulta de protocolo.
        response = self.client.post(reverse("ombudsman:track"), {"protocol": self.case.protocol})
        # Confirma que o formulário foi reapresentado, sem redirecionar ao detalhe proibido.
        self.assertEqual(response.status_code, 200)
        # Exige a mensagem que explica que o protocolo não foi encontrado entre os envios daquela conta.
        self.assertFormError(response.context["form"], "protocol", "Protocolo não encontrado entre as manifestações da sua conta. Confira o número e a conta utilizada no envio.")
        # Confirma que o campo com erro foi retirado dos dados validados do formulário.
        self.assertEqual(response.context["form"].cleaned_data, {})
        # Abre o painel do outro aluno para verificar o isolamento da listagem e das métricas.
        dashboard = self.client.get(reverse("ombudsman:student_dashboard"))
        # Exige total zero para a conta que não enviou manifestações.
        self.assertEqual(dashboard.context["metrics"]["total"], 0)
        # Confirma que o título privado da manifestação não aparece no HTML do painel de outro aluno.
        self.assertNotContains(dashboard, self.case.title)

    # Verifica que o próprio autor pode consultar um protocolo com espaços e letras minúsculas.
    def test_owner_can_track_protocol_case_insensitively(self):
        # Autentica a conta à qual pertence a manifestação inicial.
        self.client.force_login(self.student)
        # Envia o protocolo em minúsculas e cercado por espaços para testar a normalização.
        response = self.client.post(reverse("ombudsman:track"), {"protocol": " " + self.case.protocol.lower() + " "})
        # Confirma o redirecionamento para o detalhe privado do autor após normalizar o protocolo.
        self.assertRedirects(response, self.own_detail_url())

    # Verifica que ser aluno ou superusuário técnico não substitui o perfil operacional da ouvidoria.
    def test_student_and_superuser_without_staff_role_cannot_access_staff_area(self):
        # Autentica um aluno comum para tentar operações administrativas.
        self.client.force_login(self.student)
        # Exige HTTP 403 ao tentar abrir o painel reservado da ouvidoria.
        self.assertEqual(self.client.get(reverse("ombudsman:staff_dashboard")).status_code, 403)
        # Exige HTTP 403 para a tentativa de enviar resposta sem o perfil necessário.
        self.assertEqual(self.client.post(self.staff_detail_url(), {"body": "Resposta indevida", "status": "closed"}).status_code, 403)
        # Cria um superusuário técnico cujo perfil operacional permanece o padrão Aluno.
        superuser = User.objects.create_superuser("admin@camporeal.edu.br", "admin-password")
        # Troca a sessão para a conta de superusuário recém-criada.
        self.client.force_login(superuser)
        # Confirma que o superusuário também não recebe acesso operacional sem o perfil apropriado.
        self.assertEqual(self.client.get(reverse("ombudsman:staff_dashboard")).status_code, 403)

    # Verifica que até uma conta com perfil de ouvidoria precisa ter e-mail confirmado.
    def test_unverified_staff_has_no_operational_access(self):
        # Simula a retirada da confirmação de e-mail da conta de ouvidoria.
        self.staff.email_verified = False
        # Persiste somente essa alteração para que a autorização a avalie na requisição seguinte.
        self.staff.save(update_fields=["email_verified"])
        # Autentica a conta com o perfil correto, mas agora sem confirmação do e-mail.
        self.client.force_login(self.staff)
        # Exige HTTP 403, mostrando que o perfil sozinho não basta para acessar o painel.
        self.assertEqual(self.client.get(reverse("ombudsman:staff_dashboard")).status_code, 403)

    # Verifica que nome e e-mail sigilosos não alcançam a listagem, o contexto ou o HTML administrativo comum.
    def test_confidential_identity_never_reaches_staff_context_or_markup(self):
        # Autentica a equipe da ouvidoria, que pode tratar o relato sem consultar a identidade sigilosa.
        self.client.force_login(self.staff)
        # Percorre tanto a listagem administrativa quanto o detalhe da manifestação.
        for url in [reverse("ombudsman:staff_dashboard"), self.staff_detail_url()]:
            # Faz a leitura administrativa da página selecionada pelo laço.
            response = self.client.get(url)
            # Confirma que o acesso ao relato operacional em si está autorizado.
            self.assertEqual(response.status_code, 200)
            # Exige a ausência do e-mail do autor em todo o HTML devolvido à equipe.
            self.assertNotContains(response, self.student.email)
            # Exige a ausência do nome completo do autor em todo o HTML devolvido à equipe.
            self.assertNotContains(response, self.student.get_full_name())
        # Abre novamente o detalhe para inspecionar diretamente seu contexto de renderização.
        response = self.client.get(self.staff_detail_url())
        # Confirma que nenhuma identidade identificada foi anexada ao relato sigiloso.
        self.assertIsNone(response.context["identified_identity"])
        # Confirma que nenhuma identidade revelada foi anexada à leitura comum da equipe.
        self.assertIsNone(response.context["revealed_identity"])
        # Exige um dicionário limitado de dados, em vez de entregar o modelo completo ao template.
        self.assertIsInstance(response.context["case"], dict)
        # Confirma que a projeção segura não possui uma chave que dê acesso à identidade reservada.
        self.assertNotIn("identity", case_payload(self.case))

    # Verifica que o envio explicitamente identificado permite mostrar o contato à equipe da ouvidoria.
    def test_identified_identity_is_visible_to_staff(self):
        # Altera o envio inicial para a modalidade Identificada neste cenário.
        self.case.visibility = Complaint.Visibility.IDENTIFIED
        # Persiste somente a modalidade para preparar a leitura administrativa.
        self.case.save(update_fields=["visibility"])
        # Autentica o ouvidor que poderá visualizar o contato autorizado pelo aluno.
        self.client.force_login(self.staff)
        # Abre a página de tratamento da manifestação identificada.
        response = self.client.get(self.staff_detail_url())
        # Confirma que o e-mail aparece no HTML quando a modalidade permite essa exibição.
        self.assertContains(response, self.student.email)
        # Confirma que o contexto contém o e-mail correto na seção de identidade identificada.
        self.assertEqual(response.context["identified_identity"]["email"], self.student.email)

    # Verifica que possuir a senha da direção não concede à conta de ouvidor o perfil de direção.
    def test_staff_cannot_reveal_even_with_director_password(self):
        # Autentica a equipe comum da ouvidoria, sem o papel necessário à consulta sigilosa.
        self.client.force_login(self.staff)
        # Tenta a consulta com justificativa válida e senha correta da outra conta, a de direção.
        response = self.client.post(self.reveal_url(), {"reason": "Motivo excepcional longo e documentado", "password": "director-password"})
        # Exige HTTP 403 porque a autorização é avaliada pela conta autenticada, antes da senha enviada.
        self.assertEqual(response.status_code, 403)
        # Confirma que nenhuma consulta de identidade foi efetivada ou registrada como acesso autorizado.
        self.assertEqual(IdentityAccessAudit.objects.count(), 0)

    # Verifica as três condições da consulta pela direção: POST, justificativa suficiente e senha correta.
    def test_director_must_post_with_reason_and_correct_password(self):
        # Autentica o diretor que possui autorização potencial para a consulta excepcional.
        self.client.force_login(self.director)
        # Exige HTTP 405 para GET, impedindo que um simples acesso de leitura revele a identidade.
        self.assertEqual(self.client.get(self.reveal_url()).status_code, 405)
        # Confirma que o detalhe normal do diretor ainda mantém o e-mail do aluno oculto.
        self.assertNotContains(self.client.get(self.staff_detail_url()), self.student.email)
        # Percorre uma justificativa insuficiente e, separadamente, uma senha incorreta.
        for data in [{"reason": "curto", "password": "director-password"}, {"reason": "Motivo excepcional longo e documentado", "password": "incorrect"}]:
            # Envia cada combinação inválida à ação de consulta de identidade.
            response = self.client.post(self.reveal_url(), data)
            # Exige HTTP 400, indicando que a confirmação solicitada contém dados inválidos.
            self.assertEqual(response.status_code, 400)
            # Confirma que nem a página de erro contém o e-mail sigiloso do aluno.
            self.assertNotContains(response, self.student.email, status_code=400)
        # Exige ausência de registros de acesso autorizado após as tentativas inválidas.
        self.assertFalse(IdentityAccessAudit.objects.exists())

    # Verifica a auditoria da consulta válida e a ausência de identidade persistida na sessão do diretor.
    def test_reveal_is_audited_and_does_not_persist_in_session(self):
        # Autentica a conta da direção antes da confirmação sensível.
        self.client.force_login(self.director)
        # Define uma justificativa fictícia suficientemente longa para a consulta excepcional.
        reason = "Situação excepcional para investigação institucional documentada."
        # Solicita a identidade usando a senha correta da conta autenticada e a justificativa informada.
        response = self.client.post(self.reveal_url(), {"reason": reason, "password": "director-password"})
        # Confirma que a consulta válida foi atendida com HTTP 200.
        self.assertEqual(response.status_code, 200)
        # Confirma que a resposta desta consulta contém o e-mail anteriormente protegido.
        self.assertContains(response, self.student.email)
        # Lê o único registro de auditoria criado pela consulta válida.
        audit = IdentityAccessAudit.objects.get()
        # Exige que a auditoria identifique exatamente o diretor responsável pela consulta.
        self.assertEqual(audit.actor, self.director)
        # Exige que o acesso auditado esteja associado à manifestação correta.
        self.assertEqual(audit.complaint, self.case)
        # Confirma que a justificativa registrada é a mesma enviada na solicitação.
        self.assertEqual(audit.reason, reason)
        # Exige no-store no cabeçalho para orientar que a resposta sensível não seja armazenada em cache.
        self.assertIn("no-store", response["Cache-Control"])
        # Confirma que o e-mail revelado não foi gravado na sessão persistente do navegador.
        self.assertNotIn(self.student.email, str(dict(self.client.session)))
        # Abre o detalhe outra vez e confirma que a revelação não é reaproveitada em um GET posterior.
        self.assertNotContains(self.client.get(self.staff_detail_url()), self.student.email)

    # Verifica que uma conta sem senha utilizável não consegue confirmar a ação sensível por um valor especial.
    def test_director_with_unusable_password_cannot_bypass_confirmation(self):
        # Marca a senha do diretor como inutilizável, como ocorre em contas sem credencial local.
        self.director.set_unusable_password()
        # Persiste a alteração do hash de senha para a checagem feita pelo formulário.
        self.director.save(update_fields=["password"])
        # Autentica a conta diretamente, sem criar uma senha utilizável durante o teste.
        self.client.force_login(self.director)
        # Tenta usar o caractere de marcação de senha inutilizável como se fosse uma credencial real.
        response = self.client.post(self.reveal_url(), {"reason": "Motivo excepcional longo e documentado", "password": "!"})
        # Exige HTTP 400 porque a confirmação de senha deve falhar.
        self.assertEqual(response.status_code, 400)
        # Confirma que a tentativa não produziu qualquer consulta auditada de identidade.
        self.assertFalse(IdentityAccessAudit.objects.exists())

    # Verifica o bloqueio temporário depois de várias confirmações de senha malsucedidas pela direção.
    def test_failed_identity_confirmations_are_rate_limited(self):
        # Autentica a conta que fará todas as tentativas de confirmação deste cenário.
        self.client.force_login(self.director)
        # Repete cinco tentativas inválidas para atingir o limite de confirmação.
        for _ in range(5):
            # Envia justificativa suficiente, mas senha incorreta, incrementando o contador de falhas.
            self.client.post(self.reveal_url(), {"reason": "Motivo excepcional longo e documentado", "password": "incorrect"})
        # Tenta a senha correta depois de o bloqueio já ter sido ativado.
        response = self.client.post(self.reveal_url(), {"reason": "Motivo excepcional longo e documentado", "password": "director-password"})
        # Exige HTTP 429 enquanto durar o intervalo de bloqueio, mesmo com a senha correta.
        self.assertEqual(response.status_code, 429)
        # Confirma que nenhuma das tentativas conseguiu consultar a identidade.
        self.assertFalse(IdentityAccessAudit.objects.exists())

    # Verifica que responder atualiza a manifestação, o histórico e o acompanhamento do autor.
    def test_reply_reaches_owner_and_updates_status_and_timeline(self):
        # Autentica a equipe autorizada a redigir e publicar uma resposta.
        self.client.force_login(self.staff)
        # Publica uma resposta e solicita que a manifestação passe à situação Respondida.
        response = self.client.post(self.staff_detail_url(), {"body": "Recebemos seu relato e encaminhamos ao setor responsável.", "status": Complaint.Status.ANSWERED})
        # Confirma o redirecionamento de volta ao detalhe administrativo após o envio.
        self.assertRedirects(response, self.staff_detail_url())
        # Recarrega o registro porque o serviço de resposta atualizou outra instância no banco.
        self.case.refresh_from_db()
        # Exige que a nova situação persistida seja Respondida.
        self.assertEqual(self.case.status, Complaint.Status.ANSWERED)
        # Confirma que a resposta identifica a conta da equipe que a publicou.
        self.assertEqual(Reply.objects.get().author, self.staff)
        # Exige dois eventos: o recebimento inicial e a mudança de situação após a resposta.
        self.assertEqual(StatusEvent.objects.filter(complaint=self.case).count(), 2)
        # Troca a sessão para o aluno autor, simulando seu retorno ao acompanhamento.
        self.client.force_login(self.student)
        # Abre o detalhe privado pelo caminho disponível ao aluno.
        response = self.client.get(self.own_detail_url())
        # Confirma que o aluno consegue ler a resposta publicada pela equipe.
        self.assertContains(response, "Recebemos seu relato e encaminhamos ao setor responsável.")
        # Confirma que o contexto do aluno também mostra a nova situação Respondida.
        self.assertEqual(response.context["case"]["status"], Complaint.Status.ANSWERED)

    # Verifica que uma resposta inválida não cria conteúdo nem altera a situação da manifestação.
    def test_invalid_reply_does_not_mutate_case(self):
        # Autentica a equipe para que a falha venha dos dados, não da autorização.
        self.client.force_login(self.staff)
        # Envia texto curto e uma situação inexistente na lista de escolhas permitidas.
        response = self.client.post(self.staff_detail_url(), {"body": "curto", "status": "unsupported"})
        # Confirma a reapresentação da página com erros de formulário, sem redirecionamento de sucesso.
        self.assertEqual(response.status_code, 200)
        # Exige que nenhuma resposta tenha sido criada para os dados inválidos.
        self.assertFalse(Reply.objects.exists())
        # Recarrega a manifestação para inspecionar seu estado efetivamente persistido.
        self.case.refresh_from_db()
        # Confirma que a situação original Recebida não foi alterada pela tentativa inválida.
        self.assertEqual(self.case.status, Complaint.Status.RECEIVED)

    # Verifica que texto enviado por usuário é escapado, impedindo a execução de uma tag script no HTML.
    def test_scripts_in_submissions_are_escaped(self):
        # Insere uma carga fictícia de JavaScript na descrição para testar a renderização defensiva.
        self.case.description = "<script>alert('xss')</script>"
        # Persiste somente a descrição que será exibida pela página administrativa.
        self.case.save(update_fields=["description"])
        # Autentica a equipe que lerá o conteúdo submetido pelo aluno.
        self.client.force_login(self.staff)
        # Abre o detalhe que renderiza a descrição potencialmente maliciosa.
        response = self.client.get(self.staff_detail_url())
        # Exige que a tag de script literal não esteja presente no HTML retornado.
        self.assertNotContains(response, "<script>alert('xss')</script>")
        # Confirma a presença da tag escapada como texto, sem remover silenciosamente o conteúdo informado.
        self.assertContains(response, "&lt;script&gt;")

    # Verifica que respostas e consultas de identidade exigem o token de proteção contra requisições forjadas.
    def test_csrf_protects_replies_and_revelations(self):
        # Cria um cliente com validação CSRF explícita; o cliente padrão de testes não a impõe.
        client = Client(enforce_csrf_checks=True)
        # Autentica o diretor nesse cliente para isolar a proteção CSRF das verificações de login.
        client.force_login(self.director)
        # Exige HTTP 403 para uma resposta enviada sem o token CSRF, apesar da sessão autorizada.
        self.assertEqual(client.post(self.staff_detail_url(), {"body": "Resposta de teste sem CSRF", "status": "answered"}).status_code, 403)
        # Exige HTTP 403 para uma consulta de identidade sem CSRF, mesmo com senha e justificativa válidas.
        self.assertEqual(client.post(self.reveal_url(), {"reason": "Motivo excepcional longo e documentado", "password": "director-password"}).status_code, 403)

    # Verifica a busca por protocolo, o filtro de situação e as métricas administrativas.
    def test_staff_filters_and_metrics(self):
        # Autentica o ouvidor autorizado a consultar o painel operacional.
        self.client.force_login(self.staff)
        # Pesquisa o protocolo conhecido e mantém o filtro na situação Recebida.
        response = self.client.get(reverse("ombudsman:staff_dashboard"), {"status": "received", "q": self.case.protocol})
        # Confirma que a métrica geral conta a manifestação existente.
        self.assertEqual(response.context["metrics"]["total"], 1)
        # Exige que a busca retorne exatamente a manifestação que corresponde ao protocolo.
        self.assertEqual(len(response.context["cases"]), 1)
        # Aplica o filtro Concluída, que não corresponde à situação da manifestação inicial.
        response = self.client.get(reverse("ombudsman:staff_dashboard"), {"status": "closed"})
        # Confirma uma listagem vazia quando nenhuma manifestação atende ao filtro.
        self.assertEqual(response.context["cases"], [])

    # Verifica que o admin genérico do Django não oferece atalhos de acesso aos modelos sensíveis.
    def test_sensitive_models_are_not_in_generic_admin(self):
        # Importa o registro do admin apenas para inspecioná-lo neste cenário de segurança.
        from django.contrib import admin

        # Percorre usuário, manifestação, identidade reservada, resposta, histórico e auditoria.
        for model in [User, Complaint, ComplaintIdentity, Reply, StatusEvent, IdentityAccessAudit]:
            # Exige que cada modelo esteja ausente do registro de telas do admin genérico.
            self.assertNotIn(model, admin.site._registry)

    # Verifica que os dados fictícios não são duplicados e que o comando é bloqueado fora do desenvolvimento.
    def test_demo_is_idempotent_and_disabled_outside_development(self):
        # Habilita o modo de desenvolvimento e injeta uma senha fictícia apenas durante a execução deste bloco.
        with self.settings(DEBUG=True, LOCAL_ACCOUNTS_ENABLED=True), patch.dict("os.environ", {"DEMO_PASSWORD": "demo-only-secure-password"}):
            # Executa seed_demo pela primeira vez e captura sua mensagem em um buffer de texto.
            call_command("seed_demo", stdout=StringIO())
            # Guarda a quantidade de manifestações após a primeira preparação dos dados de demonstração.
            count = Complaint.objects.count()
            # Executa novamente o mesmo comando, com os mesmos dados, para verificar repetibilidade.
            call_command("seed_demo", stdout=StringIO())
            # Confirma que a segunda execução não criou manifestações duplicadas.
            self.assertEqual(Complaint.objects.count(), count)
        # Desabilita DEBUG para simular uma execução fora do modo de desenvolvimento.
        with self.settings(DEBUG=False, LOCAL_ACCOUNTS_ENABLED=True):
            # Declara que a tentativa seguinte precisa lançar o erro de comando esperado.
            with self.assertRaises(CommandError):
                # Tenta popular dados fictícios fora do desenvolvimento e comprova o bloqueio seguro.
                call_command("seed_demo", stdout=StringIO())
