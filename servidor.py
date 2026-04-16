"""
servidor.py — API que o frontend ARIA consome, agora usando o agente Agno real.
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback

# ─────────────────────────────────────────────────────────────────────────
# Importa o agente do arquivo vizinho
# ─────────────────────────────────────────────────────────────────────────
from agente_ia import agente_casa   # ← aqui está a mágica

app = Flask(__name__)
CORS(app)   # libera acesso do frontend

# ─────────────────────────────────────────────────────────────────────────
# Endpoint principal – recebe mensagem, chama o agente e retorna a resposta
# ─────────────────────────────────────────────────────────────────────────
@app.route("/api/comando", methods=["POST"])
def comando():
    data = request.get_json(force=True)
    mensagem = data.get("mensagem", "").strip()

    if not mensagem:
        return jsonify({"resposta": "Mensagem vazia."}), 400

    try:
        # Executa o agente Agno com a mensagem do usuário
        resposta = agente_casa.run(mensagem)
        # O objeto resposta tem .content (a string da resposta)
        texto_resposta = resposta.content
        return jsonify({"resposta": texto_resposta})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"resposta": f"Erro no agente: {str(e)}"}), 500

# ─────────────────────────────────────────────────────────────────────────
# Health check (opcional)
# ─────────────────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "servico": "ARIA Backend com Agno"}), 200

from flask import send_from_directory

@app.route('/')
def index():
    return send_from_directory('.', 'aria_interface.html')

if __name__ == "__main__":
    print("╔══════════════════════════════════════╗")
    print("║   ARIA — Servidor com Agno v2.0      ║")
    print("║   API: http://localhost:5000         ║")
    print("╚══════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5000, debug=False)
