import sqlite3
from datetime import date
import pandas as pd
import streamlit as st
import os
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit

# Carica le variabili d'ambiente (es. OPENAI_API_KEY dal file .env)
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")  

# Nome del file del database
DB_FILE = "bookings.db"

# =====================================
# 1️⃣ CREAZIONE E POPOLAMENTO DATABASE
# =====================================
def crea_e_popola_database():
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    # --- TABELLA CAMERE ---
    cur.execute('''
    CREATE TABLE IF NOT EXISTS camere (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipologia_camera TEXT NOT NULL UNIQUE,
            numero_camere INTEGER NOT NULL,
            capacita INTEGER NOT NULL
       );
    ''')

    cur.execute("SELECT COUNT(*) FROM camere")
    if cur.fetchone()[0] == 0:
        camere = [
            ("Standard", 6, 2),
            ("Deluxe", 4, 2),
            ("Executive", 4, 2),
            ("Junior Suite", 2, 4),
            ("Suite", 1, 2)
        ]
        cur.executemany(
            '''
            INSERT INTO camere (tipologia_camera, numero_camere, capacita)
            VALUES (?, ?, ?);
            ''',
            camere
        )
        print("Tabella 'camere' popolata.")

    # --- TABELLA PRENOTAZIONI (NUOVE COLONNE IN ITALIANO) ---
    cur.execute('''
        CREATE TABLE IF NOT EXISTS prenotazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_ospite TEXT,
            tipologia_camera TEXT,
            data_arrivo DATE,
            data_partenza DATE,
            notti INT,
            numero_ospiti INT,
            tariffa_giornaliera REAL,
            totale_soggiorno REAL,
            stato TEXT,
            data_prenotazione DATE
        );
    ''')

    cur.execute("SELECT COUNT(*) FROM prenotazioni")
    if cur.fetchone()[0] == 0:
        prenotazioni = [
            ("Mario Rossi", "Standard", "2025-11-20", "2025-11-23", 3, 2, 210.0, 630.0, "Confermata", "2025-10-29"),
            ("Lucia Bianchi", "Deluxe", "2025-11-25", "2025-11-28", 3, 2, 400.0, 1200.0, "Confermata", "2025-10-27"),
            ("Giovanni Verdi", "Suite", "2025-12-01", "2025-12-05", 4, 2, 900.0, 3600.0, "In attesa", "2025-10-30"),
            ("Elena Neri", "Executive", "2025-11-22", "2025-11-24", 2, 2, 250.0, 500.0, "Confermata", "2025-10-25"),
            ("Roberto Gialli", "Junior Suite", "2025-11-29", "2025-12-03", 4, 4, 600.0, 2400.0, "Confermata", "2025-10-24"),
            ("Chiara Blu", "Standard", "2025-12-12", "2025-12-13", 1, 2, 90.0, 90.0, "Cancellata", "2025-10-22"),
            ("Luca Viola", "Deluxe", "2025-12-14", "2025-12-17", 3, 2, 380.0, 1140.0, "Confermata", "2025-10-20"),
            ("Alessia Rossa", "Executive", "2025-12-18", "2025-12-21", 3, 2, 300.0, 900.0, "Confermata", "2025-10-18"),
            ("Giulia Azzurra", "Junior Suite", "2025-12-10", "2025-12-15", 5, 4, 700.0, 3500.0, "In attesa", "2025-11-01"),
            ("Andrea Neri", "Suite", "2025-12-20", "2025-12-22", 2, 2, 950.0, 1900.0, "Confermata", "2025-10-30"),
            ("Marco Galli", "Standard", "2025-12-15", "2025-12-17", 2, 2, 200.0, 400.0, "Confermata", "2025-11-02"),
            ("Paola Bruni", "Deluxe", "2025-12-23", "2025-12-26", 3, 2, 420.0, 1260.0, "Confermata", "2025-11-05"),
            ("Stefano Fabbri", "Executive", "2025-12-25", "2025-12-28", 3, 2, 270.0, 810.0, "Confermata", "2025-11-02"),
            ("Pietro Riva", "Standard", "2025-12-20", "2025-12-24", 4, 2, 300.0, 1200.0, "Confermata", "2025-11-10"),
            ("Giada Rossi", "Deluxe", "2025-12-22", "2025-12-26", 4, 2, 480.0, 1920.0, "Confermata", "2025-11-12"),
            ("Valentina Grassi", "Executive", "2025-12-28", "2026-01-02", 5, 2, 550.0, 2750.0, "Confermata", "2025-11-15")
        ]

        cur.executemany(
            '''
            INSERT INTO prenotazioni (
                nome_ospite, tipologia_camera, data_arrivo, data_partenza, notti,
                numero_ospiti, tariffa_giornaliera, totale_soggiorno, stato, data_prenotazione
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            ''',
            prenotazioni)
        print("Tabella 'prenotazioni' popolata.")

    db.commit()
    db.close()

