import os
import datetime
import subprocess
import logging
import base64
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
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_gdrive_service():
    creds = None
    token_path = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')
    creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
    token_b64 = os.getenv('GOOGLE_API_TOKEN_B64')

    # If GOOGLE_API_TOKEN_B64 is provided, decode and write to token_path
    if token_b64:
        logger.info(f"GOOGLE_API_TOKEN_B64 detected. Writing to {token_path}...")
        try:
            token_json = base64.b64decode(token_b64).decode('utf-8')
            with open(token_path, 'w') as f:
                f.write(token_json)
        except Exception as e:
            logger.error(f"Failed to decode GOOGLE_API_TOKEN_B64: {e}")

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
        # We use --clean and --if-exists to make the restore more robust (it will drop tables if they exist)
        result = subprocess.run(['pg_dump', db_url, '--clean', '--if-exists', '-f', backup_file], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"pg_dump failed: {result.stderr}")
            return False, result.stderr

        # Workaround for version mismatch: remove SET transaction_timeout = 0; if present
        # This parameter was introduced in Postgres 17 and causes errors on older versions.
        if os.path.exists(backup_file):
            with open(backup_file, 'r') as f:
                lines = f.readlines()
            with open(backup_file, 'w') as f:
                for line in lines:
                    if "SET transaction_timeout = 0;" not in line:
                        f.write(line)

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
        
        # Be inclusive of different MIME types and extensions for manually uploaded files
        query = "(mimeType = 'application/sql' or mimeType = 'text/plain' or mimeType = 'text/x-sql' or name contains '.sql') and trashed = false"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, createdTime, size, mimeType)',
            orderBy='createdTime desc'
        ).execute()
        
        files = results.get('files', [])
        
        # Further filter in Python to ensure we only get .sql files if they matched by broad MIME types
        backups = [f for f in files if f['name'].lower().endswith('.sql') or f.get('mimeType') == 'application/sql']
        
        return True, backups
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
        
        # Check if there are any tables in the public schema
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
        table_count = cur.fetchone()[0]
        
        if table_count == 0:
            conn.close()
            return True
            
        # If there are tables, check if all of them are empty (optional, but safer)
        # For now, if there are any tables, we check if the 'activities' table specifically has data
        # since that's our main data table. Or we can just say if there are tables, it's not empty.
        # Given the requirements, if it's the "first deployment", there should be NO tables.
        # But server.js might have created them.
        
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'activities')")
        if cur.fetchone()[0]:
            cur.execute("SELECT count(*) FROM activities")
            row_count = cur.fetchone()[0]
            conn.close()
            return row_count == 0
        
        conn.close()
        return False # Has other tables but not activities? Not empty.
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

        # Pre-process the restore file for version compatibility
        if os.path.exists(restore_file):
            with open(restore_file, 'r') as f:
                content = f.read()
            
            # Remove transaction_timeout which is incompatible with Postgres < 17
            if "SET transaction_timeout = 0;" in content:
                logger.info("Removing 'SET transaction_timeout = 0;' for compatibility")
                content = content.replace("SET transaction_timeout = 0;", "-- SET transaction_timeout = 0; (removed for compatibility)")
            
            with open(restore_file, 'w') as f:
                f.write(content)

        # Clear the database before restore to handle old backups without --clean
        logger.info("Clearing public schema before restore to ensure a clean slate...")
        try:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO public; GRANT ALL ON SCHEMA public TO \"user\";")
            conn.close()
            logger.info("Public schema cleared successfully.")
        except Exception as e:
            logger.error(f"Failed to clear schema: {e}. Attempting restore anyway...")

        # Run psql to restore
        # We use ON_ERROR_STOP=1 to make sure we catch failures
        result = subprocess.run(['psql', '-v', 'ON_ERROR_STOP=1', db_url, '-f', restore_file], capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"psql restore failed: {result.stderr}")
            # If it failed because of the schema drop, we might need to investigate
            return False, result.stderr

        logger.info("Restore completed successfully.")
        
        # Clean up local file
        os.remove(restore_file)
        return True, "Restore successful"

    except Exception as e:
        logger.exception("An error occurred during restore")
        return False, str(e)
