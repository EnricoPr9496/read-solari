const { test } = require('node:test');
const assert = require('node:assert/strict');
const { statoLettura } = require('../dashboard.js');

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
