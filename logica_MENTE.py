import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk # Per mappe avanzate con linee
from fpdf import FPDF # Per generare il PDF
import io

# --- CONFIGURAZIONE PAGINA STREAMLIT ---
st.set_page_config(page_title="Training Planning AI Optimizer PRO 2.0", layout="wide")

# --- DATABASE GEOGRAFICO INTERNO (NON SEMPLIFICATO - ESTESO) ---
# Mappa le città di partenza alle loro coordinate GPS. Ho aggiunto città del tuo esempio.
COORDINATE_CITTA = {
    "Torino": (45.07, 7.68), "Cantù": (45.73, 9.12), "Pavia": (45.18, 9.15),
    "Udine": (46.06, 13.23), "Padova": (45.40, 11.87), "Trento": (46.06, 11.12),
    "Modena": (44.64, 10.92), "Firenze": (43.82, 11.13), "Ancona": (43.61, 13.51),
    "Roma": (41.89, 12.49), "Cagliari": (39.22, 9.11), "Pescara": (42.46, 14.21),
    "Napoli": (40.85, 14.26), "Foggia": (41.46, 15.54), "Catanzaro": (38.90, 16.59),
    "Palermo": (38.11, 13.36), "Milano": (45.46, 9.18), "Brescia": (45.53, 10.21),
    "Altamura": (40.82, 16.55), "Falconara Marittima": (43.62, 13.39), "Salerno": (40.67, 14.78),
    "Bergamo": (45.69, 9.67), "Senigallia": (43.71, 13.21), "Veglie": (40.33, 17.96),
    "Ariccia": (41.72, 12.67), "Bologna": (44.49, 11.34) # Aggiunte per test
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
        self.df_pax = pd.DataFrame(columns=['citta', 'nome', 'ruolo', 'origine']) # dataframe vuoto con struttura

    def calcola_distanza_approssimativa(self, citta_orig, citta_dest):
        # Matrice distanze originale
        distanze = {
            ("Torino", "Cantù"): 320, ("Udine", "Cantù"): 700, ("Palermo", "Salerno"): 800,
            ("Ancona", "Firenze"): 400, ("Brescia", "Cantù"): 120, ("Modena", "Cantù"): 400,
            ("Milano", "Cantù"): 80, ("Roma", "Salerno"): 520, ("Cagliari", "Roma"): 600,
            ("Napoli", "Salerno"): 110, ("Foggia", "Salerno"): 350, ("Catanzaro", "Salerno"): 750,
            ("Modena", "Roma"): 380, ("Torino", "Roma"): 700, ("Udine", "Roma"): 600,
            ("Palermo", "Roma"): 800, ("Cagliari", "Roma"): 600,
        }
        return distanze.get((citta_orig, citta_dest), distanze.get((citta_dest, citta_orig), 500))

    def analizza_scenario_web(self, sedi_scelte_config, r_km, d_pranzo, c_notte, v_uomo):
        """
        Versione aggiornata: accetta una configurazione granulare delle sedi (dizionario {sede: giorni})
        """
        sedi_scelte = list(sedi_scelte_config.keys())
        if self.df_pax.empty or not sedi_scelte:
            return None, [], []

        totale_costi_vivi = 0
        totale_giornate_perse = 0
        dati_mappa = []
        dati_tabella_costi = []
        
        # Gestione Relatori: sono presenti a TUTTI gli eventi scelti
        relatori = self.df_pax[self.df_pax['ruolo'].str.contains('Relatore', case=False, na=False)]
        partecipanti = self.df_pax[~self.df_pax['ruolo'].str.contains('Relatore', case=False, na=False)]
        
        # Suddivisione logica partecipanti per le sedi scelte (Esattamente come originale)
        chunks = np.array_split(partecipanti, len(sedi_scelte))
        
        for i, sede in enumerate(sedi_scelte):
            giorni_training_sede = sedi_scelte_config[sede]
            costo_sala = self.sedi_aziendali[sede]['costo_sala']
            totale_costi_vivi += costo_sala
            coords_dest = self.sedi_aziendali[sede]['lat_long']
            
            pax_in_sede = chunks[i]
            for _, row in pax_in_sede.iterrows():
                # --- LOGICA CALCOLO ORIGINALE KM ---
                km = self.calcola_distanza_approssimativa(row['citta'], sede)
                costo_viaggio = km * r_km
                
                # Logica pernotto (Originale)
                isole = any(isla in str(row['citta']) for isla in ["Palermo", "Cagliari", "Sardegna", "Sicilia"])
                serve_pernotto = km > 450 or isole
                costo_pax = costo_viaggio + (d_pranzo * giorni_training_sede)
                if serve_pernotto: 
                    # Consideriamo pernotto e cena per tutti i giorni -1 (rientro l'ultimo giorno)
                    # Ma nel tuo esempio (reunione 9.30-17.00), se km > 450 serve pernotto PRE.
                    # Per non semplificare, usiamo la logica originale, ma estesa ai giorni.
                    costo_pax += (c_notte * (giorni_training_sede)) 
                
                totale_costi_vivi += costo_pax
                # Giornate perse: include giorni training + giorni viaggio se pernotta pre e post
                giornate_perse_pax = giorni_training_sede + (2 if serve_pernotto else 1)
                totale_giornate_perse += giornate_perse_pax

                # --- RACCOLTA DATI MAPPA (NON SEMPLIFICATO) ---
                coords_orig = COORDINATE_CITTA.get(row['citta'])
                if coords_orig:
                    dati_mappa.append({
                        "nome": row['nome'],
                        "citta_orig": row['citta'],
                        "sede_dest": sede,
                        "giorni": giorni_training_sede,
                        "lat_orig": coords_orig[0], "lon_orig": coords_orig[1],
                        "lat_dest": coords_dest[0], "lon_dest": coords_dest[1],
                        "colore": [255, 0, 0] if "Relatore" in row['ruolo'] else [0, 0, 255]
                    })
                    
                # --- RACCOLTA TABELLA COSTI AUTO (NON SEMPLIFICATO) ---
                dati_tabella_costi.append({
                    "Nome": row['nome'],
                    "Città Partenza": row['citta'],
                    "Sede Training": sede,
                    "Km A/R": km,
                    "Costo Viaggio (€)": round(costo_viaggio, 2),
                    "Giorni": giorni_training_sede,
                    "Pernotto Prev": "Sì" if serve_pernotto else "No",
                    "Costo Tot (€)": round(costo_pax, 2)
                })
                
        # Costi relatori (Originale): consideriamo che i relatori viaggiano a TUTTE le sedi
        # Per ogni sede aggiungiamo un costo trasferta standard
        # Ma Bogdan (Relatore, Modena) a Cantù non ha costo viaggio. Gabriele (Relatore, Ancona) a Falconara no.
        # Per non semplificare, calcoliamo km individuali anche per relatori su TUTTE le sedi.
        
        for _, row_r in relatori.iterrows():
            for sede_scelta in sedi_scelte:
                giorni_training_sede = sedi_scelte_config[sede_scelta]
                km_r = self.calcola_distanza_approssimativa(row_r['citta'], sede_scelta)
                costo_viaggio_r = km_r * r_km
                serve_pernotto_r = km_r > 450 or any(x in row_r['citta'] for x in ["Palermo", "Cagliari"])
                
                costo_r = costo_viaggio_r + (d_pranzo * giorni_training_sede)
                if serve_pernotto_r: costo_r += (c_notte * giorni_training_sede)
                
                totale_costi_vivi += costo_r
                # Giornate perse per l'azienda: include i giorni di training.
                giornate_perse_pax_r = giorni_training_sede + (2 if serve_pernotto_r else 1)
                totale_giornate_perse += giornate_perse_pax_r
                
                # Aggiungi a mappa come relatore (colore rosso)
                coords_orig_r = COORDINATE_CITTA.get(row_r['citta'])
                if coords_orig_r:
                     dati_mappa.append({
                        "nome": f"{row_r['nome']} (Relatore)",
                        "citta_orig": row_r['citta'],
                        "sede_dest": sede_scelta,
                        "giorni": giorni_training_sede,
                        "lat_orig": coords_orig_r[0], "lon_orig": coords_orig_r[1],
                        "lat_dest": COORDINATE_CITTA.get(sede_scelta, self.sedi_aziendali[sede_scelta]['lat_long'])[0],
                        "lon_dest": COORDINATE_CITTA.get(sede_scelta, self.sedi_aziendali[sede_scelta]['lat_long'])[1],
                        "colore": [255, 0, 0] # Rosso per Relatore
                    })
        
        impatto_economico = totale_giornate_perse * v_uomo
        
        risultati = {
            "vivi": totale_costi_vivi, "giornate": totale_giornate_perse,
            "impatto": impatto_economico, "totale": totale_costi_vivi + impatto_economico,
            "n_pax_agenti": len(partecipanti), "n_pax_relatori": len(relatori), "n_sedi": len(sedi_scelte)
        }
        return risultati, dati_mappa, dati_tabella_costi

# --- FUNZIONE GENERAZIONE PDF (NON SEMPLIFICATA - ESTESA CON TABELLE) ---
def genera_pdf_report(res_config_a, res_config_b, tab_a, tab_b, params, config_a_n, config_b_n):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, "Report Strategico Pianificazione Training Aziendale PRO", 0, 1, 'C')
    pdf.ln(10)
    
    # 1. PARAMETRI ECONOMICI
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "Parametri di Costo Utilizzati:", 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.cell(190, 7, f"- Rimborso KM Auto media/alta cilindrata: {params['r_km']} €/km", 0, 1)
    pdf.cell(190, 7, f"- Diaria Pranzo: {params['d_pranzo']} €/giorno", 0, 1)
    pdf.cell(190, 7, f"- Costo Pernotto + Cena (convegno/hotel strategic): {params['c_notte']} €/notte", 0, 1)
    pdf.cell(190, 7, f"- Valore Giornata Uomo (Fatturato commerciale perso): {params['v_uomo']} €/giorno", 0, 1)
    pdf.ln(10)

    # 2. TABELLA COMPARATIVA PRINCIPALE
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(60, 10, "Voce", 1)
    pdf.cell(65, 10, f"Scenario A ({config_a_n})", 1)
    pdf.cell(65, 10, f"Scenario B ({config_b_n})", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 11)
    linee = [
        ("N. Sedi sceltetere", f"{res_config_a['n_sedi']}", f"{res_config_b['n_sedi']}"),
        ("Partecipanti Agenti/Tecnici", f"{res_config_a['n_pax_agenti']}", f"{res_config_b['n_pax_agenti']}"),
        ("Costi Vivi Trasferte (€) (Benzina, Sala, Hotel)", f"{res_config_a['vivi']:,.2f}", f"{res_config_b['vivi']:,.2f}"),
        ("Giornate Lavoro Perse Totali", f"{res_config_a['giornate']}", f"{res_config_b['giornate']}"),
        ("Costo Opportunità Produttività (€)", f"{res_a['impatto']:,.2f}", f"{res_b['impatto']:,.2f}"),
        ("INVESTIMENTO TOTALE (€) (Costi vivi + Costo Opp.)", f"{res_config_a['totale']:,.2f}", f"{res_config_b['totale']:,.2f}")
    ]
    for n, a, b in linee:
        pdf.cell(60, 10, n, 1)
        pdf.cell(65, 10, a, 1)
        pdf.cell(65, 10, b, 1)
        pdf.ln()
    pdf.ln(10)
    
    # 3. ANALISI STRATEGICA (Originale)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(190, 10, "Analisi Strategica e Risparmio delle Energie (Esempio)", 0, 1)
    pdf.set_font("Arial", '', 11)
    testo_strategia = """
Nell'ottica di massimizzazione delle energie e risparmio, la scelta del numero di eventi (2 vs 3) è cruciale. L'opzione con 3 eventi strategic (es. Cantù, Falconara, Salerno) riduce drasticamente i chilometri totali percorsi dalla forza vendita e i conseguenti pernottamenti (es. Udine-Cantù invece di Udine-Roma). Tuttavia, questo scenario aumenta i giorni 'morti' per i relatori (Ancona, Brescia, Modena) e i costi di affitto sale (es. Hotel strategico Salerno 300-500e).
L'opzione con 2 eventi (es. Firenze, Roma) centralizza il training, riducendo i costi sale e lo stress dei relatori. Ma come formula primaria spostamento in auto media-alta cilindrata, porta ad un aumento vertiginoso dei km individuali e dei pernottamenti/cene pre e post. In questa configurazione, le giornate uomo di lavoro persi per le vendite salgono notevolmente.
La tabella dei costi auto basata sui km reali qui sotto giustifica economicamente la scelta.
    """
    pdf.multi_cell(190, 7, testo_strategia)
    pdf.ln(10)

    # 4. TABELLA DETTAGLIO COSTI AUTO (Scenario A)
    if tab_a:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 10, "Tabella Costi Auto Dettagliata (Scenario A)", 0, 1)
        pdf.set_font("Arial", 'B', 9)
        # Intestazioni tabella
        headers = ["Nome", "Origine", "Dest", "Km A/R", "€ Viaggio", "Gg", "Pern", "€ Tot"]
        w = [35, 30, 30, 20, 20, 10, 15, 25]
        for i, header in enumerate(headers):
            pdf.cell(w[i], 8, header, 1)
        pdf.ln()
        pdf.set_font("Arial", '', 8)
        # Righe tabella
        for row in tab_a:
            pdf.cell(w[0], 7, row['Nome'], 1)
            pdf.cell(w[1], 7, row['Città Partenza'], 1)
            pdf.cell(w[2], 7, row['Sede Training'], 1)
            pdf.cell(w[3], 7, str(row['Km A/R']), 1, 0, 'R')
            pdf.cell(w[4], 7, str(row['Costo Viaggio (€)']), 1, 0, 'R')
            pdf.cell(w[5], 7, str(row['Giorni']), 1, 0, 'R')
            pdf.cell(w[6], 7, row['Pernotto Prev'], 1, 0, 'C')
            pdf.cell(w[7], 7, str(row['Costo Tot (€)']), 1, 0, 'R')
            pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# --- LOGICA APP WEB STREAMLIT ---
