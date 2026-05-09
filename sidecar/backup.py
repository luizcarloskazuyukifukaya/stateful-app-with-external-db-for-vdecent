import os
import datetime
import subprocess
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_gdrive_service():
    creds = None
    token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
    creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Credentials file not found at {creds_path}")
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0, open_browser=False)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def perform_backup():
    logger.info("Starting database backup...")
    try:
        # Get environment variables
        db_url = os.getenv('DATABASE_URL')
        folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        
        if not db_url:
            raise ValueError("DATABASE_URL is not set")

        # Create backup filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backup_{timestamp}.sql"

        # Run pg_dump
        # Assuming pg_dump is available in the container
        # Format: postgresql://username:password@host:port/dbname
        env = os.environ.copy()
        # We might need to set PGPASSWORD if it's not in the URL or if pg_dump requires it separately
        # But pg_dump usually accepts the full URL
        result = subprocess.run(['pg_dump', db_url, '-f', backup_file], capture_with_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr}")
            return False, result.stderr

        # Upload to Google Drive
        service = get_gdrive_service()
        file_metadata = {'name': backup_file}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(backup_file, mimetype='application/sql')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        logger.info(f"Backup uploaded successfully. File ID: {file.get('id')}")
        
        # Clean up local file
        os.remove(backup_file)
        return True, file.get('id')

    except Exception as e:
        logger.exception("An error occurred during backup")
        return False, str(e)

def perform_restore(file_id):
    logger.info(f"Starting database restore from file ID: {file_id}...")
    try:
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL is not set")

        service = get_gdrive_service()
        
        # Download from Google Drive
        request = service.files().get_media(fileId=file_id)
        restore_file = "restore_temp.sql"
        with open(restore_file, "wb") as f:
            f.write(request.execute())

        # Run psql to restore
        # WARNING: This might overwrite existing data. In a real scenario, we might want to drop and recreate the DB.
        # For simplicity, we assume psql can run against the DB_URL.
        result = subprocess.run(['psql', db_url, '-f', restore_file], capture_with_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"psql restore failed: {result.stderr}")
            return False, result.stderr

        logger.info("Restore completed successfully.")
        
        # Clean up local file
        os.remove(restore_file)
        return True, "Restore successful"

    except Exception as e:
        logger.exception("An error occurred during restore")
        return False, str(e)
