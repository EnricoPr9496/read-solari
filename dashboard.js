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
      return { obsoleto: true, giorno: oggi.giorno, messaggio: "Manca una lettura programmata: l'aggiornamento potrebbe essere in ritardo o non riuscito. Avvialo manualmente da GitHub." };
    }
    return { obsoleto: false, giorno: oggi.giorno, messaggio: "" };
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { statoLettura };
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

  document.getElementById("ricarica-pagina").addEventListener("click", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("lettura", Date.now().toString());
    window.location.replace(url.toString());
  });
  aggiornaAvviso();
  setInterval(aggiornaAvviso, 30000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) aggiornaAvviso();
  });
})();
