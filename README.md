# Proyecto Sembrando IA - Agente

## Requisitos previos

Para ejecutar este proyecto, asegúrate de tener instalados los siguientes programas:

- [Python 3.9.x](https://www.python.org/): Se recomienda usar Python 3.9.
- [ngrok](https://ngrok.com/): Para exponer tu servidor local a una URL pública.
- [FastAPI](https://fastapi.tiangolo.com/): El framework utilizado para desarrollar la API.
- [Uvicorn](https://www.uvicorn.org/): Para ejecutar el servidor de FastAPI.
- [dotenv](https://pypi.org/project/python-dotenv/): Para gestionar variables de entorno.

## Instalación del ambiente con venv

1. **Instalar Python 3.9.x**:
   Asegúrate de tener Python 3.9.x instalado. Puedes descargarlo desde [python.org](https://www.python.org/downloads/).

2. **Crear un entorno virtual**:
   Navega al directorio del proyecto y ejecuta:
   ```sh
   python3 -m venv venv
   ```

3. **Activar el entorno virtual**:
   - En Linux/macOS:
     ```sh
     source venv/bin/activate
     ```
   - En Windows:
     ```sh
     venv\Scriptsctivate
     ```

4. **Instalar las dependencias**:
   Navega al directorio del proyecto y ejecuta:
   ```sh
   pip install -r requirements.txt
   ```
   Asegúrate de que el archivo `requirements.txt` contenga las dependencias necesarias, incluyendo `fastapi`, `uvicorn`, `python-dotenv`, entre otras.

## Configuración de variables de entorno

1. Crea un archivo `.env` en la raíz del proyecto para configurar tus variables de entorno.
   
   Ejemplo de `.env`:
   ```env
   AZURE_OPENAI_API_KEY=tu_clave_azure
   DEPLOYMENT_NAME=gpt-4o
   EMBEDDING_DEPLOYMENT_NAME=text-embedding-ada-002
   OPENAI_API_VERSION=2023-05-15
   ```

2. Asegúrate de que el archivo `.env` contenga las credenciales necesarias para conectarse a los servicios externos, como Azure OpenAI.

## Ejecución del proyecto

1. **Iniciar el servidor con Uvicorn**:
   Ejecuta el siguiente comando para iniciar el servidor FastAPI:
   ```sh
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```

2. **Exponer el servidor con ngrok**:
   Abre un nuevo terminal y ejecuta el siguiente comando:
   ```sh
   ngrok http 8000
   ```
   Esto generará una URL pública que puedes utilizar para probar el servidor desde dispositivos externos o aplicaciones como WhatsApp.

## Uso del servidor

- Puedes acceder a la URL pública proporcionada por ngrok y realizar peticiones a los endpoints `/` y `/message` definidos en el código.

## Notas adicionales

- Asegúrate de mantener ngrok en ejecución mientras estás probando el servidor.
- Puedes actualizar o regenerar el archivo `.env` según sea necesario para diferentes entornos o configuraciones.

## Solución de problemas

- Si encuentras problemas de versión, asegúrate de que el entorno virtual esté correctamente activado.
- Verifica que el archivo `.env` tenga los valores correctos y esté siendo cargado por `load_dotenv()`.
