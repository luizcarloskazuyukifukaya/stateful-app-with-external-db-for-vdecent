import os
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from backup import perform_backup, perform_restore
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

class RestoreRequest(BaseModel):
    file_id: str

def get_auth_token(x_auth_token: str = Header(None)):
    expected_token = os.getenv('RESTORE_AUTH_TOKEN')
    if not expected_token:
        logger.warning("RESTORE_AUTH_TOKEN is not set. RESTORE IS DISABLED.")
        raise HTTPException(status_code=500, detail="Restore auth token not configured")
    if x_auth_token != expected_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_auth_token

@app.post("/api/backup")
async def trigger_backup():
    success, message = perform_backup()
    if success:
        return {"status": "success", "file_id": message}
    else:
        raise HTTPException(status_code=500, detail=message)

@app.post("/api/restore")
async def trigger_restore(request: RestoreRequest, token: str = Depends(get_auth_token)):
    success, message = perform_restore(request.file_id)
    if success:
        return {"status": "success", "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)

# Scheduler for automatic backups
scheduler = BackgroundScheduler()

def scheduled_backup():
    logger.info("Starting scheduled backup...")
    perform_backup()

@app.on_event("startup")
def start_scheduler():
    interval_str = os.getenv('BACKUP_INTERVAL_MINS', '5')
    try:
        interval = int(interval_str)
        if interval < 5:
            logger.info(f"Interval {interval} is less than minimum 5 minutes. Defaulting to 5.")
            interval = 5
    except ValueError:
        logger.error(f"Invalid BACKUP_INTERVAL_MINS: {interval_str}. Defaulting to 5.")
        interval = 5
    
    scheduler.add_job(scheduled_backup, 'interval', minutes=interval)
    scheduler.start()
    logger.info(f"Backup scheduler started with interval of {interval} minutes.")

@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
