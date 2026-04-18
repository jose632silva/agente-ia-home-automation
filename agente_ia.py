"""
agente_ia.py — ARIA: Assistente Residencial Inteligente
Controla LED/servo e responde perguntas sobre sensores do ESP32.
"""
import os
import json
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from agno.agent import Agent
from agno.tools import tool
from agno.models.openai import OpenAIChat
from agno.models.groq import Groq

# ─────────────────────────────────────────────────────────────────────────
# 1. VARIÁVEIS DE AMBIENTE
# ─────────────────────────────────────────────────────────────────────────
load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "").lower()
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "jrsilva/comando")

# ─────────────────────────────────────────────────────────────────────────
# 2. CACHE DE SENSORES — compartilhado com servidor.py via importação
# ─────────────────────────────────────────────────────────────────────────
sensor_cache: dict = {
    "led":         "off",
    "servo":       0,
    "fumaca":      0.0,
    "fogo":        "normal",
    "temperatura": None,
    "pressao":     0,
    "estado":      "NORMAL",
    "sirene":      0,
    "bomba":       "Desligado",
    "mqtt":        False,
}

# ─────────────────────────────────────────────────────────────────────────
# 3. MODELO
# ─────────────────────────────────────────────────────────────────────────
def criar_modelo():
    if MODEL_PROVIDER == "groq":
        if not GROQ_API_KEY:
            raise ValueError("MODEL_PROVIDER=groq mas GROQ_API_KEY não definida.")
        print("✅ Usando Groq")
        return Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY)
    if MODEL_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("MODEL_PROVIDER=openai mas OPENAI_API_KEY não definida.")
        print("✅ Usando OpenAI")
        return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    if GROQ_API_KEY:
        print("✅ GROQ detectada — usando Groq")
        return Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY)
    if OPENAI_API_KEY:
        print("✅ OPENAI detectada — usando OpenAI")
        return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    raise ValueError("Nenhuma chave de API encontrada no .env")

model = criar_modelo()

# ─────────────────────────────────────────────────────────────────────────
# 4. TOOL — CONTROLAR ESP32 (LED, servo, sirene, bomba, etc.)
# ─────────────────────────────────────────────────────────────────────────
@tool
def controlar_esp32(comando: str, parametro: str = "") -> str:
    """
    Envia um comando MQTT para o ESP32.
    Args:
        comando:   'led_on' | 'led_off' | 'servo_angle' |
                   'sirene_on' | 'sirene_off' | 'bomba_on' | 'bomba_off' | 'reset'
        parametro: valor adicional (ex: ângulo do servo '90')
    """
    # Monta payload — servo usa formato "servo_angle:90", outros só o nome
    if comando == "servo_angle" and parametro:
        payload_str = f"servo_angle:{parametro}"
    else:
        payload_str = comando

    try:
        publish.single(
            MQTT_TOPIC,
            payload=payload_str,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            protocol=mqtt.MQTTv311,   # força protocolo explícito no paho 2.x
        )
        # Atualiza cache local imediatamente (confirmação otimista)
        if comando == "led_on":
            sensor_cache["led"] = "on"
        elif comando == "led_off":
            sensor_cache["led"] = "off"
        elif comando == "servo_angle" and parametro:
            try:
                sensor_cache["servo"] = int(parametro)
            except ValueError:
                pass
        elif comando == "sirene_on":
            sensor_cache["sirene"] = 1
        elif comando == "sirene_off":
            sensor_cache["sirene"] = 0
        elif comando == "bomba_on":
            sensor_cache["bomba"] = "Ligado"
        elif comando == "bomba_off":
            sensor_cache["bomba"] = "Desligado"

        return f"Comando '{comando}' enviado com sucesso para o ESP32."
    except Exception as e:
        return f"Erro ao enviar comando MQTT: {e}"