planner = TrainingPlanner()
st.title("📊 Training Planning AI Optimizer PRO 2.0 (Modalità Ibrida)")
st.markdown("""
Questo modulo permette di analizzare scenari di training caricando partecipanti via Excel e/o inserendoli manualmente.
Gestisce costi sale, trasferte e giorni training individuali per sede. **Non semplifica la logica originale**.
""")

# Sidebar
st.sidebar.header("⚙️ Parametri Economici (Esempio)")
params = {
    'r_km': st.sidebar.slider("Rimborso KM (Auto media/alta cilindrata) (€)", 0.20, 0.70, 0.35, help="Considera benzina, autostrade ecc."),
    'd_pranzo': st.sidebar.number_input("Diaria Pranzo (€/giorno)", value=30.0),
    'c_notte': st.sidebar.number_input("Costo Pernotto + Cena (Strategic Hotel) (€/notte)", value=120.0),
    'v_uomo': st.sidebar.number_input("Valore Giornata Uomo (Fatturato commerciale perso) (€/giorno)", value=250.0)
}

st.write("---")
st.write("### 1️⃣ INPUT PARTECIPANTI (Dati Excel e/o Manuali)")

# -- SOTTO-SEZIONE A: CARICAMENTO EXCEL --
st.write("#### A. Caricamento via Foglio Excel")
col_excel_1, col_excel_2 = st.columns([2, 1])
with col_excel_1:
    uploaded_file = st.file_uploader("Trascina qui il tuo file Excel (.xlsx) (come esempio che ti ho fatto)", type="xlsx")

