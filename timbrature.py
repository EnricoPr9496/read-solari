import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# --- Dati Presi in Sicurezza ---
USERNAME = os.environ.get("SOLARI_USER")
PASSWORD = os.environ.get("SOLARI_PASS")
ID_DIPENDENTE = os.environ.get("SOLARI_ID")
TIMEOUT = (10, 30)
TZ_ITALY = ZoneInfo("Europe/Rome")


class ErroreSolari(RuntimeError):
    pass

BASE_URL = "https://itsaas-10.solari.it/AirPowerStartweb"
LOGIN_URL = f"{BASE_URL}/Login.aspx?ReturnUrl=%2fAirPowerStartweb%2fdefault.aspx"
DASHBOARD_URL = f"{BASE_URL}/default.aspx"
API_URL = f"{BASE_URL}/rpc/Cartellino.aspx"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "it-IT,it;q=0.9",
    "Upgrade-Insecure-Requests": "1"
})

def esegui_login():
    res = session.get(LOGIN_URL, timeout=TIMEOUT)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, 'html.parser')
    form_data = {}
    for hidden_field in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        inp = soup.find("input", {"id": hidden_field})
        if inp: form_data[hidden_field] = inp.get("value")
            
    form_data["__EVENTTARGET"] = "btnLogin"
    form_data["__EVENTARGUMENT"] = ""
    form_data["tbUsername"] = USERNAME
    form_data["tbPassword"] = PASSWORD
    form_data["validUsername"] = str(int(time.time() * 1000))
    form_data["idUtenteHidden"] = ""
    form_data["TotpTextBox"] = ""
            
    login_headers = {"Content-Type": "application/x-www-form-urlencoded"}
    res = session.post(LOGIN_URL, data=form_data, headers=login_headers, allow_redirects=False, timeout=TIMEOUT)
    res.raise_for_status()
    return ".ASPXAUTH" in session.cookies.get_dict()

def ottieni_csrf_token():
    res = session.get(DASHBOARD_URL, timeout=TIMEOUT)
    res.raise_for_status()
    match = re.search(r"['\"]CSRFToken['\"]\s*,\s*['\"]([^'\"]+)['\"]", res.text)
    return match.group(1) if match else None

def genera_dashboard(csrf_token, destinazione="index.html"):
    oggi = datetime.now(TZ_ITALY).date()
    inizio_settimana = oggi - timedelta(days=oggi.weekday())
    fine_settimana = inizio_settimana + timedelta(days=6)
    primo_giorno = inizio_settimana.strftime("%Y%m%d000000")
    ultimo_giorno = fine_settimana.strftime("%Y%m%d000000")
    
    url = f"{API_URL}?PageMethod=ConsultaCartellino&iddip={ID_DIPENDENTE}&CSRFToken={csrf_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"}
    payload = {"_dtdatainizio": primo_giorno, "_dtdatafine": ultimo_giorno, "dipendenti": [], "sologganomali": False, "soloconvalidati": False, "conautstra": False, "_itiporichiesta": 0, "_iidprospetto": 0, "_itipoconsultazione": 0, "ordinamentodip": "C"}
    
    response = session.post(url, headers=headers, data=json.dumps(payload), timeout=TIMEOUT)
    response.raise_for_status()
    try:
        giornate = response.json()['result']['sintesi']['data']
        if not isinstance(giornate, list) or not giornate:
            raise ValueError("Risposta senza giornate")
        # Un formato cambiato non deve sostituire la pagina con dati parziali.
        date_ricevute = set()
        for giorno in giornate:
            data = datetime.strptime(str(giorno[1])[:8], "%Y%m%d").date()
            date_ricevute.add(data)
            if giorno[24]:
                timbri = json.loads(giorno[24])['data']
                if not isinstance(timbri, list):
                    raise ValueError("Formato timbrature non valido")
                for timbro in timbri:
                    if not isinstance(timbro[0], str) or not timbro[0] or type(timbro[1]) is not int or not 0 <= timbro[1] < 1440:
                        raise ValueError("Timbratura non valida")
        if oggi not in date_ricevute:
            raise ValueError("Manca la giornata corrente")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ErroreSolari("Risposta di Solari incompleta o non valida; ultima pagina conservata.") from exc

    aggiornato = datetime.now(TZ_ITALY)
    html = genera_html(giornate, aggiornato)
    destinazione = Path(destinazione)
    temporaneo = destinazione.with_suffix('.html.tmp')
    temporaneo.write_text(html, encoding="utf-8")
    temporaneo.replace(destinazione)


