/* Acrescenta recursos opcionais de interface; os formulários continuam utilizáveis sem JavaScript. */
(() => { // Isola as variáveis desta página para não interferir em outros scripts.
  document.documentElement.classList.add("js-enabled"); // Permite que o CSS exiba o botão de menu apenas quando este script estiver ativo.
  const toggle = document.querySelector("[data-nav-toggle]"); // Localiza o botão que abre e fecha a navegação em telas pequenas.
  const menu = document.querySelector("[data-nav-menu]"); // Localiza a navegação que será controlada pelo botão.
  if (toggle && menu) { // Só prepara o menu móvel quando os dois elementos existem nesta página.
    const mobile = window.matchMedia("(max-width: 640px)"); // Usa o mesmo limite de largura definido nos estilos do menu móvel.
    const syncMenu = () => { // Mantém o menu coerente ao abrir a página ou mudar o tamanho da janela.
      menu.hidden = mobile.matches; // Começa recolhido no celular e visível nas telas maiores.
      toggle.setAttribute("aria-expanded", String(!menu.hidden)); // Informa aos leitores de tela se a navegação está expandida.
      toggle.setAttribute("aria-label", menu.hidden ? "Abrir menu" : "Fechar menu"); // Descreve a próxima ação do botão conforme o estado atual.
    }; // Encerra a função de sincronização da navegação.
    syncMenu(); // Aplica o estado correto do menu assim que os elementos ficam disponíveis.
    mobile.addEventListener("change", syncMenu); // Reajusta a navegação quando a janela cruza o limite entre celular e computador.
    toggle.addEventListener("click", () => { // Trata o clique no botão de abrir ou fechar o menu.
      menu.hidden = !menu.hidden; // Alterna a visibilidade atual da navegação.
      toggle.setAttribute("aria-expanded", String(!menu.hidden)); // Atualiza a informação acessível depois da mudança de visibilidade.
      toggle.setAttribute("aria-label", menu.hidden ? "Abrir menu" : "Fechar menu"); // Mantém o nome do botão correspondente à ação disponível.
    }); // Encerra o tratamento do clique no botão de navegação.
    document.addEventListener("keydown", (event) => { // Observa o teclado para permitir fechar o menu sem usar o ponteiro.
      if (event.key === "Escape" && mobile.matches && !menu.hidden) { // Fecha apenas o menu móvel que estiver aberto quando a tecla Escape for pressionada.
        menu.hidden = true; // Recolhe as opções de navegação.
        toggle.setAttribute("aria-expanded", "false"); // Comunica que o menu foi recolhido aos leitores de tela.
        toggle.setAttribute("aria-label", "Abrir menu"); // Indica que o próximo clique voltará a abrir o menu.
        toggle.focus(); // Devolve o foco ao botão para preservar a continuidade da navegação pelo teclado.
      } // Encerra a condição de fechamento pela tecla Escape.
    }); // Encerra a observação do teclado para a navegação.
  } // Encerra a preparação opcional do menu móvel.
  document.querySelectorAll("textarea[data-count-target]").forEach((field) => { // Prepara contadores apenas nas áreas de texto que indicam onde mostrar a contagem.
    const counter = document.getElementById(field.dataset.countTarget); // Localiza o contador associado ao atributo data-count-target deste campo.
    if (!counter) return; // Ignora somente este campo se o elemento de contagem não existir.
    const updateCount = () => { // Recalcula a quantidade de caracteres enquanto o texto é editado.
      const limit = field.getAttribute("maxlength"); // Consulta o limite de caracteres definido no próprio formulário, quando houver.
      counter.textContent = `${field.value.length}${limit ? ` / ${limit}` : ""} caracteres`; // Exibe a quantidade atual e o limite como texto, sem interpretar HTML.
    }; // Encerra a função que atualiza a contagem do campo.
    field.addEventListener("input", updateCount); // Atualiza o contador em cada alteração de conteúdo do campo.
    updateCount(); // Mostra a contagem inicial, inclusive quando um formulário retorna com dados preenchidos.
  }); // Encerra a preparação das áreas de texto com contador.
  document.querySelectorAll("button[data-copy]").forEach((button) => { // Prepara a ação de copiar nos botões que possuem um protocolo no atributo data-copy.
    const feedback = button.parentElement.querySelector(".copy-feedback"); // Localiza a área que informa o resultado da cópia e é anunciada por leitores de tela.
    if (!feedback) return; // Evita ativar uma ação sem um local para apresentar seu resultado ao usuário.
    const selectProtocol = () => { // Oferece seleção manual quando o navegador não permite copiar diretamente.
      const protocol = button.parentElement.querySelector("strong"); // Localiza o texto visível do protocolo dentro do mesmo cartão.
      const selection = window.getSelection(); // Obtém o recurso nativo de seleção de texto da janela.
      if (protocol && selection) { // Usa a seleção manual somente se o protocolo e o recurso do navegador estiverem disponíveis.
        const range = document.createRange(); // Cria um intervalo que representará o texto a ser selecionado.
        range.selectNodeContents(protocol); // Inclui no intervalo apenas o conteúdo textual do protocolo.
        selection.removeAllRanges(); // Limpa uma seleção anterior para não misturá-la ao protocolo.
        selection.addRange(range); // Destaca o protocolo para que a pessoa use a função de copiar do dispositivo.
        feedback.textContent = "Protocolo selecionado. Use a opção de copiar do seu dispositivo."; // Informa a seleção sem afirmar que a cópia já aconteceu.
      } else { // Trata navegadores que não oferecem o recurso de seleção programática.
        feedback.textContent = "Selecione o protocolo acima para copiá-lo."; // Orienta a seleção manual do texto visível como alternativa.
      } // Encerra a escolha entre seleção automática e orientação manual.
    }; // Encerra a alternativa de cópia por seleção de texto.
    button.addEventListener("click", async () => { // Solicita a cópia apenas depois de um clique explícito da pessoa.
      if (!navigator.clipboard) { // Detecta a ausência da API de transferência, comum em páginas sem contexto seguro.
        selectProtocol(); // Usa a alternativa de seleção quando a cópia direta não existe.
        return; // Finaliza este clique sem tentar acessar uma API indisponível.
      } // Encerra a verificação de disponibilidade da cópia direta.
      try { // Tenta copiar respeitando as permissões e restrições do navegador.
        await navigator.clipboard.writeText(button.dataset.copy); // Aguarda a confirmação de gravação do protocolo na área de transferência.
        feedback.textContent = "Protocolo copiado."; // Confirma o sucesso somente depois que a gravação realmente termina.
      } catch (_) { // Trata a recusa de permissão ou outra falha da cópia sem interromper o uso da página.
        selectProtocol(); // Mantém a seleção manual como alternativa quando a tentativa direta falhar.
      } // Encerra o tratamento de sucesso ou falha da cópia.
    }); // Encerra a ação de copiar associada a este botão.
  }); // Encerra a preparação dos botões de protocolo encontrados na página.
})(); // Executa imediatamente a preparação dos recursos opcionais de interface.
