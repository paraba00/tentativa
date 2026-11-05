"""Atribui perfis institucionais apenas pela administração confiável do servidor."""

# Lê senhas no terminal sem exibir os caracteres digitados.
import getpass
# Lê a senha de confirmação de uma variável de ambiente em automações autorizadas.
import os
# Permite verificar se a entrada é um terminal interativo antes de solicitar a senha.
import sys

# Seleciona nosso usuário institucional conforme AUTH_USER_MODEL.
from django.contrib.auth import get_user_model
# Aplica as regras de força de senha configuradas no Django.
from django.contrib.auth.password_validation import validate_password
# Identifica falhas de qualidade da senha para devolvê-las como erro do comando.
from django.core.exceptions import ValidationError
# Fornece a estrutura oficial de comando Django e falhas com saída não bem-sucedida.
from django.core.management.base import BaseCommand, CommandError


# Registra o comando manage.py set_role; não cria uma rota pública para promoção de perfil.
class Command(BaseCommand):
    # Descrição exibida por manage.py help set_role.
    help = "Atribui perfil a uma conta institucional existente e confirmada."

    # Define os parâmetros aceitos, sem permitir senha diretamente na linha de comando.
    def add_arguments(self, parser):
        # Recebe o e-mail da conta já criada pelo acesso institucional.
        parser.add_argument("email", help="E-mail da conta que já acessou o site.")
        # Exige um dos três perfis conhecidos; valores arbitrários são rejeitados pelo parser.
        parser.add_argument("--role", required=True, choices=["student", "ombudsman", "director"])
        # Adiciona a opção de criar ou renovar a senha exclusiva de confirmação da direção.
        parser.add_argument(
            # Nome da opção que habilita o procedimento de definição de senha.
            "--set-confirmation-password",
            # Transforma a presença da opção em um booleano, sem receber o segredo como argumento.
            action="store_true",
            # Explica os canais de entrada que evitam expor a senha nos argumentos do processo.
            help="Define senha de confirmação da direção via prompt ou DIRECTOR_CONFIRMATION_PASSWORD.",
        )

    # Executa a operação administrativa após o Django interpretar os argumentos.
    def handle(self, *args, **options):
        # Normaliza o identificador para procurar a conta de forma consistente.
        email = options["email"].strip().lower()
        # Restringe a atribuição de perfil ao domínio institucional exato.
        if email.count("@") != 1 or email.split("@", 1)[1] != "camporeal.edu.br":
            # Encerra sem alterar o banco quando o endereço pertence a outro domínio.
            raise CommandError("O perfil exige e-mail institucional @camporeal.edu.br.")
        # Inicia uma operação que pode falhar e será traduzida em mensagem adequada ao administrador.
        try:
            # Busca uma única conta existente sem diferenciar maiúsculas no e-mail.
            user = get_user_model().objects.get(email__iexact=email)
        # Captura especificamente a ausência da conta, sem esconder outros erros do banco.
        except get_user_model().DoesNotExist as exc:
            # Evita criar uma identidade privilegiada sem primeiro haver acesso institucional.
            raise CommandError("Conta não encontrada. Faça primeiro o acesso pelo Google institucional.") from exc
        # Exige conta ativa e confirmação já estabelecida antes de conceder qualquer perfil.
        if not user.is_active or not user.email_verified:
            # Não promove contas bloqueadas ou ainda não confirmadas.
            raise CommandError("A conta precisa estar ativa e ter e-mail confirmado.")
        # Lista somente os campos que serão persistidos ao final, preservando os demais dados.
        fields = ["role"]
        # Executa a configuração de senha apenas quando solicitada expressamente.
        if options["set_confirmation_password"]:
            # A senha de confirmação sensível pertence ao fluxo da direção.
            if options["role"] != "director":
                # Recusa combinar a configuração sensível com um perfil inadequado.
                raise CommandError("A senha de confirmação é exclusiva do perfil director.")
            # Lê o segredo opcional sem imprimi-lo nem aceitá-lo no histórico de argumentos.
            password = os.environ.get("DIRECTOR_CONFIRMATION_PASSWORD")
            # Quando a automação não forneceu senha, tenta o modo de entrada interativo.
            if not password:
                # Impede ficar aguardando uma senha invisível em execução sem terminal.
                if not sys.stdin.isatty():
                    # Orienta a automação a fornecer a variável por canal seguro.
                    raise CommandError("Defina DIRECTOR_CONFIRMATION_PASSWORD para uso não interativo.")
                # Solicita o segredo sem eco de caracteres no terminal.
                password = getpass.getpass("Senha de confirmação da direção: ")
                # Pede repetição para detectar erro de digitação antes de armazenar o hash.
                if password != getpass.getpass("Repita a senha: "):
                    # Cancela a operação quando a confirmação não coincide.
                    raise CommandError("As senhas não conferem.")
            # Inicia uma operação que pode falhar e será traduzida em mensagem adequada ao administrador.
            try:
                # Confere comprimento, senhas comuns e semelhança com dados do próprio usuário.
                validate_password(password, user=user)
            # Captura rejeições das regras de qualidade de senha.
            except ValidationError as exc:
                # Mostra apenas os motivos de rejeição, nunca o valor da senha.
                raise CommandError(" ".join(exc.messages)) from exc
            # Calcula um hash pelo algoritmo Django; a senha legível não é salva no banco.
            user.set_password(password)
            # Inclui o campo de hash na atualização persistida.
            fields.append("password")
        # Não habilita a direção sem uma senha que permita confirmar consultas de identidade.
        if options["role"] == "director" and not user.has_usable_password():
            # Exige preparar a confirmação antes de gravar o perfil diretor.
            raise CommandError("Use --set-confirmation-password para habilitar a consulta auditada da direção.")
        # Aplica o perfil escolhido apenas depois de validar todos os pré-requisitos.
        user.role = options["role"]
        # Persiste a alteração de perfil e, se solicitada, a nova senha em hash.
        user.save(update_fields=fields)
        # Confirma o resultado pelo nome legível do perfil, sem exibir segredos.
        self.stdout.write(self.style.SUCCESS(f"Perfil atualizado para {user.get_role_display()}."))
