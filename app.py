import warnings
# Pulisce la console dagli avvisi di deprecazione futuri
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="google.genai")

import streamlit as st
import pandas as pd
import plotly.express as px
import os
import re
import json
import csv
from fpdf import FPDF
from datetime import datetime
from chatbot_logic import check_safety_local, ask_gemini_rotated, get_fallback_response

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    layout="wide", 
    page_title="Calcolatore Revolut 2025", 
    page_icon="💳"
)

# Recupera la fonte dal link (es. ?source=tiktok)
query_params = st.query_params
source = query_params.get("source", "direct")

# --- CSS MINIMALE ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# --- CARICAMENTO DATI ---
RULES = {
  "piani": {
    "Standard": {
        "costo_mensile": 0.00, "costo_annuale": 0.00, "costo_duo_addon": 0.00,
        "limiti": { "prelievi_atm": 200, "cambio_valuta": 1000 },
        "commissioni": { "prelievi_atm_over": 0.02, "cambio_valuta_over": 0.01, "crypto": 0.0149, "borsa": 0.0025 },
        "interessi_deposito": 0.015, "revpoints_rate": 1, "revpoints_step": 10, "cashback_pro": 0.004
    },
    "Plus": {
        "costo_mensile": 3.99, "costo_annuale": 40.00, "costo_duo_addon": 2.00,
        "limiti": { "prelievi_atm": 200, "cambio_valuta": 3000 },
        "commissioni": { "prelievi_atm_over": 0.02, "cambio_valuta_over": 0.005, "crypto": 0.0149, "borsa": 0.0025 },
        "interessi_deposito": 0.015, "revpoints_rate": 1, "revpoints_step": 10, "cashback_pro": 0.004
    },
    "Premium": {
        "costo_mensile": 9.99, "costo_annuale": 100.00, "costo_duo_addon": 4.00,
        "limiti": { "prelievi_atm": 400, "cambio_valuta": 999999999 },
        "commissioni": { "prelievi_atm_over": 0.02, "cambio_valuta_over": 0.0, "crypto": 0.0099, "borsa": 0.0025 },
        "interessi_deposito": 0.02, "revpoints_rate": 1, "revpoints_step": 4, "cashback_pro": 0.006
    },
    "Metal": {
        "costo_mensile": 15.99, "costo_annuale": 160.00, "costo_duo_addon": 6.00,
        "limiti": { "prelievi_atm": 800, "cambio_valuta": 999999999 },
        "commissioni": { "prelievi_atm_over": 0.02, "cambio_valuta_over": 0.0, "crypto": 0.0099, "borsa": 0.0025 },
        "interessi_deposito": 0.0225, "revpoints_rate": 1, "revpoints_step": 2, "cashback_pro": 0.008
    },
    "Ultra": {
        "costo_mensile": 55.00, "costo_annuale": 540.00, "costo_duo_addon": 15.00,
        "limiti": { "prelievi_atm": 2000, "cambio_valuta": 999999999 },
        "commissioni": { "prelievi_atm_over": 0.02, "cambio_valuta_over": 0.0, "crypto": 0.0049, "borsa": 0.0012 },
        "interessi_deposito": 0.025, "revpoints_rate": 1, "revpoints_step": 1, "cashback_pro": 0.01
    }
  },
  "partners_list": [
      {"name": "NordVPN", "val": 80, "min_plan": "Premium"},
      {"name": "Corriere della Sera", "val": 100, "min_plan": "Premium"},
      {"name": "Gazzetta dello Sport", "val": 60, "min_plan": "Premium"},
      {"name": "Tinder", "val": 80, "min_plan": "Premium"},
      {"name": "Headspace", "val": 60, "min_plan": "Premium"},
      {"name": "Freeletics", "val": 80, "min_plan": "Premium"},
      {"name": "Picsart", "val": 35, "min_plan": "Premium"},
      {"name": "Sleep Cycle", "val": 30, "min_plan": "Premium"},
      {"name": "Perplexity (AI)", "val": 200, "min_plan": "Premium"},
      {"name": "Financial Times", "val": 300, "min_plan": "Metal"},
      {"name": "WeWork", "val": 300, "min_plan": "Metal"},
      {"name": "MasterClass", "val": 180, "min_plan": "Metal"},
      {"name": "The Athletic", "val": 70, "min_plan": "Metal"},
      {"name": "Chess.com", "val": 100, "min_plan": "Metal"},
      {"name": "Headway", "val": 90, "min_plan": "Metal"}
  ]
}

