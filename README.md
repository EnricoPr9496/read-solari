# Dashboard timbrature Solari

Legge il cartellino Solari e genera `index.html` per GitHub Pages.
Il calcolo di uscita mantiene le regole esistenti: 8 ore di lavoro e almeno
60 minuti di pausa. Non gestisce turni notturni o più di due coppie entrata/uscita.

## Aggiornamenti

Il workflow `.github/workflows/aggiorna_sito.yml` richiede una lettura dal lunedì
al venerdì alle **10:00, 13:30, 14:30 e 16:00**, nel fuso `Europe/Rome`.
L'ora legale viene gestita dal fuso orario. GitHub Actions può ritardare o saltare
le partenze: questi sono orari richiesti, non una garanzia di puntualità.

Per aggiornare manualmente:

1. Premere **Aggiorna tramite GitHub** nella dashboard.
2. Accedere a GitHub con un account che può scrivere nel repository.
3. Premere **Run workflow**, selezionare `main` e confermare **Run workflow**.
4. Attendere il completamento di **Aggiorna Dashboard** e **pages-build-deployment**.
5. Tornare alla dashboard e premere **Ricarica pagina**.

Il collegamento apre l'avvio manuale su GitHub; non avvia il lavoro da solo.
Ricaricare la pagina recupera l'HTML pubblicato e non interroga Solari.
Non sono necessari token GitHub nel browser della dashboard.

La data mostrata indica l'ultima lettura riuscita. Se i dati risalgono a un altro
giorno, oppure una lettura programmata manca da almeno 30 minuti, compare un
avviso e vengono nascoste le previsioni obsolete. Gli orari di questo controllo
sono definiti anche in `dashboard.js`: aggiornarli insieme al workflow.

## Configurazione e diagnosi

Nei segreti GitHub Actions devono essere presenti `SOLARI_USER`, `SOLARI_PASS`
e `SOLARI_ID`. L'account deve avere accesso al proprio cartellino su Solari.
Le credenziali non devono essere aggiunte ai file del repository.

Il programma interrompe il lavoro con un errore se mancano le credenziali,
il login non riesce, manca il token di sessione o la risposta non è valida.
Le richieste hanno un limite di attesa; l'ultimo HTML valido viene conservato
in caso di errore. Non vengono stampati URL con token o risposte di Solari nei log.

In caso di dati vecchi, controllare separatamente:

- assenza di esecuzioni all'orario atteso: avvio programmato GitHub;
- esecuzione fallita: accesso, connessione o formato dei dati Solari;
- esecuzione riuscita ma sito vecchio: pubblicazione Pages o cache del browser.

### Riscontro del 13 ottobre 2026

Il workflow precedente richiedeva quattro partenze alle 08:00, 12:00, 13:00 e
16:00 UTC: in quella data erano le 10:00, 14:00, 15:00 e 18:00 italiane.
La cronologia pubblica mostrava una sola esecuzione il 12 ottobre alle 19:16
italiane e, al momento del controllo, una il 13 ottobre alle 17:30.
Quest'ultima è durata 19 secondi; Pages ha poi impiegato 1 minuto e 16 secondi.
Il lungo intervallo precede quindi la lettura, non è il tempo di esecuzione dello
script. Le informazioni pubbliche non identificano quale singola scadenza cron
abbia prodotto ogni esecuzione ritardata.

Il vecchio programma poteva anche terminare senza errore quando login o token
fallivano. Questo difetto è distinto dal ritardo osservato nelle partenze.

- [Esecuzione del 13 ottobre](https://github.com/EnricoPr9496/read-solari/actions/runs/38422657457)
- [Esecuzione del 12 ottobre](https://github.com/EnricoPr9496/read-solari/actions/runs/38283078304)
- [Pubblicazione del 13 ottobre](https://github.com/EnricoPr9496/read-solari/actions/runs/38422702376)
- [Limiti delle esecuzioni programmate](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows)
- [Avvio manuale](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)

## Verifica locale

Con Python 3.12 e Node.js disponibili:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
node --test tests/dashboard.test.cjs
```

I test usano risposte simulate, senza accesso a Solari. Una verifica completa
richiede un'esecuzione reale con i segreti già configurati e il controllo della
successiva pubblicazione Pages.

## Se serve puntualità maggiore

Un pianificatore esterno che richiama l'avvio manuale di GitHub può sostituire il
cron di GitHub, ma lascia la dipendenza dalla coda Actions e dalla pubblicazione
Pages. Per aggiornare i timbri direttamente con un pulsante nella dashboard,
serve invece un servizio applicativo autenticato che esegua la lettura e restituisca
i dati, con le credenziali conservate sul server. Questa migrazione richiede
la scelta e la configurazione di un servizio di hosting e non è inclusa qui.

Il repository e la pagina attuali sono pubblici: anche l'HTML con gli orari è
pubblico. Una futura migrazione può proteggere la dashboard con autenticazione;
cambiare il servizio non rende automaticamente privati i file già pubblicati.
