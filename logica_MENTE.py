import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import re
import io

# --- TENTA L'IMPORT DI GEOPY ---
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Global Training Optimizer 2.2", layout="wide")

if not HAS_GEOPY:
    st.warning("⚠️ ATTENZIONE: La libreria 'geopy' non è installata. Vai su GitHub, apri 'requirements.txt' e aggiungi una riga con scritto: geopy")

# Inizializziamo il geolocalizzatore con un User-Agent unico per evitare blocchi
geolocator = Nominatim(user_agent="it_training_planner_unique_99") if HAS_GEOPY else None

# --- FUNZIONI DI SERVIZIO ---
def get_coords(location_string):
    """Cerca di ottenere coordinate da testo o link."""
    if not HAS_GEOPY or not location_string: return None
    
    # 1. Prova a cercare coordinate in un link Google Maps
    # Cerca il pattern @lat,lon
    regex = r"@(-?\d+\.\d+),(-?\d+\.\d+)"
    match = re.search(regex, location_string)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    
    # 2. Prova con la geocodifica testuale
    try:
        # Puliamo la stringa da eventuali caratteri strani
        clean_loc = location_string.strip()
        location = geolocator.geocode(clean_loc, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        st.error(f"Errore di connessione al servizio mappe: {e}")
        return None
    return None

def calcola_km(orig, dest):
    if not HAS_GEOPY or not orig or not dest: return 0
    try:
        return int(geodesic(orig, dest).km * 1.25)
    except:
        return 0

# --- LOGICA DI CALCOLO ---
class TrainingPlanner:
    def __init__(self):
        if 'sedi_custom' not in st.session_state:
            st.session_state.sedi_custom = {}
        self.df_pax = pd.DataFrame()

    def get_clean_col(self, df, targets):
        """Trova una colonna indipendentemente da accenti o maiuscole."""
        for c in df.columns:
            # Rimuove accenti e spazi per il confronto
            normalized = c.lower().replace('à', 'a').strip()
            if normalized in targets:
                return c
        return None

    def analizza(self, sedi_config, r_km, d_pranzo, c_notte, v_uomo):
        if self.df_pax.empty or not sedi_config: return None, [], []
        
        # Trova colonne
        c_citta = self.get_clean_col(self.df_pax, ['citta', 'luogo', 'indirizzo', 'partenza'])
        c_nome = self.get_clean_col(self.df_pax, ['nome', 'partecipante', 'tecnico'])
        c_ruolo = self.get_clean_col(self.df_pax, ['ruolo', 'mansione'])

        if not c_citta:
            st.error("❌ Non trovo la colonna 'Città' nel file Excel. Controlla il nome della colonna!")
            return None, [], []

        tot_vivi, tot_gg = 0, 0
        mappa_data, tabella = [], []
        
        # Separiamo Relatori e Partecipanti
        is_rel = self.df_pax[c_ruolo].str.contains('relatore', case=False, na=False) if c_ruolo else [False]*len(self.df_pax)
        relatori = self.df_pax[is_rel]
        pax = self.df_pax[~is_rel]

        sedi_nomi = list(sedi_config.keys())
        
        # Ciclo Partecipanti
        for _, row in pax.iterrows():
            orig_coords = get_coords(str(row[c_citta]))
            if not orig_coords: continue
            
            # Trova sede più vicina
            dists = {s: calcola_km(orig_coords, st.session_state.sedi_custom[s]['lat_long']) for s in sedi_nomi}
            sede_opt = min(dists, key=dists.get)
            km = dists[sede_opt]
            
            gg_tr = sedi_config[sede_opt]
            pernotto = km > 350 or any(x in str(row[c_citta]).lower() for x in ["cagliari", "palermo", "sicilia", "sardegna"])
            
            costo = (km * 2 * r_km) + (d_pranzo * gg_tr) + (c_notte * gg_tr if pernotto else 0)
            gg_p = gg_tr + (2 if pernotto else 1)
            
            tot_vivi += costo
            tot_gg += gg_p
            
            dest_coords = st.session_state.sedi_custom[sede_opt]['lat_long']
            mappa_data.append({"n": row[c_nome], "lo": orig_coords[0], "oo": orig_coords[1], "ld": dest_coords[0], "od": dest_coords[1]})
            tabella.append({"Nome": row[c_nome], "Da": row[c_citta], "A": sede_opt, "Km A/R": km*2, "Costo": round(costo,2), "Gg Persi": gg_p})

        # Ciclo Relatori (viaggiano su tutte le sedi dello scenario)
        for _, row in relatori.iterrows():
            rel_coords = get_coords(str(row[c_citta]))
            if not rel_coords: continue
            for s_n in sedi_nomi:
                km_r = calcola_km(rel_coords, st.session_state.sedi_custom[s_n]['lat_long'])
                tot_vivi += (km_r * 2 * r_km) + (d_pranzo + c_notte)
                tot_gg += (sedi_config[s_n] + 1)

        for s in sedi_nomi: tot_vivi += st.session_state.sedi_custom[s]['costo']

        return {"tot": tot_vivi + (tot_gg * v_uomo), "vivi": tot_vivi, "gg": tot_gg}, mappa_data, tabella

# --- INTERFACCIA ---
planner = TrainingPlanner()
st.title("🚀 Optimizer 2.2 - Prossimità e Risparmio")

with st.sidebar:
    st.header("💰 Parametri")
    r_km = st.number_input("Rimborso KM (€)", value=0.44)
    v_u = st.number_input("Valore Giorno Uomo (€)", value=500)

# 1. GESTIONE SEDI
st.subheader("1️⃣ Definisci le Sedi degli Eventi")
c1, c2, c3 = st.columns([3, 1, 1])
input_sede = c1.text_input("Inserisci Città o Indirizzo (es: Falconara Marittima)")
costo_s = c2.number_input("Costo Sala (€)", 0)
if c3.button("Aggiungi Sede"):
    coords = get_coords(input_sede)
    if coords:
        nome_pulito = input_sede.split(',')[0]
        st.session_state.sedi_custom[nome_pulito] = {"lat_long": coords, "costo": costo_s}
        st.success(f"✅ Sede aggiunta: {nome_pulito}")
    else:
        st.error("❌ Indirizzo non trovato. Prova a scrivere solo la città.")

if st.session_state.sedi_custom:
    st.write("**Sedi registrate:** " + ", ".join(st.session_state.sedi_custom.keys()))

# 2. FILE
st.subheader("2️⃣ Carica Partecipanti")
file = st.file_uploader("Upload Excel", type="xlsx")
if file:
    planner.df_pax = pd.read_excel(file)
    st.write("✅ File caricato con successo!")

# 3. CONFRONTO
if not planner.df_pax.empty and st.session_state.sedi_custom:
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.info("### SCENARIO A (es. 3 Eventi)")
        sc_a = st.multiselect("Sedi A", list(st.session_state.sedi_custom.keys()), key="ma")
        conf_a = {s: st.number_input(f"Gg a {s}", 1, 3, 1, key=f"ga{s}") for s in sc_a}
        res_a, map_a, tab_a = planner.analizza(conf_a, r_km, 30, 130, v_u)

    with col_b:
        st.error("### SCENARIO B (es. 2 Eventi)")
        sc_b = st.multiselect("Sedi B", list(st.session_state.sedi_custom.keys()), key="mb")
        conf_b = {s: st.number_input(f"Gg a {s}", 1, 3, 1, key=f"gb{s}") for s in sc_b}
        res_b, map_b, tab_b = planner.analizza(conf_b, r_km, 30, 130, v_u)

    if res_a and res_b:
        st.divider()
        risparmio = res_b['tot'] - res_a['tot']
        gg_salvati = res_b['gg'] - res_a['gg']
        
        st.metric("Risparmio Totale con Scenario A", f"€ {risparmio:,.2f}", delta=f"{gg_salvati} giornate uomo recuperate")
        
        if map_a:
            st.pydeck_chart(pdk.Deck(
                map_style=None,
                initial_view_state=pdk.ViewState(latitude=42, longitude=12, zoom=5),
                layers=[pdk.Layer("ArcLayer", pd.DataFrame(map_a), get_source_position=["oo","lo"], get_target_position=["od","ld"], get_width=3)]
            ))
        st.dataframe(pd.DataFrame(tab_a))
