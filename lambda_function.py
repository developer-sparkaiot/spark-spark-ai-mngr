from tools import lookup_project_info,validate_date,next_day_of_week,write_to_sheet_with_validation,modify_sheet,erase_from_sheet
from utils import get_colombia_time, send_message, split_text, split_text_and_images , get_prompts
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory
from langchain_openai import AzureOpenAIEmbeddings,AzureChatOpenAI,ChatOpenAI
from langchain_core.messages import trim_messages, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition
from langgraph.graph import StateGraph, START
#from langchain_openai import AzureChatOpenAI
from typing_extensions import TypedDict
from langgraph.prebuilt import ToolNode
from langchain.schema import AIMessage
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from typing import Annotated
from time import sleep
import uvicorn
import logging
import boto3
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
app = FastAPI()

# Inicializa DynamoDB
dynamodb = boto3.resource('dynamodb')

table_name = os.getenv("MESSAGE_MEMORY_TABLE") # Nombre de la tabla de DynamoDB

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
llm = ChatOpenAI(model=os.getenv('GPT_MODEL'), max_tokens=250)
"""
llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_DEPLOYMENT_NAME"),
    api_version="2024-05-01-preview",
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
)
embeddings = AzureOpenAIEmbeddings(
    model="text-embedding-ada-002",
    openai_api_version=os.getenv("OPENAI_API_VERSION"),
)
"""
class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            configuration = config.get("configurable", {})
            passenger_id = configuration.get("passenger_id", None)
            state = {**state, "user_info": passenger_id,"time":get_colombia_time().strftime("%Y-%m-%d %H:%M:%S")}
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}

def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


prompt=get_prompts()
primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            prompt,
        ),
        ("placeholder", "{messages}"),
    ]
)

tools = [lookup_project_info,modify_sheet,erase_from_sheet,validate_date,next_day_of_week,write_to_sheet_with_validation]
part_1_assistant_runnable = primary_assistant_prompt | llm.bind_tools(tools)

builder = StateGraph(State)

# Define nodes: these do the work
builder.add_node("assistant", Assistant(part_1_assistant_runnable))
builder.add_node("tools", create_tool_node_with_fallback(tools))
# Define edges: these determine how the control flow moves
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    tools_condition,
)
builder.add_edge("tools", "assistant")

# The checkpointer lets the graph persist its state
# this is a complete memory for the entire graph.
memory = MemorySaver()
part_1_graph = builder.compile(checkpointer=memory)

@app.get("/")
async def index():
    logger.info("Endpoint '/' was called.")
    return {"msg": "working"}

@app.post("/message")
async def chat_with_user(request: Request):
    logger.info("Received a new message.")
    form_data = await request.form()
    user_message = form_data["Body"]
    whatsapp_number = form_data["From"].replace('whatsapp:', '')
    date_today = get_colombia_time().strftime("%Y-%m-%d")  # Formato de fecha YYYY-MM-DD

    # Inicializa DynamoDBChatMessageHistory con el número de teléfono y la fecha
    session_id = f"{whatsapp_number}#{date_today}"
    logger.info(f"Session ID: {session_id}")

    my_key = {
    "PhoneNumber": whatsapp_number,
    "Date": date_today,
    }

    history = DynamoDBChatMessageHistory(table_name=table_name, session_id=session_id, key=my_key)

    # Recupera el historial de mensajes de DynamoDB
    previous_messages = history.messages  # Recupera el historial almacenado
    logger.info(f"Previous messages: {previous_messages}")

    # Almacena el mensaje del usuario en DynamoDB
    history.add_user_message(user_message)
    logger.info(f"User message stored: {user_message}")

    history_messages = previous_messages + [("user", user_message)]
    history_messages = trim_messages(
        history_messages,
        strategy="last",
        token_counter=len,
        max_tokens=5,
        start_on="human",
        end_on=("human", "tool"),
        include_system=True,
    )

    
    # Prepara el estado y la configuración
    state = {
        "messages": previous_messages + [("user", user_message)]  # Combina el historial con el nuevo mensaje
    }

    config = {
        "configurable": {
            "passenger_id": None,
            "thread_id": whatsapp_number, # Usa el número de WhatsApp como ID de hilo
        }
    }

    # Ejecuta el asistente
    try:
        events = part_1_graph.stream(
            state, config, stream_mode="values"
        )

        for event in events:
            ia_messages = [msg.content for msg in event.get("messages", []) if isinstance(msg, AIMessage)]

        # Dividir el último mensaje en texto y URLs de imágenes
        if ia_messages:
            message_text = ia_messages[-1]
            history.add_ai_message(message_text)
            logger.info(f"AI message stored: {message_text}")
            text_content, image_urls = split_text_and_images(message_text)

            # Enviar el texto primero
            if text_content:
                messages=split_text(text_content)
                for message in messages:
                    send_message(whatsapp_number, message)
                    sleep(1)
                logger.info(f"Sent text message to {whatsapp_number}: {text_content}")

            # Enviar cada imagen como mensaje independiente
            for image_url in image_urls:
                send_message(whatsapp_number, "", media_url=image_url)
                logger.info(f"Sent image to {whatsapp_number}: {image_url}")
        

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        assistant_response = "Lo siento, ha ocurrido un error."
        send_message(whatsapp_number, assistant_response)

    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
