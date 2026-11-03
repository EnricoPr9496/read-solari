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

1. Una volta per browser, aprire **Accesso da questo browser** e salvare un
   token GitHub fine-grained, limitato al repository `read-solari`, con il solo
   permesso **Actions: Read and write** (Metadata in lettura è automatico).
2. Premere **Aggiorna timbrature**. Non occorre aprire GitHub.
3. Attendere la lettura e la pubblicazione: la pagina si ricarica automaticamente
   quando il lavoro è riuscito e l'HTML pubblicato contiene dati più recenti.

Il token resta in `localStorage` di questo browser e viene inviato solo a
`api.github.com` nell'header Authorization. Non è inserito nei file, negli URL
o nelle richieste alla pagina pubblica. La password Solari resta nei segreti
GitHub. Usare un browser personale: chi accede al suo profilo, e gli script
della stessa origine, possono accedere al token salvato. Non aggiungere script
di terze parti alla dashboard.

Si può scegliere **No expiration** alla creazione, se consentito dall'account.
GitHub può comunque revocare i token non usati per un anno. Cancellare i dati
del sito rimuove la configurazione; **Rimuovi da questo browser** cancella la
copia locale, senza revocare il token su GitHub. Su altri dispositivi occorre
una configurazione separata. Per trasferire l'accesso a un altro proprio browser,
premere **Copia token per un altro browser** dal browser già configurato,
incollarlo nel campo Token GitHub della stessa dashboard nell'altro browser e
salvarlo. Questa operazione copia la credenziale negli appunti solo su richiesta;
non condividerla tramite messaggi e sostituire il contenuto degli appunti dopo
l'uso. Revocare il token su GitHub disabilita tutte le copie.

Il pulsante invia una sola richiesta di avvio, impedisce doppi clic e controlla
lo stato per un massimo di circa 15 minuti (oltre ai tempi di rete). Un errore
o un'attesa lunga non causa altri avvii automatici. La chiave non è necessaria
per leggere la dashboard o per gli aggiornamenti già programmati.

**Ricarica pagina** recupera l'HTML pubblicato e non interroga Solari. Senza
JavaScript resta disponibile il collegamento di avvio manuale su GitHub.

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
Pages. Il pulsante attuale avvia Actions dal browser e attende Pages. Per leggere
Solari senza attendere Actions e la pubblicazione, serve invece un servizio
applicativo autenticato che esegua la lettura e restituisca i dati, con le
credenziali conservate sul server. Questa migrazione non è inclusa qui.

Il repository e la pagina attuali sono pubblici: anche l'HTML con gli orari è
pubblico. Una futura migrazione può proteggere la dashboard con autenticazione;
cambiare il servizio non rende automaticamente privati i file già pubblicati.
