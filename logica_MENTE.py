import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
from fpdf import FPDF
import io
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# --- CONFIGURAZIONE ---
st.set_page_config(page_title="Global Training Optimizer PRO 2.0", layout="wide")
geolocator = Nominatim(user_agent="training_optimizer_v2")

# --- FUNZIONI DI SERVIZIO ---
@st.cache_data
def get_coords(citta):
    try:
        location = geolocator.geocode(citta, timeout=10)
        if location:
            return (float(location.latitude), float(location.longitude))
    except:
        return None
    return None

def calcola_km(orig_coords, dest_coords):
    if not orig_coords or not dest_coords: return 0
    dist_lineare = geodesic(orig_coords, dest_coords).km
    return int(dist_lineare * 1.25) # Fattore correttivo stradale

# --- CLASSE LOGICA MIGLIORATA ---
class GlobalTrainingPlanner:
    def __init__(self):
        if 'sedi_custom' not in st.session_state:
            st.session_state.sedi_custom = {}
        self.df_pax = pd.DataFrame()

    def analizza(self, sedi_config, r_km, d_pranzo, c_notte, v_uomo):
        if self.df_pax.empty or not sedi_config:
            return None, [], []

        tot_vivi = 0
        tot_gg_persi = 0
        mappa_data = []
        tabella_dettaglio = []
        
        relatori = self.df_pax[self.df_pax['ruolo'].str.contains('relatore', case=False, na=False)]
        partecipanti = self.df_pax[~self.df_pax['ruolo'].str.contains('relatore', case=False, na=False)]

        # 1. LOGICA PARTECIPANTI (Vanno alla sede più vicina)
        sedi_nomi = list(sedi_config.keys())
        for _, row in partecipanti.iterrows():
            coords_pax = get_coords(row['citta'])
            if not coords_pax: continue
            
            distanze = {s: calcola_km(coords_pax, st.session_state.sedi_custom[s]['lat_long']) for s in sedi_nomi}
            sede_opt = min(distanze, key=distanze.get)
            km = distanze[sede_opt]
            gg_training = sedi_config[sede_opt]
            
            # Calcolo costi e giorni
            serve_pernotto = km > 350 or any(x in row['citta'].lower() for x in ["sicilia", "sardegna", "cagliari", "palermo"])
            costo_viaggio = km * 2 * r_km
            costo_pax = costo_viaggio + (d_pranzo * gg_training) + (c_notte * gg_training if serve_pernotto else 0)
            gg_persi = gg_training + (2 if serve_pernotto else 1)
            
            tot_vivi += costo_pax
            tot_gg_persi += gg_persi
            
            c_dest = st.session_state.sedi_custom[sede_opt]['lat_long']
            mappa_data.append({
                "nome": row['nome'], "orig": row['citta'], "dest": sede_opt,
                "lat_o": coords_pax[0], "lon_o": coords_pax[1],
                "lat_d": c_dest[0], "lon_d": c_dest[1], "tipo": "Partecipante"
            })
            tabella_dettaglio.append({
                "Ruolo": "Pax", "Nome": row['nome'], "Sede": sede_opt, "Km A/R": km*2, "Pernotto": "Sì" if serve_pernotto else "No", "Costo (€)": round(costo_pax, 2), "Gg Persi": gg_persi
            })

        # 2. LOGICA RELATORI (Viaggiano per TUTTE le sedi dello scenario)
        for _, row in relatori.iterrows():
            coords_rel = get_coords(row['citta'])
            if not coords_rel: continue
            for s_nome in sedi_nomi:
                c_sede = st.session_state.sedi_custom[s_nome]['lat_long']
                km_rel = calcola_km(coords_rel, c_sede)
                gg_rel = sedi_config[s_nome]
                
                costo_r = (km_rel * 2 * r_km) + (d_pranzo * gg_rel) + (c_notte * gg_rel) # Relatori pernottano quasi sempre
                tot_vivi += costo_r
                tot_gg_persi += (gg_rel + 1)
                
                mappa_data.append({
                    "nome": f"{row['nome']} (REL)", "orig": row['citta'], "dest": s_nome,
                    "lat_o": coords_rel[0], "lon_o": coords_rel[1],
                    "lat_d": c_sede[0], "lon_d": c_sede[1], "tipo": "Relatore"
                })

        # 3. COSTI FISSI SALE
        for s in sedi_nomi: tot_vivi += st.session_state.sedi_custom[s]['costo']

        res = {"vivi": tot_vivi, "gg": tot_gg_persi, "impatto": tot_gg_persi * v_uomo}
        res["totale"] = res["vivi"] + res["impatto"]
        return res, mappa_data, tabella_dettaglio

