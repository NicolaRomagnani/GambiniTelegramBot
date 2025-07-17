import os
import json
import openai

# Qui c'è la tua chiave API
openai.api_key = "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"

def interroga_cliente(nome_cliente, domanda):
    path_file = f"clienti/{nome_cliente.replace(' ', '_')}.json"

    if not os.path.exists(path_file):
        print(f"❌ Nessun dato trovato per il cliente '{nome_cliente}'")
        return

    with open(path_file, "r", encoding="utf-8") as f:
        dati = json.load(f)

    prompt = f"""
Sei un assistente commerciale per Gambini S.p.A.

Hai a disposizione questo archivio JSON di interazioni con un cliente nel settore della carta tissue:

{json.dumps(dati, ensure_ascii=False, indent=2)}

Rispondi in modo professionale e chiaro alla seguente domanda del venditore:
"{domanda}"

Non inventare nulla. Se un'informazione non è presente, dillo chiaramente.
    """

    risposta = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=500
    )

    print("\n📣 Risposta GPT:")
    print(risposta["choices"][0]["message"]["content"])

# ESEMPIO DI UTILIZZO
if __name__ == "__main__":
    cliente = input("🔍 Nome cliente: ").strip()
    domanda = input("💬 Domanda da fare su questo cliente: ").strip()
    interroga_cliente(cliente, domanda)