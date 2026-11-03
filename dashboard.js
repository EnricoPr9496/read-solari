/* Gli orari devono corrispondere al workflow aggiorna_sito.yml. */
(function () {
  "use strict";
  const ORARI = [600, 810, 870, 960];
  const TOLLERANZA = 30;
  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/Rome", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23", weekday: "short"
  });

  function oraItaliana(data) {
    const parti = Object.fromEntries(formatter.formatToParts(data).map(p => [p.type, p.value]));
    return {
      giorno: `${parti.year}-${parti.month}-${parti.day}`,
      minuti: Number(parti.hour) * 60 + Number(parti.minute),
      feriale: !["Sat", "Sun"].includes(parti.weekday)
    };
  }

  function statoLettura(ultimoAggiornamento, adesso = new Date()) {
    const oggi = oraItaliana(adesso);
    const ultimo = new Date(ultimoAggiornamento);
    if (!ultimoAggiornamento || Number.isNaN(ultimo.getTime())) {
      return { obsoleto: true, giorno: oggi.giorno, messaggio: "Data dell'ultima lettura non disponibile. Avvia un aggiornamento manuale." };
    }
    const letto = oraItaliana(ultimo);
    if (letto.giorno !== oggi.giorno) {
      return { obsoleto: true, giorno: oggi.giorno, messaggio: "Questi dati non sono di oggi. Aggiorna le timbrature prima di usare la previsione di uscita." };
    }
    const attesi = oggi.feriale ? ORARI.filter(m => oggi.minuti >= m + TOLLERANZA) : [];
    if (attesi.length && letto.minuti < attesi[attesi.length - 1]) {
      return { obsoleto: true, giorno: oggi.giorno, messaggio: "Manca una lettura programmata: premi Aggiorna timbrature per richiedere nuovi dati." };
    }
    return { obsoleto: false, giorno: oggi.giorno, messaggio: "" };
  }

  const API = "https://api.github.com/repos/EnricoPr9496/read-solari";
  const WORKFLOW = "/actions/workflows/aggiorna_sito.yml";
  const TOKEN_KEY = "read-solari:github-token";

  class ErroreAggiornamento extends Error {
    constructor(message, status = 0) { super(message); this.status = status; }
  }

  function messaggioErrore(status) {
    if (status === 401) return "Autorizzazione scaduta o revocata. Configura di nuovo questo browser.";
    if (status === 403 || status === 404) return "Autorizzazione insufficiente o limite GitHub raggiunto. Verifica il token: solo read-solari, Actions in lettura e scrittura.";
    if (status === 429) return "GitHub ha ricevuto troppe richieste. Riprova tra qualche minuto.";
    return "GitHub non ha completato la richiesta. Riprova più tardi.";
  }

  function creaClient(token, fetchImpl = fetch) {
    async function api(path, body) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 20000);
      try {
        const response = await fetchImpl(API + path, {
          method: body === undefined ? "GET" : "POST",
          headers: {
            Accept: "application/vnd.github+json",
            Authorization: `Bearer ${token}`,
            "X-GitHub-Api-Version": "2026-03-10",
            ...(body === undefined ? {} : { "Content-Type": "application/json" })
          },
          body: body === undefined ? undefined : JSON.stringify(body),
          cache: "no-store", credentials: "omit", redirect: "error", signal: controller.signal
        });
        if (!response.ok) throw new ErroreAggiornamento(messaggioErrore(response.status), response.status);
        return response.status === 204 ? null : await response.json();
      } catch (error) {
        if (error instanceof ErroreAggiornamento) throw error;
        // Non includere risposte o eccezioni che potrebbero contenere credenziali.
        throw new ErroreAggiornamento("Connessione interrotta. La richiesta potrebbe essere già partita: attendi e ricarica la pagina prima di riprovare.");
      } finally { clearTimeout(timer); }
    }
    return {
      verifica: () => api(WORKFLOW),
      elenco: () => api(WORKFLOW + "/runs?event=workflow_dispatch&branch=main&per_page=20"),
      avvia: () => api(WORKFLOW + "/dispatches", { ref: "main" }),
      stato: id => {
        if (!Number.isSafeInteger(id) || id <= 0) throw new ErroreAggiornamento("Risposta di GitHub non valida.");
        return api("/actions/runs/" + id);
      }
    };
  }

  async function aggiornaDaGitHub({ client, leggiPubblicazione, ultimoAggiornamento, segnala,
    attendi = ms => new Promise(resolve => setTimeout(resolve, ms)), maxTentativi = 90 }) {
    // Il confronto serve alle versioni API che accettano l'avvio senza restituire l'ID.
    const precedenti = new Set((await client.elenco()).workflow_runs.map(run => run.id));
    segnala("Invio della richiesta…");
    const risposta = await client.avvia(); // Una sola POST; mai ritentare automaticamente.
    let runId = risposta && risposta.workflow_run_id;
    let completato = false;
    for (let tentativo = 0; tentativo < maxTentativi; tentativo++) {
      if (!runId) {
        const nuovi = (await client.elenco()).workflow_runs.filter(run => !precedenti.has(run.id));
        if (nuovi.length > 1) throw new ErroreAggiornamento("Sono partiti più aggiornamenti. Attendi qualche minuto, poi ricarica la pagina.");
        if (nuovi.length === 1) runId = nuovi[0].id;
      }
      if (runId && !completato) {
        const run = await client.stato(runId);
        if (run.status === "completed") {
          if (run.conclusion !== "success") throw new ErroreAggiornamento("L'aggiornamento non è riuscito. Gli ultimi dati validi sono stati conservati. Controlla l'esecuzione su GitHub.");
          completato = true;
        }
      }
      segnala(completato ? "Lettura completata. Attendo la pubblicazione…" : "Aggiornamento in corso… Puoi restare su questa pagina.");
      if (completato) {
        const pubblicato = await leggiPubblicazione();
        const prima = Date.parse(ultimoAggiornamento);
        const dopo = Date.parse(pubblicato);
        if (Number.isFinite(dopo) && (!Number.isFinite(prima) || dopo > prima)) return;
      }
      await attendi(10000);
    }
    throw new ErroreAggiornamento("L'aggiornamento sta impiegando più del previsto. Può continuare in background: ricarica la pagina tra qualche minuto.");
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { statoLettura, creaClient, aggiornaDaGitHub };
  }
  if (typeof document === "undefined") return;

  function aggiornaAvviso() {
    const stato = statoLettura(document.body.dataset.updatedAt);
    const avviso = document.getElementById("avviso-dati");
    avviso.hidden = !stato.obsoleto;
    avviso.textContent = stato.messaggio;
    document.querySelectorAll("li[data-date]").forEach(riga => {
      const oggi = riga.dataset.date === stato.giorno;
      riga.classList.toggle("oggi", oggi);
      if (!oggi) {
        const etichetta = riga.querySelector("strong");
        if (etichetta) etichetta.textContent = etichetta.textContent.replace(" (OGGI)", "");
      }
      riga.querySelectorAll(".previsione").forEach(previsione => {
        previsione.hidden = stato.obsoleto || !oggi;
      });
    });
  }

  function ricarica() {
    const url = new URL(window.location.href);
    url.searchParams.set("lettura", Date.now().toString());
    window.location.replace(url.toString());
  }

  function configuraAggiornamento() {
    const azioni = document.querySelector(".azioni");
    const linkGitHub = azioni.querySelector("a");
    const aggiorna = document.createElement("button");
    aggiorna.type = "button";
    aggiorna.id = "aggiorna-timbrature";
    aggiorna.textContent = "Aggiorna timbrature";
    aggiorna.style.cssText = "background:#2563eb;color:white";
    linkGitHub.replaceWith(aggiorna);

    const nota = document.querySelector(".nota");
    nota.textContent = "Premi Aggiorna timbrature per leggere nuovi dati. La pagina si ricarica al termine: può richiedere alcuni minuti.";
    const stato = document.createElement("p");
    stato.id = "stato-aggiornamento";
    stato.className = "nota";
    stato.setAttribute("role", "status");
    stato.setAttribute("aria-live", "polite");
    nota.after(stato);

    const impostazioni = document.createElement("details");
    impostazioni.className = "nota";
    impostazioni.innerHTML = '<summary>Accesso da questo browser</summary>' +
      '<p id="stato-accesso"></p>' +
      '<form id="configura-accesso"><label for="token-github">Token GitHub</label>' +
      '<input id="token-github" type="password" autocomplete="off" spellcheck="false" required style="display:block;box-sizing:border-box;width:100%;padding:10px;margin:8px 0">' +
      '<p>Usa un token limitato a read-solari, con Actions in lettura e scrittura. Viene salvato solo in questo browser e inviato esclusivamente a GitHub. La password Solari resta nei segreti GitHub.</p>' +
      '<div class="azioni"><button type="submit">Salva su questo browser</button>' +
      '<button type="button" id="copia-accesso">Copia token per un altro browser</button>' +
      '<button type="button" id="rimuovi-accesso">Rimuovi da questo browser</button></div></form>' +
      '<p><a href="https://github.com/settings/personal-access-tokens/new?name=Read+Solari+browser&target_name=EnricoPr9496&expires_in=none&actions=write" target="_blank" rel="noopener noreferrer">Crea token su GitHub</a> · ' +
      '<a href="https://github.com/EnricoPr9496/read-solari/actions/workflows/aggiorna_sito.yml" target="_blank" rel="noopener noreferrer">Controlla esecuzioni su GitHub</a></p>';
    stato.after(impostazioni);

    const campo = document.getElementById("token-github");
    const statoAccesso = document.getElementById("stato-accesso");
    const form = document.getElementById("configura-accesso");
    const rimuovi = document.getElementById("rimuovi-accesso");
    const copia = document.getElementById("copia-accesso");
    let occupato = false;

    function leggiToken() {
      try { return window.localStorage.getItem(TOKEN_KEY) || ""; }
      catch { throw new Error("Il browser blocca il salvataggio. Abilita i dati del sito per configurare l'accesso."); }
    }
    function aggiornaAccesso() {
      try {
        const presente = Boolean(leggiToken());
        statoAccesso.textContent = presente ? "Questo browser è configurato. Puoi aggiornare con un clic." : "Configura una volta questo browser per aggiornare direttamente dal sito.";
        rimuovi.disabled = !presente;
        copia.disabled = !presente;
      } catch (error) { statoAccesso.textContent = error.message; }
    }
    function blocca(valore) {
      occupato = valore;
      aggiorna.disabled = valore;
      aggiorna.style.opacity = valore ? "0.6" : "1";
      form.querySelectorAll("input, button").forEach(el => { el.disabled = valore; });
      if (!valore) aggiornaAccesso();
    }

    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (occupato) return;
      const token = campo.value.trim();
      if (!token) return;
      blocca(true);
      stato.textContent = "Verifico l'accesso…";
      try {
        await creaClient(token).verifica();
        window.localStorage.setItem(TOKEN_KEY, token);
        stato.textContent = "Accesso salvato in questo browser. Premi Aggiorna timbrature.";
        impostazioni.open = false;
      } catch (error) {
        stato.textContent = error instanceof ErroreAggiornamento ? error.message : "Impossibile salvare l'accesso. Controlla le impostazioni dei dati del sito.";
      } finally { campo.value = ""; blocca(false); }
    });

    copia.addEventListener("click", async () => {
      if (occupato) return;
      try {
        const token = leggiToken();
        if (!token) return;
        await navigator.clipboard.writeText(token);
        stato.textContent = "Token copiato. Nell'altro browser apri questo sito, incollalo in Accesso da questo browser e premi Salva. Non condividerlo in chat o messaggi.";
      } catch {
        stato.textContent = "Il browser non consente di copiare il token negli appunti.";
      }
    });

    rimuovi.addEventListener("click", () => {
      if (occupato) return;
      const confermato = window.confirm(
        "Vuoi davvero rimuovere l'accesso da questo browser?\n\n" +
        "Il token salvato qui verrà cancellato. Per aggiornare le timbrature dovrai inserirlo di nuovo.\n\n" +
        "Premi Annulla per mantenere l'accesso."
      );
      if (!confermato) return;
      try {
        window.localStorage.removeItem(TOKEN_KEY);
        campo.value = "";
        stato.textContent = "Accesso rimosso da questo browser. Il token può essere revocato nelle impostazioni GitHub.";
        aggiornaAccesso();
      } catch { stato.textContent = "Il browser non consente di modificare i dati del sito."; }
    });

    aggiorna.addEventListener("click", async () => {
      if (occupato) return;
      let token;
      try { token = leggiToken(); }
      catch (error) { stato.textContent = error.message; return; }
      if (!token) {
        impostazioni.open = true;
        stato.textContent = "Configura l'accesso una sola volta per questo browser.";
        campo.focus();
        return;
      }
      blocca(true);
      stato.textContent = "Preparo l'aggiornamento…";
      try {
        await aggiornaDaGitHub({
          client: creaClient(token),
          ultimoAggiornamento: document.body.dataset.updatedAt,
          segnala: messaggio => { stato.textContent = messaggio; },
          leggiPubblicazione: async () => {
            const url = new URL(window.location.href);
            url.searchParams.set("lettura", Date.now().toString());
            try {
              const response = await fetch(url, { cache: "no-store", credentials: "omit", signal: AbortSignal.timeout(15000) });
              if (!response.ok) return "";
              const html = new DOMParser().parseFromString(await response.text(), "text/html");
              return html.body.dataset.updatedAt || "";
            } catch { return ""; }
          }
        });
        stato.textContent = "Nuovi dati pubblicati. Ricarico…";
        ricarica();
      } catch (error) {
        stato.textContent = error instanceof ErroreAggiornamento ? error.message : "Impossibile verificare l'aggiornamento. Attendi qualche minuto e ricarica la pagina.";
        if (error.status === 401 || error.status === 403 || error.status === 404) impostazioni.open = true;
      } finally { blocca(false); }
    });
    aggiornaAccesso();
  }

  document.getElementById("ricarica-pagina").addEventListener("click", ricarica);
  configuraAggiornamento();
  aggiornaAvviso();
  setInterval(aggiornaAvviso, 30000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) aggiornaAvviso();
  });
})();