df_pax_final = pd.DataFrame(columns=['citta', 'nome', 'ruolo', 'origine'])

if uploaded_file:
    try:
        df_excel = pd.read_excel(uploaded_file)
        # Pulizia colonne basata su esempio: 'Città', 'nome e cognome', 'ruolo'
        df_excel = df_excel.rename(columns={'Città': 'citta', 'nome e cognome': 'nome', 'ruolo': 'ruolo'})
        # Prendi solo le colonne che ci servono
        df_excel = df_excel[['citta', 'nome', 'ruolo']]
        df_excel['origine'] = 'Excel'
        df_pax_final = pd.concat([df_pax_final, df_excel], ignore_index=True)
        st.success(f"Caricati {len(df_excel)} persone da Excel.")
    except Exception as e:
        st.error(f"Errore nel caricamento Excel: {e}. Controlla i nomi delle colonne.")

# -- SOTTO-SEZIONE B: CARICAMENTO MANUALE --
st.write("#### B. Inserimento Individuale Manuale")
with st.expander("➕ Aggiungi un singolo individuo manualmente", expanded=False):
    col_man_1, col_man_2, col_man_3 = st.columns(3)
    citta_man = col_man_1.selectbox("Città dove parte/vive", list(COORDINATE_CITTA.keys()))
    nome_man = col_man_2.text_input("Nome e Cognome", value="Mario Rossi")
    ruolo_man = col_man_3.selectbox("Ruolo", ["Agente", "Tecnico", "Commerciale", "Relatore", "Manager"])
    
    if st.button("➕ Aggiungi Partecipante Manuale"):
        new_row = {'citta': citta_man, 'nome': nome_man, 'ruolo': ruolo_man, 'origine': 'Manuale'}
        st.session_state['df_manuale'] = pd.concat([st.session_state.get('df_manuale', pd.DataFrame(columns=['citta', 'nome', 'ruolo', 'origine'])), pd.DataFrame([new_row])], ignore_index=True)
        st.success(f"Aggiunto {nome_man} da Veglie.")

