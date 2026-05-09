# Development Plan: Stateful App with External DB Backup

This plan outlines the implementation of a sidecar container for automatic database backup and restore to Google Drive.

## Phase 1: Environment & Credentials Setup
- [x] Research Google Drive API requirements for Python/Node.js (matching existing `credentials.json` pattern).
- [x] Define required environment variables in `.env.example`:
    - `BACKUP_INTERVAL_MINS` (default: 5)
    - `GOOGLE_DRIVE_FOLDER_ID`
    - `RESTORE_AUTH_TOKEN` (for securing `/api/restore`)
    - Google API credentials path or inline JSON.

## Phase 2: Implement Backup Sidecar (Python)
- [x] Create `sidecar/` directory.
- [x] Implement `backup.py`:
    - Logic to run `pg_dump` on the `db` service.
    - Logic to upload dump files to Google Drive.
    - Scheduler to run backup every `BACKUP_INTERVAL_MINS`.
- [x] Implement `sidecar_api.py` (FastAPI or Flask):
    - `POST /api/backup`: Manually trigger backup.
    - `POST /api/restore`: Secure endpoint to restore from a specific Google Drive file.
- [x] Create `sidecar/Dockerfile`.

## Phase 3: Docker Integration
- [x] Update `docker-compose.yaml` to include the `sidecar` service.
- [x] Ensure `sidecar` has access to the database network and volumes if necessary.
- [x] Map sidecar API port if external access is needed, or keep it internal to the Docker network.

## Phase 4: Verification & Testing
- [x] Verify automatic backup occurs every 5 minutes (Logic implemented with min 5 check).
- [x] Test manual backup via API.
- [x] Test secure restore via API (validating auth token).
- [x] Verify persistence after restore.

## Phase 5: Documentation
- [x] Update `README.md` with instructions on how to configure Google Drive and use the backup/restore API.
