# Acessa configurações Django já carregadas, sem passar credenciais aos templates.
from django.conf import settings


# Acrescenta flags de apresentação ao contexto de todas as páginas renderizadas.
def environment(request):
    # O template recebe somente este dicionário de indicadores públicos, não os segredos do ambiente.
    return {
        # Permite avisar quando o site está em desenvolvimento.
        "development_mode": settings.DEBUG,
        # Controla a exibição do formulário local; a autorização efetiva também é checada na view.
        "local_accounts_enabled": settings.LOCAL_ACCOUNTS_ENABLED,
        # Habilita o botão Google quando as credenciais foram configuradas, sem revelar seus valores.
        "google_enabled": settings.GOOGLE_ENABLED,
        # Só habilita as logos quando os dois arquivos originais existem, evitando imagens quebradas.
        "brand_logos_available": all(
            # Verifica se o caminho esperado aponta para um arquivo, sem inventar uma marca substituta.
            (settings.BASE_DIR / "static" / "img" / name).is_file()
            # Exige as versões azul e branca para cabeçalho e fundos escuros.
            for name in ("camporeal-azul.png", "camporeal-branca.png")
        ),
    }
