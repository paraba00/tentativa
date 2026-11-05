# Importa o acesso às variáveis de ambiente, onde a senha de demonstração é fornecida.
import os

# Importa as configurações carregadas pelo projeto, sem fixar valores de implantação neste módulo.
from django.conf import settings
# Importa as funções de autenticação e abertura de sessão do Django.
from django.contrib.auth import get_user_model
# Importa a estrutura e os erros dos comandos executados por manage.py.
from django.core.management.base import BaseCommand, CommandError
# Importa os recursos do ORM para tabelas, campos e transações no banco de dados.
from django.db import transaction

# Importa os modelos necessários para preparar dados fictícios de demonstração.
from ombudsman.models import Complaint, ComplaintIdentity, Reply, StatusEvent


# Cria o comando manage.py seed_demo, destinado exclusivamente à apresentação local com dados fictícios.
class Command(BaseCommand):
    # Define a explicação exibida por manage.py help seed_demo.
    help = "Cria dados fictícios apenas em desenvolvimento. Exige DEMO_PASSWORD no ambiente."

    # Executa toda a preparação em uma transação: uma falha impede uma demonstração gravada pela metade.
    @transaction.atomic
    # Implementa a rotina executada quando o comando é chamado no terminal.
    def handle(self, *args, **options):
        # Exige modo de desenvolvimento e contas locais habilitadas, evitando criar acessos de demonstração em produção.
        if not settings.DEBUG or not getattr(settings, "LOCAL_ACCOUNTS_ENABLED", settings.DEBUG):
            # Interrompe o comando com um erro legível se o ambiente não permite demonstração.
            raise CommandError("Dados de demonstração são permitidos somente com DEBUG e LOCAL_ACCOUNTS_ENABLED.")
        # Lê a senha de uma variável de ambiente; nenhum valor de senha fica fixo neste arquivo.
        password = os.environ.get("DEMO_PASSWORD", "")
        # Confere o tamanho mínimo exigido para a senha das novas contas fictícias.
        if len(password) < 12:
            # Orienta a fornecer uma senha adequada e encerra antes de gravar dados.
            raise CommandError("Defina DEMO_PASSWORD com pelo menos 12 caracteres antes de executar este comando.")
        # Obtém o modelo de usuário ativo nas configurações do projeto.
        User = get_user_model()
        # Prepara um dicionário para reutilizar as contas criadas nos exemplos de manifestações.
        users = {}
        # Percorre três contas de apresentação; cada tupla fornece chave interna, e-mail, nome e perfil.
        for key, email, name, role in [
            # Define a conta fictícia que será autora das manifestações de exemplo.
            ("student", "aluno.demo@camporeal.edu.br", "Marina Demo", User.Role.STUDENT),
            # Define a conta fictícia que demonstrará as respostas da ouvidoria.
            ("ombudsman", "ouvidoria.demo@camporeal.edu.br", "Equipe Demo", User.Role.OMBUDSMAN),
            # Define a conta fictícia para demonstrar a consulta auditada exclusiva da direção.
            ("director", "direcao.demo@camporeal.edu.br", "Direção Demo", User.Role.DIRECTOR),
        ]:
            # Reaproveita a conta existente ou cria uma conta demonstrativa já confirmada; não altera os campos de uma conta existente.
            user, created = User.objects.get_or_create(email=email, defaults={"first_name": name, "role": role, "email_verified": True})
            # Só define a senha quando a conta foi criada nesta execução.
            if created:
                # Transforma a senha fornecida em hash antes de gravá-la.
                user.set_password(password)
                # Persiste somente o hash da senha, sem modificar outros campos.
                user.save(update_fields=["password"])
            # Guarda a conta sob sua chave para associá-la aos dados de exemplo seguintes.
            users[key] = user
        # Declara os quatro relatos fictícios, cada um com assunto, tipo, setor, identificação, situação e texto.
        samples = [
            # Prepara uma sugestão sigilosa de infraestrutura em análise.
            ("Melhoria na iluminação do estacionamento", Complaint.Category.SUGGESTION, Complaint.Sector.INFRASTRUCTURE, Complaint.Visibility.CONFIDENTIAL, Complaint.Status.IN_REVIEW, "Gostaria de sugerir uma revisão na iluminação do estacionamento próximo ao bloco principal. À noite, alguns trechos ficam pouco iluminados."),
            # Prepara um elogio identificado do setor administrativo já respondido.
            ("Atendimento da secretaria acadêmica", Complaint.Category.PRAISE, Complaint.Sector.ADMINISTRATIVE, Complaint.Visibility.IDENTIFIED, Complaint.Status.ANSWERED, "Quero registrar meu agradecimento pelo atendimento acolhedor da secretaria durante o processo de renovação de matrícula."),
            # Prepara uma solicitação sigilosa acadêmica recém-recebida.
            ("Acesso aos laboratórios no intervalo", Complaint.Category.REQUEST, Complaint.Sector.ACADEMIC, Complaint.Visibility.CONFIDENTIAL, Complaint.Status.RECEIVED, "Gostaria de saber se os laboratórios de informática podem ficar disponíveis para os alunos estudarem durante o intervalo das aulas."),
            # Prepara uma solicitação identificada financeira com atendimento concluído.
            ("Informações sobre o calendário de bolsas", Complaint.Category.REQUEST, Complaint.Sector.FINANCIAL, Complaint.Visibility.IDENTIFIED, Complaint.Status.CLOSED, "Solicito mais informações sobre as datas de inscrição e renovação das bolsas de estudo para o próximo semestre."),
        ]
        # Desempacota os seis dados de cada exemplo para criar os registros relacionados.
        for title, category, sector, visibility, status, description in samples:
            # Verifica se o aluno de demonstração já possui esse relato para tornar a execução repetível sem duplicatas.
            if Complaint.objects.filter(title=title, identity__user=users["student"]).exists():
                # Pula o exemplo já existente e prossegue para o próximo da lista.
                continue
            # Grava o relato fictício e deixa o modelo gerar seu protocolo automaticamente.
            case = Complaint.objects.create(title=title, category=category, sector=sector, visibility=visibility, status=status, description=description)
            # Associa o relato ao aluno de demonstração na tabela de identidade reservada.
            ComplaintIdentity.objects.create(complaint=case, user=users["student"])
            # Insere o recebimento inicial na linha do tempo do exemplo.
            StatusEvent.objects.create(complaint=case, status=Complaint.Status.RECEIVED, note="Manifestação recebida pela ouvidoria.")
            # Verifica se o exemplo precisa de uma segunda etapa para representar sua situação atual.
            if status != Complaint.Status.RECEIVED:
                # Registra no histórico a etapa adicional já apresentada pelo relato fictício.
                StatusEvent.objects.create(complaint=case, status=status, note="Situação atualizada pela ouvidoria.")
            # Cria uma resposta de exemplo somente para os casos apresentados como respondidos ou concluídos.
            if status in {Complaint.Status.ANSWERED, Complaint.Status.CLOSED}:
                # Associa uma resposta fictícia à conta da equipe, permitindo demonstrar sua leitura pelo aluno.
                Reply.objects.create(complaint=case, author=users["ombudsman"], body="Agradecemos por compartilhar sua manifestação. A equipe responsável recebeu seu relato e os esclarecimentos estão disponíveis na secretaria. Conte com a ouvidoria sempre que precisar.")
        # Informa o término e os identificadores das contas, sem imprimir a senha de demonstração.
        self.stdout.write(self.style.SUCCESS("Demonstração preparada (dados fictícios). Contas: aluno.demo, ouvidoria.demo e direcao.demo @camporeal.edu.br. Senhas existentes foram preservadas."))
