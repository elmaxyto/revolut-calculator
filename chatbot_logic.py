import json
from google import genai
from google.genai import types
import streamlit as st

# --- LAYER 1: SICUREZZA ---
def check_safety_local(query):
    blacklist = ['calcio', 'politica', 'meteo', 'serie a', 'ricetta', 'film', 'sport']
    query_lower = query.lower().strip()

    if len(query_lower) < 3:
        return False, "Domanda troppo breve. Chiedi info sui piani Revolut."

    for w in blacklist:
        if w in query_lower:
            return False, f"Argomento non supportato ('{w}'). Posso rispondere solo su Revolut."

    return True, ""

# --- LAYER 2: GEMINI 2.0 (CASCADE) ---
def ask_gemini_rotated(query, context_rules):
    try:
        api_keys = st.secrets["google_keys"]
    except:
        print("LOG: Secrets 'google_keys' non trovati.")
        return None

    # LISTA MODELLI VALIDATI (Gennaio 2025)
    # Ordine di priorità: Economico/Veloce -> Standard -> Avanzato -> Sperimentale
    candidate_models = [
        "gemini-2.0-flash-lite",       # Super veloce ed efficiente
        "gemini-2.0-flash",            # Standard bilanciato
        "gemini-2.5-flash",            # Ultima generazione
        "gemini-2.0-flash-exp"         # Fallback sperimentale
    ]

    # Prompt di Sistema
    sys_prompt = f"""
    SEI UN CONSULENTE FINANZIARIO ESPERTO DI REVOLUT.
    DATI UFFICIALI: {json.dumps(context_rules)}

    REGOLE:
    1. Rispondi in italiano, tono professionale ma diretto.
    2. Sii sintetico (max 3-4 frasi o elenco puntato).
    3. Usa SOLO i dati forniti nel JSON.
    4. Se chiedono di viaggi, rispondi SOLO su assicurazioni, lounge e cambio valuta.
    """

    full_prompt = f"{sys_prompt}\n\nDOMANDA UTENTE: {query}"

    # Logica di Rotazione (Chiavi -> Modelli)
    for key in api_keys:
        try:
            client = genai.Client(api_key=key)

            for model_name in candidate_models:
                try:
                    # Tentativo di generazione
                    response = client.models.generate_content(
                        model=model_name,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(temperature=0.3)
                    )
                    return response.text # SUCCESSO!

                except Exception as e_model:
                    # Se il modello fallisce (es. sovraccarico momentaneo), prova il prossimo
                    print(f"LOG: Modello {model_name} fallito. Motivo: {e_model}")
                    continue

        except Exception as e_key:
            print(f"LOG: Chiave fallita completamente. Passo alla successiva.")
            continue

    return None

# --- LAYER 3: FALLBACK ---
def get_fallback_response(query):
    """
    Risponde usando un database locale se l'AI non è raggiungibile.
    Non serve internet.
    """
    q = query.lower()

    # DATABASE LOCALE DI EMERGENZA
    knowledge_base = {
        "standard": "Il piano **Standard** è gratuito (0€/mese). Include bonifici istantanei gratis e cambio valuta fino a 1.000€/mese senza commissioni.",
        "plus": "Il piano **Plus** costa 3.99€/mese. Offre cambio valuta fino a 3.000€/mese e priorità supporto.",
        "premium": "Il piano **Premium** costa 9.99€/mese. È ottimo per viaggiare: cambio valuta illimitato, assicurazione medica globale e sconti sui bonifici internazionali.",
        "metal": "Il piano **Metal** costa 15.99€/mese. Include cashback dello 0.1% in Europa (1% fuori), assicurazione franchigia noleggio auto e carta in metallo esclusiva.",
        "ultra": "Il piano **Ultra** costa 55€/mese (o 540€/anno). È il top: accesso illimitato alle Lounge aeroportuali, assicurazione annullamento viaggi e commissioni di investimento ridotte.",
        "viaggi": "Per i viaggi consiglio **Premium** o **Metal**: entrambi offrono cambio valuta illimitato senza commissioni e assicurazione medica inclusa. Il Metal aggiunge la franchigia auto.",
        "lounge": "L'accesso alle Lounge aeroportuali è scontato con Premium e Metal, ma è **gratuito e illimitato** solo con il piano **Ultra**.",
        "crypto": "Le commissioni Crypto variano: Standard/Plus 1.49%, Premium/Metal 0.99%, Ultra 0.49%.",
        "investimenti": "Revolut offre azioni e ETF. Con Ultra hai 10 operazioni gratis al mese e commissioni ridotte allo 0.12%.",
        "assicurazione": "L'assicurazione medica è inclusa da Premium in su. Copre spese mediche d'emergenza all'estero. Metal e Ultra aggiungono assicurazione ritardo volo e bagaglio."
    }

    # Cerca la parola chiave più rilevante
    for key, answer in knowledge_base.items():
        if key in q:
            return f"⚠️ **Modalità Offline:** {answer}"

    # Risposta generica se non trova parole chiave
    return "⚠️ **Modalità Offline:** Non riesco a connettermi al cervello AI, ma posso dirti che i piani vanno da 0€ (Standard) a 55€ (Ultra). Prova a chiedere 'Costo Metal' o 'Vantaggi Premium'."
