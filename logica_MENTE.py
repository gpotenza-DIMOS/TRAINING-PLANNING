import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from fpdf import FPDF
import io
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from itertools import combinations

# ---------------------- CONFIGURAZIONE ----------------------
st.set_page_config(page_title="Global Training Optimizer PRO", layout="wide")
geolocator = Nominatim(user_agent="training_optimizer_pro")

# ---------------------- FUNZIONI ----------------------
@st.cache_data
def get_coords(citta):
    """Restituisce coordinate GPS di qualsiasi città."""
    try:
        location = geolocator.geocode(citta, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except:
        return None
    return None

def calcola_km(orig_coords, dest_coords):
    """Calcola km stimati tra due coordinate GPS con fattore stradale 1.25"""
    dist_lineare = geodesic(orig_coords, dest_coords).km
    return int(dist_lineare * 1.25)

def car_pooling_auto(df_map, max_per_auto=2):
    """Raggruppa partecipanti vicini per car pooling semplice"""
    gruppi = []
    df_map_copy = df_map.copy()
    df_map_copy = df_map_copy.reset_index(drop=True)
    while not df_map_copy.empty:
        base = df_map_copy.iloc[0]
        gruppo = [base['nome']]
        df_map_copy = df_map_copy.drop(0).reset_index(drop=True)
        for idx, row in df_map_copy.iterrows():
            if len(gruppo) < max_per_auto:
                gruppo.append(row['nome'])
        df_map_copy = df_map_copy.drop(df_map_copy.index[:len(gruppo)-1]).reset_index(drop=True)
        gruppi.append(gruppo)
    return gruppi

# ---------------------- CLASSE PRINCIPALE ----------------------
class GlobalTrainingPlanner:
    def __init__(self):
        if 'sedi_custom' not in st.session_state:
            st.session_state.sedi_custom = {}  # Dizionario sedi
        self.df_pax = pd.DataFrame()
        self.df_relat = pd.DataFrame()

    def analizza(self, sedi_config, r_km, d_pranzo, c_notte, v_uomo, fattore_volo=1.0):
        """Analizza scenario e calcola costi, giorni persi e mappa"""
        if self.df_pax.empty or not sedi_config:
            return None, [], []

        tot_vivi = 0
        tot_gg_persi = 0
        mappa = []
        tabella = []

        relatori = self.df_pax[self.df_pax['ruolo'].str.contains('Relatore', case=False, na=False)]
        partecipanti = self.df_pax[~self.df_pax['ruolo'].str.contains('Relatore', case=False, na=False)]
        sedi_nomi = list(sedi_config.keys())

        for _, row in partecipanti.iterrows():
            coords_pax = get_coords(row['citta'])
            if not coords_pax:
                continue

            # Sede più vicina
            distanze_sedi = {s: calcola_km(coords_pax, st.session_state.sedi_custom[s]['lat_long']) for s in sedi_nomi}
            sede_opt = min(distanze_sedi, key=distanze_sedi.get)
            km = distanze_sedi[sede_opt]
            gg_training = sedi_config[sede_opt]

            # Determina se serve pernottamento
            serve_pernotto = km > 400 or any(x in row['citta'].lower() for x in ["sicilia", "sardegna", "palermo", "cagliari"])
            
            # Costi trasporto
            costo_viaggio = km * 2 * r_km
            if serve_pernotto:
                # Simula volo/traghetto per isole
                if any(x in row['citta'].lower() for x in ["palermo", "cagliari"]):
                    costo_viaggio = costo_viaggio * fattore_volo
            costo_pax = costo_viaggio + (d_pranzo * gg_training)
            if serve_pernotto:
                costo_pax += c_notte * gg_training

            gg_persi = gg_training + (2 if serve_pernotto else 1)
            tot_vivi += costo_pax
            tot_gg_persi += gg_persi

            c_dest = st.session_state.sedi_custom[sede_opt]['lat_long']
            mappa.append({
                "nome": row['nome'], "orig": row['citta'], "dest": sede_opt,
                "lat_o": coords_pax[0], "lon_o": coords_pax[1],
                "lat_d": c_dest[0], "lon_d": c_dest[1],
                "tipo": "Partecipante",
                "costo": round(costo_pax,2), "giorni": gg_persi
            })
            tabella.append({
                "Nome": row['nome'], "Partenza": row['citta'], "Sede": sede_opt,
                "Km A/R": km*2, "Costo (€)": round(costo_pax, 2), "Gg Lavoro Persi": gg_persi
            })

        # Aggiungi costi sale
        for s in sedi_nomi:
            tot_vivi += st.session_state.sedi_custom[s]['costo']

        res = {"vivi": tot_vivi, "gg": tot_gg_persi, "impatto": tot_gg_persi*v_uomo}
        res["totale"] = res["vivi"] + res["impatto"]
        return res, mappa, tabella

    def genera_pdf(self, tabella, scenario_name):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Report Scenario: {scenario_name}", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", '', 10)
        for r in tabella:
            pdf.cell(0, 6, f"{r['Nome']} - {r['Partenza']} -> {r['Sede']} | Km: {r['Km A/R']} | Costo: €{r['Costo (€)']} | Giorni Persi: {r['Gg Lavoro Persi']}", ln=True)
        return pdf

