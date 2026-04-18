"""
servidor.py — API Flask para o frontend ARIA.
  • Assina jrsilva/telemetria e mantém sensor_cache atualizado em tempo real.
  • Expõe /api/comando (agente IA) e /api/status (leitura do ESP32).
"""
import json
import threading
import traceback

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from agente_ia import agente_casa, sensor_cache   # compartilha o cache

# ─────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────
MQTT_BROKER   = "broker.emqx.io"
MQTT_PORT     = 1883
TOPIC_TEL     = "jrsilva/telemetria"   # tópico publicado pelo ESP32
RECONNECT_SEC = 5

# ─────────────────────────────────────────────────────────────────────────
# SUBSCRIBER MQTT — roda em thread separada
# ─────────────────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Conectado ao broker ({MQTT_BROKER})")
        client.subscribe(TOPIC_TEL)
        sensor_cache["mqtt"] = True
    else:
        print(f"[MQTT] Falha de conexão rc={rc}")
        sensor_cache["mqtt"] = False

def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Desconectado rc={rc} — reconectando em {RECONNECT_SEC}s")
    sensor_cache["mqtt"] = False

def on_message(client, userdata, msg):
    """Atualiza sensor_cache com cada payload de telemetria do ESP32."""
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        # Campos enviados pelo ESP32:
        # fumaca, fogo, temperatura, pressao, estado,
        # sirene, bomba, led, servo
        for key in ("fumaca", "fogo", "temperatura", "pressao",
                    "estado", "sirene", "bomba", "led", "servo"):
            if key in data:
                sensor_cache[key] = data[key]
        sensor_cache["mqtt"] = True
    except Exception as e:
        print(f"[MQTT] Erro ao parsear telemetria: {e}")

def start_mqtt_subscriber():
    """Loop de subscriber MQTT com reconexão automática — compatível paho 2.x."""
    # paho-mqtt 2.x exige CallbackAPIVersion explícito
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id="ARIA_Server_Sub",
        clean_session=True
    )
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()           # bloqueia até desconectar
        except Exception as e:
            print(f"[MQTT] Exceção: {e} — retry em {RECONNECT_SEC}s")
            sensor_cache["mqtt"] = False
            import time; time.sleep(RECONNECT_SEC)

# Inicia subscriber em thread daemon
threading.Thread(target=start_mqtt_subscriber, daemon=True, name="mqtt-sub").start()

# ─────────────────────────────────────────────────────────────────────────
# FLASK
# ─────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── /api/comando ──────────────────────────────────────────────────────────
@app.route("/api/comando", methods=["POST"])
def comando():
    from datetime import datetime
    data     = request.get_json(force=True)
    mensagem = data.get("mensagem", "").strip()
    if not mensagem:
        return jsonify({"resposta": "Mensagem vazia."}), 400
    try:
        # Injeta snapshot dos sensores direto no prompt — dados sempre frescos,
        # sem depender de cache interno do agente.
        s = dict(sensor_cache)
        agora = datetime.now().strftime("%H:%M:%S")

        temp_str = (f"{s.get('temperatura',-127):.1f}°C"
                    if s.get("temperatura") not in (None, -127)
                    else "sensor desconectado")

        snapshot = (
            f"\n\n[SNAPSHOT SENSORES @ {agora}]\n"
            f"led={s.get('led','?')}  servo={s.get('servo',0)}°\n"
            f"temperatura={temp_str}  fumaca={s.get('fumaca',0):.0f}ppm\n"
            f"fogo={s.get('fogo','normal')}  pressao={s.get('pressao',0)}kPa\n"
            f"estado={s.get('estado','NORMAL')}  "
            f"sirene={'ativa' if s.get('sirene') else 'inativa'}  "
            f"bomba={s.get('bomba','Desligado')}\n"
            f"[USE ESTES VALORES para responder perguntas sobre sensores]"
        )

        resposta = agente_casa.run(mensagem + snapshot)
        texto_resposta = resposta.content
        return jsonify({"resposta": texto_resposta})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"resposta": f"Erro no agente: {e}"}), 500

# ── /api/status ───────────────────────────────────────────────────────────
@app.route("/api/status", methods=["GET"])
def status():
    """
    Retorna o estado atual dos sensores e atuadores.
    Resposta exemplo:
    {
      "led": "on", "servo": 90,
      "temperatura": 25.3, "fumaca": 45, "fogo": "normal",
      "pressao": 80, "estado": "NORMAL",
      "sirene": 0, "bomba": "Desligado",
      "mqtt": true
    }
    """
    return jsonify(dict(sensor_cache))

# ── /health ───────────────────────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status":  "ok",
        "servico": "ARIA Backend",
        "mqtt":    sensor_cache.get("mqtt", False),
    }), 200

# ── Serve o frontend ──────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(".", "aria_interface.html")

# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("╔══════════════════════════════════════════╗")
    print("║   ARIA — Servidor v3.0 (sensores)        ║")
    print("║   API:  http://localhost:5000            ║")
    print("║   Sub:  jrsilva/telemetria               ║")
    print("╚══════════════════════════════════════════╝")
    app.run(host="0.0.0.0", port=5000, debug=False)
