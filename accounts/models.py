# Importa a classe base para o gerenciador que cria e localiza contas.
from django.contrib.auth.base_user import BaseUserManager
# Importa o modelo de usuário padrão, que será adaptado para e-mail institucional.
from django.contrib.auth.models import AbstractUser
# Importa os recursos do ORM para tabelas, campos e transações no banco de dados.
from django.db import models


# Centraliza a busca e a criação de usuários, em vez de espalhar essas regras pelas views.
class UserManager(BaseUserManager):
    # Permite que o gerenciador seja representado nas migrations históricas deste modelo.
    use_in_migrations = True

    # Define como o backend de autenticação localiza a conta a partir do identificador de login.
    def get_by_natural_key(self, email):
        # Busca o e-mail sem diferenciar maiúsculas de minúsculas; ausência ou duplicidade geram as exceções do ORM.
        return self.get(email__iexact=email)

    # Cria uma conta comum; extra_fields permite informar nome e outros campos ao chamar o gerenciador.
    def create_user(self, email, password=None, **extra_fields):
        # Impede a criação de uma conta sem identificador de e-mail.
        if not email:
            # Interrompe a operação e informa ao código chamador qual dado obrigatório está ausente.
            raise ValueError("Informe o e-mail institucional.")
        # Monta a instância do usuário com o e-mail normalizado e os campos adicionais recebidos.
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        # Armazena o hash da senha; se a senha for None, torna o login por senha inutilizável.
        user.set_password(password)
        # Persiste a conta na conexão de banco associada a este gerenciador.
        user.save(using=self._db)
        # Devolve a instância criada ao chamador para uso nas próximas operações.
        return user

    # Implementa a criação de superusuários, usada pelo comando createsuperuser do Django.
    def create_superuser(self, email, password=None, **extra_fields):
        # Define acesso administrativo padrão apenas se o chamador ainda não forneceu esse campo.
        extra_fields.setdefault("is_staff", True)
        # Define o indicador de superusuário sem substituir silenciosamente um valor explícito.
        extra_fields.setdefault("is_superuser", True)
        # Marca como confirmado o e-mail da conta criada por administração confiável do servidor.
        extra_fields.setdefault("email_verified", True)
        # Confere os dois indicadores exigidos para que a conta seja realmente um superusuário.
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            # Recusa uma configuração contraditória de superusuário.
            raise ValueError("Superusuários precisam de is_staff e is_superuser.")
        # Reaproveita a criação normal para normalizar o e-mail, gerar o hash e salvar a conta.
        return self.create_user(email, password, **extra_fields)


# Especializa o usuário do Django, mantendo os recursos de senha, sessão e permissões.
class User(AbstractUser):
    # Agrupa os valores internos dos perfis e os rótulos em português exibidos na interface.
    class Role(models.TextChoices):
        # Representa o aluno, autorizado a criar e acompanhar suas próprias manifestações.
        STUDENT = "student", "Aluno"
        # Representa a equipe que analisa manifestações e envia respostas.
        OMBUDSMAN = "ombudsman", "Ouvidoria"
        # Representa a direção, que também pode solicitar uma consulta auditada de identidade.
        DIRECTOR = "director", "Direção"

    # Remove o campo username herdado; o identificador desta aplicação é o e-mail.
    username = None
    # Cria o campo de e-mail e exige um valor único na tabela de usuários.
    email = models.EmailField("e-mail institucional", unique=True)
    # Armazena o perfil com até 20 caracteres; uma conta nova recebe o perfil de aluno.
    role = models.CharField("perfil", max_length=20, choices=Role.choices, default=Role.STUDENT)
    # Registra a confirmação do e-mail; o cadastro público começa sem confirmação.
    email_verified = models.BooleanField("e-mail confirmado", default=False)

    # Informa aos mecanismos de autenticação do Django que o login usa o campo email.
    USERNAME_FIELD = "email"
    # Não exige campos adicionais no createsuperuser além do identificador e da senha.
    REQUIRED_FIELDS = []
    # Conecta o modelo ao gerenciador personalizado definido acima.
    objects = UserManager()

    # Normaliza o e-mail em qualquer salvamento da conta, não apenas no cadastro público.
    def save(self, *args, **kwargs):
        # Remove espaços nas extremidades e converte o e-mail para letras minúsculas.
        self.email = self.email.strip().lower()
        # Executa a persistência padrão do Django, preservando os argumentos do chamador.
        super().save(*args, **kwargs)

    # Define a representação textual do objeto em logs e ferramentas internas.
    def __str__(self):
        # Usa o e-mail como texto identificador da conta.
        return self.email

    # Permite consultar a verificação abaixo como atributo, sem chamar um método com parênteses.
    @property
    # Calcula se a conta pode entrar na área operacional da ouvidoria.
    def is_ombudsman(self):
        # Exige conta ativa, e-mail confirmado e perfil de ouvidoria ou direção simultaneamente.
        return self.is_active and self.email_verified and self.role in {self.Role.OMBUDSMAN, self.Role.DIRECTOR}

    # Permite consultar a verificação abaixo como atributo, sem chamar um método com parênteses.
    @property
    # Calcula se a conta atende aos requisitos do acesso reservado à direção.
    def is_director(self):
        # Exige conta ativa, e-mail confirmado e perfil explicitamente igual a direção.
        return self.is_active and self.email_verified and self.role == self.Role.DIRECTOR