# ---------------------- INTERFACCIA ----------------------
planner = GlobalTrainingPlanner()
st.title("🌍 AI Global Training Optimizer PRO - Enterprise")

# Sidebar: Parametri economici
st.sidebar.header("💰 Parametri Economici")
r_km = st.sidebar.slider("Rimborso KM (€)", 0.10, 1.0, 0.44)
v_uomo = st.sidebar.number_input("Valore Giorno/Uomo (€)", value=500)
d_pranzo = st.sidebar.number_input("Costo pranzo/giorno (€)", 0, 100, 30)
c_notte = st.sidebar.number_input("Costo notte (€)", 0, 300, 130)
fattore_volo = st.sidebar.number_input("Fattore stimato volo/traghetto", 1.0, 5.0, 1.5)

# --- 1. Configurazione Sedi ---
st.subheader("1️⃣ Configurazione Sedi Training")
with st.expander("📍 Aggiungi qualsiasi sede con note e indirizzi"):
    col1, col2, col3 = st.columns([2,1,2])
    c_input = col1.text_input("Città sede")
    c_costo = col2.number_input("Costo sala (€)", value=0)
    c_note = col3.text_input("Note/Indirizzo")
    if st.button("Registra Sede"):
        coords = get_coords(c_input)
        if coords:
            st.session_state.sedi_custom[c_input] = {"costo": c_costo, "note": c_note, "lat_long": coords}
            st.success(f"Sede {c_input} registrata con successo!")
        else:
            st.error("Città non trovata.")

if st.session_state.sedi_custom:
    st.write("Sedi attive:", ", ".join(st.session_state.sedi_custom.keys()))

# --- 2. Upload partecipanti ---
st.subheader("2️⃣ Partecipanti")
uploaded = st.file_uploader("Carica Excel/CSV con colonne 'citta', 'nome', 'ruolo'", type=["xlsx", "csv"])
if uploaded:
    if uploaded.name.endswith('.csv'):
        planner.df_pax = pd.read_csv(uploaded)
    else:
        planner.df_pax = pd.read_excel(uploaded)
    st.write(planner.df_pax.head())

# --- 3. Analisi scenari multipli ---
if not planner.df_pax.empty and st.session_state.sedi_custom:
    st.divider()
    col_a, col_b = st.columns(2)

    # Scenario A
    with col_a:
        st.write("### Scenario A")
        scelta_a = st.multiselect("Seleziona Sedi A", list(st.session_state.sedi_custom.keys()), key="sel_a")
        config_a = {s: st.number_input(f"Giorni a {s} (A)", 1, 5, 1, key=f"ga_{s}") for s in scelta_a}
        res_a, map_a, tab_a = planner.analizza(config_a, r_km, d_pranzo, c_notte, v_uomo, fattore_volo)
        if res_a:
            st.metric("Totale Scenario A", f"€{res_a['totale']:,.0f}")

    # Scenario B
    with col_b:
        st.write("### Scenario B")
        scelta_b = st.multiselect("Seleziona Sedi B", list(st.session_state.sedi_custom.keys()), key="sel_b")
        config_b = {s: st.number_input(f"Giorni a {s} (B)", 1, 5, 1, key=f"gb_{s}") for s in scelta_b}
        res_b, map_b, tab_b = planner.analizza(config_b, r_km, d_pranzo, c_notte, v_uomo, fattore_volo)
        if res_b:
            st.metric("Totale Scenario B", f"€{res_b['totale']:,.0f}")

    # --- 4. Visualizzazione Mappa ---
    st.subheader("🗺️ Visualizzazione Logistica Scenario A")
    if map_a:
        df_map = pd.DataFrame(map_a)
        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(latitude=42, longitude=12, zoom=5),
            layers=[
                pdk.Layer(
                    "ArcLayer",
                    df_map,
                    get_source_position=["lon_o", "lat_o"],
                    get_target_position=["lon_d", "lat_d"],
                    get_source_color=[0, 0, 255, 100],
                    get_target_color=[0, 255, 0, 100],
                    get_width=2
                ),
                pdk.Layer(
                    "ScatterplotLayer",
                    df_map,
                    get_position=["lon_o", "lat_o"],
                    get_radius=10000,
                    get_color=[255, 0, 0],
                    pickable=True
                ),
                pdk.Layer(
                    "ScatterplotLayer",
                    df_map,
                    get_position=["lon_d", "lat_d"],
                    get_radius=15000,
                    get_color=[0, 255, 0],
                    pickable=True
                )
            ],
            tooltip={"text": "{nome}\nDa: {orig}\nA: {dest}\nCosto: €{costo}\nGiorni Persi: {giorni}"}
        ))

    st.subheader("📊 Tabella Dettaglio Scenario A")
    if tab_a:
        st.dataframe(pd.DataFrame(tab_a))

    # --- 5. Export PDF ---
    if tab_a:
        pdf = planner.genera_pdf(tab_a, "Scenario A")
        pdf_buffer = io.BytesIO()
        pdf.output(pdf_buffer)
        st.download_button("📥 Scarica Report PDF Scenario A", data=pdf_buffer, file_name="ScenarioA_Report.pdf", mime="application/pdf")
