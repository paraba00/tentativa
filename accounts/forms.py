# Importa a API de formulários, responsável por validar os dados recebidos do navegador.
from django import forms
# Importa os formulários de cadastro e autenticação, reaproveitando a validação de senhas do Django.
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

# Importa os modelos de dados desta aplicação, para validação e consultas no banco.
from .models import User


# Centraliza o domínio aceito no cadastro local institucional.
INSTITUTIONAL_DOMAIN = "camporeal.edu.br"


# Reaproveita a criação de usuários e a conferência de senhas do Django.
class RegistrationForm(UserCreationForm):
    # Solicita o nome do aluno, com limite compatível com o campo do usuário.
    first_name = forms.CharField(label="Nome", max_length=150)
    # Solicita o sobrenome, também limitado a 150 caracteres.
    last_name = forms.CharField(label="Sobrenome", max_length=150)
    # Valida o formato do e-mail e usa um campo HTML de e-mail com exemplo e preenchimento automático apropriado.
    email = forms.EmailField(label="E-mail institucional", widget=forms.EmailInput(attrs={"placeholder": "voce@camporeal.edu.br", "autocomplete": "email"}))

    # Relaciona o formulário ao modelo e declara os campos expostos ao navegador.
    class Meta:
        # Indica que o cadastro produzirá uma instância do usuário institucional.
        model = User
        # Limita a edição pública a nome, sobrenome, e-mail e confirmação da senha; não expõe perfil ou privilégios.
        fields = ("first_name", "last_name", "email", "password1", "password2")

    # Acrescenta a validação institucional à validação básica do campo de e-mail.
    def clean_email(self):
        # Normaliza o e-mail já validado pelo tipo EmailField.
        email = self.cleaned_data["email"].strip().lower()
        # Compara o domínio inteiro para rejeitar domínios parecidos e subdomínios não autorizados.
        if email.rsplit("@", 1)[-1] != INSTITUTIONAL_DOMAIN:
            # Associa ao campo uma mensagem legível quando o domínio não é institucional.
            raise forms.ValidationError("Use seu e-mail institucional @camporeal.edu.br.")
        # Verifica se uma conta com esse e-mail já existe, ignorando diferenças de caixa.
        if User.objects.filter(email__iexact=email).exists():
            # Impede um cadastro duplicado e orienta o usuário a entrar na conta existente.
            raise forms.ValidationError("Este e-mail já está cadastrado. Acesse sua conta.")
        # Devolve o valor normalizado para substituir o valor do campo em cleaned_data.
        return email

    # Monta uma conta segura; commit controla se a instância será salva imediatamente.
    def save(self, commit=True):
        # Deixa a classe base preparar o usuário e o hash da senha, ainda sem gravar no banco.
        user = super().save(commit=False)
        # O formulário público ignora cargos e privilégios que alguém tente forjar no POST.
        # Força o perfil de aluno, mesmo se uma requisição adulterada enviar um cargo superior.
        user.role = User.Role.STUDENT
        # Exige confirmação da caixa postal antes de permitir o envio de manifestações.
        user.email_verified = False
        # Impede que o cadastro público conceda acesso administrativo.
        user.is_staff = False
        # Impede que o cadastro público conceda permissões globais de superusuário.
        user.is_superuser = False
        # Respeita o comportamento padrão dos ModelForms para persistência opcional.
        if commit:
            # Salva a conta já preparada com os indicadores de segurança corretos.
            user.save()
        # Entrega ao chamador o usuário preparado ou persistido.
        return user


# Adapta a autenticação local para mostrar o e-mail no lugar do campo username.
class EmailAuthenticationForm(AuthenticationForm):
    # Cria o campo visível de login; autocomplete=username auxilia os gerenciadores de senhas.
    email = forms.EmailField(label="E-mail institucional", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "username", "placeholder": "voce@camporeal.edu.br"}))

    # Ajusta os dados de entrada antes de inicializar o formulário padrão de autenticação.
    def __init__(self, request=None, *args, **kwargs):
        # O AuthenticationForm usa o nome username internamente, embora a interface use e-mail.
        # Obtém os dados enviados ao formulário, quando há uma tentativa de login.
        data = kwargs.get("data")
        # Só prepara os dados quando o formulário está vinculado a uma requisição enviada.
        if data is not None:
            # Copia os dados porque o QueryDict original da requisição pode ser imutável.
            data = data.copy()
            # Fornece ao mecanismo herdado o identificador esperado, usando o e-mail normalizado.
            data["username"] = data.get("email", "").strip().lower()
            # Substitui apenas os dados deste formulário pela cópia ajustada.
            kwargs["data"] = data
        # Inicializa os campos e metadados padrão de autenticação antes de remover username.
        super().__init__(request, *args, **kwargs)
        # Retira o campo legado da interface; o aluno verá apenas e-mail e senha.
        self.fields.pop("username", None)

    # Valida o par e-mail/senha e guarda a conta autenticada para a view de login.
    def clean(self):
        # Importa as funções de autenticação e abertura de sessão do Django.
        from django.contrib.auth import authenticate

        # Lê o e-mail após a validação individual do campo.
        email = self.cleaned_data.get("email")
        # Lê a senha recebida; seu valor não é gravado em logs nem no banco em texto puro.
        password = self.cleaned_data.get("password")
        # Só consulta a autenticação se os dois dados mínimos estiverem disponíveis.
        if email is not None and password:
            # Consulta os backends configurados; o Django compara a senha com o hash armazenado.
            self.user_cache = authenticate(self.request, username=email.lower(), password=password)
            # Detecta que nenhum backend reconheceu credenciais válidas.
            if self.user_cache is None:
                # Devolve o erro genérico de login, sem afirmar se a conta existe.
                raise self.get_invalid_login_error()
            # Aplica as regras do formulário padrão, como impedir entrada de uma conta inativa.
            self.confirm_login_allowed(self.user_cache)
        # Devolve os dados finais para concluir a validação do formulário.
        return self.cleaned_data
