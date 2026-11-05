# Importa a API de formulários, responsável por validar os dados recebidos do navegador.
from django import forms

# Importa os modelos de dados desta aplicação, para validação e consultas no banco.
from .models import Complaint


# Cria e valida manifestações usando os campos públicos do modelo Complaint.
class ComplaintForm(forms.ModelForm):
    # Acrescenta um aceite obrigatório do aviso; este campo de formulário não é um cargo nem uma autorização para revelar identidade.
    privacy_ack = forms.BooleanField(
        # Define o texto exibido ao lado da caixa de aceite.
        label="Li e compreendi como minha identidade será tratada.",
        # Explica o alcance real do sigilo antes do envio, evitando prometer anonimato absoluto.
        help_text="No envio sigiloso, sua identidade fica oculta da equipe de ouvidoria. Somente a direção poderá consultá-la em situações excepcionais, com justificativa e registro de auditoria. Não há anonimato absoluto.",
        # Mostra uma mensagem específica quando o aluno tenta enviar sem marcar o aceite obrigatório.
        error_messages={"required": "Confirme que compreendeu as condições de privacidade."},
    )

    # Define o modelo, os campos editáveis e os componentes HTML deste formulário.
    class Meta:
        # Informa que form.save criará uma manifestação no banco.
        model = Complaint
        # Expõe somente tipo, setor, assunto, texto e identificação; protocolo, situação e identidade do autor ficam sob controle do servidor.
        fields = ("category", "sector", "title", "description", "visibility")
        # Personaliza como os campos serão desenhados no HTML, sem substituir suas validações.
        widgets = {
            # Usa uma entrada curta com uma orientação inicial para o assunto.
            "title": forms.TextInput(attrs={"placeholder": "Resuma o que você quer compartilhar"}),
            # Oferece uma área de sete linhas e orienta a evitar dados pessoais desnecessários.
            "description": forms.Textarea(attrs={"rows": 7, "placeholder": "Conte o que aconteceu, onde e quando. Não inclua dados de outras pessoas sem necessidade."}),
            # Mostra as opções de identificação como botões de escolha única.
            "visibility": forms.RadioSelect,
        }

    # Valida o assunto além dos limites definidos no modelo.
    def clean_title(self):
        # Retira espaços nas extremidades antes de medir o assunto.
        title = self.cleaned_data["title"].strip()
        # Exige um mínimo de cinco caracteres úteis no assunto.
        if len(title) < 5:
            # Associa um erro ao campo de assunto quando o texto é curto demais.
            raise forms.ValidationError("Escreva um assunto com pelo menos 5 caracteres.")
        # Devolve o assunto normalizado para os dados finais do formulário.
        return title

    # Valida um conteúdo mínimo que ajude a equipe a compreender o relato.
    def clean_description(self):
        # Remove espaços no início e no fim da descrição antes de validá-la.
        description = self.cleaned_data["description"].strip()
        # Exige pelo menos vinte caracteres na descrição.
        if len(description) < 20:
            # Explica por que a descrição ainda não pode ser enviada.
            raise forms.ValidationError("Descreva sua manifestação com pelo menos 20 caracteres.")
        # Devolve o texto validado que será persistido no relato.
        return description


# Valida o número de protocolo usado para procurar uma manifestação da própria conta.
class TrackForm(forms.Form):
    # Recebe até 30 caracteres e mostra o formato do protocolo; a autorização será verificada na view.
    protocol = forms.CharField(label="Número de protocolo", max_length=30, widget=forms.TextInput(attrs={"placeholder": "CR-2026-XXXXXXXXXXXX", "autocomplete": "off"}))

    # Uniformiza a escrita do protocolo para evitar falhas por caixa ou espaços extras.
    def clean_protocol(self):
        # Retira espaços das pontas e converte o protocolo para letras maiúsculas.
        return self.cleaned_data["protocol"].strip().upper()


# Valida a resposta administrativa e a situação escolhida para o relato.
class ReplyForm(forms.Form):
    # Exige uma resposta entre 10 e 10 mil caracteres e apresenta uma área de texto de cinco linhas.
    body = forms.CharField(label="Resposta ao aluno", min_length=10, max_length=10000, widget=forms.Textarea(attrs={"rows": 5, "placeholder": "Escreva uma resposta clara e acolhedora."}))
    # Aceita somente situações conhecidas e sugere Respondida no preenchimento inicial.
    status = forms.ChoiceField(label="Atualizar situação", choices=Complaint.Status.choices, initial=Complaint.Status.ANSWERED)


# Valida os dados exigidos antes de uma consulta excepcional de identidade pela direção.
class RevealIdentityForm(forms.Form):
    # Exige uma justificativa entre 20 e 2 mil caracteres, que será registrada na auditoria.
    reason = forms.CharField(label="Justificativa da consulta", min_length=20, max_length=2000, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Descreva a situação excepcional que justifica esta consulta."}))
    # Solicita senha em campo mascarado; strip=False preserva espaços que façam parte da senha real.
    password = forms.CharField(label="Confirme sua senha de direção", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}), strip=False)

    # Recebe a conta da sessão pelo servidor para conferir a senha, sem aceitar essa identidade do navegador.
    def __init__(self, *args, user=None, **kwargs):
        # Guarda a conta que deve confirmar a autorização para esta consulta.
        self.user = user
        # Inicializa os campos e os dados do formulário pelo comportamento padrão do Django.
        super().__init__(*args, **kwargs)

    # Confere simultaneamente perfil, existência de senha utilizável e correspondência do hash.
    def clean_password(self):
        # Lê a senha enviada sem registrá-la em log ou salvá-la em texto puro.
        password = self.cleaned_data["password"]
        # Recusa a operação se faltar usuário, perfil de direção, senha local habilitada ou senha correta.
        if not self.user or not self.user.is_director or not self.user.has_usable_password() or not self.user.check_password(password):
            # Informa a falha de confirmação sem revelar qual parte da verificação não foi satisfeita.
            raise forms.ValidationError("Não foi possível confirmar sua senha de direção.")
        # Retorna a senha validada apenas para o processamento deste formulário; ela não compõe a auditoria.
        return password