def load_data():
    try:
        if os.path.exists('data/rules.json'):
            with open('data/rules.json') as f:
                rules = json.load(f)
            return rules, True
        else:
            return RULES, True # Fallback attivo
    except Exception as e:
        return RULES, True

RULES_LOADED, data_loaded = load_data()

def create_pdf(piano, vantaggio_netto, dettagli):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=14)

    # Titolo
    pdf.cell(200, 10, txt=f"Report Revolut - Piano {piano}", ln=True, align='C')
    pdf.ln(10)

    # Vantaggio
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt=f"Vantaggio Netto Stimato: {vantaggio_netto} EUR", ln=True, align='C')
    pdf.ln(10)

    # Dettagli
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt="Dettaglio del Risparmio: Voce per Voce", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", size=12)
    for key, value in dettagli.items():
        # Encoding sicuro per caratteri speciali
        clean_key = key.encode('latin-1', 'replace').decode('latin-1')
        sign = "+" if value >= 0 else ""
        formatted_value = f"{sign} EUR {abs(value):.2f}"
        pdf.cell(200, 8, txt=f"{clean_key}: {formatted_value}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", size=12, style='B')
    pdf.cell(200, 10, txt=f"Vantaggio Netto Finale: EUR {vantaggio_netto}", ln=True, align='C')

    pdf.ln(10)
    pdf.set_font("Arial", size=10, style='I')
    pdf.cell(200, 10, txt="Generato da Budget Tech ITA", ln=True, align='C')

    return pdf.output(dest='S').encode('latin-1', 'replace')

def save_lead(email, source):
    # Salva email e fonte nel CSV
    file_exists = os.path.isfile('leads.csv')
    try:
        with open('leads.csv', 'a', newline='') as f:
            writer = csv.writer(f)
            # Se il file è nuovo, aggiungiamo la colonna 'Source'
            if not file_exists:
                writer.writerow(['Data', 'Email', 'Source'])
            
            writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, source])
    except Exception as e:
        print(f"Errore salvataggio lead: {e}")

