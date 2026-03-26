import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from fpdf import FPDF
import io
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Global Training Optimizer PRO", layout="wide")
geolocator = Nominatim(user_agent="training_optimizer_pro")

# --- FUNZIONI UTILI ---
@st.cache_data
def get_coords(citta):
    """Ottiene coordinate GPS di qualsiasi città nel mondo."""
    try:
        location = geolocator.geocode(citta, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except:
        return None
    return None

def calcola_km(orig_coords, dest_coords):
    """Calcola km tra due punti GPS con fattore correttivo stradale (1.25)."""
    dist_lineare = geodesic(orig_coords, dest_coords).km
    return int(dist_lineare * 1.25) 

# --- CLASSE PRINCIPALE ---
class GlobalTrainingPlanner:
    def __init__(self):
        if 'sedi_custom' not in st.session_state:
            st.session_state.sedi_custom = {}  # Dizionario sedi
        self.df_pax = pd.DataFrame()

    def analizza(self, sedi_config, r_km, d_pranzo, c_notte, v_uomo):
        if self.df_pax.empty or not sedi_config:
            return None, [], []

        tot_vivi = 0
        tot_gg_persi = 0
        mappa = []
        tabella = []
        
        # Divisione Relatori / Partecipanti
        relatori = self.df_pax[self.df_pax['ruolo'].str.contains('relatore', case=False, na=False)]
        partecipanti = self.df_pax[~self.df_pax['ruolo'].str.contains('relatore', case=False, na=False)]

        sedi_nomi = list(sedi_config.keys())
        
        for _, row in partecipanti.iterrows():
            coords_pax = get_coords(row['citta'])
            if not coords_pax:
                continue
            
            # Sede più vicina
            distanze_sedi = {}
            for s_nome in sedi_nomi:
                c_sede = st.session_state.sedi_custom[s_nome]['lat_long']
                distanze_sedi[s_nome] = calcola_km(coords_pax, c_sede)
            
            sede_opt = min(distanze_sedi, key=distanze_sedi.get)
            km = distanze_sedi[sede_opt]
            gg_training = sedi_config[sede_opt]
            
            # Pernotto / costo
            serve_pernotto = km > 400 or any(x in row['citta'].lower() for x in ["sicilia", "sardegna", "palermo", "cagliari"])
            costo_viaggio = km * 2 * r_km
            costo_pax = costo_viaggio + (d_pranzo * gg_training)
            if serve_pernotto:
                costo_pax += (c_notte * gg_training)
            
            gg_persi = gg_training + (2 if serve_pernotto else 1)
            
            tot_vivi += costo_pax
            tot_gg_persi += gg_persi
            
            c_dest = st.session_state.sedi_custom[sede_opt]['lat_long']
            mappa.append({
                "nome": row['nome'], "orig": row['citta'], "dest": sede_opt,
                "lat_o": coords_pax[0], "lon_o": coords_pax[1],
                "lat_d": c_dest[0], "lon_d": c_dest[1], "colore": [0, 0, 255]
            })
            tabella.append({
                "Nome": row['nome'], "Partenza": row['citta'], "Sede": sede_opt,
                "Km A/R": km*2, "Costo (€)": round(costo_pax, 2), "Gg Lavoro Persi": gg_persi
            })

        # Costi fissi sale
        for s in sedi_nomi:
            tot_vivi += st.session_state.sedi_custom[s]['costo']

        res = {"vivi": tot_vivi, "gg": tot_gg_persi, "impatto": tot_gg_persi * v_uomo}
        res["totale"] = res["vivi"] + res["impatto"]
        return res, mappa, tabella

# --- INTERFACCIA ---
planner = GlobalTrainingPlanner()
st.title("🌍 AI Global Training Optimizer 2.0")

# Sidebar - Parametri economici
st.sidebar.header("💰 Parametri Economici")
r_km = st.sidebar.slider("Rimborso KM (€)", 0.10, 1.0, 0.44)
v_uomo = st.sidebar.number_input("Valore Giorno/Uomo (€)", value=500)
d_pranzo = st.sidebar.number_input("Costo Pranzo (€)", value=30)
c_notte = st.sidebar.number_input("Costo Pernotto (€)", value=130)

# 1. Configurazione sedi
st.subheader("1️⃣ Configurazione Sedi Training")
with st.expander("📍 Aggiungi qualsiasi città nel mondo come sede"):
    col1, col2, col3 = st.columns([2,1,2])
    c_input = col1.text_input("Inserisci Città (es: Firenze, London, New York)")
    c_costo = col2.number_input("Costo Sala (€)", value=0)
    c_note = col3.text_input("Note/Indirizzo")
    if st.button("Registra Sede"):
        coords = get_coords(c_input)
        if coords:
            st.session_state.sedi_custom[c_input] = {"costo": c_costo, "note": c_note, "lat_long": coords}
            st.success(f"Sede {c_input} registrata con successo!")
        else:
            st.error("Città non trovata. Riprova.")

if st.session_state.sedi_custom:
    st.write("Sedi attive:", ", ".join(st.session_state.sedi_custom.keys()))

# 2. Input partecipanti
st.subheader("2️⃣ Partecipanti")
uploaded = st.file_uploader("Carica Excel/CSV con colonne 'citta', 'nome', 'ruolo'", type=["xlsx", "csv"])
if uploaded:
    # Lettura file
    if uploaded.name.endswith('.csv'):
        planner.df_pax = pd.read_csv(uploaded)
    else:
        planner.df_pax = pd.read_excel(uploaded)
    
    # Normalizza intestazioni
    planner.df_pax.columns = planner.df_pax.columns.str.strip().str.lower()
    
    # Controllo colonne obbligatorie
    richieste = ['citta', 'nome', 'ruolo']
    if not all(col in planner.df_pax.columns for col in richieste):
        st.error(f"File mancante colonne obbligatorie: {richieste}")
    else:
        st.success("File caricato correttamente!")
        st.write(planner.df_pax.head())

# 3. Analisi comparativa
if not planner.df_pax.empty and st.session_state.sedi_custom:
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.write("### Scenario A")
        scelta_a = st.multiselect("Seleziona Sedi A", list(st.session_state.sedi_custom.keys()))
        config_a = {s: st.number_input(f"Giorni a {s} (A)", 1, 5, 1) for s in scelta_a}
        res_a, map_a, tab_a = planner.analizza(config_a, r_km, d_pranzo, c_notte, v_uomo)
        if res_a:
            st.metric("Totale Scenario A", f"€{res_a['totale']:,.0f}")

    with col_b:
        st.write("### Scenario B")
        scelta_b = st.multiselect("Seleziona Sedi B", list(st.session_state.sedi_custom.keys()))
        config_b = {s: st.number_input(f"Giorni a {s} (B)", 1, 5, 1) for s in scelta_b}
        res_b, map_b, tab_b = planner.analizza(config_b, r_km, d_pranzo, c_notte, v_uomo)
        if res_b:
            st.metric("Totale Scenario B", f"€{res_b['totale']:,.0f}")

    # Mappa
    if map_a:
        st.write("### 🗺️ Visualizzazione Logistica")
        df_map = pd.DataFrame(map_a)
        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(latitude=42, longitude=12, zoom=5),
            layers=[
                pdk.Layer(
                    "ArcLayer", df_map,
                    get_source_position=["lon_o", "lat_o"],
                    get_target_position=["lon_d", "lat_d"],
                    get_source_color=[0,0,255,100],
                    get_target_color=[0,255,0,100],
                    get_width=2
                ),
                pdk.Layer(
                    "ScatterplotLayer", df_map,
                    get_position=["lon_o", "lat_o"],
                    get_radius=10000,
                    get_color=[255,0,0]
                )
            ]
        ))
        st.write("### 📊 Dettaglio Costi")
        st.dataframe(pd.DataFrame(tab_a))
