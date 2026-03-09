import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
from datetime import datetime, timedelta
import calendar

# --- Dati Presi in Sicurezza ---
USERNAME = os.environ.get("SOLARI_USER")
PASSWORD = os.environ.get("SOLARI_PASS")
ID_DIPENDENTE = os.environ.get("SOLARI_ID", "136") 

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
    res = session.get(LOGIN_URL)
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
    session.post(LOGIN_URL, data=form_data, headers=login_headers, allow_redirects=False)
    return ".ASPXAUTH" in session.cookies.get_dict()

def ottieni_csrf_token():
    res = session.get(DASHBOARD_URL)
    match = re.search(r"['\"]CSRFToken['\"]\s*,\s*['\"]([^'\"]+)['\"]", res.text)
    return match.group(1) if match else None

def genera_dashboard(csrf_token):
    oggi = datetime.now().date()
    primo_giorno = datetime(oggi.year, oggi.month, 1).strftime("%Y%m%d000000")
    giorni_nel_mese = calendar.monthrange(oggi.year, oggi.month)[1]
    ultimo_giorno = datetime(oggi.year, oggi.month, giorni_nel_mese).strftime("%Y%m%d000000")
    
    inizio_settimana = oggi - timedelta(days=oggi.weekday())
    fine_settimana = inizio_settimana + timedelta(days=6)
    
    url = f"{API_URL}?PageMethod=ConsultaCartellino&iddip={ID_DIPENDENTE}&CSRFToken={csrf_token}"
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "X-Requested-With": "XMLHttpRequest"}
    payload = {"_dtdatainizio": primo_giorno, "_dtdatafine": ultimo_giorno, "dipendenti": [], "sologganomali": False, "soloconvalidati": False, "conautstra": False, "_itiporichiesta": 0, "_iidprospetto": 0, "_itipoconsultazione": 0, "ordinamentodip": "C"}
    
    response = session.post(url, headers=headers, data=json.dumps(payload))
    
    ora_aggiornamento = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y alle %H:%M")
    
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
        </style>
    </head>
    <body>
        <div class="container">
            <h2>⏱ I Miei Orari (Settimana)</h2>
            <div class="update">Ultimo controllo automatico: {ora_aggiornamento}</div>
            <ul>
    """

    if response.status_code == 200:
        dati = response.json()
        giornate = dati['result']['sintesi']['data']
        
        for giorno in giornate:
            data_string = str(giorno[1])
            data_obj = datetime.strptime(data_string[:8], "%Y%m%d").date()
            
            if inizio_settimana <= data_obj <= fine_settimana:
                data_formattata = data_obj.strftime("%d/%m/%Y")
                is_oggi = (data_obj == oggi)
                classe_css = ' class="oggi"' if is_oggi else ''
                
                # Nome base del giorno
                etichetta_data = f"<strong>{data_formattata} (OGGI)</strong>" if is_oggi else data_formattata
                
                timbrature_raw = giorno[24] 
                timbrature_str = "Nessuna"
                
                # --- CALCOLO MATEMATICO DELLE 8 ORE ---
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
                        
                    # Se è "oggi", proviamo a calcolare l'uscita a 8 ore
                    if is_oggi:
                        minuti_totali = 480 # 8 ore
                        min_pausa = 60      # 1 ora
                        
                        if len(t_list) == 1:
                            # Solo 1 timbratura (entrato stamattina) -> Aggiungo 8 ore + 1 di pausa
                            in_1 = t_list[0][1]
                            out_previsto = in_1 + minuti_totali + min_pausa
                            etichetta_data += f"<span class='previsione'>🏁 Prevista: {out_previsto//60:02d}:{out_previsto%60:02d}</span>"
                        
                        elif len(t_list) == 2:
                            # Ha timbrato IN e OUT al mattino (ora è in pausa)
                            in_1 = t_list[0][1]
                            out_1 = t_list[1][1]
                            lavorati = out_1 - in_1
                            # Prevediamo rientri dopo 1 ora esatta
                            out_previsto = out_1 + min_pausa + (minuti_totali - lavorati)
                            etichetta_data += f"<span class='previsione'>🏁 Prevista: {out_previsto//60:02d}:{out_previsto%60:02d} (con 1h pausa)</span>"
                            
                        elif len(t_list) == 3:
                            # Rientrato dalla pausa pranzo! Calcoliamo l'uscita esatta
                            in_1 = t_list[0][1]
                            out_1 = t_list[1][1]
                            in_2 = t_list[2][1]
                            lavorati_mattina = out_1 - in_1
                            da_fare = minuti_totali - lavorati_mattina
                            out_previsto = in_2 + da_fare
                            etichetta_data += f"<span class='previsione'>🏁 Fine 8h: {out_previsto//60:02d}:{out_previsto%60:02d}</span>"
                            
                        elif len(t_list) >= 4:
                            # Giornata finita (4 timbrate)
                            in_1 = t_list[0][1]; out_1 = t_list[1][1]
                            in_2 = t_list[2][1]; out_2 = t_list[3][1]
                            if (out_1 - in_1) + (out_2 - in_2) >= 480:
                                etichetta_data += f"<span class='previsione completato'>✅ 8 ore raggiunte</span>"
                
                html += f"<li{classe_css}><div>{etichetta_data}</div><div class='timbrature'>{timbrature_str}</div></li>\n"
    else:
        html += "<li>Errore di connessione a Solari.</li>"

    html += """
            </ul>
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if esegui_login():
    token = ottieni_csrf_token()
    if token:
        genera_dashboard(token)
