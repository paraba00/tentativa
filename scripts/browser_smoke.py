"""Verificação opcional do fluxo completo da demonstração local (cria um relato).

Requer Playwright, um navegador, dados criados por seed_demo e DEMO_PASSWORD
no ambiente ou no arquivo ignorado .env.demo. Não usar com dados reais de alunos.
"""
# Permite ler configurações do ambiente sem colocar a senha diretamente no código.
import os
# Oferece expressões regulares, usadas para reconhecer URLs com partes variáveis.
import re
# datetime obtém a data e a hora; timezone permite usar o fuso UTC explicitamente.
from datetime import datetime, timezone
# Path representa caminhos de arquivos e pastas de forma adequada ao sistema operacional.
from pathlib import Path

# Lê pares de nome e valor de um arquivo .env, sem exportá-los para o ambiente.
from dotenv import dotenv_values
# sync_playwright controla o navegador; expect verifica resultados com espera automática.
from playwright.sync_api import expect, sync_playwright

# Parte deste arquivo, resolve seu caminho absoluto e sobe duas pastas até a raiz do projeto.
ROOT = Path(__file__).resolve().parent.parent
# Usa a URL informada no ambiente ou a URL local padrão; remove barras finais para montar rotas.
BASE_URL = os.getenv("SMOKE_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
# Prioriza a senha do ambiente e, se ela estiver vazia ou ausente, consulta o arquivo local de demonstração.
PASSWORD = os.getenv("DEMO_PASSWORD") or dotenv_values(ROOT / ".env.demo").get("DEMO_PASSWORD")
# Interrompe a execução se nenhuma das fontes fornecer a senha das contas fictícias.
if not PASSWORD:
    # SystemExit encerra o script com uma mensagem que explica o requisito faltante.
    raise SystemExit("Defina DEMO_PASSWORD para as contas fictícias criadas por seed_demo.")
# Define a pasta que receberá as capturas de tela produzidas por este teste.
ARTIFACTS = ROOT / "artifacts"
# Cria a pasta; exist_ok=True permite reutilizá-la se ela já existir.
ARTIFACTS.mkdir(exist_ok=True)


# Reúne a verificação de largura para reutilizá-la em várias telas e tamanhos de janela.
def assert_fits(page):
    # Executa JavaScript e falha se a largura total do documento superar a área visível da janela.
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), "Conteúdo ultrapassa a tela"


# Recebe uma aba e um e-mail para entrar na conta de demonstração correspondente.
def login(page, email):
    # Abre a página de autenticação no servidor configurado.
    page.goto(BASE_URL + "/conta/entrar/")
    # Localiza o campo pelo atributo HTML name e preenche o e-mail recebido.
    page.locator('[name="email"]').fill(email)
    # Preenche a senha de demonstração lida no início do script.
    page.locator('[name="password"]').fill(PASSWORD)
    # Clica no botão cujo nome acessível é exatamente Entrar, evitando nomes apenas semelhantes.
    page.get_by_role("button", name="Entrar", exact=True).click()
    # Aguarda uma URL terminada em /ouvidoria/ ou /gestao/, os destinos esperados após o login.
    page.wait_for_url(re.compile(r"/(ouvidoria|gestao)/$"))


