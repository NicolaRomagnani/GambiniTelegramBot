import os
import json
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from pathlib import Path
import openai

# --- Configurazione e Inizializzazione ---

load_dotenv()
openai.api_key = "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"
TELEGRAM_TOKEN = "7930781685:AAG9fBHNnWJrF6j8kErKtvjrajFy9DSGVYY"

CARTELLA_CLIENTI = "clienti"

# Configurazione del logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Utility per la gestione dei dati cliente ---

def formatta_nome_cliente_per_file(nome_cliente: str) -> str:
    """Formatta il nome del cliente per corrispondere al nome del file (minuscolo, underscore)."""
    return nome_cliente.replace(' ', '_').lower()

def carica_dati_cliente(nome_cliente: str) -> dict | None:
    """
    Carica i dati di un cliente dal file JSON corrispondente.
    Ritorna un dizionario con i dati o None se il file non esiste.
    """
    nome_file_formattato = formatta_nome_cliente_per_file(nome_cliente)
    file_path = Path(CARTELLA_CLIENTI) / f"{nome_file_formattato}.json"
    
    if not file_path.exists():
        logger.warning(f"File dati non trovato per il cliente: {file_path}")
        return None
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Errore nella lettura del file JSON {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Errore generico nel caricamento dati cliente {file_path}: {e}")
        return None

async def gpt_call(prompt: str, model: str = "gpt-4o", temperature: float = 0.5, max_tokens: int = 1000) -> str:
    """
    Funzione ausiliaria per effettuare chiamate asincrone all'API OpenAI.
    Aumentato il modello a gpt-4o e max_tokens per risposte più elaborate.
    """
    try:
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except openai.error.OpenAIError as e:
        logger.error(f"Errore OpenAI: {e}")
        return f"Si è verificato un problema con l'intelligenza artificiale: {e}"
    except Exception as e:
        logger.error(f"Errore durante la chiamata GPT: {e}")
        return "Si è verificato un errore inaspettato nell'elaborazione della richiesta."

# --- Comandi GPT per interpretazione e generazione ---

async def interpreta_messaggio_gpt(testo: str) -> dict:
    """
    Usa GPT per interpretare il messaggio dell'utente, identificare cliente e comando.
    Restituisce un dizionario con 'cliente', 'comando', 'dettagli' e 'linguaggio_naturale_risposta_iniziale'.
    Aggiunto il comando 'email_ringraziamento'.
    """
    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A., azienda che progetta e produce linee di trasformazione per la carta tissue. Sei esperto, informato, preciso, dettagliato e concreto.
    Ricevi messaggi da un venditore o da un dipendente dell'azienda.

    **Regola chiave:** Identifica sempre il cliente principale MENZIONATO ESPLICITAMENTE nella "RICHIESTA". Se un cliente è esplicitamente nominato nella RICHIESTA, IGNORA qualsiasi "CONTESTO" precedente e considera quel cliente come il focus. Se NESSUN cliente è esplicitamente nominato nella RICHIESTA, usa il "CONTESTO" fornito.

    La tua input potrebbe iniziare con "CONTESTO: [NomeClienteContesto]. RICHIESTA: [TestoOriginale]".
    - Se [TestoOriginale] contiene un nome di cliente, quello è il cliente principale.
    - Se [TestoOriginale] NON contiene un nome di cliente, allora [NomeClienteContesto] è il cliente principale.

    Il tuo compito è analizzare la RICHIESTA e identificare:
    1. Il nome del cliente. Questo deve essere il cliente principale identificato come sopra. Lascia a null se nessun cliente è identificabile.
    2. Il tipo di informazione richiesta. Usa le seguenti categorie: "problemi", "urgenze", "statistiche", "appuntamenti", "sintesi", "report_completo", "elenco_clienti", "benvenuto", "chiarimento", "email_ringraziamento", "altro".
    3. Qualsiasi dettaglio aggiuntivo rilevante per la richiesta (es. il tipo specifico di problema).
    4. Se la richiesta è troppo generica o non chiara per essere elaborata subito con un comando specifico, fornisci una breve "linguaggio_naturale_risposta_iniziale" che chieda chiarimenti. Altrimenti, lascia a null.

    Rispondi ESCLUSIVAMENTE con un blocco JSON, seguendo lo schema seguente. Se non hai un'informazione, usa `null`.

    ```json
    {{
      "cliente": "NomeCliente",
      "comando": "tipo_comando_identificato",
      "dettagli": "ulteriori_dettagli_se_necessari",
      "linguaggio_naturale_risposta_iniziale": "Se il messaggio è ambiguo, fornisci qui una breve risposta che chieda chiarimenti."
    }}
    ```

    Esempi di interazione:

    Utente: CONTESTO: Essity. RICHIESTA: Problemi.
    ```json
    {{ "cliente": "Essity", "comando": "problemi", "dettagli": null, "linguaggio_naturale_risposta_iniziale": null }}
    ```

    Utente: CONTEXT: Essity. RICHIESTA: Raccontami tutto di Wepa.
    ```json
    {{ "cliente": "Wepa", "comando": "report_completo", "dettagli": null, "linguaggio_naturale_risposta_iniziale": null }}
    ```

    Utente: Dimmi il report completo di Sofidel
    ```json
    {{ "cliente": "Sofidel", "comando": "report_completo", "dettagli": null, "linguaggio_naturale_risposta_iniziale": null }}
    ```

    Utente: Fammi una sintesi di Lucart.
    ```json
    {{ "cliente": "Lucart", "comando": "sintesi", "dettagli": null, "linguaggio_naturale_risposta_iniziale": null }}
    ```

    Utente: Solo ciao
    ```json
    {{ "cliente": null, "comando": "benvenuto", "dettagli": null, "linguaggio_naturale_risposta_iniziale": "Ciao! Come posso aiutarti oggi?" }}
    ```

    Utente: Non ho capito
    ```json
    {{ "cliente": null, "comando": "chiarimento", "dettagli": null, "linguaggio_naturale_risposta_iniziale": "Potresti riformulare la tua richiesta o essere più specifico? Sono qui per aiutarti." }}
    ```

    Utente: Elenca i clienti
    ```json
    {{ "cliente": null, "comando": "elenco_clienti", "dettagli": null, "linguaggio_naturale_risposta_iniziale": null }}
    ```
    Utente: A chi devo mandare un'e-mail di ringraziamento?
    ```json
    {{ "cliente": null, "comando": "email_ringraziamento", "dettagli": "e-mail di ringraziamento", "linguaggio_naturale_risposta_iniziale": null }}
    ```
    Utente: CONTESTO: Essity. RICHIESTA: A chi devo mandare un'e-mail di ringraziamento?
    ```json
    {{ "cliente": "Essity", "comando": "email_ringraziamento", "dettagli": "e-mail di ringraziamento", "linguaggio_naturale_risposta_iniziale": null }}
    ```

    Utente: {testo}
    """
    
    risposta_gpt_raw = await gpt_call(prompt, model="gpt-3.5-turbo", max_tokens=300, temperature=0.0)
    
    # Estrai il blocco JSON dalla risposta
    blocchi = re.findall(r"```json\s*(\{.*?\})\s*```", risposta_gpt_raw, re.DOTALL)
    
    if blocchi:
        try:
            dati_json = json.loads(blocchi[0])
            # Normalizza il nome del cliente estratto per coerenza (solo capitalizza la prima lettera)
            if dati_json.get("cliente"):
                dati_json["cliente"] = dati_json["cliente"].capitalize()
            return dati_json
        except json.JSONDecodeError:
            logger.error(f"Errore nel parsing JSON da GPT: {blocchi[0]}")
            return {"cliente": None, "comando": "errore_json", "dettagli": risposta_gpt_raw, "linguaggio_naturale_risposta_iniziale": "Ho avuto un problema a capire i dettagli della tua richiesta. Riprova o sii più esplicito."}
    else:
        logger.warning(f"Nessun blocco JSON valido trovato nella risposta GPT: {risposta_gpt_raw}")
        return {"cliente": None, "comando": "fallimento_interpretazione", "dettagli": risposta_gpt_raw, "linguaggio_naturale_risposta_iniziale": "Non sono riuscito a interpretare la tua richiesta. Puoi essere più specifico, per favore?"}

# --- Funzioni di risposta specifiche per comandi (ORA USANO GPT PER GENERAZIONE) ---

async def invia_report(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """Invia un report completo di tutte le interazioni del cliente in linguaggio naturale."""
    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto un report completo sul cliente '{cliente}'.
    Ecco tutti i dati disponibili sulle interazioni con {cliente}:
    {json.dumps(dati_cliente, indent=2, ensure_ascii=False)}

    Genera un report dettagliato e ben strutturato, utilizzando un linguaggio naturale e professionale.
    Organizza le informazioni in modo logico:
    - Inizia con un'introduzione concisa.
    - Elenca le interazioni in ordine cronologico inverso (dalla più recente). Per ogni interazione, includi tipo, data, problema (se presente), azione, urgenza, prossimo step e note.
    - Concludi con un breve riepilogo o considerazioni generali.
    Usa la formattazione Markdown per migliorare la leggibilità (es. titoli, grassetti, elenchi).
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=1500)
    for chunk in split_long_message(risposta_generata):
        await update.message.reply_text(chunk, parse_mode='Markdown')

async def invia_sintesi(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """Genera e invia una sintesi testuale delle informazioni principali di un cliente tramite GPT."""
    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto una sintesi del cliente '{cliente}'.
    Ecco i dati disponibili per il cliente {cliente}:
    {json.dumps(dati_cliente, indent=2, ensure_ascii=False)}

    Genera una sintesi concisa ma informativa e in linguaggio naturale sulle informazioni chiave del cliente.
    Includi:
    - Dati generali (settore, ultima modifica).
    - Referenti principali.
    - Riepilogo dei problemi aperti e delle urgenze (se presenti).
    - Prossimi appuntamenti o step principali (se presenti).
    - Qualsiasi altra nota o informazione rilevante.
    Rendi la risposta professionale e facile da leggere per un ingegnere. Usa la formattazione Markdown (es. **grassetto**, _corsivo_).
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=700)
    await update.message.reply_text(risposta_generata, parse_mode='Markdown')

async def invia_problemi(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """Invia un elenco dei problemi aperti per un cliente in linguaggio naturale."""
    problemi_aperti = [i for i in dati_cliente.get('interazioni', []) if i.get('problema', '').lower() not in ('nessun problema', '', None) and i.get('risolto', False) == False]
    
    if not problemi_aperti:
        await update.message.reply_text(f"✅ Il cliente '{cliente.capitalize()}' non ha problemi aperti rilevanti al momento. Ottime notizie!", parse_mode='Markdown')
        return

    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto di elencare i problemi aperti del cliente '{cliente}'.
    Ecco i problemi aperti rilevati:
    {json.dumps(problemi_aperti, indent=2, ensure_ascii=False)}

    Genera una risposta in linguaggio naturale che elenchi chiaramente ogni problema aperto.
    Per ogni problema, includi: descrizione, tipo di interazione, azione intrapresa, prossimo step, livello di urgenza e data dell'interazione.
    Rendi la risposta concisa ma informativa. Usa la formattazione Markdown per la leggibilità (es. grassetti per i nomi dei problemi).
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=700)
    for chunk in split_long_message(risposta_generata):
        await update.message.reply_text(chunk, parse_mode='Markdown')

async def invia_urgenze(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """Invia un elenco delle urgenze per un cliente in linguaggio naturale."""
    urgenze = [i for i in dati_cliente.get('interazioni', []) if i.get('urgenza', '').lower() == 'alta' and i.get('risolto', False) == False]
    
    if not urgenze:
        await update.message.reply_text(f"✅ Nessuna urgenza attiva segnalata per il cliente '{cliente.capitalize()}'. Puoi stare tranquillo su questo fronte.", parse_mode='Markdown')
        return

    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto di elencare le urgenze attive per il cliente '{cliente}'.
    Ecco le urgenze attive:
    {json.dumps(urgenze, indent=2, ensure_ascii=False)}

    Genera una risposta in linguaggio naturale che evidenzi le urgenze attive.
    Per ogni urgenza, includi: descrizione del problema, tipo di interazione, azione intrapresa, prossimo step, e data.
    Sottolinea la criticità. Usa la formattazione Markdown.
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=700)
    for chunk in split_long_message(risposta_generata):
        await update.message.reply_text(chunk, parse_mode='Markdown')

async def invia_statistiche(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """Invia statistiche sulle interazioni per un cliente in linguaggio naturale."""
    interazioni = dati_cliente.get('interazioni', [])
    conteggio = {
        "visita": 0, "chiamata": 0, "email": 0,
        "service": 0, "offerta": 0, "altro": 0
    }
    
    for i in interazioni:
        tipo = i.get("tipo_interazione", "").lower()
        if tipo in conteggio:
            conteggio[tipo] += 1
        else:
            conteggio["altro"] += 1
            
    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto statistiche sulle interazioni con il cliente '{cliente}'.
    Ecco i conteggi delle interazioni per tipo:
    {json.dumps(conteggio, indent=2)}
    Il cliente ha avuto un totale di {len(interazioni)} interazioni.

    Genera una risposta in linguaggio naturale che presenti queste statistiche in modo chiaro e utile.
    Commenta i dati, ad esempio, quale tipo di interazione è più frequente.
    Usa la formattazione Markdown (es. elenchi, grassetti).
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=500)
    await update.message.reply_text(risposta_generata, parse_mode='Markdown')

async def invia_appuntamenti(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """Invia un elenco degli appuntamenti futuri per un cliente in linguaggio naturale."""
    appuntamenti_futuri = [
        i for i in dati_cliente.get('interazioni', [])
        if i.get('tipo_interazione', '').lower() == 'visita' and i.get('timestamp') and
           datetime.strptime(i['timestamp'].split(' ')[0], '%Y-%m-%d').date() >= datetime.now().date()
    ]
    appuntamenti_futuri.sort(key=lambda x: datetime.strptime(x['timestamp'].split(' ')[0], '%Y-%m-%d'))

    if not appuntamenti_futuri:
        await update.message.reply_text(f"✅ Nessun appuntamento futuro pianificato per il cliente '{cliente.capitalize()}'. Sei libero per ora!", parse_mode='Markdown')
        return

    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto gli appuntamenti futuri con il cliente '{cliente}'.
    Ecco i prossimi appuntamenti pianificati:
    {json.dumps(appuntamenti_futuri, indent=2, ensure_ascii=False)}

    Genera una risposta in linguaggio naturale che elenchi chiaramente gli appuntamenti.
    Per ogni appuntamento, includi: data, tipo, eventuali note e obiettivi (prossimo step).
    Sottolinea il più imminente. Usa la formattazione Markdown.
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=700)
    for chunk in split_long_message(risposta_generata):
        await update.message.reply_text(chunk, parse_mode='Markdown')

async def invia_elenco_clienti(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invia un elenco di tutti i clienti disponibili nel database in linguaggio naturale."""
    clienti_disponibili = [f.stem.replace('_', ' ').title() for f in Path(CARTELLA_CLIENTI).glob("*.json")]
    
    if not clienti_disponibili:
        await update.message.reply_text("Non ho trovato nessun cliente nel database. Dovremmo crearne qualcuno!", parse_mode='Markdown')
        return
    
    prompt = f"""
    Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto l'elenco dei clienti disponibili.
    Ecco la lista dei clienti: {', '.join(sorted(clienti_disponibili))}.

    Genera una risposta in linguaggio naturale che presenti questa lista in modo amichevole e organizzato.
    Incoraggia l'utente a chiedere dettagli su un cliente specifico.
    Usa la formattazione Markdown.
    """
    risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=500)
    await update.message.reply_text(risposta_generata, parse_mode='Markdown')

