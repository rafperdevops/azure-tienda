import json
import uuid
from flask import Flask, request, jsonify
from azure.storage.blob import BlobServiceClient
import pyodbc
from PIL import Image
import io
import os

from dotenv import load_dotenv
load_dotenv()

# --- Configuración Real de Azure ---
BLOB_STORAGE_CONNECTION_STRING = os.getenv("BLOB_STORAGE_CONNECTION_STRING")
SQL_DATABASE_CONNECTION_STRING = os.getenv("SQL_DATABASE_CONNECTION_STRING")


# Inicializar clientes de Azure
blob_service_client = BlobServiceClient.from_connection_string(BLOB_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client("product-images")

# Inicializar Flask
app = Flask(__name__)

@app.route('/upload-image', methods=['POST'])
def upload_image():
    image_file = request.files['image']
    name = request.form.get("name")
    price = request.form.get("price")

    if image_file:
        unique_filename = f"{uuid.uuid4()}_{image_file.filename}"
        blob_client = container_client.get_blob_client(unique_filename)
        blob_client.upload_blob(image_file.read(), overwrite=True)
        print(f"Imagen cargada a Azure Blob Storage: {unique_filename}")        

        # Guardar en Azure SQL Database
        try:
            # Leer imagen para Pillow antes de subirla
            image_bytes = image_file.read()
            image_stream = io.BytesIO(image_bytes)
            image = Image.open(image_stream)
            image_metadata = {
                "format": image.format,
                "mode": image.mode,
                "width": image.width,
                "height": image.height
            }

            # # Subir al Blob
            # blob_client.upload_blob(image_bytes, overwrite=True)
            # print(f"Imagen cargada a Azure Blob Storage: {unique_filename}")

            # Guardar metadatos en SQL
            cnxn = pyodbc.connect(SQL_DATABASE_CONNECTION_STRING)
            cursor = cnxn.cursor()
            metadata_json = json.dumps(image_metadata)
            cursor.execute("INSERT INTO Products (Name, Price, ImageBlobName, ImageMetadata) VALUES (?, ?, ?, ?)",
                           name, price, unique_filename, metadata_json)
            cnxn.commit()

            # Obtener el ID insertado si lo necesitas
            cursor.execute("SELECT @@IDENTITY AS ID;")
            product_id_from_sql = cursor.fetchone()[0]

            cnxn.close()
            print(f"Datos de producto guardados en Azure SQL Database para {unique_filename}")

            return jsonify({
                "message": "Imagen cargada y procesamiento inicial iniciado.",
                "image_info": image_metadata,
                "blob_url": blob_client.url,
                "product_id": product_id_from_sql
            }), 200

        except Exception as e:
            print(f"Error en el procesamiento: {e}")
            return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Archivo no válido"}), 400