# =====================================
# 2️⃣ CONNESSIONE AL DATABASE + VERIFICA
# =====================================
def mostra_dati_da_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        camere_df = pd.read_sql_query("SELECT * FROM camere;", conn)
        prenotazioni_df = pd.read_sql_query("SELECT * FROM prenotazioni;", conn)
        conn.close()
        return camere_df, prenotazioni_df
    except Exception as e:
        st.error(f"Errore nella lettura del database: {e}")
        return pd.DataFrame(), pd.DataFrame()

# =====================================
# 3️⃣ LLM + LANGCHAIN SQL AGENT
# =====================================
def crea_sql_agent():
    system_prompt = f"""
 Sei un assistente virtuale altamente qualificato per l'hotel "Chalet Monte Bianco".
La data odierna è {date.today().strftime("%Y-%m-%d")}.

Hai accesso alle seguenti tabelle SQL:

1. camere:
   - id
   - tipologia_camera
   - numero_camere
   - capacita

2. prenotazioni:
   - id
   - nome_ospite
   - tipologia_camera
   - data_arrivo
   - data_partenza
   - notti
   - numero_ospiti
   - tariffa_giornaliera
   - totale_soggiorno
   - stato
   - data_prenotazione

REGOLE OPERATIVE:
- Rispondi **sempre e solo in italiano**, anche se i dati o i nomi delle colonne sembrano in inglese. 
  Non usare mai l’inglese a meno che l’utente non lo richieda esplicitamente.
- Calcola la disponibilità delle camere sottraendo le prenotazioni confermate dal numero totale di camere.
- Considera attive solo le prenotazioni con stato "Confermata". Ignora "Cancellata" e "In attesa".
- Controlla sempre che data_arrivo < data_partenza. Se mancano dati essenziali, chiedi chiarimenti.
- Non mostrare mai le query SQL.
- Non inventare prenotazioni, camere, prezzi o politiche non presenti nel database.
- Mantieni un tono professionale, cordiale ed elegante.
- Organizza le risposte in sezioni (es. Disponibilità, Dettagli, Note).
- Presenta prezzi in modo leggibile (es. "€ 150,00 a notte").

GESTIONE DELLE RICHIESTE:
- Se la domanda è ambigua, chiedi chiarimenti.
- Se la domanda non è pertinente, spiega gentilmente che non puoi aiutare.
- Se l’utente chiede informazioni non presenti nel database, specifica che non sono disponibili.

FUNZIONI AVANZATE (solo se richiesto dal management):
- Tasso di occupazione.
- Ricavi stimati.
- Periodi di alta affluenza.
- Camere più richieste.
"""
    print(api_key)
    db = SQLDatabase.from_uri(f"sqlite:///{DB_FILE}")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, openai_api_key=api_key)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    agent_executor = create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        verbose=True,
        agent_type="openai-tools",
        system_prefix=system_prompt
    )
    return agent_executor

# =====================================
# 4️⃣ STREAMLIT APP
# =====================================
def main():
    st.set_page_config(page_title="Smart Reservation Assistant", page_icon="🏨")
    st.title("🏨 Smart Reservation Assistant")
    st.markdown("### Chalet Monte Bianco")

    crea_e_popola_database()

    with st.expander("📂 Visualizza Dati del Database di Esempio"):
        camere_df, prenotazioni_df = mostra_dati_da_db()
        st.subheader("Inventario Camere")
        st.dataframe(camere_df, width=True)
        st.subheader("Elenco Prenotazioni")
        st.dataframe(prenotazioni_df, width=True)

    @st.cache_resource
    def get_agent():
        return crea_sql_agent()

    agent = get_agent()

    st.subheader("💬 Chiedi all'Assistente Virtuale")
    st.info("""
    **Puoi chiedere cose come:**
    - "Quante camere Standard sono libere per il 25 dicembre 2025?"
    - "Quali sono le date di check-in e check-out per la prenotazione di Mario Rossi?"
    - "Qual è il ricavo totale generato dalle prenotazioni confermate nel mese di dicembre 2025?"
    - "Qual è il tasso di occupazione per le suite domani?"
    """)

    query = st.text_input("La tua domanda:", key="user_query")

    if query:
        with st.spinner("Sto elaborando la tua richiesta..."):
            try:
                response = agent.invoke({"input": query})
                st.success("**Risposta:**")
                st.write(response["output"])
            except Exception as e:
                st.error(f"Si è verificato un errore: {e}")

if __name__ == "__main__":
    main()
