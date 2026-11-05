# Importa um gerador de números aleatórios adequado para criar protocolos difíceis de prever.
import secrets

# Importa as configurações carregadas pelo projeto, sem fixar valores de implantação neste módulo.
from django.conf import settings
# Importa os recursos do ORM para tabelas, campos e transações no banco de dados.
from django.db import models
# Importa as utilidades de data e hora com o fuso configurado no projeto.
from django.utils import timezone


# Cria um identificador público para a manifestação, sem incorporar o nome ou o e-mail do aluno.
def generate_protocol():
    # Combina prefixo institucional, ano local e 6 bytes aleatórios (12 caracteres hexadecimais); a propriedade ainda será conferida ao consultar.
    return f"CR-{timezone.localdate():%Y}-{secrets.token_hex(6).upper()}"


# Representa os dados operacionais de uma manifestação; a identidade fica em outra tabela.
class Complaint(models.Model):
    # Define os códigos persistidos e os rótulos dos tipos de manifestação.
    class Category(models.TextChoices):
        # Classifica relatos de insatisfação como reclamações.
        COMPLAINT = "complaint", "Reclamação"
        # Classifica avaliações críticas enviadas pelo aluno.
        CRITICISM = "criticism", "Crítica"
        # Classifica propostas de melhoria como sugestões.
        SUGGESTION = "suggestion", "Sugestão"
        # Classifica manifestações de reconhecimento ou agradecimento.
        PRAISE = "praise", "Elogio"
        # Classifica pedidos de informação ou providências.
        REQUEST = "request", "Solicitação"

    # Define os setores aos quais o relato pode estar relacionado.
    class Sector(models.TextChoices):
        # Identifica assuntos de ensino, aulas e atividades acadêmicas.
        ACADEMIC = "academic", "Acadêmico"
        # Identifica assuntos de atendimento e rotinas administrativas.
        ADMINISTRATIVE = "administrative", "Administrativo"
        # Identifica assuntos sobre espaços, equipamentos e instalações.
        INFRASTRUCTURE = "infrastructure", "Infraestrutura"
        # Identifica assuntos financeiros, como bolsas e mensalidades.
        FINANCIAL = "financial", "Financeiro"
        # Oferece uma alternativa quando nenhum setor anterior descreve o assunto.
        OTHER = "other", "Outros"

    # Define como a identidade será apresentada à equipe operacional.
    class Visibility(models.TextChoices):
        # Permite que a ouvidoria veja o nome e o e-mail do autor no detalhe da manifestação.
        IDENTIFIED = "identified", "Identificada"
        # Oculta a identidade da equipe; uma consulta excepcional da direção exige senha, motivo e auditoria.
        CONFIDENTIAL = "confidential", "Sigilosa"

    # Representa as etapas de atendimento usadas na listagem e no histórico.
    class Status(models.TextChoices):
        # Marca o recebimento inicial da manifestação.
        RECEIVED = "received", "Recebida"
        # Marca que a equipe está analisando o relato.
        IN_REVIEW = "in_review", "Em análise"
        # Marca que a equipe disponibilizou uma resposta ao aluno.
        ANSWERED = "answered", "Respondida"
        # Marca o encerramento do atendimento.
        CLOSED = "closed", "Concluída"

    # Armazena um protocolo único de até 30 caracteres; o gerador é chamado a cada novo registro e o formulário não pode editá-lo.
    protocol = models.CharField("protocolo", max_length=30, unique=True, default=generate_protocol, editable=False)
    # Armazena o código do tipo; choices fornece opções válidas aos formulários do Django.
    category = models.CharField("tipo de manifestação", max_length=20, choices=Category.choices)
    # Armazena o código do setor associado à manifestação.
    sector = models.CharField("setor", max_length=20, choices=Sector.choices)
    # Guarda um assunto curto, limitado a 160 caracteres.
    title = models.CharField("assunto", max_length=160)
    # Guarda o texto do relato; o limite de 10 mil caracteres é aplicado na validação do formulário.
    description = models.TextField("sua manifestação", max_length=10000)
    # Registra o modo de identificação, adotando sigilo como opção inicial.
    visibility = models.CharField("identificação", max_length=20, choices=Visibility.choices, default=Visibility.CONFIDENTIAL)
    # Inicia a manifestação como recebida e cria um índice para facilitar consultas por situação.
    status = models.CharField("situação", max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    # Registra qual versão do aviso de privacidade se aplica ao envio.
    privacy_notice_version = models.CharField(max_length=20, default="2026-01")
    # Registra automaticamente a data e hora da criação deste registro.
    created_at = models.DateTimeField(auto_now_add=True)
    # Atualiza automaticamente a data e hora quando o registro é salvo.
    updated_at = models.DateTimeField(auto_now=True)

    # Agrupa opções do modelo que controlam sua apresentação e ordenação padrão.
    class Meta:
        # Ordena primeiro os registros mais recentes; o sinal de menos indica ordem decrescente.
        ordering = ["-created_at"]
        # Define o nome legível singular do modelo.
        verbose_name = "manifestação"
        # Define o nome legível plural do modelo.
        verbose_name_plural = "manifestações"

    # Define uma representação textual que evita exibir identidade ou conteúdo do relato.
    def __str__(self):
        # Usa somente o protocolo para identificar o objeto como texto.
        return self.protocol


# Relaciona cada manifestação ao autor em uma tabela separada dos dados operacionais.
class ComplaintIdentity(models.Model):
    """Identidade separada dos dados operacionais e ausente dos dados enviados à equipe."""

    # Garante uma identidade por manifestação; ao excluir o relato, remove o vínculo, acessível pelo nome reverso identity.
    complaint = models.OneToOneField(Complaint, on_delete=models.CASCADE, related_name="identity")
    # Liga o vínculo ao usuário e impede apagar uma conta ainda referenciada por manifestações.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="complaint_identities")

    # Agrupa opções do modelo que controlam sua apresentação e ordenação padrão.
    class Meta:
        # Nomeia o vínculo de identidade de forma legível nas ferramentas do Django.
        verbose_name = "identidade reservada"


# Armazena uma resposta da equipe enviada para uma manifestação.
class Reply(models.Model):
    # Liga várias respostas a uma manifestação; suas respostas são removidas se o relato for excluído.
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="replies")
    # Registra qual integrante da equipe respondeu e protege essa conta contra exclusão enquanto houver respostas.
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ombudsman_replies")
    # Armazena o conteúdo da resposta, com limite validado pelo formulário.
    body = models.TextField("resposta", max_length=10000)
    # Registra automaticamente a data e hora da criação deste registro.
    created_at = models.DateTimeField(auto_now_add=True)

    # Agrupa opções do modelo que controlam sua apresentação e ordenação padrão.
    class Meta:
        # Exibe eventos do mais antigo ao mais recente e usa a chave primária para desempatar horários iguais.
        ordering = ["created_at", "pk"]


