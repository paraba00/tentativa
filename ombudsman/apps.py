# Importa a classe que identifica e configura uma aplicação instalada no Django.
from django.apps import AppConfig


# Descreve a aplicação ombudsman para que o Django descubra seus modelos e recursos.
class OmbudsmanConfig(AppConfig):
    # Escolhe inteiros grandes como chave primária automática dos modelos que não declaram sua própria chave.
    default_auto_field = "django.db.models.BigAutoField"
    # Indica o caminho Python do pacote ombudsman.
    name = "ombudsman"
    # Define o nome legível da aplicação nas ferramentas do Django.
    verbose_name = "Ouvidoria"
