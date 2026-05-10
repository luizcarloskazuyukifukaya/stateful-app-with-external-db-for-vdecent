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

    if os.path.exists(token_path) and os.path.getsize(token_path) > 0:
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            logger.warning(f"Could not load token from {token_path}: {e}")
    
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
        result = subprocess.run(['pg_dump', db_url, '-f', backup_file], capture_output=True, text=True)
        
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

        # Automatically purge if retention is set
        perform_purge()
        
        return True, file.get('id')

    except Exception as e:
        logger.exception("An error occurred during backup")
        return False, str(e)

def perform_purge():
    logger.info("Checking for old backups to purge...")
    try:
        retention_count_str = os.getenv('BACKUP_RETENTION_COUNT')
        if not retention_count_str:
            logger.info("BACKUP_RETENTION_COUNT not set. Skipping purge.")
            return True, "No retention set"
        
        retention_count = int(retention_count_str)
        success, result = list_backups()
        if not success:
            return False, result
        
        files = result
        logger.info(f"Found {len(files)} backups.")

        if len(files) > retention_count:
            files_to_delete = files[retention_count:]
            logger.info(f"Purging {len(files_to_delete)} old backups...")
            service = get_gdrive_service()
            for f in files_to_delete:
                logger.info(f"Deleting old backup: {f['name']} (ID: {f['id']})")
                service.files().delete(fileId=f['id']).execute()
            return True, f"Purged {len(files_to_delete)} files"
        
        return True, "No files to purge"

    except Exception as e:
        logger.exception("An error occurred during purge")
        return False, str(e)

def list_backups():
    logger.info("Listing backups from Google Drive...")
    try:
        folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        service = get_gdrive_service()
        
        query = "mimeType = 'application/sql' and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, createdTime, size)',
            orderBy='createdTime desc'
        ).execute()
        
        return True, results.get('files', [])
    except Exception as e:
        logger.exception("An error occurred while listing backups")
        return False, str(e)

import time
import psycopg2
from urllib.parse import urlparse

def wait_for_db(timeout=60):
    logger.info("Waiting for database to be ready...")
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("DATABASE_URL is not set.")
        return False
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(db_url)
            conn.close()
            logger.info("Database is ready.")
            return True
        except Exception:
            time.sleep(2)
    
    logger.error(f"Database wait timed out after {timeout} seconds.")
    return False

def is_db_empty():
    try:
        db_url = os.getenv('DATABASE_URL')
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # First check if the activities table exists
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'activities')")
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            # If table doesn't exist, it's definitely empty
            conn.close()
            return True
            
        # If table exists, check if it has any rows
        cur.execute("SELECT count(*) FROM activities")
        row_count = cur.fetchone()[0]
        conn.close()
        
        return row_count == 0
    except Exception as e:
        logger.warning(f"Could not check if DB is empty: {e}. Assuming it might need restore.")
        return True

def restore_latest_on_startup():
    logger.info("Checking if initial restore is needed...")
    if not wait_for_db():
        return
    
    if not is_db_empty():
        logger.info("Database is not empty. Skipping initial restore.")
        return

    logger.info("Database is empty. Attempting to restore latest backup from Google Drive...")
    success, backups = list_backups()
    if success and backups:
        latest_backup = backups[0]
        logger.info(f"Found latest backup: {latest_backup['name']} (ID: {latest_backup['id']})")
        perform_restore(latest_backup['id'])
    else:
        logger.info("No backups found in Google Drive to restore.")

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
        result = subprocess.run(['psql', db_url, '-f', restore_file], capture_output=True, text=True)
        
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
