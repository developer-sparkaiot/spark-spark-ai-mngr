# Standard library import
import uuid
from googleapiclient.discovery import build
from botocore.exceptions import ClientError
from google.oauth2 import service_account
from twilio.rest import Client
from dotenv import load_dotenv
from datetime import datetime
import logging
import boto3
import json
import pytz
import re
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv('TWILIO_NUMBER')
client = Client(account_sid, auth_token)

# Set up logging

# Sending message logic through Twilio Messaging API
def send_message(to_number, body_text, media_url=None):
    try:
        if media_url:
            logger.info(media_url)
            message = client.messages.create(   
                from_=f"whatsapp:{twilio_number}",
                media_url=[media_url],
                body=body_text,
                to=f"whatsapp:{to_number}"
                )
        else:
            logger.info(f"{twilio_number} Enviando mensaje sin imagen")
            message = client.messages.create(   
                from_=f"whatsapp:{twilio_number}",
                body=body_text,
                to=f"whatsapp:{to_number}"
                )
        logger.info(f"Message sent to {to_number}: {message.body}")
    except Exception as e:
        logger.error(f"Error sending message to {to_number}: {e}")


def split_text_and_images(text):
    # Expresión regular para encontrar URLs de imágenes en el mensaje
    url_pattern = r"\[Imagen: (https?://[^\s]+)\]"
    # Extraer todas las URLs de imágenes
    urls = re.findall(url_pattern, text)
    # Eliminar las URLs de imágenes del mensaje original
    clean_text = re.sub(url_pattern, "", text).strip()
    return clean_text, urls

# Función para dividir el mensaje y enviar imágenes por separado eliminando la URL
def send_message_with_images(to_number, message_text):
    # Expresión regular para encontrar URLs de imágenes en el mensaje
    url_pattern = r"\[Imagen: (https?://[^\s]+)\]"
    
    # Extraer todas las URLs de imágenes
    urls = re.findall(url_pattern, message_text)
    
    # Eliminar las URLs de imágenes del mensaje original
    clean_text = re.sub(url_pattern, "", message_text)
    
    # Dividir el texto limpio en secciones lógicas si es necesario
    text_parts = clean_text.split("\n\n")
    
    # Enviar el texto limpio por partes
    for part in text_parts:
        if part.strip():  # Evita enviar mensajes vacíos
            send_message(to_number, part.strip())
    
    # Enviar cada imagen de forma independiente
    for url in urls:
        send_message(to_number, "", media_url=url)

def get_prompts()-> str:
    s3 = boto3.client('s3')
    bucket_name=os.getenv('PROMPT_BUCKET_NAME')
    try:
        response = s3.get_object(Bucket=bucket_name, Key=os.getenv('NAME_FILE'))
        content = response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.info(f"Error al leer el archivo: {e}")
    return content

def get_secret() -> str:
    secret_name = os.getenv("SECRET")
    region_name = os.getenv("REGION")

    session = boto3.session.Session()
    client = session.client(service_name='secretsmanager', region_name=region_name)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret = response['SecretString']
        return secret
    except ClientError as e:
        logger.info(f"Error al obtener el secreto: {e}")
        raise RuntimeError("No se pudo obtener el secreto.") from e

def get_google_sheets_service() -> object:
    try:
        secret_key = get_secret()
        key_dict = json.loads(secret_key)
        scopes = [os.getenv("GOOGLE_SCOPES")]
        credentials = service_account.Credentials.from_service_account_info(key_dict, scopes=scopes)
        service = build('sheets', 'v4', credentials=credentials, cache_discovery=False)
        return service
    except Exception as e:
        raise RuntimeError(f"Error al configurar el cliente de Google Sheets: {e}")

def get_colombia_time():
    colombia_tz = pytz.timezone("America/Bogota")
    return datetime.now(colombia_tz)

def generar_codigo_cita(nombre_paciente):
    unique_id = uuid.uuid4().hex[:8]
    codigo_cita = f"{nombre_paciente[:3].upper()}-{unique_id}"
    return codigo_cita

def buscar_fila(codigo: str) -> int:
    sheet_id=os.getenv("SHEET_ID")
    service = get_google_sheets_service()
    sheet = service.spreadsheets()

    try:
        rows = sheet.values().get(spreadsheetId=sheet_id, range='A:A').execute().get('values', [])

        for i, row in enumerate(rows):
            if row and row[0] == codigo:
                return i

        return -1
    except Exception as e:
        raise RuntimeError(f"Error al buscar el código: {e}")