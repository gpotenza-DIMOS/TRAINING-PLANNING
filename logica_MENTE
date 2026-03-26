import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk # Per mappe avanzate con linee
from fpdf import FPDF # Per generare il PDF
import io

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(page_title="Training Planning AI Optimizer PRO", layout="wide")

# --- DATABASE GEOGRAFICO INTERNO (Per non semplificare e non usare API esterne) ---
# Mappa le città di partenza alle loro coordinate GPS
COORDINATE_CITTA = {
    "Torino": (45.07, 7.68), "Cantù": (45.73, 9.12), "Pavia": (45.18, 9.15),
    "Udine": (46.06, 13.23), "Padova": (45.40, 11.87), "Trento": (46.06, 11.12),
    "Modena": (44.64, 10.92), "Firenze": (43.82, 11.13), "Ancona": (43.61, 13.51),
    "Roma": (41.89, 12.49), "Cagliari": (39.22, 9.11), "Pescara": (42.46, 14.21),
    "Napoli": (40.85, 14.26), "Foggia": (41.46, 15.54), "Catanzaro": (38.90, 16.59),
    "Palermo": (38.11, 13.36), "Milano": (45.46, 9.18), "Brescia": (45.53, 10.21),
    "Altamura": (40.82, 16.55), "Falconara Marittima": (43.62, 13.39), "Salerno": (40.67, 14.78)
}

# --- CLASSE ORIGINALE (NON SEMPLIFICATA) ---
class TrainingPlanner:
    def __init__(self):
        # Database delle sedi e costi fissi (ESATTAMENTE COME IL TUO)
        self.sedi_aziendali = {
            "Firenze": {"costo_sala": 0, "lat_long": (43.82, 11.13)},
            "Falconara Marittima": {"costo_sala": 0, "lat_long": (43.62, 13.39)},
            "Roma": {"costo_sala": 225, "lat_long": (41.89, 12.49)}, 
            "Cantù": {"costo_sala": 0, "lat_long": (45.73, 9.12)},
            "Salerno": {"costo_sala": 400, "lat_long": (40.67, 14.78)}
        }
        self.df_pax = pd.DataFrame()

    def calcola_distanza_approssimativa(self, citta_orig, citta_dest):
        # Matrice distanze originale
        distanze = {
            ("Torino", "Cantù"): 320, ("Udine", "Cantù"): 700, ("Palermo", "Salerno"): 800,
            ("Ancona", "Firenze"): 400, ("Brescia", "Cantù"): 120, ("Modena", "Cantù"): 400,
            ("Milano", "Cantù"): 80, ("Roma", "Salerno"): 520, ("Cagliari", "Roma"): 600,
            ("Napoli", "Salerno"): 110, ("Foggia", "Salerno"): 350, ("Catanzaro", "Salerno"): 750,
        }
        return distanze.get((citta_orig, citta_dest), distanze.get((citta_dest, citta_orig), 500))

    def analizza_scenario_web(self, sedi_scelte, giorni_training, r_km, d_pranzo, c_notte, v_uomo):
        if self.df_pax.empty or not sedi_scelte:
            return None, []

        totale_costi_vivi = 0
        totale_giornate_perse = 0
        dati_mappa = [] # Nuova lista per tracciare i percorsi
        
        relatori = self.df_pax[self.df_pax['ruolo'].str.contains('Relatore', case=False, na=False)]
        partecipanti = self.df_pax[~self.df_pax['ruolo'].str.contains('Relatore', case=False, na=False)]
        
        # Suddivisione logica partecipanti (Esattamente come originale)
        chunks = np.array_split(partecipanti, len(sedi_scelte))
        
        for i, sede in enumerate(sedi_scelte):
            costo_sala = self.sedi_aziendali[sede]['costo_sala']
            totale_costi_vivi += costo_sala
            coords_dest = self.sedi_aziendali[sede]['lat_long']
            
            pax_in_sede = chunks[i]
            for _, row in pax_in_sede.iterrows():
                # --- LOGICA CALCOLO ORIGINALE ---
                km = self.calcola_distanza_approssimativa(row['citta'], sede)
                costo_viaggio = km * r_km
                isole = any(isla in str(row['citta']) for isla in ["Palermo", "Cagliari", "Sardegna", "Sicilia"])
                serve_pernotto = km > 450 or isole
                costo_pax = costo_viaggio + d_pranzo
                if serve_pernotto: costo_pax += c_notte
                
                totale_costi_vivi += costo_pax
                totale_giornate_perse += giorni_training

                # --- RACCOLTA DATI MAPPA (NUOVO) ---
                coords_orig = COORDINATE_CITTA.get(row['citta'])
                if coords_orig:
                    dati_mappa.append({
                        "nome": row['nome'],
                        "citta_orig": row['citta'],
                        "sede_dest": sede,
                        "lat_orig": coords_orig[0], "lon_orig": coords_orig[1],
                        "lat_dest": coords_dest[0], "lon_dest": coords_dest[1],
                        "colore": [255, 0, 0] if "Relatore" in row['ruolo'] else [0, 0, 255]
                    })
                
        # Costi relatori (Originale)
        costo_viaggio_relatori = len(relatori) * len(sedi_scelte) * 150 
        totale_costi_vivi += costo_viaggio_relatori
        impatto_economico = totale_giornate_perse * v_uomo
        
        risultati = {
            "vivi": totale_costi_vivi, "giornate": totale_giornate_perse,
            "impatto": impatto_economico, "totale": totale_costi_vivi + impatto_economico,
            "n_pax": len(partecipanti), "n_sedi": len(sedi_scelte)
        }
        return risultati, dati_mappa

