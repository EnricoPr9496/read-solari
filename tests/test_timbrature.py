import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import timbrature as app


def giornata(data="20261013000000", timbri=None):
    riga = [None] * 25
    riga[1] = data
    riga[24] = json.dumps({"data": timbri or []})
    return riga


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.adesso = datetime(2026, 10, 13, 14, 30, tzinfo=app.TZ_ITALY)

    def esegui_main(self, **opzioni):
        with patch.multiple(app, USERNAME="test", PASSWORD="test", ID_DIPENDENTE="123"), \
             patch.object(app, "esegui_login", return_value=opzioni.get("login", True)), \
             patch.object(app, "ottieni_csrf_token", return_value=opzioni.get("token", "token-test")), \
             patch.object(app, "genera_dashboard", side_effect=opzioni.get("errore")) as genera, \
             contextlib.redirect_stderr(io.StringIO()) as log:
            risultato = app.main()
        return risultato, genera, log.getvalue()

    def test_login_fallito_interrompe_aggiornamento(self):
        risultato, genera, log = self.esegui_main(login=False)
        self.assertEqual(risultato, 1)
        genera.assert_not_called()
        self.assertIn("Accesso", log)

    def test_csrf_assente_interrompe_aggiornamento(self):
        risultato, genera, log = self.esegui_main(token=None)
        self.assertEqual(risultato, 1)
        genera.assert_not_called()
        self.assertIn("CSRF", log)

    def test_errore_di_rete_non_espone_token(self):
        risultato, _, log = self.esegui_main(errore=requests.Timeout("url?CSRFToken=SEGRETO"))
        self.assertEqual(risultato, 1)
        self.assertNotIn("SEGRETO", log)

    def test_segreti_mancanti_non_chiamano_solari(self):
        with patch.object(app, "USERNAME", None), patch.object(app, "esegui_login") as login, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(app.main(), 1)
            login.assert_not_called()

    def test_risposte_errate_conservano_pagina_e_timestamp(self):
        for dati in [{"error": "session expired"}, {"result": {"sintesi": {"data": []}}},
                     {"result": {"sintesi": {"data": [giornata("20261012000000")]}}},
                     {"result": {"sintesi": {"data": [giornata(timbri=[["E", "08:00"]])]}}}]:
            with self.subTest(dati=dati), tempfile.TemporaryDirectory() as cartella:
                destinazione = Path(cartella) / "index.html"
                destinazione.write_text("ultima pagina valida", encoding="utf-8")
                response = Mock()
                response.json.return_value = dati
                with patch.object(app.session, "post", return_value=response), patch.object(app, "datetime", wraps=datetime) as clock:
                    clock.now.return_value = self.adesso
                    with self.assertRaises(app.ErroreSolari):
                        app.genera_dashboard("token", destinazione)
                self.assertEqual(destinazione.read_text(encoding="utf-8"), "ultima pagina valida")

    def test_http_500_non_sovrascrive_pagina(self):
        with tempfile.TemporaryDirectory() as cartella:
            destinazione = Path(cartella) / "index.html"
            destinazione.write_text("precedente", encoding="utf-8")
            response = Mock()
            response.raise_for_status.side_effect = requests.HTTPError()
            with patch.object(app.session, "post", return_value=response), self.assertRaises(requests.HTTPError):
                app.genera_dashboard("token", destinazione)
            self.assertEqual(destinazione.read_text(encoding="utf-8"), "precedente")

    def test_settimana_fra_due_mesi_e_scrittura_riuscita(self):
        adesso = datetime(2026, 10, 1, 10, tzinfo=app.TZ_ITALY)
        response = Mock()
        response.json.return_value = {"result": {"sintesi": {"data": [giornata("20261001000000")]}}}
        with tempfile.TemporaryDirectory() as cartella, patch.object(app.session, "post", return_value=response) as post, \
             patch.object(app, "datetime", wraps=datetime) as clock:
            clock.now.return_value = adesso
            destinazione = Path(cartella) / "index.html"
            app.genera_dashboard("token", destinazione)
            payload = json.loads(post.call_args.kwargs["data"])
            self.assertEqual(payload["_dtdatainizio"], "20260928000000")
            self.assertEqual(payload["_dtdatafine"], "20261004000000")
            self.assertEqual(post.call_args.kwargs["timeout"], app.TIMEOUT)
            self.assertIn(adesso.isoformat(), destinazione.read_text(encoding="utf-8"))

    def test_pausa_minima_e_uscita_previste_preservate(self):
        html = app.genera_html([giornata(timbri=[["E", 8 * 60 + 43], ["U", 12 * 60 + 51], ["E", 13 * 60 + 49]])], self.adesso)
        self.assertIn("Fine 8h: 17:43", html)
        self.assertIn('data-updated-at="2026-10-13T14:30:00+02:00"', html)
        self.assertIn("Aggiorna tramite GitHub", html)
        self.assertIn("dashboard.js", html)


if __name__ == "__main__":
    unittest.main()