# Mantém um registro histórico de cada situação atribuída à manifestação.
class StatusEvent(models.Model):
    # Relaciona os eventos ao relato, permitindo consultar sua linha do tempo por events.
    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="events")
    # Armazena a situação representada por este evento histórico.
    status = models.CharField(max_length=20, choices=Complaint.Status.choices)
    # Permite uma observação de até 200 caracteres; blank aceita texto vazio na validação.
    note = models.CharField(max_length=200, blank=True)
    # Registra automaticamente a data e hora da criação deste registro.
    created_at = models.DateTimeField(auto_now_add=True)

    # Agrupa opções do modelo que controlam sua apresentação e ordenação padrão.
    class Meta:
        # Exibe eventos do mais antigo ao mais recente e usa a chave primária para desempatar horários iguais.
        ordering = ["created_at", "pk"]


# Registra cada consulta excepcional à identidade sigilosa para permitir sua auditoria posterior.
class IdentityAccessAudit(models.Model):
    # Vincula a consulta ao relato e impede sua exclusão enquanto houver registros de auditoria relacionados.
    complaint = models.ForeignKey(Complaint, on_delete=models.PROTECT, related_name="identity_accesses")
    # Registra quem consultou a identidade e protege a conta contra exclusão que apagaria essa referência.
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="identity_accesses")
    # Guarda a justificativa da direção, limitada a 2 mil caracteres pela validação do formulário.
    reason = models.TextField(max_length=2000)
    # Registra automaticamente a data e hora da criação deste registro.
    created_at = models.DateTimeField(auto_now_add=True)

    # Agrupa opções do modelo que controlam sua apresentação e ordenação padrão.
    class Meta:
        # Ordena primeiro os registros mais recentes; o sinal de menos indica ordem decrescente.
        ordering = ["-created_at"]
        # Nomeia o modelo de auditoria de maneira compreensível.
        verbose_name = "consulta de identidade"