# --- FUNZIONE GENERAZIONE PDF (NUOVA) ---
def genera_pdf(res_a, res_b, params):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "Report di Pianificazione Training Aziendale", 0, 1, 'C')
    pdf.ln(10)
    
    # Parametri
    pdf.set_font("Arial", '', 12)
    pdf.cell(100, 10, f"Parametri: Rimborso KM: {params['r_km']}e/km | Valore Giorno: {params['v_uomo']}e")
    pdf.ln(15)

    # Tabella Comparativa
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(60, 10, "Voce", 1)
    pdf.cell(65, 10, "Scenario A (Ottimizzato)", 1)
    pdf.cell(65, 10, "Scenario B (Ridotto)", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 12)
    linee = [
        ("Costi Vivi Trasferte", f"{res_a['vivi']:,.2f} e", f"{res_b['vivi']:,.2f} e"),
        ("Giornate Lavoro Perse", f"{res_a['giornate']}", f"{res_b['giornate']}"),
        ("Costo Opportunita", f"{res_a['impatto']:,.2f} e", f"{res_b['impatto']:,.2f} e"),
        ("INVESTIMENTO TOTALE", f"{res_a['totale']:,.2f} e", f"{res_b['totale']:,.2f} e")
    ]
    for n, a, b in linee:
        pdf.cell(60, 10, n, 1)
        pdf.cell(65, 10, a, 1)
        pdf.cell(65, 10, b, 1)
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# --- LOGICA APP WEB STREAMLIT ---
planner = TrainingPlanner()
st.title("📊 Training Planning AI Optimizer PRO")

# Sidebar
st.sidebar.header("⚙️ Parametri Economici")
params = {
    'r_km': st.sidebar.slider("Rimborso KM (€)", 0.20, 0.70, 0.35),
    'd_pranzo': st.sidebar.number_input("Costo Pranzo (€)", value=30.0),
    'c_notte': st.sidebar.number_input("Costo Pernotto + Cena (€)", value=120.0),
    'v_uomo': st.sidebar.number_input("Valore Giornata Uomo (€)", value=250.0)
}

uploaded_file = st.file_uploader("Carica Excel Partecipanti", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = ['citta', 'nome', 'ruolo', 'sessione', 'pernotto', 'km']
    planner.df_pax = df
    st.success(f"Caricate {len(df)} persone.")

if not planner.df_pax.empty:
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Scenario A (Ottimizzato)")
        sedi_a = st.multiselect("Sedi A", list(planner.sedi_aziendali.keys()), default=["Cantù", "Falconara Marittima", "Salerno"], key="sa")
        giorni_a = st.number_input("Giorni A", 1, 5, 1, key="ga")
        res_a, map_a = planner.analizza_scenario_web(sedi_a, giorni_a, **params)
        if res_a: st.metric("Totale A", f"€{res_a['totale']:,.2f}")

    with col2:
        st.subheader("Scenario B (Ridotto)")
        sedi_b = st.multiselect("Sedi B", list(planner.sedi_aziendali.keys()), default=["Firenze", "Roma"], key="sb")
        giorni_b = st.number_input("Giorni B", 1, 5, 2, key="gb")
        res_b, map_b = planner.analizza_scenario_web(sedi_b, giorni_b, **params)
        if res_b: st.metric("Totale B", f"€{res_b['totale']:,.2f}", f"{res_b['totale']-res_a['totale']:,.2f} € vs A", delta_color="inverse")

    # --- SEZIONE MAPPA (NUOVA) ---
    st.divider()
    st.write("### 🗺️ Mappa dei Percorsi Individuali (Scenario A)")
    df_map = pd.DataFrame(map_a)
    
    if not df_map.empty:
        # Layer 1: Punti di partenza (Scatterplot)
        layer_punti = pdk.Layer(
            "ScatterplotLayer", df_map,
            get_position=["lon_orig", "lat_orig"],
            get_color="colore", get_radius=20000, pickable=True,
        )
        
        # Layer 2: Linee di percorso (ArcLayer per effetto scenico o LineLayer per pulizia)
        layer_linee = pdk.Layer(
            "ArcLayer", df_map,
            get_source_position=["lon_orig", "lat_orig"],
            get_target_position=["lon_dest", "lat_dest"],
            get_source_color=[0, 0, 255, 100], get_target_color=[0, 255, 0, 100],
            getWidth=2, pickable=True,
        )

        # Layer 3: Testo (Nome e Cognome a fianco al simbolo)
        # Nota: Pydeck TextLayer richiede un leggero offset per non sovrapporsi al punto
        df_map['lon_text'] = df_map['lon_orig'] + 0.1 
        layer_testo = pdk.Layer(
            "TextLayer", df_map,
            get_position=["lon_text", "lat_orig"],
            get_text="nome", get_size=15, get_color=[0, 0, 0],
            get_alignment_baseline="'bottom'",
        )

        st.pydeck_chart(pdk.Deck(
            map_style="mapbox://styles/mapbox/light-v9",
            initial_view_state=pdk.ViewState(latitude=42.5, longitude=12.5, zoom=5, pitch=40),
            layers=[layer_linee, layer_punti, layer_testo],
            tooltip={"text": "{nome} da {citta_orig} a {sede_dest}"}
        ))
    
    # --- SEZIONE PDF (NUOVA) ---
    st.divider()
    if res_a and res_b:
        pdf_data = genera_pdf(res_a, res_b, params)
        st.download_button(
            label="📩 Scarica Report PDF Finale",
            data=pdf_data,
            file_name="report_pianificazione_training.pdf",
            mime="application/pdf",
        )
