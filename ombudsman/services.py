# Serviços concentram gravações relacionadas e a preparação de dados seguros para as páginas.
# A identidade do aluno é guardada separadamente e não faz parte da projeção operacional do relato.

# Fornece atomic, que confirma ou desfaz conjuntamente as operações de uma transação.
from django.db import transaction

# Importa relato, autoria reservada, auditoria, respostas e eventos de situação.
from .models import Complaint, ComplaintIdentity, IdentityAccessAudit, Reply, StatusEvent


# Se uma das três gravações falhar, desfaz todas para não deixar relato sem autor ou sem histórico.
@transaction.atomic
# Exige argumentos nomeados; user vem da sessão e form já foi validado pela view.
def create_complaint(*, user, form):
    # Persiste os campos permitidos do formulário; protocolo e situação inicial são definidos pelo modelo.
    case = form.save()
    # Registra a autoria em outra tabela, sem acrescentar dados pessoais ao relato operacional.
    ComplaintIdentity.objects.create(complaint=case, user=user)
    # Cria o primeiro ponto da linha do tempo para o aluno acompanhar o recebimento.
    StatusEvent.objects.create(complaint=case, status=case.status, note="Manifestação recebida pela ouvidoria.")
    # Entrega a manifestação gravada para a view informar o protocolo e redirecionar o aluno.
    return case


# Mantém resposta, eventual evento e mudança de situação na mesma transação de banco.
@transaction.atomic
# Recebe explicitamente o relato, a conta responsável, o texto validado e a nova situação.
def respond(*, case, user, body, status):
    # Bloqueia a linha durante esta transação para serializar respostas concorrentes e manter o histórico coerente.
    case = Complaint.objects.select_for_update().get(pk=case.pk)
    # Persiste o texto e vincula a resposta à manifestação e à conta que a publicou.
    Reply.objects.create(complaint=case, author=user, body=body)
    # Um novo evento de situação só é necessário quando o código realmente muda.
    if case.status != status:
        # Registra a etapa ocorrida sem copiar os dados pessoais do autor da manifestação.
        StatusEvent.objects.create(complaint=case, status=status, note="Situação atualizada pela ouvidoria.")
    # Atualiza a situação operacional na instância bloqueada pela transação.
    case.status = status
    # Grava a situação e inclui updated_at para atualizar também o momento da última alteração.
    case.save(update_fields=["status", "updated_at"])


# Auditoria e leitura são tratadas como uma unidade; qualquer falha desfaz a operação.
@transaction.atomic
# A view já confirmou senha e justificativa; o serviço repete a exigência de perfil e modalidade.
def reveal_identity(*, case, director, reason):
    # Reconfere a conta ativa, verificada e com perfil de direção mesmo fora do caminho normal da view.
    if not director.is_director:
        # Interrompe a chamada antes da consulta à tabela reservada de autoria.
        raise PermissionError("Somente a direção pode consultar a identidade.")
    # A consulta excepcional se destina somente aos envios escolhidos como sigilosos.
    if case.visibility != Complaint.Visibility.CONFIDENTIAL:
        # Sinaliza uso indevido do serviço para um relato cujo contato já pode ser mostrado normalmente.
        raise ValueError("Esta manifestação já é identificada.")
    # A inserção da auditoria precisa ser bem-sucedida antes que qualquer dado pessoal seja retornado.
    IdentityAccessAudit.objects.create(complaint=case, actor=director, reason=reason)
    # Carrega o vínculo reservado e o usuário na mesma consulta ao banco.
    user = ComplaintIdentity.objects.select_related("user").get(complaint=case).user
    # Retorna só os dados necessários à consulta, sem entregar o objeto de usuário inteiro ao template.
    return {
        # Usa o nome completo ou um rótulo genérico caso o cadastro esteja sem nome.
        "name": user.get_full_name() or "Aluno",
        # Fornece o e-mail do autor apenas após a autorização e a inserção da auditoria.
        "email": user.email,
    }


