import os
import json
import paho.mqtt.publish as publish
from dotenv import load_dotenv

from agno.agent import Agent
from agno.tools import tool

# Importar os modelos disponíveis
from agno.models.openai import OpenAIChat
from agno.models.groq import Groq

# =====================================================
# 1. CARREGAR VARIÁVEIS DO .env
# =====================================================
load_dotenv()

# Chaves e provedor
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "").lower()

# Configurações MQTT (AJUSTADAS PARA O BROKER REAL)
MQTT_BROKER = os.getenv("MQTT_BROKER", "analyticsiotconects.com.br")  # <-- broker real
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "jrsilva/comando")              # <-- tópico real
MQTT_USER = os.getenv("MQTT_USER", "usuarioroot")                    # <-- usuário
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "senharoot")              # <-- senha

# Modelos específicos (valores padrão)
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# =====================================================
# 2. DECIDIR QUAL PROVEDOR USAR
# =====================================================
def criar_modelo():
    """Retorna a instância do modelo com base nas variáveis de ambiente."""
    if MODEL_PROVIDER == "groq":
        if not GROQ_API_KEY:
            raise ValueError("❌ MODEL_PROVIDER=groq mas GROQ_API_KEY não está definida no .env")
        print("✅ Usando modelo: Groq")
        return Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY)
    
    if MODEL_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("❌ MODEL_PROVIDER=openai mas OPENAI_API_KEY não está definida no .env")
        print("✅ Usando modelo: OpenAI")
        return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    
    if GROQ_API_KEY:
        print("✅ GROQ_API_KEY detectada. Usando Groq.")
        return Groq(id=GROQ_MODEL, api_key=GROQ_API_KEY)
    elif OPENAI_API_KEY:
        print("✅ OPENAI_API_KEY detectada. Usando OpenAI.")
        return OpenAIChat(id=OPENAI_MODEL, api_key=OPENAI_API_KEY)
    else:
        raise ValueError("❌ Nenhuma chave de API encontrada. Defina GROQ_API_KEY ou OPENAI_API_KEY no .env")

model = criar_modelo()

# =====================================================
# 3. TOOL PARA CONTROLAR O ESP32 (COM AUTENTICAÇÃO MQTT)
# =====================================================
@tool
def controlar_esp32(comando: str, parametro: str = "") -> str:
    """
    Envia um comando para o ESP32 via MQTT.
    Args:
        comando: Ação ('led_on', 'led_off', 'servo_angle', etc.)
        parametro: Parâmetro adicional (ex: ângulo do servo)
    """
    mensagem = {"comando": comando, "parametro": parametro}
    try:
        # Publica com autenticação
        publish.single(
            MQTT_TOPIC,
            payload=json.dumps(mensagem),
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
            auth={'username': MQTT_USER, 'password': MQTT_PASSWORD}  # <-- credenciais
        )
        return f"✅ Comando '{comando}' enviado com sucesso para o ESP32."
    except Exception as e:
        return f"❌ Erro ao enviar comando MQTT: {e}"

# =====================================================
# 4. CRIAÇÃO DO AGENTE
# =====================================================
agente_casa = Agent(
    name="Assistente Residencial",
    model=model,
    tools=[controlar_esp32],
    instructions="""
        Você é a ARIA, uma assistente residencial inteligente, amigável e prestativa. 
        Seu objetivo é interpretar comandos em linguagem natural e controlar os dispositivos da casa usando a ferramenta 'controlar_esp32'.

        REGRAS IMPORTANTES:
        1. SEMPRE que o usuário pedir para ligar ou desligar a luz, acione a ferramenta com comando='led_on' ou 'led_off'.
        2. SEMPRE que o usuário pedir para mover o servo (girar, posicionar, ângulo), use comando='servo_angle' e passe o ângulo no parâmetro.
        3. Se o comando não for claro ou faltar informação (ex: 'gire o servo' sem ângulo), pergunte educadamente o que falta.
        4. Após executar o comando, responda de forma natural e confirme a ação (ex: 'Prontinho! A luz foi acesa.').
        5. Se o usuário pedir algo que você não pode fazer, explique que ainda não aprendeu aquilo e sugira os comandos disponíveis.

        EXEMPLOS DE INTERPRETAÇÃO:
        - "acende a luz", "liga a lâmpada", "pode acender a luz?" → comando='led_on'
        - "apaga a luz", "desliga", "apaga tudo" (se contexto for luz) → comando='led_off'
        - "gira o servo pra 45 graus", "posiciona em 90°", "ângulo 30" → comando='servo_angle', parametro='45' (ou o número informado)
        - "está escuro aqui" → entenda como pedido para ligar a luz.
        - "quero ler" → se não houver tool específica, avise que não pode ajudar com isso ainda.

        Seja breve, objetiva e simpática. Use poucos emojis (💡, ⚙️, ✅) para dar feedback visual.
        """
)

# =====================================================
# 5. LOOP DE INTERAÇÃO
# =====================================================
if __name__ == "__main__":
    print("🤖 Assistente Residencial IA iniciado! Digite 'sair' para encerrar.\n")
    while True:
        user_input = input("Você: ")
        if user_input.lower() == 'sair':
            break
        agente_casa.print_response(user_input, stream=True)