/* Melhorias de interface. Todas as ações também funcionam sem JavaScript (formulários comuns). */
(() => {
  "use strict";

  const $ = (seletor, raiz = document) => raiz.querySelector(seletor);
  const $$ = (seletor, raiz = document) => [...raiz.querySelectorAll(seletor)];

  // ------------------------------------------------------------ toast
  let temporizadorToast;
  function toast(mensagem, acao) {
    const area = $("#toast");
    if (!area) return;
    const caixa = document.createElement("div");
    caixa.className =
      "pointer-events-auto flex items-center gap-4 rounded-card bg-ink px-4 py-3 text-sm text-white shadow-lg";
    caixa.append(mensagem);
    if (acao) {
      const link = document.createElement("a");
      link.href = acao.href;
      link.textContent = acao.texto;
      link.className = "font-semibold underline underline-offset-2";
      caixa.append(link);
    }
    area.replaceChildren(caixa);
    clearTimeout(temporizadorToast);
    temporizadorToast = setTimeout(() => area.replaceChildren(), 4000);
  }

  function atualizarContador(quantidade) {
    $$("[data-contador-sacola]").forEach((el) => {
      el.textContent = quantidade;
      el.hidden = !quantidade;
    });
  }

  async function enviarJson(form) {
    const resposta = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });
    return { resposta, dados: await resposta.json().catch(() => ({})) };
  }

  // ------------------------------------------------------------ cliques gerais
  document.addEventListener("click", (evento) => {
    const alvo = evento.target;

    const abrir = alvo.closest("[data-abrir]");
    if (abrir) {
      const dialogo = document.getElementById(abrir.dataset.abrir);
      if (dialogo && typeof dialogo.showModal === "function") {
        dialogo.showModal();
        const foco = abrir.dataset.foco && document.getElementById(abrir.dataset.foco);
        if (foco) foco.scrollIntoView({ block: "start" });
      }
      return;
    }

    if (alvo.closest("[data-fechar]")) {
      alvo.closest("dialog")?.close();
      return;
    }

    // Clique no fundo escuro fecha o diálogo
    if (alvo instanceof HTMLDialogElement) {
      const r = alvo.getBoundingClientRect();
      const fora =
        evento.clientX < r.left || evento.clientX > r.right || evento.clientY < r.top || evento.clientY > r.bottom;
      if (fora) alvo.close();
      return;
    }

    const alternar = alvo.closest("[data-alternar]");
    if (alternar) {
      const painel = document.getElementById(alternar.dataset.alternar);
      if (painel) {
        painel.hidden = !painel.hidden;
        alternar.setAttribute("aria-expanded", String(!painel.hidden));
        if (!painel.hidden) $("input:not([type=hidden])", painel)?.focus();
      }
      return;
    }

    const copiar = alvo.closest("[data-copiar]");
    if (copiar) {
      const campo = document.getElementById(copiar.dataset.copiar);
      if (!campo) return;
      const concluir = () => toast("Código Pix copiado");
      if (navigator.clipboard) {
        navigator.clipboard.writeText(campo.value).then(concluir, () => {
          campo.select();
          document.execCommand("copy");
          concluir();
        });
      } else {
        campo.select();
        document.execCommand("copy");
        concluir();
      }
      return;
    }

    if (alvo.closest("[data-aceitar-cookies]")) {
      try {
        localStorage.setItem("cookies-ok", "1");
      } catch (_) {
        /* navegação privada: só esconde */
      }
      $("#aviso-cookies").hidden = true;
    }
  });

  // Confirmação antes de excluir/remover
  document.addEventListener(
    "submit",
    (evento) => {
      const mensagem = evento.target.dataset?.confirmar;
      if (mensagem && !window.confirm(mensagem)) {
        evento.preventDefault();
        evento.stopImmediatePropagation();
      }
    },
    true,
  );

  // ------------------------------------------------------------ aviso de cookies
  try {
    if (!localStorage.getItem("cookies-ok")) $("#aviso-cookies")?.removeAttribute("hidden");
  } catch (_) {
    /* sem armazenamento: não insiste no aviso */
  }

  // ------------------------------------------------------------ galeria do produto
  const galeria = $("[data-galeria]");
  if (galeria) {
    const pontos = $$("[data-ponto]");
    const atual = () => Math.round(galeria.scrollLeft / Math.max(galeria.clientWidth, 1));
    const marcar = () => {
      const indice = atual();
      pontos.forEach((ponto, i) => {
        ponto.classList.toggle("bg-ink", i === indice);
        ponto.classList.toggle("bg-line", i !== indice);
        if (i === indice) ponto.setAttribute("aria-current", "true");
        else ponto.removeAttribute("aria-current");
      });
    };
    galeria.addEventListener("scroll", () => requestAnimationFrame(marcar), { passive: true });
    pontos.forEach((ponto, i) =>
      ponto.addEventListener("click", () => galeria.scrollTo({ left: i * galeria.clientWidth, behavior: "smooth" })),
    );
    galeria.addEventListener("keydown", (evento) => {
      const passo = { ArrowRight: 1, ArrowLeft: -1 }[evento.key];
      if (passo) galeria.scrollBy({ left: passo * galeria.clientWidth, behavior: "smooth" });
    });
  }

  // ------------------------------------------------------------ produto: cor, tamanho e sacola
  const formAdicionar = $("[data-adicionar]");
  const dadosVariacoes = $("#dados-variacoes");
  if (formAdicionar && dadosVariacoes) {
    const variacoes = JSON.parse(dadosVariacoes.textContent);
    const campoVariacao = $("[data-variacao]", formAdicionar);
    const erro = $("[data-erro-adicionar]");
    const botao = $("[data-botao-adicionar]");
    const nomeCor = $("[data-cor-nome]");

    const atualizar = () => {
      const cor = $("[data-cor]:checked", formAdicionar)?.value;
      if (nomeCor) nomeCor.textContent = cor || "";
      $$("[data-tamanho]", formAdicionar).forEach((opcao) => {
        const variacao = variacoes.find((v) => v.cor === cor && v.tamanho === opcao.value);
        const disponivel = Boolean(variacao && variacao.estoque > 0);
        opcao.disabled = !disponivel;
        if (!disponivel) opcao.checked = false;
        const aviso = $("[data-esgotado]", opcao.nextElementSibling);
        if (aviso) aviso.textContent = disponivel ? "" : " (esgotado)";
      });
      const tamanho = $("[data-tamanho]:checked", formAdicionar)?.value;
      const escolhida = variacoes.find((v) => v.cor === cor && v.tamanho === tamanho);
      campoVariacao.value = escolhida ? escolhida.id : "";
      erro.textContent = "";
    };
    formAdicionar.addEventListener("change", atualizar);
    atualizar();

    formAdicionar.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      if (!campoVariacao.value) {
        erro.textContent = "Escolha o tamanho.";
        $("[data-tamanho]:not(:disabled)", formAdicionar)?.focus();
        return;
      }
      botao.disabled = true;
      try {
        const { resposta, dados } = await enviarJson(formAdicionar);
        if (!resposta.ok) {
          erro.textContent = dados.erro || "Não foi possível adicionar. Tente de novo.";
          return;
        }
        atualizarContador(dados.quantidade);
        toast("Adicionado à sacola.", { href: "/sacola", texto: "Ver sacola" });
      } catch (_) {
        formAdicionar.submit();
      } finally {
        botao.disabled = false;
      }
    });
  }

  // Favoritar sem recarregar
  $$("[data-favoritar]").forEach((form) =>
    form.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      try {
        const { resposta, dados } = await enviarJson(form);
        if (resposta.status === 401 && dados.login) {
          window.location.href = dados.login;
          return;
        }
        if (!resposta.ok) throw new Error("falha");
        const botao = $("button", form);
        botao.setAttribute("aria-pressed", String(dados.favorito));
        botao.classList.toggle("text-rose", dados.favorito);
        $("svg", botao)?.classList.toggle("fill-current", dados.favorito);
        toast(dados.favorito ? "Salvo nos favoritos." : "Removido dos favoritos.");
      } catch (_) {
        form.submit();
      }
    }),
  );

  // ------------------------------------------------------------ checkout
  // Entrega: o frete muda conforme o endereço escolhido
  const opcaoEntrega = $("[data-frete-entrega]");
  if (opcaoEntrega) {
    document.addEventListener("change", (evento) => {
      const escolhido = evento.target;
      if (escolhido.name !== "endereco_id") return;
      const cartao = opcaoEntrega.closest("label");
      const subtitulo = $(".min-w-0 > span:last-child", cartao);
      const valor = cartao.lastElementChild;
      if (subtitulo && escolhido.dataset.prazo) subtitulo.textContent = escolhido.dataset.prazo;
      if (valor && valor !== subtitulo && escolhido.dataset.frete) valor.textContent = escolhido.dataset.frete;
      opcaoEntrega.disabled = false;
      opcaoEntrega.checked = true;
    });
  }

  // Pagamento: total na barra inferior acompanha o frete
  const totalAtual = $("[data-total-atual]");
  if (totalAtual) {
    document.addEventListener("change", (evento) => {
      if (evento.target.name === "tipo_frete" && evento.target.dataset.total) {
        totalAtual.textContent = evento.target.dataset.total;
      }
    });
  }

  // Evita pedido duplicado com duplo toque
  $$("[data-confirmar-pedido]").forEach((form) =>
    form.addEventListener("submit", () => {
      const botao = $("button[type=submit]", form);
      setTimeout(() => {
        botao.disabled = true;
        botao.textContent = "Gerando Pix…";
      }, 0);
    }),
  );

  // CEP: máscara e preenchimento pelo ViaCEP
  $$("[data-form-endereco]").forEach((form) => {
    const campoCep = $("[data-cep]", form);
    const status = $("[data-cep-status]", form);
    if (!campoCep) return;
    let ultimo = "";
    campoCep.addEventListener("input", async () => {
      const digitos = campoCep.value.replace(/\D/g, "").slice(0, 8);
      campoCep.value = digitos.length > 5 ? `${digitos.slice(0, 5)}-${digitos.slice(5)}` : digitos;
      if (digitos.length !== 8 || digitos === ultimo) return;
      ultimo = digitos;
      if (status) status.textContent = "Buscando endereço…";
      try {
        const resposta = await fetch(`https://viacep.com.br/ws/${digitos}/json/`);
        const dados = await resposta.json();
        if (dados.erro) throw new Error("CEP não encontrado");
        $$("[data-cep-campo]", form).forEach((campo) => {
          const valor = dados[campo.dataset.cepCampo];
          if (valor) campo.value = valor;
        });
        if (status) status.textContent = "";
        $("[name=numero]", form)?.focus();
      } catch (_) {
        if (status) status.textContent = "CEP não encontrado. Preencha o endereço.";
      }
    });
  });

  // ------------------------------------------------------------ pedido aguardando Pix
  const acompanhar = $("[data-acompanhar-pedido]");
  if (acompanhar) {
    const consultar = async () => {
      try {
        const resposta = await fetch(acompanhar.dataset.acompanharPedido, { headers: { Accept: "application/json" } });
        if (!resposta.ok) return;
        const dados = await resposta.json();
        if (dados.status !== "AGUARDANDO_PAGAMENTO") window.location.reload();
      } catch (_) {
        /* tenta de novo no próximo intervalo */
      }
    };
    setInterval(consultar, 5000);
  }
})();