def genera_html(giornate, aggiornato):
    oggi = aggiornato.astimezone(TZ_ITALY).date()
    inizio_settimana = oggi - timedelta(days=oggi.weekday())
    fine_settimana = inizio_settimana + timedelta(days=6)
    ora_aggiornamento = aggiornato.astimezone(TZ_ITALY).strftime("%d/%m/%Y alle %H:%M")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Timbri</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; color: #333; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            h2 {{ text-align: center; color: #2c3e50; }}
            .update {{ text-align: center; font-size: 0.8em; color: #7f8c8d; margin-bottom: 20px; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ padding: 12px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }}
            .oggi {{ background-color: #e8f8f5; border-left: 4px solid #1abc9c; }}
            .timbrature {{ color: #2980b9; font-weight: bold; text-align: right; }}
            .previsione {{ font-size: 0.85em; color: #e67e22; font-weight: bold; margin-top: 5px; display: block; }}
            .completato {{ color: #27ae60; }}
            .errore {{ color: #e74c3c; }}
            .azioni {{ display: flex; gap: 10px; flex-wrap: wrap; margin: 16px 0 8px; }}
            .azioni a, .azioni button {{ background: #2563eb; color: white; border: 0; border-radius: 7px; padding: 11px 14px; font: inherit; text-decoration: none; cursor: pointer; }}
            .azioni button {{ background: #e8edf3; color: #233348; }}
            .nota {{ color: #526071; font-size: 0.85em; line-height: 1.5; }}
            .avviso {{ background: #fff4d6; color: #704b00; padding: 12px; border-radius: 7px; line-height: 1.5; }}
            [hidden] {{ display: none !important; }}
        </style>
    </head>
    <body data-updated-at="{aggiornato.isoformat()}">
        <div class="container">
            <h2>⏱ I Miei Orari (Settimana)</h2>
            <div class="update">Ultima lettura riuscita: {ora_aggiornamento}</div>
            <div id="avviso-dati" class="avviso" role="status" hidden></div>
            <div class="azioni">
                <a href="https://github.com/EnricoPr9496/read-solari/actions/workflows/aggiorna_sito.yml" target="_blank" rel="noopener noreferrer">Aggiorna tramite GitHub ↗</a>
                <button type="button" id="ricarica-pagina">Ricarica pagina</button>
            </div>
            <p class="nota">Per leggere nuovi timbri, apri GitHub e premi <strong>Run workflow</strong> sul ramo <strong>main</strong>.
                Quando l'aggiornamento e la pubblicazione sono terminati, ricarica questa pagina.
                Serve l'accesso al tuo account GitHub.</p>
            <p class="nota">Letture programmate: lun–ven alle 10:00, 13:30, 14:30 e 16:00 (Italia).
                Le partenze automatiche possono subire ritardi.</p>
            <ul>
    """

    if giornate:
        for giorno in giornate:
            data_string = str(giorno[1])
            data_obj = datetime.strptime(data_string[:8], "%Y%m%d").date()
            
            if inizio_settimana <= data_obj <= fine_settimana:
                data_formattata = data_obj.strftime("%d/%m/%Y")
                is_oggi = (data_obj == oggi)
                classe_css = ' class="oggi"' if is_oggi else ''
                
                etichetta_data = f"<strong>{data_formattata} (OGGI)</strong>" if is_oggi else data_formattata
                
                timbrature_raw = giorno[24] 
                timbrature_str = "Nessuna"
                
                if timbrature_raw:
                    timb_json = json.loads(timbrature_raw)
                    t_list = timb_json.get('data', [])
                    
                    timbrature_lista = []
                    for t in t_list:
                        verso = "IN" if t[0] == 'E' else "OUT"
                        minuti = t[1] 
                        timbrature_lista.append(f"{verso} {minuti//60:02d}:{minuti%60:02d}")
                    
                    if timbrature_lista:
                        timbrature_str = " <br> ".join(timbrature_lista)
                        
                    if is_oggi:
                        minuti_totali = 480 # 8 ore lavorative
                        min_pausa = 60      # 1 ora di pausa minima
                        
                        if len(t_list) == 1:
                            in_1 = t_list[0][1]
                            out_previsto = in_1 + minuti_totali + min_pausa
                            etichetta_data += f"<span class='previsione'>🏁 Prevista: {out_previsto//60:02d}:{out_previsto%60:02d}</span>"
                        
                        elif len(t_list) == 2:
                            in_1 = t_list[0][1]
                            out_1 = t_list[1][1]
                            lavorati_mattina = out_1 - in_1
                            eff_in_2 = out_1 + min_pausa
                            out_previsto = eff_in_2 + (minuti_totali - lavorati_mattina)
                            etichetta_data += f"<span class='previsione'>🏁 Prevista: {out_previsto//60:02d}:{out_previsto%60:02d} (con 1h pausa)</span>"
                            
                        elif len(t_list) == 3:
                            in_1 = t_list[0][1]
                            out_1 = t_list[1][1]
                            in_2 = t_list[2][1]
                            lavorati_mattina = out_1 - in_1
                            da_fare = minuti_totali - lavorati_mattina
                            
                            # Regola della Pausa Minima: si riprende a contare dal maggiore tra 
                            # l'ora di timbrata e l'orario in cui scade l'ora di pausa obbligatoria.
                            eff_in_2 = max(in_2, out_1 + min_pausa)
                            
                            out_previsto = eff_in_2 + da_fare
                            etichetta_data += f"<span class='previsione'>🏁 Fine 8h: {out_previsto//60:02d}:{out_previsto%60:02d}</span>"
                            
                        elif len(t_list) >= 4:
                            in_1 = t_list[0][1]; out_1 = t_list[1][1]
                            in_2 = t_list[2][1]; out_2 = t_list[3][1]
                            
                            eff_in_2 = max(in_2, out_1 + min_pausa)
                            totale_lavorato = (out_1 - in_1) + (out_2 - eff_in_2)
                            
                            if totale_lavorato >= 480:
                                etichetta_data += f"<span class='previsione completato'>✅ 8 ore raggiunte</span>"
                            else:
                                mancano = 480 - totale_lavorato
                                etichetta_data += f"<span class='previsione errore'>⚠️ Mancano {mancano} min (uscita anticipata)</span>"
                
                html += f"<li{classe_css} data-date='{data_obj.isoformat()}'><div>{etichetta_data}</div><div class='timbrature'>{timbrature_str}</div></li>\n"

    html += """
            </ul>
        </div>
        <script src="dashboard.js"></script>
    </body>
    </html>
    """
    
    return html


def main():
    try:
        if not all((USERNAME, PASSWORD, ID_DIPENDENTE)):
            raise ErroreSolari("Configura SOLARI_USER, SOLARI_PASS e SOLARI_ID nei segreti del repository.")
        if not esegui_login():
            raise ErroreSolari("Accesso a Solari non riuscito; ultima pagina conservata.")
        token = ottieni_csrf_token()
        if not token:
            raise ErroreSolari("Sessione Solari non valida: token CSRF assente; ultima pagina conservata.")
        genera_dashboard(token)
    except ErroreSolari as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException:
        # Non stampare URL, token di sessione o corpo della risposta nei log pubblici.
        print("Errore di rete o HTTP durante la lettura di Solari; ultima pagina conservata.", file=sys.stderr)
        return 1
    print("Lettura Solari completata e dashboard aggiornata.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
