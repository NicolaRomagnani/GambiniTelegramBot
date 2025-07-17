import os
import telebot
from dotenv import load_dotenv
import openai
import whisper
import json
from datetime import datetime
import tempfile

# Carica variabili ambiente
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# Inizializza bot Telegram e OpenAI
bot = telebot.TeleBot(TELEGRAM_TOKEN)
openai.api_key = "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"
model = whisper.load_model("large")

# Assicurati che esistano le cartelle
os.makedirs("clienti", exist_ok=True)
os.makedirs("logs", exist_ok=True)

def trascrivi_audio(path):
    result = model.transcribe(path, language="italian")
    return result["text"]

def analizza_con_gpt(testo):
    prompt = f"""
Sei un assistente commerciale per Gambini S.p.A., azienda che produce linee per la trasformazione della carta tissue.

Ricevi un messaggio vocale da un venditore. Estrai le seguenti informazioni e restituiscile in JSON valido, senza alcuna spiegazione:

- cliente: nome dell'azienda cliente
- tipo_interazione: (visita, chiamata, email, service, offerta)
- problema: descrizione del problema o situazione
- azione: cosa ha fatto il venditore
- urgenza: (bassa, media, alta)
- prossimo_step: prossima azione da fare
- note: eventuali note aggiuntive

Testo del messaggio:
\"\"\"{testo}\"\"\"
"""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )
    return response.choices[0].message.content

def salva_interazione(json_data, cliente):
    file_path = f"clienti/{cliente.replace(' ', '_')}.json"
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            storico = json.load(f)
    else:
        storico = {"cliente": cliente, "interazioni": []}

    dati = json.loads(json_data)
    dati["timestamp"] = datetime.now().isoformat()
    storico["interazioni"].append(dati)

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(storico, f, indent=2, ensure_ascii=False)

    return dati

@bot.message_handler(content_types=['voice', 'audio'])
def gestisci_vocale(message):
    try:
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_audio:
            temp_audio.write(downloaded_file)
            audio_path = temp_audio.name

        testo = trascrivi_audio(audio_path)
        bot.reply_to(message, f"📝 Trascrizione:\n{testo}")

        risposta_json = analizza_con_gpt(testo)
        dati = json.loads(risposta_json)
        salva_interazione(risposta_json, dati.get("cliente", "Cliente_Sconosciuto"))

        # Costruisci risposta utente
        risposta = f"""
🏢 {dati.get("cliente", "N/A")}
📌 Tipo: {dati.get("tipo_interazione", "N/A")}
⚠️ Problema: {dati.get("problema", "N/A")}
✅ Azione: {dati.get("azione", "N/A")}
🔥 Urgenza: {dati.get("urgenza", "N/A")}
🔜 Prossimo step: {dati.get("prossimo_step", "N/A")}
🗒 Note: {dati.get("note", "N/A")}
"""
        bot.send_message(message.chat.id, risposta.strip())

    except Exception as e:
        bot.reply_to(message, f"❌ Errore: {e}")

@bot.message_handler(commands=['start', 'help'])
def start(message):
    bot.reply_to(message, "🎤 Inviami un vocale con aggiornamenti su un cliente.")

print("🚀 Bot Telegram in ascolto...")
bot.polling()