async def invia_email_ringraziamento_info(update: Update, context: ContextTypes.DEFAULT_TYPE, cliente: str, dati_cliente: dict):
    """
    Fornisce informazioni su chi mandare l'email di ringraziamento,
    cercando nelle note del cliente o inferendo dal contesto.
    """
    interazioni_recente_con_nota_email = [
        i for i in dati_cliente.get('interazioni', [])
        if "ringraziamento" in i.get('note', '').lower() or "ringraziare" in i.get('prossimo_step', '').lower()
    ]

    # Ordina per data, dalla più recente
    interazioni_recente_con_nota_email.sort(key=lambda x: datetime.strptime(x['timestamp'].split(' ')[0], '%Y-%m-%d'), reverse=True)

    if interazioni_recente_con_nota_email:
        interazione_pertinente = interazioni_recente_con_nota_email[0]
        data_interazione = interazione_pertinente.get('timestamp', 'N/D').split(' ')[0]
        referente = dati_cliente.get('referenti', [{}])[0].get('nome', 'il referente principale') # Prende il primo referente come default
        
        prompt = f"""
        Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto a chi mandare un'e-mail di ringraziamento per il cliente '{cliente}'.
        Abbiamo trovato una nota o un prossimo step rilevante sull'ultima interazione ({data_interazione}) che indica la necessità di un ringraziamento.
        Il referente principale registrato è '{referente}'.
        Ecco i dettagli dell'interazione pertinente:
        {json.dumps(interazione_pertinente, indent=2, ensure_ascii=False)}
        
        Genera una risposta in linguaggio naturale che suggerisca a chi inviare l'email di ringraziamento.
        Indica il cliente e, se disponibile, un referente o un suggerimento su come trovare il contatto corretto.
        Rendi la risposta concisa e utile. Evita di inventare testi di email se non esplicitamente richiesto.
        Usa la formattazione Markdown.
        """
        risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=300)
    else:
        # Se non ci sono note specifiche, genera una risposta più generica ma sul cliente corretto
        prompt = f"""
        Sei un assistente commerciale della Gambini S.p.A.. Il venditore ti ha chiesto a chi mandare un'e-mail di ringraziamento per il cliente '{cliente}'.
        Non ho trovato note o prossimi step specifici che menzionino esplicitamente un'email di ringraziamento per '{cliente}'.
        Il referente principale registrato per {cliente} è '{dati_cliente.get('referenti', [{}])[0].get('nome', 'il referente principale') if dati_cliente.get('referenti') else 'un referente valido'}'.
        
        Genera una risposta in linguaggio naturale che suggerisca a chi inviare l'email di ringraziamento, basandoti sulla buona pratica generale, ma senza inventare dettagli.
        Consiglia di inviarla al referente con cui si è avuta l'ultima interazione o al referente principale, e di verificare i contatti.
        Usa la formattazione Markdown.
        """
        risposta_generata = await gpt_call(prompt, model="gpt-4o", max_tokens=300)
    
    await update.message.reply_text(risposta_generata, parse_mode='Markdown')