# ─────────────────────────────────────────────────────────────────────────
# 5. TOOL — LER SENSORES
# ─────────────────────────────────────────────────────────────────────────
@tool
def ler_sensores(sensor: str = "todos") -> str:
    """
    Lê os valores atuais dos sensores e atuadores do ESP32.
    Args:
        sensor: 'todos' | 'temperatura' | 'fumaca' | 'fogo' | 'pressao' |
                'estado' | 'sirene' | 'bomba' | 'led' | 'servo'
    """
    c = sensor_cache

    if not c.get("mqtt"):
        aviso = "⚠ ESP32 pode estar offline (ainda sem dados via MQTT). "
    else:
        aviso = ""

    def fmt_temp():
        t = c.get("temperatura")
        if t is None or t == -127:
            return "Temperatura: sensor desconectado"
        return f"Temperatura: {t:.1f}°C"

    def fmt_fumaca():
        ppm = c.get("fumaca", 0)
        nivel = "normal" if ppm < 300 else ("elevada" if ppm < 1000 else "CRÍTICA")
        return f"Fumaça: {ppm:.0f} PPM ({nivel})"

    def fmt_fogo():
        f = c.get("fogo", "normal")
        return f"Fogo: {'DETECTADO' if f != 'normal' else 'não detectado'}"

    def fmt_pressao():
        p = c.get('pressao', 0)
        nivel = "baixa" if p < 30 else ("normal" if p < 80 else "alta")
        return f"Pressão: {p} kPa ({nivel})"

    def fmt_estado():
        return f"Estado do sistema: {c.get('estado', 'NORMAL')}"

    def fmt_sirene():
        return f"Sirene: {'ATIVA' if c.get('sirene') else 'inativa'}"

    def fmt_bomba():
        return f"Bomba: {c.get('bomba', 'Desligado')}"

    def fmt_led():
        return f"Luz (LED): {'ligada' if c.get('led') == 'on' else 'desligada'}"

    def fmt_servo():
        return f"Servo: {c.get('servo', 0)}°"

    mapa = {
        "temperatura": fmt_temp,
        "fumaca":      fmt_fumaca,
        "fogo":        fmt_fogo,
        "pressao":     fmt_pressao,
        "estado":      fmt_estado,
        "sirene":      fmt_sirene,
        "bomba":       fmt_bomba,
        "led":         fmt_led,
        "servo":       fmt_servo,
    }

    s = sensor.lower().strip()
    if s in mapa:
        return aviso + mapa[s]()

    # todos
    linhas = [f() for f in mapa.values()]
    return aviso + "\n".join(linhas)

# ─────────────────────────────────────────────────────────────────────────
# 6. AGENTE
# ─────────────────────────────────────────────────────────────────────────
agente_casa = Agent(
    name="ARIA",
    model=model,
    tools=[controlar_esp32, ler_sensores],
    # Sem histórico: cada pergunta é independente
    num_history_messages=0,
    instructions="""
Você é a ARIA, assistente residencial inteligente, simpática e objetiva.

═══ DADOS DOS SENSORES ═══
Cada mensagem do usuário chega com um bloco [SNAPSHOT SENSORES @ HH:MM:SS] no final.
Use SEMPRE esses valores para responder perguntas sobre temperatura, fumaça, fogo,
pressão, estado do sistema, LED, servo, sirene e bomba.
NÃO chame ler_sensores para consultas — os dados já estão no snapshot.

═══ CONTROLE DE DISPOSITIVOS ═══
SEMPRE chame controlar_esp32 para acionar hardware:
- Ligar luz  → controlar_esp32(comando='led_on')
- Apagar luz → controlar_esp32(comando='led_off')
- Servo      → controlar_esp32(comando='servo_angle', parametro='<ângulo>')
  · Se o ângulo não for informado, pergunte antes.
- Sirene on/off → controlar_esp32(comando='sirene_on' ou 'sirene_off')
- Bomba on/off  → controlar_esp32(comando='bomba_on'  ou 'bomba_off')

═══ EXEMPLOS DE INTERPRETAÇÃO ═══
- "acende a luz" / "liga a lâmpada" / "está escuro" → led_on
- "apaga" / "desliga a luz" → led_off
- "gira 90 graus" / "posiciona em 45°" → servo_angle com o ângulo
- "qual a temperatura?" / "está quente?" → leia do snapshot e responda
- "tem fumaça?" → leia fumaca do snapshot
- "como está a casa?" → resuma todos os campos do snapshot
- "tem incêndio?" → leia fogo e estado do snapshot

═══ REGRAS ═══
1. Para LEITURA de sensores: use o snapshot — nunca invente valores.
2. Para CONTROLE de hardware: sempre chame controlar_esp32.
3. Se estado=ALARME ou CRITICO no snapshot, avise com destaque.
4. Seja breve. Respostas curtas e diretas.
5. Não use emojis no texto (eles serão lidos em voz alta).
    """,
)

# ─────────────────────────────────────────────────────────────────────────
# 7. LOOP INTERATIVO (execução direta)
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("ARIA iniciada. Digite 'sair' para encerrar.\n")
    while True:
        u = input("Você: ")
        if u.lower() == "sair":
            break
        agente_casa.print_response(u, stream=True)