# Define explicitamente quais atributos operacionais podem chegar aos templates.
def case_payload(case):
    """Produz uma projeção segura do relato, sem incluir o objeto de identidade reservada."""
    # Um dicionário limitado impede que o template percorra relações sensíveis do modelo.
    return {
        # Inclui o identificador interno do relato, que não representa a identidade do autor.
        "id": case.pk,
        # Inclui o código público de referência; as views ainda exigem autorização para abri-lo.
        "protocol": case.protocol,
        # Inclui o assunto curto informado pelo aluno.
        "title": case.title,
        # Inclui o texto do relato; os templates devem renderizá-lo com o escape padrão do Django.
        "description": case.description,
        # Inclui o código da categoria para decisões de apresentação e filtros.
        "category": case.category,
        # Converte o código da categoria em seu rótulo legível em português.
        "category_label": case.get_category_display(),
        # Inclui o código do setor ao qual o relato se refere.
        "sector": case.sector,
        # Disponibiliza o nome legível do setor para a interface.
        "sector_label": case.get_sector_display(),
        # Inclui o código da modalidade de identificação escolhida pelo aluno.
        "visibility": case.visibility,
        # Inclui o rótulo Identificada ou Sigilosa, sem revelar nenhum dado pessoal.
        "visibility_label": case.get_visibility_display(),
        # Inclui o código da situação atual, usado por filtros e componentes de apresentação.
        "status": case.status,
        # Fornece o texto legível da situação para que o template não repita as regras do modelo.
        "status_label": case.get_status_display(),
        # Inclui o instante de recebimento para a listagem e o acompanhamento.
        "created_at": case.created_at,
        # Inclui o instante da última atualização operacional registrada no relato.
        "updated_at": case.updated_at,
        # Facilita a apresentação do aviso de sigilo sem entregar o vínculo de autoria.
        "is_confidential": case.visibility == Complaint.Visibility.CONFIDENTIAL,
    }


# Prepara as respostas e os eventos sem expor objetos de modelo às páginas.
def conversation_payload(case):
    # Percorre as respostas na ordenação definida pelo modelo e limita os atributos apresentados.
    replies = [
        {
            # Contém a mensagem de resposta publicada pela ouvidoria.
            "body": reply.body,
            # Registra o instante de publicação da resposta para o acompanhamento.
            "created_at": reply.created_at,
            # Apresenta um rótulo institucional fixo, sem entregar a conta interna do atendente.
            "author_label": "Ouvidoria Campo Real",
        }
        # A relação reversa replies busca somente as respostas associadas a este relato.
        for reply in case.replies.all()
    ]
    # Converte cada evento da manifestação em uma etapa explícita da linha do tempo.
    timeline = [
        {
            # Mantém o código da situação ocorrida para apresentação consistente.
            "status": event.status,
            # Fornece o rótulo legível da situação registrada naquele evento.
            "status_label": event.get_status_display(),
            # Inclui a observação operacional curta associada à mudança.
            "note": event.note,
            # Informa quando a etapa foi registrada no banco.
            "created_at": event.created_at,
        }
        # A relação reversa events mantém apenas os eventos desta manifestação, na ordem do modelo.
        for event in case.events.all()
    ]
    # Entrega duas listas prontas para os componentes de resposta e linha do tempo.
    return {"replies": replies, "timeline": timeline}


# Resume um queryset já autorizado pela view, seja ele pessoal ou administrativo.
def metrics(queryset):
    # Count faz contagens no banco; Q permite aplicar condições específicas em cada contagem.
    from django.db.models import Count, Q

    # Executa as quatro contagens em uma única consulta agregada, sem carregar todos os relatos em Python.
    return queryset.aggregate(
        # Conta todos os identificadores presentes na consulta recebida.
        total=Count("pk"),
        # Considera abertas as manifestações recebidas ou que ainda estão em análise.
        open=Count("pk", filter=Q(status__in=[Complaint.Status.RECEIVED, Complaint.Status.IN_REVIEW])),
        # Conta somente as manifestações que possuem a situação Respondida neste momento.
        answered=Count("pk", filter=Q(status=Complaint.Status.ANSWERED)),
        # Conta somente as manifestações que já estão na situação Concluída.
        closed=Count("pk", filter=Q(status=Complaint.Status.CLOSED)),
    )