# --- UI STREAMLIT ---
planner = GlobalTrainingPlanner()
st.title("📊 AI Training Strategy Optimizer 2.0")

# Sidebar
st.sidebar.header("⚙️ Parametri Economici")
r_km = st.sidebar.slider("Rimborso KM (€)", 0.20, 0.80, 0.44)
v_uomo = st.sidebar.number_input("Valore Giornata Uomo (€)", value=500)

# 1. SEDI
st.subheader("1️⃣ Configura Sedi Disponibili")
with st.expander("Aggiungi Sede (Esempi: Firenze, Falconara Marittima, Roma, Cantù, Salerno)"):
    c1, c2, c3 = st.columns([2,1,2])
    c_nome = c1.text_input("Città")
    c_costo = c2.number_input("Costo Sala (€)", 0)
    if st.button("Aggiungi Sede"):
        coo = get_coords(c_nome)
        if coo:
            st.session_state.sedi_custom[c_nome] = {"lat_long": coo, "costo": c_costo}
            st.success(f"{c_nome} registrata.")

# 2. PARTECIPANTI
st.subheader("2️⃣ Caricamento Partecipanti")
uploaded = st.file_uploader("Carica Excel (colonne: nome, citta, ruolo)", type="xlsx")
if uploaded:
    planner.df_pax = pd.read_excel(uploaded)
    planner.df_pax.columns = planner.df_pax.columns.str.lower()
    st.dataframe(planner.df_pax.head(), use_container_width=True)

# 3. ANALISI COMPARATIVA
if not planner.df_pax.empty and st.session_state.sedi_custom:
    st.divider()
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.info("### SCENARIO A (es. 3 Eventi)")
        sedi_a = st.multiselect("Sedi A", list(st.session_state.sedi_custom.keys()), key="sa")
        conf_a = {s: st.number_input(f"Giorni a {s}", 1, 3, 1, key=f"ga{s}") for s in sedi_a}
        res_a, map_a, tab_a = planner.analizza(conf_a, r_km, 30, 130, v_uomo)
        
    with col_b:
        st.error("### SCENARIO B (es. 2 Eventi)")
        sedi_b = st.multiselect("Sedi B", list(st.session_state.sedi_custom.keys()), key="sb")
        conf_b = {s: st.number_input(f"Giorni a {s}", 1, 3, 1, key=f"gb{s}") for s in sedi_b}
        res_b, map_b, tab_b = planner.analizza(conf_b, r_km, 30, 130, v_uomo)

    if res_a and res_b:
        st.divider()
        # CRUSCOTTO DECISIONALE
        c1, c2, c3 = st.columns(3)
        diff_gg = res_b['gg'] - res_a['gg']
        diff_euro = res_b['totale'] - res_a['totale']
        
        c1.metric("Giornate Lavoro Guadagnate (A vs B)", f"{diff_gg} gg", delta=f"{diff_gg} risparmiati")
        c2.metric("Risparmio Economico Totale (A vs B)", f"€ {diff_euro:,.2f}")
        c3.write(f"**Conclusione:** Lo Scenario A permette di recuperare **{diff_gg} giornate** di attività commerciale, che equivalgono a circa **€ {diff_gg * v_uomo:,.2f}** di fatturato potenziale salvato.")

        # MAPPA (FIXED)
        st.subheader("🗺️ Mappa Spostamenti (Scenario A)")
        df_map = pd.DataFrame(map_a)
        if not df_map.empty:
            st.pydeck_chart(pdk.Deck(
                map_style=None, # Rimuove dipendenza da Mapbox token
                initial_view_state=pdk.ViewState(latitude=42, longitude=12, zoom=5, pitch=45),
                layers=[
                    pdk.Layer(
                        "ArcLayer", df_map,
                        get_source_position=["lon_o", "lat_o"], get_target_position=["lon_d", "lat_d"],
                        get_source_color=[0, 100, 255, 150], get_target_color=[255, 100, 0, 150],
                        get_width=3,
                    ),
                    pdk.Layer(
                        "ScatterplotLayer", df_map,
                        get_position=["lon_o", "lat_o"],
                        get_color="[200, 30, 0]" if "Relatore" in df_map['tipo'].values else "[0, 100, 200]",
                        get_radius=15000,
                    )
                ],
                tooltip={"text": "{nome}\nDa: {orig}\nA: {dest}"}
            ))

        st.subheader("📊 Dettaglio Analisi Costi Auto")
        st.dataframe(pd.DataFrame(tab_a), use_container_width=True)
