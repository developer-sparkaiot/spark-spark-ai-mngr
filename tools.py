from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from object.informacion_cita import InformacionCita
from utils import buscar_fila, generar_codigo_cita, get_colombia_time, get_google_sheets_service
from datetime import datetime, timedelta
from langchain_core.tools import tool
from pydantic import ValidationError
from dotenv import load_dotenv
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
def lookup_project_info(query: str) -> str:
    """
    Consulta información general sobre la compañia Spark basada en atributos específicos desde un índice Pinecone.
    Args:
        query (str): La consulta de búsqueda que contiene la información que se desea recuperar sobre el proyecto.
    
    Returns:
        str: Un string con la información relevante del proyecto basada en los criterios de búsqueda.

    Ejemplo de uso:
        lookup_project_info(query="Cuéntame sobre las metas del proyecto")
        lookup_project_info(query="que productos tienen")
    """
    from langchain_pinecone import PineconeVectorStore
    load_dotenv()
    index_name = os.getenv('INDEX_NAME')
    embeddings = OpenAIEmbeddings()
    vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)
    docs = vectorstore.similarity_search(query, k=2)
    llm = ChatOpenAI(model=os.getenv('GPT_MODEL'), max_tokens=180)

    relevant_texts = [doc.page_content for doc in docs]
    prompt = f"""
        Aquí tienes información extraída de un proyecto:

        {''.join(relevant_texts)}

        Basado en la consulta: "{query}"
        proporciona una respuesta clara
    """
    response = llm.invoke(prompt)
    return response.content

@tool("validate_date")
def validate_date(mes: int, dia: int) -> str:
    """
    Valida si la fecha solicitada es válida y si cumple con las condiciones requeridas.

    Args:
        mes (int): El mes de la fecha que se desea validar.
        dia (int): El día de la fecha que se desea validar.
    
    Returns:
        str: Un mensaje indicando si la fecha es válida o no.

    Ejemplo de uso:
        validate_date(mes=12, dia=25)
        validate_date(mes=2, dia=30)
    """
    try:
        actual_date = get_colombia_time()
        anio = actual_date.year
        user_date = datetime(anio, mes, dia)
        if actual_date.month > user_date.month or (actual_date.month == user_date.month and actual_date.day > user_date.day):
            anio += 1
        fecha_input = datetime(anio, mes, dia)
        three_months_ahead = actual_date + timedelta(days=90)
        
        if fecha_input <= actual_date or fecha_input > three_months_ahead:
            return "la fecha ya paso"
        
        if fecha_input.weekday() >= 1 and fecha_input.weekday() <= 6:
            return "La fecha es válida."
        else:
            return "La fecha debe ser entre lunes y sabado."
    except ValueError:
        return "La fecha no existe."

@tool("get_next_day")
def next_day_of_week(start_date: str, weekday: str) -> str:
    """
    Encuentra la próxima fecha con el día de la semana especificado a partir de una fecha inicial.

    Args:
        start_date (str): Fecha de inicio en formato 'DD/MM/YYYY'.
        weekday (str): Nombre del día de la semana en inglés (por ejemplo, 'Monday', 'Tuesday', etc.).
    
    Returns:
        str: Fecha de la próxima ocurrencia del día de la semana en formato 'DD/MM/YYYY'.

    Ejemplo de uso:
        next_day_of_week(start_date="01/12/2024", weekday="Thursday")
        next_day_of_week(start_date="30/11/2024", weekday="Monday")
    """
    days_of_week = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    
    if weekday.lower() not in days_of_week:
        return "Error: Día de la semana no válido. Usa 'Monday', 'Tuesday', etc."
    
    date = datetime.strptime(start_date, "%d/%m/%Y")
    target_day = days_of_week[weekday.lower()]
    delta_days = (target_day - date.weekday() + 7) % 7
    if delta_days == 0:
        delta_days = 7
    
    next_date = date + timedelta(days=delta_days)
    return next_date.strftime("%d/%m/%Y")

@tool("write_to_sheet_with_validation")
def write_to_sheet_with_validation(cadena: str) -> str:
    """
    Valida que no existan conflictos de horarios en la hoja de cálculo y, si no los hay, guarda los datos.

    Args:
        cadena (str): Cadena con los datos de la persona en formato CSV, separados por comas.
            Ejemplo:
            "Juan, juan@example.com, 2024-12-01, 10:00:00,virtual"

    Returns:
        str: Mensaje indicando el resultado de la operación.
    """
    load_dotenv()
    sheet_id=os.getenv("SHEET_ID")
    service = get_google_sheets_service()
    sheet = service.spreadsheets()

    try:
        cita = InformacionCita.from_string(cadena)
        persona = cita.to_dict()

        fecha_persona = persona.get("fecha")
        hora_persona = persona.get("hora")

        if not fecha_persona or not hora_persona:
            return "Error: La fecha o la hora no están definidas en los datos proporcionados."

        # Obtener los encabezados de la hoja
        headers = sheet.values().get(spreadsheetId=sheet_id, range='A:Z').execute().get('values', [])[0]

        if "Fecha" not in headers or "Hora" not in headers:
            return "Problemas en el Excel de citas: faltan los encabezados 'Fecha' o 'Hora'."

        # Identificar las columnas de Fecha y Hora
        fecha_col = chr(headers.index("Fecha") + ord('A'))
        hora_col = chr(headers.index("Hora") + ord('A'))
        data_range = f"{fecha_col}:{hora_col}"

        # Leer los datos dentro del rango dinámico
        rows = sheet.values().get(spreadsheetId=sheet_id, range=data_range).execute().get('values', [])

        if len(rows) == 1:  # Solo contiene los encabezados
            persona["codigo"] = generar_codigo_cita(persona.get("nombre"))
            save_values = [list(persona.values())]
            sheet.values().append(
                spreadsheetId=sheet_id,
                range='A:Z',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': save_values}
            ).execute()
            return "Guardado exitoso"

        # Validar conflictos de horario
        conflict="Horarios ocupados:"
        for row in rows[1:]:
            if len(row) > 1:  # Asegurarse de que la fila tenga datos en ambas columnas
                if row[0] == fecha_persona and row[1] == hora_persona:
                    for row in rows[1:]:
                        if len(row) > 1:
                            if row[0] == fecha_persona:
                                conflict+=f"\n{row[1]}"
                    return conflict

        # Guardar los datos si no hay conflictos
        persona["codigo"] = generar_codigo_cita(persona.get("nombre"))
        save_values = [list(persona.values())]
        sheet.values().append(
            spreadsheetId=sheet_id,
            range='A:Z',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': save_values}
        ).execute()
        return f"Guardado exitoso. Código generado: {persona.get('codigo')}"

    except ValidationError as ve:
        return f"Error en los datos proporcionados: {ve}"
    except Exception as e:
        raise RuntimeError(f"Error al escribir en la hoja: {e}")
    