def split_long_message(text: str, max_length: int = 4096) -> list[str]:
    """Divide un messaggio lungo in più parti per rispettare il limite di Telegram."""
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    # Dividi per linea e aggiungi al chunk finché non supera max_length
    for line in text.splitlines(keepends=True): # keepends=True per mantenere i newline
        if len(current_chunk) + len(line) <= max_length:
            current_chunk += line
        else:
            chunks.append(current_chunk)
            current_chunk = line
    if current_chunk: # Aggiungi l'ultimo chunk
        chunks.append(current_chunk)
    return chunks

# --- Comandi Telegram (Handler) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start del bot."""
    welcome_message = (
        "🤖 Ciao! Sono l'assistente commerciale di Gambini S.p.A. "
        "Sono qui per aiutarti a trovare rapidamente informazioni sui clienti. "
        "Chiedimi pure:\n"
        "- `Sintesi di Rotocart`\n"
        "- `Problemi con Essity`\n"
        "- `Quando devo andare da Lucart?`\n"
        "- `Fammi il report completo di Sofidel`\n"
        "- `Elenco clienti`\n\n"
        "E non preoccuparti, mi ricorderò sempre di quale cliente stiamo parlando per le domande successive! 😉"
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    if 'last_customer_context' in context.user_data:
        del context.user_data['last_customer_context']
        logger.info("Contesto cliente resettato con /start.")

async def cliente_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cliente NOME_CLIENTE per ottenere una sintesi dettagliata via GPT."""
    if not context.args:
        await update.message.reply_text("❗️ Usa il comando così: `/cliente NOME_CLIENTE` per una sintesi dettagliata da parte dell'AI.", parse_mode='Markdown')
        return

    nome_cliente = " ".join(context.args)
    dati_cliente = carica_dati_cliente(nome_cliente)
    
    if not dati_cliente:
        prompt_not_found = f"Il venditore ha chiesto informazioni sul cliente '{nome_cliente}'. Questo cliente non è presente nel database. Formula una frase simpatica e incoraggiante per dirlo a un ingegnere con la passione per la politica, suggerendo di controllare il nome o di aggiungerlo al database."
        risposta_ai_no_data = await gpt_call(prompt_not_found, model="gpt-4o", max_tokens=150)
        await update.message.reply_text(risposta_ai_no_data, parse_mode='Markdown')
        context.user_data.pop('last_customer_context', None)
        return

    # Richiama la funzione invia_sintesi che ora usa GPT
    await invia_sintesi(update, context, nome_cliente, dati_cliente)
    context.user_data['last_customer_context'] = nome_cliente

# --- Gestione messaggi liberi e flusso principale ---

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Gestisce i messaggi di testo non-comando, interpretandoli con GPT e rispondendo di conseguenza.
    Mantiene il contesto dell'ultimo cliente menzionato.
    """
    user_text = update.message.text
    logger.info(f"Messaggio ricevuto: {user_text}")

    # Recupera l'ultimo cliente dal contesto se disponibile
    last_customer_in_context = context.user_data.get('last_customer_context')
    
    # 1. Tentativo di pre-identificazione del cliente nel testo tramite i nomi dei file
    clienti_nel_database = {f.stem.replace('_', ' ').lower() for f in Path(CARTELLA_CLIENTI).glob("*.json")}
    
    cliente_esplicito_nel_messaggio = None
    for db_client_name in sorted(list(clienti_nel_database), key=len, reverse=True):
        if db_client_name in user_text.lower():
            cliente_esplicito_nel_messaggio = db_client_name.title()
            break

    # 2. Prepara il testo per GPT, aggiungendo il contesto solo se necessario
    text_for_gpt = user_text
    if last_customer_in_context and not cliente_esplicito_nel_messaggio:
        text_for_gpt = f"CONTESTO: {last_customer_in_context}. RICHIESTA: {user_text}"
        logger.info(f"Aggiunto contesto '{last_customer_in_context}' al messaggio: '{text_for_gpt}'")
    else:
        logger.info(f"Nessun contesto aggiunto. Cliente esplicito nel messaggio: '{cliente_esplicito_nel_messaggio if cliente_esplicito_nel_messaggio else 'Nessuno'}'. Contesto precedente: '{last_customer_in_context if last_customer_in_context else 'Nessuno'}'")


    # Interpretazione del messaggio tramite GPT
    interpretazione_gpt = await interpreta_messaggio_gpt(text_for_gpt)
    
    cliente_riconosciuto_da_gpt = interpretazione_gpt.get("cliente")
    comando_riconosciuto_da_gpt = interpretazione_gpt.get("comando")
    risposta_iniziale_gpt = interpretazione_gpt.get("linguaggio_naturale_risposta_iniziale")
    
    logger.info(f"Interpretazione GPT: Cliente='{cliente_riconosciuto_da_gpt}', Comando='{comando_riconosciuto_da_gpt}', Risposta Iniziale='{risposta_iniziale_gpt}'")

    # Gestione delle risposte immediate da GPT (chiarimenti, saluti, fallimenti)
    if risposta_iniziale_gpt:
        await update.message.reply_text(risposta_iniziale_gpt, parse_mode='Markdown')
        if not cliente_riconosciuto_da_gpt and 'last_customer_context' in context.user_data:
            del context.user_data['last_customer_context']
            logger.info("Contesto cliente rimosso a causa di risposta iniziale generica.")
        return

    # Aggiorna il contesto dell'ultimo cliente riconosciuto da GPT
    if cliente_riconosciuto_da_gpt:
        context.user_data['last_customer_context'] = cliente_riconosciuto_da_gpt
        logger.info(f"Contesto aggiornato: last_customer_context = {cliente_riconosciuto_da_gpt}")
    elif not cliente_riconosciuto_da_gpt and last_customer_in_context:
        cliente_riconosciuto_da_gpt = last_customer_in_context
        logger.info(f"GPT non ha riconosciuto un cliente nel nuovo messaggio, usando il contesto precedente: {cliente_riconosciuto_da_gpt}")
    
    # Se, a questo punto, non abbiamo un cliente, o il comando è specifico e non ha un cliente
    # e non è "elenco_clienti" (che non lo richiede), chiediamo chiarimenti.
    if not cliente_riconosciuto_da_gpt and comando_riconosciuto_da_gpt not in ["elenco_clienti", "benvenuto", "chiarimento"]:
        prompt_clarification = f"Il venditore ha chiesto '{user_text}'. Non sono riuscito a identificare il cliente e non ho un contesto valido. Formula una domanda educata per chiedere il nome del cliente, considerando che l'utente è un ingegnere e apprezzerebbe una risposta concisa."
        response_clarification = await gpt_call(prompt_clarification, model="gpt-4o", max_tokens=100)
        await update.message.reply_text(response_clarification, parse_mode='Markdown')
        context.user_data.pop('last_customer_context', None)
        return
    
    # Se il comando è "elenco_clienti", eseguilo senza dati cliente
    if comando_riconosciuto_da_gpt == "elenco_clienti":
        await invia_elenco_clienti(update, context)
        context.user_data.pop('last_customer_context', None)
        return

    # A questo punto, dovremmo avere un cliente_riconosciuto_da_gpt valido
    dati_cliente = carica_dati_cliente(cliente_riconosciuto_da_gpt)
    if not dati_cliente:
        prompt_no_data = f"Il cliente '{cliente_riconosciuto_da_gpt}' è stato riconosciuto, ma non è presente nel database (file JSON non trovato). Inventa una frase simpatica per dirlo al venditore, che è un ingegnere, magari con un leggero riferimento alla sua passione per la politica, e proponi di aggiungerlo o di controllare il nome."
        risposta_gpt_no_data = await gpt_call(prompt_no_data, model="gpt-4o", max_tokens=150)
        await update.message.reply_text(risposta_gpt_no_data, parse_mode='Markdown')
        context.user_data.pop('last_customer_context', None)
        return
    
    # Esegui l'azione basata sul comando riconosciuto da GPT, passando i dati caricati
    if comando_riconosciuto_da_gpt == "sintesi":
        await invia_sintesi(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    elif comando_riconosciuto_da_gpt == "problemi":
        await invia_problemi(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    elif comando_riconosciuto_da_gpt == "urgenze":
        await invia_urgenze(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    elif comando_riconosciuto_da_gpt == "statistiche":
        await invia_statistiche(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    elif comando_riconosciuto_da_gpt == "appuntamenti":
        await invia_appuntamenti(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    elif comando_riconosciuto_da_gpt == "report_completo":
        await invia_report(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    elif comando_riconosciuto_da_gpt == "email_ringraziamento":
        await invia_email_ringraziamento_info(update, context, cliente_riconosciuto_da_gpt, dati_cliente)
    else:
        # Se il comando non è riconosciuto o è "altro", usa GPT per una risposta più generica
        prompt_generico = f"""
        L'utente ha chiesto: "{user_text}".
        Il bot ha identificato il cliente: {cliente_riconosciuto_da_gpt}.
        Ecco i dati disponibili per {cliente_riconosciuto_da_gpt}:
        {json.dumps(dati_cliente, indent=2, ensure_ascii=False)}

        Fornisci una risposta utile, concisa e professionale basata sui dati disponibili o sulla natura della domanda. Se le informazioni non sono direttamente presenti, fai delle inferenze intelligenti o suggerisci dove trovarle/cosa fare. Sei un assistente per un venditore di Gambini S.p.A. Formatta con Markdown per chiarezza.
        """
        risposta_gpt_generica = await gpt_call(prompt_generico, model="gpt-4o", max_tokens=400, temperature=0.5)
        await update.message.reply_text(risposta_gpt_generica, parse_mode='Markdown')


# --- Main Function ---

def main():
    """Avvia il bot."""
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Handlers per i comandi specifici
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cliente", cliente_command))
    
    # Wrapper generico per i comandi che richiedono un cliente
    async def cmd_wrapper(func, update, context):
        if not context.args:
            cliente_target = context.user_data.get('last_customer_context')
            if not cliente_target:
                await update.message.reply_text("Di quale cliente hai bisogno di informazioni? Specifica il nome o usa un comando completo come `/problemi Essity`.", parse_mode='Markdown')
                return
        else:
            cliente_target = " ".join(context.args)

        dati = carica_dati_cliente(cliente_target)
        if not dati:
            await update.message.reply_text(f"❌ Nessun dato trovato per il cliente '{cliente_target}'.", parse_mode='Markdown')
            context.user_data.pop('last_customer_context', None)
            return
        context.user_data['last_customer_context'] = cliente_target
        await func(update, context, cliente_target, dati)

    # Assicurati che le funzioni chiamate da CommandHandler siano quelle che prendono `dati_cliente`
    application.add_handler(CommandHandler("problemi", lambda u, c: cmd_wrapper(invia_problemi, u, c)))
    application.add_handler(CommandHandler("urgenze", lambda u, c: cmd_wrapper(invia_urgenze, u, c)))
    application.add_handler(CommandHandler("statistiche", lambda u, c: cmd_wrapper(invia_statistiche, u, c)))
    application.add_handler(CommandHandler("appuntamenti", lambda u, c: cmd_wrapper(invia_appuntamenti, u, c)))
    application.add_handler(CommandHandler("report", lambda u, c: cmd_wrapper(invia_report, u, c)))
    
    application.add_handler(CommandHandler("clienti", invia_elenco_clienti))
    application.add_handler(CommandHandler("email_ringraziamento", lambda u, c: cmd_wrapper(invia_email_ringraziamento_info, u, c))) # Aggiunto handler specifico
    

    # Handler per tutti i messaggi di testo non-comando
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))

    logger.info("📡 Bot attivo. In attesa di messaggi...")
    application.run_polling()

if __name__ == "__main__":
    main()