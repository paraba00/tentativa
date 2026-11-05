"""Protege contas institucionais da navegação no admin genérico do Django.

Os usuários não são registrados aqui: a criação de perfis usa um comando de
administração do servidor. Assim, a equipe operacional não recebe uma tela para
listar contas e tentar correlacioná-las com manifestações sigilosas.
"""
# Este módulo existe por convenção do Django, mas não registra modelos no admin.