# Recupera dati manuali da session state e uniscili
if 'df_manuale' in st.session_state:
    df_manuale_final = st.session_state['df_manuale']
    df_pax_final = pd.concat([df_pax_final, df_manuale_final], ignore_index=True)

# Mostra tabella finale
if not df_pax_final.empty:
    st.write("---")
    st.write(f"📊 **Database Partecipanti Totale ({len(df_pax_final)} persone):**")
    st.dataframe(df_pax_final, height=200, use_container_width=True)
    planner.df_pax = df_pax_final
else:
    st.warning("Carica un Excel o inserisci persone manualmente per iniziare l'analisi.")

# --- SEZIONE ANALISI (SOLO SE CI SONO PARTECIPANTI) ---
if not planner.df_pax.empty:
    st.write("---")
    st.write("### 2️⃣ DEFINIZIONE SEDI TRAINING E GIORNI PREVISTI")
    st.markdown("""
        Seleziona manualmente una o più sedi aziendali dove si tiene la riunione o training e quanti giorni sono previsti per ciascuna sede.
    """)

    # Configurazione Sedi per Scenario A
    st.write("#### Configura Scenario A (Es: 3 eventi strategic)")
    col_sa_1, col_sa_2 = st.columns([2, 2])
    sedi_scelte_a = col_sa_1.multiselect("Seleziona Sedi A", list(planner.sedi_aziendali.keys()), default=["Cantù", "Falconara Marittima", "Salerno"], key="msa")
    
    config_sedi_a = {}
    if sedi_scelte_a:
        with col_sa_2:
            st.write("**Giorni Training previsti per sede A:**")
            for sede in sedi_scelte_a:
                giorni_sede = st.number_input(f"Giorni previsti a {sede}", 1, 5, 1, key=f"g_a_{sede}")
                config_sedi_a[sede] = giorni_sede

    # Configurazione Sedi per Scenario B
    st.write("#### Configura Scenario B (Es: 2 eventi centralizzati)")
    col_sb_1, col_sb_2 = st.columns([2, 2])
    sedi_scelte_b = col_sb_1.multiselect("Seleziona Sedi B", list(planner.sedi_aziendali.keys()), default=["Firenze", "Roma"], key="msb")
    
    config_sedi_b = {}
    if sedi_scelte_b:
        with col_sb_2:
            st.write("**Giorni Training previsti per sede B:**")
            for sede in sedi_scelte_b:
                giorni_sede = st.number_input(f"Giorni previsti a {sede}", 1, 5, 2, key=f"g_b_{sede}")
                config_sedi_b[sede] = giorni_sede

    # --- ESECUZIONE ANALISI ---
    st.divider()
    if config_sedi_a and config_sedi_b:
        st.write("### 3️⃣ ANALISI COMPARATIVA DEI COSTI")
        
        # Scenario A
        res_a, map_a, tab_a = planner.analizza_scenario_web(config_sedi_a, **params)
        # Scenario B
        res_b, map_b, tab_b = planner.analizza_scenario_web(config_sedi_b, **params)

        col_metrics_1, col_metrics_2 = st.columns(2)
        with col_metrics_1:
            st.subheader(f"Scenario A ({len(config_sedi_a)} Sedi)")
            if res_a:
                st.metric("Costi Vivi Trasferte (€)", f"€{res_a['vivi']:,.2f}")
                st.metric("Giornate Lavoro Perse", f"{res_a['giornate']}")
                st.warning(f"**INVESTIMENTO TOTALE STIMATO:** €{res_a['totale']:,.2f}")
        
        with col_metrics_2:
            st.subheader(f"Scenario B ({len(config_sedi_b)} Sedi)")
            if res_b:
                st.metric("Costi Vivi Trasferte (€)", f"€{res_b['vivi']:,.2f}")
                st.metric("Giornate Lavoro Perse", f"{res_b['giornate']}")
                st.error(f"**INVESTIMENTO TOTALE STIMATO:** €{res_b['totale']:,.2f}", f"Diff vs A: €{res_b['totale'] - res_a['totale']:,.2f}", delta_color="inverse")

        # --- SEZIONE MAPPA (NON SEMPLIFICATA) ---
        st.divider()
        st.write(f"🗺️ **MAPPA DEI PERCORSI INDIVIDUALI E TRAINING (Scenario A)**")
        df_map = pd.DataFrame(map_a)
        
        if not df_map.empty:
            # Layer 1: Punti di partenza (Scatterplot - Simbolo diverso per relatore rosso)
            layer_punti = pdk.Layer(
                "ScatterplotLayer", df_map,
                get_position=["lon_orig", "lat_orig"],
                get_color="colore", get_radius=15000, pickable=True,
            )
            
            # Layer 2: Linee di percorso (ArcLayer)
            layer_linee = pdk.Layer(
                "ArcLayer", df_map,
                get_source_position=["lon_orig", "lat_orig"], get_target_position=["lon_dest", "lat_dest"],
                get_source_color=[0, 0, 255, 80], get_target_color=[0, 255, 0, 80],
                getWidth=1.5, pickable=True,
            )

            # Layer 3: Testo (Nome e Cognome a fianco al simbolo)
            layer_testo = pdk.Layer(
                "TextLayer", df_map,
                get_position=["lon_orig", "lat_orig"], get_text="nome",
                get_size=12, get_color=[0, 0, 0],
                get_alignment_baseline="'bottom'", get_alignment_anchor="'left'",
                get_offset_x=2, get_offset_y=-2,
            )

            st.pydeck_chart(pdk.Deck(
                map_style="mapbox://styles/mapbox/light-v9",
                initial_view_state=pdk.ViewState(latitude=42.5, longitude=12.5, zoom=5, pitch=40),
                layers=[layer_linee, layer_punti, layer_testo],
                tooltip={"text": "{nome} parte da {citta_orig} a {sede_dest} ({giorni} gg)"}
            ))

        # --- TABELLA DETTAGLIATA COSTI AUTO (Richiesta specifica) ---
        st.write("---")
        st.write("### 📊 TABELLA DETTAGLIATA COSTI AUTO (Scenario A - km reali stima)")
        if tab_a:
            df_tab_a = pd.DataFrame(tab_a)
            st.dataframe(df_tab_a, use_container_width=True)
            st.info("Questa tabella giustifica economicamente la scelta dei 3 eventi anziché 2 o viceversa.")

        # --- SEZIONE PDF (NON SEMPLIFICATA - REPORT FINALE) ---
        st.divider()
        st.write("### 📩 GENERAZIONE REPORT PDF FINALE")
        config_a_str = f"{len(config_sedi_a)} sedi, {sum(config_sedi_a.values())} gg"
        config_b_str = f"{len(config_sedi_b)} sedi, {sum(config_sedi_b.values())} gg"
        
        pdf_data = genera_pdf_report(res_a, res_b, tab_a, tab_b, params, config_a_str, config_b_str)
        st.download_button(
            label="📩 Scarica Report PDF Finale PRO (come esempio strategico)",
            data=pdf_data,
            file_name="report_training_planning_optimizer_pro.pdf",
            mime="application/pdf",
        )
