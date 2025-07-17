import json
import os
from datetime import datetime

def genera_report(cliente):
    path_json = f"clienti/{cliente.replace(' ', '_')}.json"
    path_report = f"report/{cliente.replace(' ', '_')}_report.txt"

    if not os.path.exists(path_json):
        print("❌ Cliente non trovato.")
        return

    with open(path_json, 'r', encoding='utf-8') as f:
        dati = json.load(f)

    report_lines = []
    report_lines.append(f"🧾 REPORT CLIENTE: {cliente}")
    report_lines.append("=" * 50)
    report_lines.append(f"Ultima modifica dati: {dati.get('ultima_modifica', 'Data non disponibile')}")
    report_lines.append(f"Numero interazioni totali: {len(dati['interazioni'])}")
    report_lines.append("")

    for i, interazione in enumerate(dati["interazioni"], 1):
        report_lines.append(f"🔹 Interazione {i} - {interazione.get('timestamp', 'data sconosciuta')}")
        report_lines.append(f"- Tipo: {interazione.get('tipo_interazione', 'N/A')}")
        report_lines.append(f"- Problema: {interazione.get('problema', 'N/A')}")
        report_lines.append(f"- Azione: {interazione.get('azione', 'N/A')}")
        report_lines.append(f"- Urgenza: {interazione.get('urgenza', 'N/A')}")
        report_lines.append(f"- Prossimo step: {interazione.get('prossimo_step', 'N/A')}")
        note = interazione.get('note', '')
        if note:
            report_lines.append(f"- Note: {note}")
        report_lines.append("-" * 30)

    # Assicurati che esista la cartella "report"
    os.makedirs("report", exist_ok=True)

    with open(path_report, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

    print(f"✅ Report generato: {path_report}")

# Esegui manualmente
if __name__ == "__main__":
    cliente = input("🧾 Inserisci il nome del cliente: ").strip()
    genera_report(cliente)