@tool("erase_from_sheet")
def erase_from_sheet(codigo: str) -> str:
    """
    Borra una cita de la hoja de cálculo dado un código.

    Args:
        codigo (str): Código de la cita a borrar.

    Returns:
        str: Mensaje indicando el resultado de la operación.
    """
    load_dotenv()
    sheet_id=os.getenv("SHEET_ID")
    service = get_google_sheets_service()
    sheet = service.spreadsheets()

    try:
        # Buscar la fila correspondiente al código
        fila = buscar_fila(codigo)

        if fila == -1:
            return "No se encontró la cita con el código especificado."

        # Eliminar la fila encontrada
        sheet.batchUpdate(
            spreadsheetId=sheet_id,
            body={
                'requests': [
                    {
                        'deleteDimension': {
                            'range': {
                                'sheetId': 0,  # Suponiendo que es la primera hoja
                                'dimension': 'ROWS',
                                'startIndex': fila,
                                'endIndex': fila + 1
                            }
                        }
                    }
                ]
            }
        ).execute()

        return "Cita borrada exitosamente."

    except Exception as e:
        raise RuntimeError(f"Error al borrar la cita: {e}")

@tool("modify_sheet")
def modify_sheet(codigo: str, hora: str = None, fecha: str = None, modalidad: str = None) -> str:
    """
    Modifica una cita en la hoja de cálculo dado un código y los nuevos valores. Solo se actualizan los campos proporcionados.

    Args:
        codigo (str): Código de la cita a modificar.
        hora (str, optional): Nueva hora de la cita en formato HH:MM:SS.
        fecha (str, optional): Nueva fecha de la cita en formato YYYY-MM-DD.
        modalidad (str, optional): Nueva modalidad de la cita.

    Returns:
        str: Mensaje indicando el resultado de la operación.
    example:
    Ejemplo de uso:("JUA-b2295cec",None,None,"Presencial")
    """
    load_dotenv()
    sheet_id=os.getenv("SHEET_ID")
    service = get_google_sheets_service()
    sheet = service.spreadsheets()

    try:
        # Buscar la fila correspondiente al código
        fila = buscar_fila(codigo)

        if fila == -1:
            return "No se encontró la cita con el código especificado."

        # Leer los encabezados
        headers = sheet.values().get(spreadsheetId=sheet_id, range='A:Z').execute().get('values', [])[0]

        # Leer la fila específica
        row_data = sheet.values().get(
            spreadsheetId=sheet_id,
            range=f"A{fila + 1}:Z{fila + 1}"
        ).execute().get('values', [[]])[0]

        # Crear un diccionario con los datos actuales
        cita = {headers[i]: row_data[i] for i in range(len(headers))}

        # Actualizar solo los campos proporcionados
        if fecha:
            cita["Fecha"] = fecha
        if hora:
            cita["Hora"] = hora
        if modalidad:
            cita["Modalidad"] = modalidad
        
        if(fecha or hora):
            fecha_col = chr(headers.index("Fecha") + ord('A'))
            hora_col = chr(headers.index("Hora") + ord('A'))
            data_range = f"{fecha_col}:{hora_col}"
            # Leer los datos dentro del rango dinámico
            rows = sheet.values().get(spreadsheetId=sheet_id, range=data_range).execute().get('values', [])
            for row in rows[1:]:
                if len(row) > 1:  # Asegurarse de que la fila tenga datos en ambas columnas
                    if row[0] == cita["Fecha"] and row[1] == cita["Hora"]:
                        return f"Horarios ocupados: {rows[1:]}"

        # Preparar los datos actualizados para escribir
        updated_row = [cita.get(header, "") for header in headers]

        # Escribir los datos actualizados en la hoja
        sheet.values().update(
            spreadsheetId=sheet_id,
            range=f"A{fila + 1}:Z{fila + 1}",
            valueInputOption='RAW',
            body={"values": [updated_row]}
        ).execute()

        return "Cita modificada exitosamente."

    except Exception as e:
        raise RuntimeError(f"Error al modificar la cita: {e}")