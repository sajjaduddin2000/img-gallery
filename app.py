import os
import logging
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from flask_cors import CORS  
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Fetch connection details
connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
container_name = "photos"

if not connect_str or not account_name or not account_key:
    raise ValueError("Missing Azure Storage environment variables in .env!")

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
container_client = blob_service_client.get_container_client(container_name)

# Ensure Container Exists
try:
    container_client.get_container_properties()
except Exception as e:
    logging.warning(f"Container {container_name} not found. Creating it now...")
    container_client.create_container()

@app.route("/photos", methods=["GET"])
def get_photos():
    try:
        blobs = container_client.list_blobs()
        photos = []
        for blob in blobs:
            try:
                sas_token = generate_blob_sas(
                    account_name=account_name,
                    container_name=container_name,
                    blob_name=blob.name,
                    account_key=account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(hours=1)
                )
                blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob.name}?{sas_token}"
                photos.append(blob_url)
            except Exception as sas_error:
                logging.error(f"Error generating SAS for {blob.name}: {sas_error}")
        return jsonify({"photos": photos})
    except Exception as e:
        logging.error(f"Error fetching photos: {e}")
        return jsonify({"error": "Failed to retrieve photos."}), 500

@app.route("/upload", methods=["POST"])
def upload_photos():
    if "photos" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    for file in request.files.getlist("photos"):
        if file.filename == "":
            continue
        try:
            blob_client = container_client.get_blob_client(file.filename)
            blob_client.upload_blob(
                file.read(),
                overwrite=True,
                content_settings=ContentSettings(content_type=file.content_type)
            )
            logging.info(f"Uploaded {file.filename} successfully.")
        except Exception as e:
            logging.error(f"Upload failed for {file.filename}: {e}")
            return jsonify({"error": f"Upload failed for {file.filename}"}), 500
    return jsonify({"message": "Upload successful"})

# Use Gunicorn for Production Deployment
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
