"""
agente_ia.py — ARIA v4.0
Controla dispositivos via MQTT. Sensores lidos pelo browser (WebSocket MQTT).
"""
import os
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

from agno.agent import Agent
from agno.tools import tool
from agno.models.openai import OpenAIChat
from agno.models.groq import Groq

load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "").lower()
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_PORT   = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "jrsilva/comando")

def criar_modelo():
    if MODEL_PROVIDER == "groq" and GROQ_API_KEY:
        print("Usando Groq"); return Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY)
    if MODEL_PROVIDER == "openai" and OPENAI_API_KEY:
        print("Usando OpenAI"); return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    if GROQ_API_KEY:
        print("Usando Groq"); return Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY)
    if OPENAI_API_KEY:
        print("Usando OpenAI"); return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    raise ValueError("Nenhuma chave de API encontrada no .env")

model = criar_modelo()

@tool
def controlar_esp32(comando: str, parametro: str = "") -> str:
    """
    Envia um comando MQTT para o ESP32.
    Args:
        comando:   'led_on' | 'led_off' | 'servo_angle' |
                   'sirene_on' | 'sirene_off' | 'bomba_on' | 'bomba_off' | 'reset'
        parametro: valor adicional (ex: ângulo '90' para servo_angle)
    """
    payload_str = f"servo_angle:{parametro}" if comando == "servo_angle" and parametro else comando
    try:
        publish.single(
            MQTT_TOPIC,
            payload=payload_str,
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            protocol=mqtt.MQTTv311,
        )
        return f"Comando '{comando}' enviado com sucesso para o ESP32."
    except Exception as e:
        return f"Erro ao enviar comando MQTT: {e}"

agente_casa = Agent(
    name="ARIA",
    model=model,
    tools=[controlar_esp32],
    num_history_messages=0,
    instructions="""
Você é a ARIA, assistente residencial inteligente, simpática e objetiva.

═══ DADOS DOS SENSORES ═══
Cada mensagem chega com um bloco [SNAPSHOT SENSORES @ HH:MM:SS].
Use SEMPRE esses valores para responder perguntas sobre sensores.
Nunca invente valores — use apenas o que está no snapshot.

═══ CONTROLE DE DISPOSITIVOS ═══
Chame controlar_esp32 para acionar hardware:
- Ligar luz    → controlar_esp32(comando='led_on')
- Apagar luz   → controlar_esp32(comando='led_off')
- Mover servo  → controlar_esp32(comando='servo_angle', parametro='<graus>')
  · Se o ângulo não for informado, pergunte antes.
- Sirene       → controlar_esp32(comando='sirene_on' ou 'sirene_off')
- Bomba        → controlar_esp32(comando='bomba_on'  ou 'bomba_off')

═══ EXEMPLOS ═══
"acende a luz" / "está escuro"       → led_on
"apaga" / "desliga a luz"            → led_off
"gira 90 graus"                      → servo_angle, parametro='90'
"qual a temperatura?" / "está quente?"  → leia temperatura do snapshot
"tem fumaça?" / "como está a casa?"     → leia do snapshot e responda
Estado ALARME ou CRITICO no snapshot    → avise com destaque

═══ REGRAS ═══
1. Sensores: use o snapshot — nunca invente.
2. Comandos: sempre chame controlar_esp32.
3. Seja breve e direto.
4. Não use emojis (o texto é lido em voz alta).
    """,
)

if __name__ == "__main__":
    print("ARIA iniciada. Digite 'sair' para encerrar.\n")
    while True:
        u = input("Você: ")
        if u.lower() == "sair": break
        agente_casa.print_response(u, stream=True)
