"""
servidor.py — ARIA Backend v4.0
  • SEM thread MQTT — o browser assina diretamente via WebSocket MQTT
  • /api/comando recebe { mensagem, sensores } com dados frescos do browser
"""
import traceback
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from agente_ia import agente_casa

app = Flask(__name__)
CORS(app)

@app.route("/api/comando", methods=["POST"])
def comando():
    data     = request.get_json(force=True)
    mensagem = data.get("mensagem", "").strip()
    sensores = data.get("sensores", {})   # valores frescos enviados pelo browser

    if not mensagem:
        return jsonify({"resposta": "Mensagem vazia."}), 400

    try:
        agora = datetime.now().strftime("%H:%M:%S")
        s     = sensores

        temp = s.get("temperatura")
        if temp is None or str(temp) == "-127":
            temp_str = "sensor desconectado"
        else:
            try:    temp_str = f"{float(temp):.1f}°C"
            except: temp_str = f"{temp}°C"

        snapshot = (
            f"\n\n[SNAPSHOT SENSORES @ {agora}]\n"
            f"led={s.get('led','?')}  servo={s.get('servo','?')}°\n"
            f"temperatura={temp_str}  fumaca={s.get('fumaca','?')}ppm\n"
            f"fogo={s.get('fogo','normal')}  pressao={s.get('pressao','?')}kPa\n"
            f"estado={s.get('estado','NORMAL')}  "
            f"sirene={'ativa' if s.get('sirene') else 'inativa'}  "
            f"bomba={s.get('bomba','Desligado')}\n"
            "[USE ESTES VALORES para responder perguntas sobre sensores]"
        )

        resposta = agente_casa.run(mensagem + snapshot)
        return jsonify({"resposta": resposta.content})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"resposta": f"Erro: {e}"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "versao": "4.0"}), 200

@app.route("/")
def index():
    return send_from_directory(".", "aria_interface.html")

if __name__ == "__main__":
    print("ARIA Servidor v4.0 — http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