# Inicializa o Playwright; o bloco with também encerra seus recursos ao terminar.
with sync_playwright() as playwright:
    # Permite selecionar um executável de Chromium instalado em outro caminho.
    executable = os.getenv("CHROMIUM_PATH")
    # Sem caminho configurado, verifica se existe o Chromium disponibilizado pelo sistema.
    if not executable and Path("/usr/bin/chromium").exists():
        # Seleciona esse executável em vez do navegador gerenciado pelo Playwright.
        executable = "/usr/bin/chromium"
    # Inicia o Chromium; None usa o navegador padrão do Playwright. --no-sandbox desativa sua sandbox.
    browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
    # Acumula erros JavaScript não tratados nas abas em que um observador será registrado.
    errors = []
    # Cria uma sessão pública isolada, com área de visualização de 1440 por 1000 pixels.
    public = browser.new_context(viewport={"width": 1440, "height": 1000})
    # Abre uma aba dentro dessa sessão, sem autenticação.
    page = public.new_page()
    # Para cada erro da página, a função lambda adiciona sua representação textual à lista.
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    # Abre a página inicial e espera um intervalo sem atividade de rede antes de continuar.
    page.goto(BASE_URL + "/", wait_until="networkidle")
    # Confere se o título principal, de nível 1, contém o texto esperado da página inicial.
    expect(page.get_by_role("heading", level=1)).to_contain_text("Uma escuta")
    # Verifica se a página inicial cabe horizontalmente na janela de desktop.
    assert_fits(page)
    # Salva uma imagem de toda a página, incluindo conteúdo abaixo da área inicialmente visível.
    page.screenshot(path=str(ARTIFACTS / "home-desktop.png"), full_page=True)
    # Redimensiona a área visível para simular a largura e a altura de um celular.
    page.set_viewport_size({"width": 390, "height": 844})
    # Recarrega a página nesse tamanho e aguarda a rede ficar ociosa.
    page.reload(wait_until="networkidle")
    # Confere se o layout de celular também evita conteúdo mais largo que a janela.
    assert_fits(page)
    # Aciona o botão acessível que abre o menu da navegação móvel.
    page.get_by_role("button", name="Abrir menu").click()
    # Aguarda e verifica se a região de navegação principal ficou visível.
    expect(page.get_by_role("navigation", name="Navegação principal")).to_be_visible()
    # Simula a tecla Escape para testar o fechamento do menu pelo teclado.
    page.keyboard.press("Escape")
    # Confere se o botão passou a informar às tecnologias assistivas que o menu está recolhido.
    expect(page.get_by_role("button", name="Abrir menu")).to_have_attribute("aria-expanded", "false")
    # Registra o resultado visual da página inicial em tamanho de celular.
    page.screenshot(path=str(ARTIFACTS / "home-mobile.png"), full_page=True)

    # Cria outra sessão, com cookies próprios, para testar a conta do aluno sem misturar acessos.
    student_context = browser.new_context(viewport={"width": 1440, "height": 1000})
    # Abre a aba em que serão executadas as ações do aluno fictício.
    student = student_context.new_page()
    # Inclui os erros JavaScript dessa aba na mesma lista usada pela página pública.
    student.on("pageerror", lambda exc: errors.append(str(exc)))
    # Reutiliza a função de login com o e-mail da conta de demonstração do aluno.
    login(student, "aluno.demo@camporeal.edu.br")
    # Salva uma captura da tela que o aluno encontra após entrar.
    student.screenshot(path=str(ARTIFACTS / "aluno-desktop.png"), full_page=True)
    # Abre o formulário com a categoria de sugestão indicada no parâmetro da URL.
    student.goto(BASE_URL + "/ouvidoria/nova/?category=suggestion")
    # Verifica se o formulário realmente pré-selecionou a categoria solicitada pela URL.
    expect(student.locator('[name="category"]')).to_have_value("suggestion")
    # Seleciona a opção de infraestrutura no campo de setor.
    student.locator('[name="sector"]').select_option("infrastructure")
    # Acrescenta a data e a hora UTC ao título, distinguindo execuções realizadas em segundos diferentes.
    title = "Teste no navegador · " + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    # Preenche o título do relato com o texto gerado para esta execução.
    student.locator('[name="title"]').fill(title)
    # Preenche a descrição com um relato explicitamente fictício para o teste de integração.
    student.locator('textarea[name="description"]').fill("Relato fictício de integração para verificar o fluxo da ouvidoria no TCC.")
    # Marca a modalidade confidencial, cujo tratamento da identidade será verificado mais adiante.
    student.locator('[name="visibility"][value="confidential"]').check()
    # Marca a confirmação de ciência sobre o tratamento de privacidade no formulário.
    student.locator('[name="privacy_ack"]').check()
    # Envia o formulário; esta ação cria uma manifestação na base de demonstração.
    student.get_by_role("button", name="Enviar manifestação").click()
    # Aguarda a página do protocolo: CR, quatro dígitos e um identificador hexadecimal em maiúsculas.
    student.wait_for_url(re.compile(r"/ouvidoria/CR-\d{4}-[A-F0-9]+/$"))
    # Remove a barra final e extrai o último trecho da URL para reutilizar o protocolo nas consultas.
    protocol = student.url.rstrip("/").rsplit("/", 1)[-1]
    # Aciona a função da interface que tenta copiar o protocolo.
    student.get_by_role("button", name="Copiar protocolo").click()
    # Confere se a interface apresentou alguma mensagem; não lê diretamente a área de transferência.
    expect(student.locator(".copy-feedback")).not_to_be_empty()
    # Reduz a aba do aluno ao tamanho usado nos testes de celular.
    student.set_viewport_size({"width": 390, "height": 844})
    # Verifica se a página do protocolo cabe na largura reduzida.
    assert_fits(student)
    # Salva uma captura completa do protocolo no layout móvel.
    student.screenshot(path=str(ARTIFACTS / "protocolo-mobile.png"), full_page=True)

    # Separa a sessão da ouvidoria da sessão do aluno, mantendo autenticações independentes.
    staff_context = browser.new_context(viewport={"width": 1440, "height": 1000})
    # Abre a aba que representará o atendente da ouvidoria.
    staff = staff_context.new_page()
    # Autentica a conta fictícia com perfil de ouvidoria.
    login(staff, "ouvidoria.demo@camporeal.edu.br")
    # Registra a tela inicial da gestão para inspeção visual posterior.
    staff.screenshot(path=str(ARTIFACTS / "gestao-desktop.png"), full_page=True)
    # Acessa, na área de gestão, a manifestação criada pelo aluno nesta execução.
    staff.goto(BASE_URL + "/gestao/" + protocol + "/")
    # Falha se o e-mail do aluno aparecer no HTML entregue ao atendente nesta página.
    assert "aluno.demo@camporeal.edu.br" not in staff.content()
    # Faz a mesma verificação para o nome fictício do aluno, cobrindo outro dado identificável.
    assert "Marina Demo" not in staff.content()
    # Guarda o texto esperado para poder enviá-lo e depois verificar sua exibição.
    reply = "Resposta fictícia registrada no teste de integração do navegador."
    # Preenche o corpo da resposta que será publicada pela ouvidoria.
    staff.locator('[name="body"]').fill(reply)
    # Seleciona o estado interno answered, correspondente à manifestação respondida.
    staff.locator('[name="status"]').select_option("answered")
    # Publica a resposta e a alteração de estado pelo formulário da gestão.
    staff.get_by_role("button", name="Publicar resposta").click()
    # Aguarda e verifica se a resposta publicada aparece na página de gestão.
    expect(staff.locator(".reply-body")).to_contain_text(reply)
    # Confere também a largura dessa tela após a publicação da resposta.
    assert_fits(staff)

    # Volta à aba autenticada do aluno e abre a consulta por protocolo.
    student.goto(BASE_URL + "/acompanhar/")
    # Informa o protocolo extraído da manifestação criada neste teste.
    student.locator('[name="protocol"]').fill(protocol)
    # Submete a consulta pela interface, como faria o aluno.
    student.get_by_role("button", name="Consultar manifestação").click()
    # Verifica se o aluno consegue visualizar o texto exato publicado pela ouvidoria.
    expect(student.get_by_text(reply, exact=True)).to_be_visible()
    # Confere se o indicador de estado do cabeçalho mostra a tradução Respondida.
    expect(student.locator(".page-heading .badge")).to_contain_text("Respondida")

    # Cria uma terceira sessão autenticada para testar as permissões específicas da direção.
    director_context = browser.new_context(viewport={"width": 1440, "height": 1000})
    # Abre a aba usada pelas ações da direção fictícia.
    director = director_context.new_page()
    # Entra com a conta de demonstração que possui o perfil da direção.
    login(director, "direcao.demo@camporeal.edu.br")
    # Abre a mesma manifestação na área de gestão, agora com esse perfil.
    director.goto(BASE_URL + "/gestao/" + protocol + "/")
    # Confere se o e-mail também permanece ausente do HTML antes da consulta justificada.
    assert "aluno.demo@camporeal.edu.br" not in director.content()
    # Informa uma justificativa fictícia que deverá constar no registro de auditoria.
    director.locator('[name="reason"]').fill("Consulta fictícia para demonstrar a auditoria da direção no TCC.")
    # Reapresenta a senha de demonstração para confirmar a operação de consulta de identidade.
    director.locator('[name="password"]').fill(PASSWORD)
    # Envia a justificativa e solicita a visualização da identidade pela interface autorizada.
    director.get_by_role("button", name="Justificar e consultar identidade").click()
    # Verifica se o e-mail aparece na área específica de identidade revelada após a solicitação.
    expect(director.locator(".revealed-identity")).to_contain_text("aluno.demo@camporeal.edu.br")
    # Confere se a lista de auditoria mostra o trecho da justificativa registrada.
    expect(director.locator(".audit-list")).to_contain_text("Consulta fictícia")
    # Acessa novamente a página sem reenviar o pedido de revelação de identidade.
    director.goto(BASE_URL + "/gestao/" + protocol + "/")
    # Confere se o e-mail voltou a ficar ausente do HTML nessa nova requisição.
    assert "aluno.demo@camporeal.edu.br" not in director.content()
    # Atualiza a aba da ouvidoria para verificar o conteúdo recebido após a consulta da direção.
    staff.reload()
    # Confere se a consulta da direção não passou a expor o e-mail ao atendente nessa página.
    assert "aluno.demo@camporeal.edu.br" not in staff.content()
    # Falha se as abas pública ou do aluno registraram erros JavaScript; exibe a lista na falha.
    assert not errors, errors
    # Fecha o navegador e suas abas após concluir as verificações.
    browser.close()
# Exibe o resumo somente se a execução chegou ao fim sem falhas nas verificações anteriores.
print("Navegador: home desktop/mobile, menu, envio, protocolo, resposta, acompanhamento e consulta auditada passaram.")