# --- SIDEBAR PULITA ---
with st.sidebar:
    st.title("💸 Budget Tech ITA")
    st.caption("Tech che ti fa risparmiare")
    st.header("Assistente AI")

    # Inizializza history se non esiste
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Ciao! Chiedimi info sui piani (es. 'Conviene il Metal?')."}]

    # Container per i messaggi (così l'input resta in basso)
    chat_container = st.container(height=400) # Altezza fissa scrollabile

    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Input del Chatbot (Streamlit lo piazza in fondo alla sidebar se chiamato qui)
    if prompt := st.chat_input("Chiedi all'AI...", key="sidebar_chat"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container: # Scriviamo nel container scrollabile
            with st.chat_message("user"):
                st.markdown(prompt)

            # Logica Risposta
            response_text = ""
            safe, error_msg = check_safety_local(prompt)

            if not safe:
                 response_text = f"🚫 {error_msg}"
            else:
                with st.spinner("..."):
                    ai_response = ask_gemini_rotated(prompt, RULES_LOADED)

                if ai_response:
                    response_text = ai_response
                else:
                    response_text = get_fallback_response(prompt)

            with st.chat_message("assistant"):
                st.markdown(response_text)

            st.session_state.messages.append({"role": "assistant", "content": response_text})
    st.divider()

    st.subheader("📘 Guida Completa")
    st.info("I migliori trucchi per usare Revolut al 100%.")

    with st.expander("📄 Leggi l'Informativa Privacy completa (GDPR)"):
        st.markdown("""
**Informativa semplificata ai sensi dell'art. 13 del Regolamento UE 2016/679 (GDPR)**

**1. Titolare del Trattamento**
Il titolare del trattamento è: **Massimo Slomp**
Contatto per privacy e cancellazione: **massimo.spooky@gmail.com**

**2. Dati raccolti e Finalità**
Raccogliamo il tuo indirizzo email esclusivamente per:
* Inviarti il documento PDF richiesto.
* Inviarti aggiornamenti, guide e comunicazioni informative relative a Revolut e alla finanza personale (Newsletter).

**3. Consenso e Diritti**
Il conferimento dei dati è facoltativo, ma necessario per ricevere il materiale.
L'utente ha il diritto di **disiscriversi in qualsiasi momento** (link in calce a ogni email) e di chiedere la cancellazione dei dati scrivendo all'indirizzo email sopra indicato.

**4. Terze parti**
I dati non saranno venduti a terzi. Potrebbero essere gestiti tramite piattaforme tecniche di invio email che agiscono come responsabili del trattamento per conto del titolare.
""")

    with st.expander("📥 Scarica la Guida PDF", expanded=True):
        email_guida = st.text_input("La tua email:", placeholder="nome@mail.com", key="email_sidebar")
        privacy_guida = st.checkbox("Ho letto l'informativa Privacy e acconsento al trattamento dei dati per ricevere il documento e aggiornamenti correlati.", key="privacy_sidebar")

        guide_path = "data/guida_tricks.pdf"

        if os.path.exists(guide_path):
            with open(guide_path, "rb") as f:
                pdf_data = f.read()

            st.download_button(
                label="📥 SCARICA ORA",
                data=pdf_data,
                file_name="Guida_Trucchi_Revolut.pdf",
                mime="application/pdf",
                on_click=save_lead,
                args=(email_guida, "guida_sidebar"), # Tracciamo che viene dalla guida
                use_container_width=True,
                disabled=not (email_guida and "@" in email_guida and privacy_guida)
            )
        else:
            st.warning("Guida in aggiornamento (caricare file 'data/guida_tricks.pdf')")

    # st.subheader("💎 Patreon")
    # st.info("Supporta il progetto per €9/mese")
    #
    # st.markdown("""
    # * ✅ Guida 2025
    # * ✅ Chatbot 24/7
    # * ✅ Tool Esclusivi
    # """)
    # st.divider()
    
    if data_loaded:
        last_update = datetime.now().strftime('%d/%m/%Y') # Placeholder data
        st.caption(f"📅 Dati aggiornati al: {last_update}")
        if st.button("🔄 Aggiorna Dati", use_container_width=True):
            st.rerun()


# --- HEADER PRINCIPALE ---
st.title("💰 Calcolatore Risparmio Revolut")
if not data_loaded:
    st.error("Errore: Impossibile caricare i dati.")
st.markdown("Analizza il tuo profilo di spesa e scopri il piano migliore.")

# --- CARD INPUT ---
with st.container(border=True):
    st.subheader("1. Configura il tuo profilo")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown("**🏦 Banca Attuale**")
        canone = st.number_input("Canone (€/mese)", value=10.0, step=1.0, min_value=0.0)
        bonifici_istantanei = st.number_input("Bonifici Istantanei (n/anno)", value=12, min_value=0)
        costo_bonifico = st.number_input("Costo Unitario Bonifico (€)", value=2.00, step=0.10, min_value=0.0)
        pagopa = st.number_input("PagoPA (n/anno)", value=12, min_value=0)
        costo_pagopa = st.number_input("Costo Unitario PagoPA (€)", value=1.50, step=0.10, min_value=0.0)

    with c2:
        st.markdown("**💳 Utilizzo Carta**")
        spese = st.number_input("Spesa carta mensile (€)", value=400.0, step=50.0, min_value=0.0)
        viaggi = st.number_input("Viaggi all'estero (n/anno)", value=2, min_value=0)
        spesa_prelievi_mensile = st.number_input("Spesa prelievi mensile (€)", value=0.0, step=10.0, min_value=0.0, help="Inserisci la spesa mensile per prelievi ATM. Se 0, verrà stimata in base ai viaggi.")
        liquidita_media = st.number_input("Liquidità Media (€)", value=1000.0, step=100.0, min_value=0.0, help="Soldi che tieni sul conto (Salvadanaio/Flessibile) che generano interessi")

    with c3:
        st.markdown("**🌍 Extra & Pro**")
        lounge = st.number_input("Ingressi Lounge (n/anno)", value=1, min_value=0)
        bonifici_int = st.number_input("Bonifici Extra-UE (n/anno)", value=2, min_value=0)
        revolut_pro = st.number_input("Revolut Pro (€/mese)", value=100.0, min_value=0.0, help="Inserisci valore solo se hai P.IVA/Freelance. Offre cashback elevato")

    with c4:
        st.markdown("**📈 Investimenti**")
        volume_crypto = st.number_input("Vol. Crypto mensile (€)", value=0.0, min_value=0.0)
        volume_borsa = st.number_input("Vol. Azioni mensile (€)", value=0.0, min_value=0.0)

st.markdown("---")
opt1, opt2 = st.columns(2)
with opt1:
    fatturazione_annuale = st.toggle("Fatturazione Annuale (Risparmio ~20%)", value=True)
with opt2:
    modalita_duo = st.checkbox("Modalità Duo (x2 Persone)", help="Risparmia fino al 36% attivando un piano per te e un partner o familiare. Include 2 account completi.")
membri_duo = 2 if modalita_duo else 1

# --- SEZIONE ABBONAMENTI PARTNER ---
with st.container(border=True):
    st.subheader("🎁 Abbonamenti Inclusi")
    st.write("Da Revolut Premium in su hai accesso gratuito a diversi abbonamenti che trovi qui sotto.")

    # Mappa per lookup veloce di valori
    partner_map = {p['name']: p for p in RULES_LOADED['partners_list']}

    selected_partners = st.multiselect(
        "Quali di questi servizi usi o useresti se fossero gratis?",
        options=partner_map.keys(),
        default=[],
        format_func=lambda x: f"{x} (€{partner_map[x]['val']}/anno)",
        help="Seleziona i servizi che utilizzi o potresti utilizzare. Il valore verrà aggiunto al calcolo del vantaggio per i piani che li includono."
    )

# CALCOLI
results = []
if data_loaded:
    for piano in RULES_LOADED['piani']:
        # Costo Abbonamento
        if fatturazione_annuale:
            base = RULES_LOADED['piani'][piano]['costo_annuale']
        else:
            base = RULES_LOADED['piani'][piano]['costo_mensile'] * 12
        if modalita_duo:
            costo_abbonamento = base + (RULES_LOADED['piani'][piano]['costo_duo_addon'] * 12)
        else:
            costo_abbonamento = base

        # Calcolo Commissioni & Risparmi
        # Prelievi ATM
        spesa_prelievi_annui = spesa_prelievi_mensile * 12 if spesa_prelievi_mensile > 0 else viaggi * 200
        costo_banca_atm = (viaggi * 3) * RULES_LOADED['benchmark_banca']['fee_atm_altri']
        eccedenza_atm = max(0, spesa_prelievi_annui - (RULES_LOADED['piani'][piano]['limiti']['prelievi_atm'] * 12))
        fee_revolut_atm = eccedenza_atm * RULES_LOADED['piani'][piano]['commissioni']['prelievi_atm_over']
        risparmio_atm = costo_banca_atm - fee_revolut_atm

        # Cambio Valuta
        spesa_fx_annua = viaggi * 500
        costo_banca_fx = spesa_fx_annua * RULES_LOADED['benchmark_banca']['fee_cambio_valuta']
        eccedenza_fx = max(0, spesa_fx_annua - (RULES_LOADED['piani'][piano]['limiti']['cambio_valuta'] * 12))
        fee_revolut_fx = eccedenza_fx * RULES_LOADED['piani'][piano]['commissioni']['cambio_valuta_over']
        risparmio_fx = costo_banca_fx - fee_revolut_fx

        # Interessi
        interessi = liquidita_media * RULES_LOADED['piani'][piano]['interessi_deposito']

        # RevPoints
        step = RULES_LOADED['piani'][piano]['revpoints_step']
        rate = RULES_LOADED['piani'][piano]['revpoints_rate']
        if rate > 0:
            punti = (spese * 12 / step) * rate
            valore_revpoints = punti * 0.01
        else:
            valore_revpoints = 0

        # Investimenti
        risparmio_crypto = (volume_crypto * 12) * (RULES_LOADED['benchmark_banca']['fee_crypto'] - RULES_LOADED['piani'][piano]['commissioni']['crypto'])
        risparmio_borsa = (volume_borsa * 12) * (RULES_LOADED['benchmark_banca']['fee_borsa'] - RULES_LOADED['piani'][piano]['commissioni']['borsa'])

        # Cashback Pro
        cashback_pro_val = (revolut_pro * 12) * RULES_LOADED['piani'][piano]['cashback_pro']

        # Valore Partner
        valore_partner = 0
        for partner in selected_partners:
            partner_info = next((p for p in RULES_LOADED['partners_list'] if p['name'] == partner), None)
            if partner_info:
                min_plan = partner_info['min_plan']
                if piano in ['Premium', 'Metal', 'Ultra']:
                    if min_plan == 'Premium' or (min_plan == 'Metal' and piano in ['Metal', 'Ultra']):
                        valore_partner += partner_info['val']

        # Totale Netto
        risparmio_canone = canone * 12
        risparmio_bonifici = bonifici_istantanei * costo_bonifico + pagopa * costo_pagopa
        totale_netto = (risparmio_canone + risparmio_bonifici + risparmio_atm + risparmio_fx + interessi + valore_revpoints + cashback_pro_val + risparmio_crypto + risparmio_borsa + valore_partner) - costo_abbonamento

        results.append({
            'Piano': piano,
            'Risparmio Canone': risparmio_canone,
            'Risparmio Bonifici': risparmio_bonifici,
            'Risparmio ATM': risparmio_atm,
            'Risparmio FX': risparmio_fx,
            'Interessi': interessi,
            'RevPoints': valore_revpoints,
            'Risparmio Crypto': risparmio_crypto,
            'Risparmio Borsa': risparmio_borsa,
            'Cashback Pro': cashback_pro_val,
            'Valore Partner': valore_partner,
            'Costo Abbonamento': costo_abbonamento,
            'Vantaggio Netto': totale_netto
        })

    df = pd.DataFrame(results)
    miglior = df.loc[df['Vantaggio Netto'].idxmax()]

    st.markdown("### 🏆 Risultati Analisi")

    # Trova l'indice del piano migliore per impostarlo come default
    index_miglior = df[df['Piano'] == miglior['Piano']].index[0]

    # Selectbox per cambiare visualizzazione
    piano_selezionato_nome = st.selectbox(
        "Visualizza dettagli per il piano:",
        options=df['Piano'].tolist(),
        index=int(index_miglior)
    )

    # Recupera i dati del piano selezionato
    piano_corrente = df[df['Piano'] == piano_selezionato_nome].iloc[0]

    # --- METRICHE HERO ---
    m1, m2, m3 = st.columns(3)
    with m1:
        label = "Piano Selezionato"
        if piano_corrente['Piano'] == miglior['Piano']:
            label += " 🏆 (Consigliato)"
        st.metric(label=label, value=piano_corrente['Piano'])
    with m2:
        st.metric(label="Vantaggio Netto Annuo", value=f"€ {piano_corrente['Vantaggio Netto']:.2f}")
    with m3:
        st.metric(label="Risparmio Mensile", value=f"€ {piano_corrente['Vantaggio Netto']/12:.2f}")

    # --- BREAKDOWN DETTAGLIATO ---
    with st.expander("🔍 Analisi dettagliata: Da dove arriva il mio risparmio?", expanded=True):
        st.write(f"Per il piano **{piano_corrente['Piano']}** (scelta selezionata):")
        st.write(f"🏦 Risparmio Canone: +€{piano_corrente['Risparmio Canone']:.2f}")
        st.write(f"💸 Risparmio Bonifici/PagoPA: +€{piano_corrente['Risparmio Bonifici']:.2f}")
        st.write(f"🏧 Risparmio ATM: +€{piano_corrente['Risparmio ATM']:.2f}")
        st.write(f"💱 Risparmio FX: +€{piano_corrente['Risparmio FX']:.2f}")
        st.write(f"📈 Interessi: +€{piano_corrente['Interessi']:.2f}")
        st.write(f"🎁 RevPoints: +€{piano_corrente['RevPoints']:.2f}")
        st.write(f"🪙 Risparmio Crypto: +€{piano_corrente['Risparmio Crypto']:.2f}")
        st.write(f"📊 Risparmio Borsa: +€{piano_corrente['Risparmio Borsa']:.2f}")
        st.write(f"💼 Cashback Pro: +€{piano_corrente['Cashback Pro']:.2f}")
        st.write(f"🎁 Valore App Partner: +€{piano_corrente['Valore Partner']:.2f}")
        if modalita_duo:
            st.write(f"➖ Costo Add-on Duo: -€{RULES_LOADED['piani'][piano_corrente['Piano']]['costo_duo_addon'] * 12:.2f}")
        st.write(f"➖ Costo Abbonamento: -€{piano_corrente['Costo Abbonamento']:.2f}")
        if modalita_duo:
            st.write("💡 **Nota:** Il prezzo dell'abbonamento copre 2 persone.")
        st.write(f"**Totale Vantaggio Netto: €{piano_corrente['Vantaggio Netto']:.2f}**")

        # --- GRAFICO E TABELLA ---
        col_chart, col_data = st.columns([2, 1])

        with col_chart:
            with st.container(border=True):
                chart_title = "Confronto Vantaggio Netto"
                if modalita_duo:
                    chart_title += " (Modalità Duo Attiva - Prezzi per 2 Persone)"
                st.subheader(chart_title)
                # Stacked Bar Chart per componenti
                df_long = df.melt(id_vars=['Piano'], value_vars=['Risparmio Canone', 'Risparmio Bonifici', 'Risparmio ATM', 'Risparmio FX', 'Interessi', 'RevPoints', 'Risparmio Crypto', 'Risparmio Borsa', 'Cashback Pro', 'Valore Partner', 'Costo Abbonamento'],
                                  var_name='Componente', value_name='Valore')
                # Per stacked, rendi negativo il costo
                df_long['Valore'] = df_long.apply(lambda row: -row['Valore'] if row['Componente'] == 'Costo Abbonamento' else row['Valore'], axis=1)
                fig = px.bar(
                    df_long,
                    x='Piano',
                    y='Valore',
                    color='Componente',
                    color_discrete_map={
                        'Risparmio Canone': 'darkgreen',
                        'Risparmio Bonifici': 'green',
                        'Risparmio ATM': 'lightgreen',
                        'Risparmio FX': 'lime',
                        'Interessi': 'blue',
                        'RevPoints': 'cyan',
                        'Risparmio Crypto': 'purple',
                        'Risparmio Borsa': 'magenta',
                        'Cashback Pro': 'orange',
                        'Valore Partner': 'gold',
                        'Costo Abbonamento': 'red'
                    },
                    barmode='stack',
                    text_auto='.0f'
                )
                fig.update_layout(
                    xaxis_title=None,
                    yaxis_title="Vantaggio Netto (€)",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_data:
            with st.container(border=True):
                st.subheader("Dettaglio")
                st.dataframe(
                    df[['Piano', 'Vantaggio Netto']].style.background_gradient(cmap='Blues'),
                    use_container_width=True,
                    height=300,
                    hide_index=True
                )

        # --- CALL TO ACTION ---
        st.info(f"💡 **Consiglio:** Attivando {miglior['Piano']} otterrai un vantaggio netto di **€{miglior['Vantaggio Netto']/12:.0f} al mese** rispetto alla tua banca attuale.")

    # --- SCARICA IL TUO REPORT ---
    with st.container(border=True):
        st.subheader("📄 Scarica il tuo Report")
        user_email = st.text_input("La tua email", placeholder="nome@email.com", key="user_email")
        with st.expander("📄 Leggi l'Informativa Privacy completa (GDPR)"):
            st.markdown("""
**Informativa semplificata ai sensi dell'art. 13 del Regolamento UE 2016/679 (GDPR)**

**1. Titolare del Trattamento**
Il titolare del trattamento è: **Massimo Slomp**
Contatto per privacy e cancellazione: **massimo.spooky@gmail.com**

**2. Dati raccolti e Finalità**
Raccogliamo il tuo indirizzo email esclusivamente per:
* Inviarti il documento PDF richiesto.
* Inviarti aggiornamenti, guide e comunicazioni informative relative a Revolut e alla finanza personale (Newsletter).

**3. Consenso e Diritti**
Il conferimento dei dati è facoltativo, ma necessario per ricevere il materiale.
L'utente ha il diritto di **disiscriversi in qualsiasi momento** (link in calce a ogni email) e di chiedere la cancellazione dei dati scrivendo all'indirizzo email sopra indicato.

**4. Terze parti**
I dati non saranno venduti a terzi. Potrebbero essere gestiti tramite piattaforme tecniche di invio email che agiscono come responsabili del trattamento per conto del titolare.
""")
        privacy_consent = st.checkbox("Ho letto l'informativa Privacy e acconsento al trattamento dei dati per ricevere il documento e aggiornamenti correlati.", value=False)

        dettagli_pdf = {
            "Risparmio Canone": piano_corrente['Risparmio Canone'],
            "Risparmio Bonifici/PagoPA": piano_corrente['Risparmio Bonifici'],
            "Risparmio Prelievi ATM": piano_corrente['Risparmio ATM'],
            "Risparmio Cambio Valuta": piano_corrente['Risparmio FX'],
            "Guadagno Interessi": piano_corrente['Interessi'],
            "Valore RevPoints": piano_corrente['RevPoints'],
            "Risparmio Crypto": piano_corrente['Risparmio Crypto'],
            "Risparmio Borsa": piano_corrente['Risparmio Borsa'],
            "Cashback Pro": piano_corrente['Cashback Pro'],
            "Valore Abbonamenti Partner": piano_corrente['Valore Partner'],
            "Costo Abbonamento": -piano_corrente['Costo Abbonamento']
        }
        pdf_bytes = create_pdf(piano_corrente['Piano'], f"{piano_corrente['Vantaggio Netto']:.2f}", dettagli_pdf)

        st.download_button(
            label="📄 SCARICA PDF",
            data=pdf_bytes,
            file_name=f"report_revolut_{piano_corrente['Piano']}.pdf",
            mime="application/pdf",
            use_container_width=True,
            disabled=not (user_email and "@" in user_email and privacy_consent),
            on_click=save_lead,
            args=(user_email, source)
        )



st.divider()

# Link Config
link_revolut = "https://revolut.com/referral/?referral-code=massimfc2m!DEC2-25-AR-L1-MDL-ROI&geo-redirect"
link_donazione = "https://ko-fi.com/budgettechita" # Placeholder per PayPal/Ko-fi futuro

c_cta1, c_cta2 = st.columns(2)

with c_cta1:
    st.markdown(f"""
    <div style='text-align:center; padding:20px; background: linear-gradient(135deg, #0075EB 0%, #00BFFA 100%); color:white; border-radius:12px; height: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h4 style='margin:0 0 10px 0;'>🚀 Ottimizza le tue finanze</h4>
        <p style='font-size:14px; margin-bottom:20px;'>Apri il tuo conto gratuito in pochi minuti e inizia a gestire le tue spese in modo intelligente.</p>
        <a href='{link_revolut}' target='_blank' style='background:white; color:#0075EB; padding:10px 24px; text-decoration:none; border-radius:30px; font-weight:bold; display:inline-block; border: 2px solid white;'>👉 PROVA REVOLUT GRATIS</a>
    </div>
    """, unsafe_allow_html=True)

with c_cta2:
    st.markdown(f"""
    <div style='text-align:center; padding:20px; background: #1e293b; color: white; border-radius:12px; height: 100%; border: 1px solid #334155; box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h4 style='margin:0 0 10px 0;'>☕ Ti è stato utile?</h4>
        <p style='font-size:14px; margin-bottom:20px;'>Il tool è gratuito. Se vuoi, supportami con un caffè!</p>
        <a href='{link_donazione}' target='_blank' style='background:#FFDD00; color:#000; padding:10px 24px; text-decoration:none; border-radius:30px; font-weight:bold; display:inline-block;'>☕ OFFRIMI UN CAFFÈ</a>
    </div>
    """, unsafe_allow_html=True)

st.divider()
st.markdown("### ⚖️ Disclaimer & Note Legali")
st.caption("""
**Limitazione di Responsabilità:**
Questo strumento è un simulatore indipendente sviluppato a scopo puramente informativo e didattico. **Non è affiliato, approvato o sponsorizzato da Revolut Ltd.** o dalle sue sussidiarie.

I risultati dei calcoli sono stime basate su dati approssimativi e sulle condizioni di mercato al momento dell'ultimo aggiornamento. I tassi, le commissioni e le offerte dei partner possono variare senza preavviso.
Questo strumento **non costituisce consulenza finanziaria, fiscale o legale**.

L'autore non si assume alcuna responsabilità per eventuali inesattezze, errori nei calcoli o per decisioni finanziarie prese dall'utente sulla base di queste informazioni.
Si invita l'utente a verificare sempre i Fogli Informativi Analitici e le condizioni contrattuali ufficiali sul sito revolut.com prima di sottoscrivere qualsiasi prodotto.

Tutti i marchi citati (es. Revolut, Metal, Ultra) appartengono ai rispettivi proprietari.
           
Nota: In questa pagina possono essere presenti link di invito personali che generano una piccola ricompensa per l'autore senza costi aggiuntivi per l'utente.           
""")
