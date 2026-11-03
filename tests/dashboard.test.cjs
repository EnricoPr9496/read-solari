const { test } = require('node:test');
const assert = require('node:assert/strict');
const { statoLettura, creaClient, aggiornaDaGitHub } = require('../dashboard.js');

test('dati di ieri non sono validi come previsione per oggi', () => {
  assert.equal(statoLettura('2026-10-12T16:00:00+02:00', new Date('2026-10-13T09:00:00+02:00')).obsoleto, true);
});
test('la pausa fra 10:00 e 13:30 non viene segnalata come ritardo', () => {
  assert.equal(statoLettura('2026-10-13T10:03:00+02:00', new Date('2026-10-13T13:45:00+02:00')).obsoleto, false);
});
test('lettura 13:30 mancante viene segnalata dopo 30 minuti', () => {
  assert.equal(statoLettura('2026-10-13T10:03:00+02:00', new Date('2026-10-13T14:00:00+02:00')).obsoleto, true);
});
test('una lettura manuale successiva risolve il ritardo', () => {
  assert.equal(statoLettura('2026-10-13T14:10:00+02:00', new Date('2026-10-13T14:20:00+02:00')).obsoleto, false);
});
test('orario italiano anche dopo il cambio di ora', () => {
  assert.equal(statoLettura('2026-10-26T09:01:00Z', new Date('2026-10-26T12:45:00Z')).obsoleto, false);
  assert.equal(statoLettura('2026-10-26T09:01:00Z', new Date('2026-10-26T13:00:00Z')).obsoleto, true);
});
test('nel weekend non si aspetta una lettura programmata', () => {
  assert.equal(statoLettura('2026-10-17T09:00:00+02:00', new Date('2026-10-17T18:00:00+02:00')).obsoleto, false);
});
test('un timestamp assente o non valido non appare aggiornato', () => {
  assert.equal(statoLettura('').obsoleto, true);
  assert.equal(statoLettura('non-una-data').obsoleto, true);
});

test('token solo nell’header GitHub, avvio main senza redirect', async () => {
  const chiamate = [];
  const client = creaClient('credenziale-di-test', async (url, options) => {
    chiamate.push({ url, options });
    return { ok: true, status: 200, json: async () => ({ workflow_run_id: 42 }) };
  });
  assert.deepEqual(await client.avvia(), { workflow_run_id: 42 });
  const { url, options } = chiamate[0];
  assert.equal(url, 'https://api.github.com/repos/EnricoPr9496/read-solari/actions/workflows/aggiorna_sito.yml/dispatches');
  assert.equal(options.headers.Authorization, 'Bearer credenziale-di-test');
  assert.equal(options.redirect, 'error');
  assert.equal(options.credentials, 'omit');
  assert.deepEqual(JSON.parse(options.body), { ref: 'main' });
  assert.ok(!url.includes('credenziale-di-test'));
  assert.ok(!options.body.includes('credenziale-di-test'));
  assert.throws(() => client.stato('../secrets'), /non valida/);
});

test('errori di autorizzazione utili senza risposte sensibili', async () => {
  for (const [status, messaggio] of [[401, /scaduta o revocata/], [403, /insufficiente/], [429, /troppe richieste/]]) {
    const client = creaClient('segreto', async () => ({
      ok: false, status, json: async () => { throw new Error('risposta contenente segreto'); }
    }));
    await assert.rejects(client.verifica(), error => error.status === status && messaggio.test(error.message) && !error.message.includes('segreto'));
  }
});

test('errore di rete non rivela il token e non ritenta l’avvio', async () => {
  let richieste = 0;
  const client = creaClient('segreto', async () => { richieste++; throw new Error('Authorization: Bearer segreto'); });
  await assert.rejects(client.avvia(), error => !error.message.includes('segreto') && /potrebbe essere già partita/.test(error.message));
  assert.equal(richieste, 1);
});

function scenario(opzioni = {}) {
  const contatori = { avvii: 0, pagine: 0, stati: 0 };
  const messaggi = [];
  const config = {
    client: {
      elenco: async () => ({ workflow_runs: [{ id: 1 }] }),
      avvia: async () => { contatori.avvii++; return { workflow_run_id: 42 }; },
      stato: async id => {
        assert.equal(id, 42);
        contatori.stati++;
        return { status: 'completed', conclusion: 'success' };
      }
    },
    ultimoAggiornamento: '2026-11-03T10:00:00+01:00',
    leggiPubblicazione: async () => { contatori.pagine++; return '2026-11-03T11:00:00+01:00'; },
    segnala: messaggio => messaggi.push(messaggio),
    attendi: async () => {}, maxTentativi: 3, ...opzioni
  };
  return { config, contatori, messaggi };
}

test('attende successo del lavoro e pubblicazione di una pagina più recente', async () => {
  const { config, contatori, messaggi } = scenario();
  config.client.stato = async () => {
    contatori.stati++;
    return contatori.stati === 1 ? { status: 'queued' } : { status: 'completed', conclusion: 'success' };
  };
  config.leggiPubblicazione = async () => {
    contatori.pagine++;
    return contatori.pagine === 1 ? config.ultimoAggiornamento : '2026-11-03T11:00:00+01:00';
  };
  await aggiornaDaGitHub(config);
  assert.deepEqual(contatori, { avvii: 1, pagine: 2, stati: 2 });
  assert.ok(messaggi.some(message => /pubblicazione/.test(message)));
});

test('un lavoro fallito non viene presentato come riuscito', async () => {
  const { config, contatori } = scenario();
  config.client.stato = async () => ({ status: 'completed', conclusion: 'failure' });
  await assert.rejects(aggiornaDaGitHub(config), /non è riuscito/);
  assert.equal(contatori.pagine, 0);
  assert.equal(contatori.avvii, 1);
});

test('pagina non disponibile: termina senza altri avvii', async () => {
  const { config, contatori } = scenario({ leggiPubblicazione: async () => 'non disponibile' });
  await assert.rejects(aggiornaDaGitHub(config), /più del previsto/);
  assert.equal(contatori.avvii, 1);
});

test('risposta 204: individua il nuovo avvio senza usare quello precedente', async () => {
  const { config, contatori } = scenario();
  let elenchi = 0;
  config.client.elenco = async () => ({ workflow_runs: ++elenchi === 1 ? [{ id: 1 }] : [{ id: 42 }, { id: 1 }] });
  config.client.avvia = async () => { contatori.avvii++; return null; };
  await aggiornaDaGitHub(config);
  assert.equal(contatori.avvii, 1);
});

test('due nuovi avvii senza ID non producono un successo arbitrario', async () => {
  const { config } = scenario();
  let elenchi = 0;
  config.client.elenco = async () => ({ workflow_runs: ++elenchi === 1 ? [] : [{ id: 42 }, { id: 43 }] });
  config.client.avvia = async () => null;
  await assert.rejects(aggiornaDaGitHub(config), /più aggiornamenti/);
});
