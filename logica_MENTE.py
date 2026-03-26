import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import re
import io
from fpdf import FPDF

# Tenta l'import di geopy, altrimenti avvisa l'utente
try:
    from geopy.geocoders import Nominatim
    from geopy.distance import geodesic
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Global Training Optimizer PRO 2.1", layout="wide")

if not HAS_GEOPY:
    st.error("⚠️ Libreria 'geopy' non trovata. Aggiungi 'geopy' al file requirements.txt")

geolocator = Nominatim(user_agent="training_optimizer_v2_1") if HAS_GEOPY else None

# --- FUNZIONI DI SERVIZIO ---
@st.cache_data
def get_coords(location_string):
    """Estrae coordinate da indirizzo, città o link Google Maps."""
    if not geolocator: return None
    
    # Pulizia se è un link Google Maps (estrazione coordinate da URL)
    if "google.com/maps" in location_string:
        regex = r"@(-?\d+\.\d+),(-?\d+\.\d+)"
        match = re.search(regex, location_string)
        if match:
            return (float(match.group(1)), float(match.group(2)))
    
    try:
        location = geolocator.geocode(location_string, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except:
        return None
    return None

def calcola_km(orig_coords, dest_coords):
    if not HAS_GEOPY or not orig_coords or not dest_coords: return 0
    dist_lineare = geodesic(orig_coords, dest_coords).km
    return int(dist_lineare * 1.25) # Fattore correttivo stradale

# --- CLASSE LOGICA AGGIORNATA ---
class GlobalTrainingPlanner:
    def __init__(self):
        if 'sedi_custom' not in st.session_state:
            st.session_state.sedi_custom = {}
        self.df_pax = pd.DataFrame()

    def analizza(self, sedi_config, r_km, d_pranzo, c_notte, v_uomo):
        if self.df_pax.empty or not sedi_config:
            return None, [], []

        # Verifica colonna città nel dataframe caricato
        col_citta = next((c for c in self.df_pax.columns if c.lower() in ['citta', 'città', 'luogo', 'partenza']), None)
        if not col_citta:
            st.error("Colonna 'Città' non trovata nel file. Verifica i nomi delle colonne.")
            return None, [], []

        tot_vivi = 0
        tot_gg_persi = 0
        mappa_data = []
        tabella_dettaglio = []
        
        relatori = self.df_pax[self.df_pax['ruolo'].str.contains('relatore', case=False, na=False)]
        partecipanti = self.df_pax[~self.df_pax['ruolo'].str.contains('relatore', case=False, na=False)]

        sedi_nomi = list(sedi_config.keys())
        for _, row in partecipanti.iterrows():
            coords_pax = get_coords(row[col_citta])
            if not coords_pax: continue
            
            distanze = {s: calcola_km(coords_pax, st.session_state.sedi_custom[s]['lat_long']) for s in sedi_nomi}
            sede_opt = min(distanze, key=distanze.get)
            km = distanze[sede_opt]
            gg_training = sedi_config[sede_opt]
            
            serve_pernotto = km > 350 or any(x in str(row[col_citta]).lower() for x in ["sicilia", "sardegna", "cagliari", "palermo"])
            costo_viaggio = km * 2 * r_km
            costo_pax = costo_viaggio + (d_pranzo * gg_training) + (c_notte * gg_training if serve_pernotto else 0)
            gg_persi = gg_training + (2 if serve_pernotto else 1)
            
            tot_vivi += costo_pax
            tot_gg_persi += gg_persi
            
            c_dest = st.session_state.sedi_custom[sede_opt]['lat_long']
            mappa_data.append({
                "nome": row['nome'], "orig": row[col_citta], "dest": sede_opt,
                "lat_o": coords_pax[0], "lon_o": coords_pax[1],
                "lat_d": c_dest[0], "lon_d": c_dest[1]
            })
            tabella_dettaglio.append({
                "Nome": row['nome'], "Sede": sede_opt, "Km A/R": km*2, "Costo (€)": round(costo_pax, 2), "Gg Persi": gg_persi
            })

        for s in sedi_nomi: tot_vivi += st.session_state.sedi_custom[s]['costo']
        
        # Aggiunta logica relatori che viaggiano su tutte le sedi (come richiesto precedentemente)
        for _, row in relatori.iterrows():
            coords_rel = get_coords(row[col_citta])
            if not coords_rel: continue
            for s_nome in sedi_nomi:
                c_sede = st.session_state.sedi_custom[s_nome]['lat_long']
                km_rel = calcola_km(coords_rel, c_sede)
                tot_vivi += (km_rel * 2 * r_km) + (d_pranzo + c_notte)
                tot_gg_persi += (sedi_config[s_nome] + 1)

        res = {"vivi": tot_vivi, "gg": tot_gg_persi, "impatto": tot_gg_persi * v_uomo}
        res["totale"] = res["vivi"] + res["impatto"]
        return res, mappa_data, tabella_dettaglio

planner = GlobalTrainingPlanner()
st.title("📊 Training Strategy Optimizer 2.1")

# Sidebar
st.sidebar.header("⚙️ Parametri")
r_km = st.sidebar.slider("Rimborso KM (€)", 0.20, 0.80, 0.44)
v_uomo = st.sidebar.number_input("Valore Giornata Uomo (€)", value=500)

# 1. SEDI (MIGLIORATA)
st.subheader("1️⃣ Configura Sedi (Città, Indirizzo o Link Maps)")
with st.expander("Aggiungi Sede"):
    c1, c2 = st.columns([3,1])
    loc_input = c1.text_input("Inserisci Città, Indirizzo completo o Link Google Maps")
    c_costo = c2.number_input("Costo Sala (€)", 0)
    if st.button("Registra Sede"):
        coo = get_coords(loc_input)
        if coo:
            # Estraiamo un nome leggibile per la sede
            nome_sede = loc_input.split(',')[0] if ',' in loc_input else loc_input
            if "google.com" in nome_sede: nome_sede = "Sede da Link"
            st.session_state.sedi_custom[nome_sede] = {"lat_long": coo, "costo": c_costo, "input_originale": loc_input}
            st.success(f"Sede '{nome_sede}' registrata correttamente!")
        else:
            st.error("Impossibile trovare la posizione. Verifica l'indirizzo o il link.")

# 2. CARICAMENTO
uploaded = st.file_uploader("Carica Excel partecipanti", type="xlsx")
if uploaded:
    planner.df_pax = pd.read_excel(uploaded)
    st.dataframe(planner.df_pax.head())

# 3. ANALISI
if not planner.df_pax.empty and st.session_state.sedi_custom:
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.info("### SCENARIO A")
        sedi_a = st.multiselect("Sedi Scenario A", list(st.session_state.sedi_custom.keys()), key="sa")
        conf_a = {s: st.number_input(f"Giorni a {s}", 1, 3, 1, key=f"ga{s}") for s in sedi_a}
        res_a, map_a, tab_a = planner.analizza(conf_a, r_km, 30, 130, v_uomo)
        
    with col_b:
        st.error("### SCENARIO B")
        sedi_b = st.multiselect("Sedi Scenario B", list(st.session_state.sedi_custom.keys()), key="sb")
        conf_b = {s: st.number_input(f"Giorni a {s}", 1, 3, 1, key=f"gb{s}") for s in sedi_b}
        res_b, map_b, tab_b = planner.analizza(conf_b, r_km, 30, 130, v_uomo)

    if res_a and res_b:
        st.divider()
        diff_gg = res_b['gg'] - res_a['gg']
        st.metric("Tempo guadagnato con Scenario A", f"{diff_gg} giornate uomo", delta=f"Risparmio produttività: €{diff_gg*v_uomo:,.0f}")
        
        if map_a:
            st.subheader("🗺️ Mappa Scenario A")
            df_map = pd.DataFrame(map_a)
            st.pydeck_chart(pdk.Deck(
                map_style=None,
                initial_view_state=pdk.ViewState(latitude=42, longitude=12, zoom=5),
                layers=[
                    pdk.Layer("ArcLayer", df_map, get_source_position=["lon_o", "lat_o"], get_target_position=["lon_d", "lat_d"],
                              get_source_color=[0, 128, 255, 160], get_target_color=[255, 128, 0, 160], get_width=3)
                ]
            ))
