# Stateful App with External Backup for V-Decent

A stateful activity logging application built with Node.js and PostgreSQL. Optimized for deployment on **Coolify**.

## Features

- **Activity Tracking:** Log activities with types, timestamps, and Markdown notes.
- **Data Persistence:** Uses PostgreSQL for reliable storage.
- **Automated Backups:** Sidecar container automatically backs up the database to Google Drive every 5 minutes.
- **Backup Retention (Purge):** Automatically purges old backups based on a configurable retention count.
- **Backup/Restore/Purge API:** Secure endpoints to trigger manual backups, restores, and purges.
- **Coolify Optimized:** Standardized port 80 and Docker Compose orchestration.
- **Themable:** Responsive UI with clean aesthetics.

## Backup & Store Design

The system employs a **Sidecar Architecture** to decouple database management from the core application logic.

### 1. Architecture Overview
- **Core App Container:** Handles the web interface and activity logging.
- **Database Container:** PostgreSQL 16 instance.
- **Sidecar Container:** A Python-based service responsible for interacting with the database and Google Drive. It operates independently, ensuring that backup operations do not impact the application's availability.

### 2. Google Drive as the Source of Truth
- The sidecar is **stateless**. It does not maintain a local record of backups.
- Every operation (listing, purging, restoring) queries Google Drive in real-time. This ensures that manual deletions in the Google Drive UI are immediately reflected in the system.

### 3. Automated Backup Lifecycle
- **Backup:** Runs every `BACKUP_INTERVAL_MINS` (default 5). It uses `pg_dump` to create a timestamped `.sql` file and uploads it to Google Drive.
- **Purge:** After every successful backup, the sidecar checks the `BACKUP_RETENTION_COUNT`. It keeps the $N$ most recent backups and deletes the rest from Google Drive automatically.

### 4. Zero-Touch Initial Setup
- On the first deployment (when the database is empty), the sidecar automatically detects the lack of data.
- It scans the Google Drive folder for the most recent backup and triggers an **Initial Restore** automatically.
- This ensures that a new environment can be spun up and populated with the latest production state without manual intervention.

### 5. Secure Operations
- While backups are automatic, **Restore** and **Purge** operations via the API require a secure `X-Auth-Token`. This prevents unauthorized modifications to the database state.

## Backup & Restore Sidecar

The application includes a sidecar container that manages database backups to Google Drive.

### Configuration

Set the following in your `.env` file:

- `BACKUP_INTERVAL_MINS`: Frequency of automatic backups (minimum 5).
- `BACKUP_RETENTION_COUNT`: Number of recent backups to keep in Google Drive. Oldest are purged.
- `GOOGLE_DRIVE_FOLDER_ID`: The ID of the Google Drive folder where backups will be stored.
- `RESTORE_AUTH_TOKEN`: A secret token used to authorize restore and purge requests.
- `GOOGLE_CREDENTIALS_PATH`: Path to your Google API `credentials.json`.
- `GOOGLE_TOKEN_PATH`: Path to your Google API `token.json`.

### API Endpoints

The sidecar exposes an API on port `8000`:

#### Trigger Manual Backup
- **Endpoint:** `POST /api/backup`
- **Description:** Triggers an immediate backup of the database to Google Drive and runs the purge logic.

#### List Backups
- **Endpoint:** `GET /api/list`
- **Headers:** `X-Auth-Token: <your-restore-auth-token>`
- **Description:** Returns a list of all available backups in Google Drive, including their names (with timestamps), File IDs, and creation times.

#### Trigger Manual Purge
- **Endpoint:** `POST /api/purge`
- **Headers:** `X-Auth-Token: <your-restore-auth-token>`
- **Description:** Triggers the purge logic manually to keep only `BACKUP_RETENTION_COUNT` files.

#### Trigger Restore
- **Endpoint:** `POST /api/restore`
- **Headers:** `X-Auth-Token: <your-restore-auth-token>`
- **Body:**
  ```json
  {
    "file_id": "google-drive-file-id"
  }
  ```
- **Description:** Downloads the specified file from Google Drive and restores the database.

## Google Drive Authentication Setup
This application uses Google Drive for backup and restore operations through the `sidecar` container.
Before starting the application, you must provide Google OAuth credentials files:
- `credentials.json`
- `token.json`

### Detailed Setup Guides
For step-by-step instructions, please refer to:
- [Google Drive Environment Setup Guide](./google_drive_env_setup_guide.md): Instructions on setting up Google Cloud projects and environment variables.
- [Token JSON Generation Flow](./token_json_generation_flow.md): Guide on generating the `token.json` file.

---

### Directory Structure
After cloning the repository, place the files inside the `sidecar` directory:
```text
project-root/
├── docker-compose.yaml
├── .env
├── app/
├── sidecar/
│   ├── credentials.json
│   ├── token.json
│   └── Dockerfile

## Local Development

1. **Setup Environment:**
   ```bash
   cp .env.example .env
   ```
2. **Install Dependencies:**
   ```bash
   npm install
   ```
3. **Run Postgres:**
   Ensure you have a PostgreSQL instance running and update `DATABASE_URL` in `.env`.
4. **Start App:**
   ```bash
   npm start
   ```

## Testing Locally with Docker (Recommended)

For a quick and consistent local test environment that includes the Database, Application, and Sidecar, use the provided helper script:

1. **Make the script executable:**
   ```bash
   chmod +x run_local.sh
   ```
2. **Run the script:**
   ```bash
   ./run_local.sh
   ```

### What `run_local.sh` does:
- **Port Detection:** Automatically finds an available port (starting from 80, then 8081-8085).
- **Environment Setup:** Creates a `.env` file from `.env.example` if it doesn't exist.
- **Docker Orchestration:** Build and launches all containers (App, DB, Sidecar) using `docker-compose`.
- **Access URLs:** Provides the local and network URLs to access the application once it's up.

### Commands for Management:
- **Logs:** `docker-compose logs -f app` (or `sidecar` / `db`)
- **Stop:** `docker-compose down`

## Deployment on Coolify

1. Create a new **Application** in Coolify from GitHub.
2. Select **Docker Compose** as the build pack.
3. The `docker-compose.yaml` will automatically set up both the Node.js app and the PostgreSQL database.
4. Set your **Domain** (e.g., `https://activity.yourdomain.com`).
5. Coolify will handle the mapping to the container's port 80 automatically.

## License
MIT

## Troubleshooting
### Case 1: Postgres connection failure
This error message is very specific:

  unable to get image 'postgres:16-alpine': permission denied while trying to connect to the docker API
  at unix:///var/run/docker.sock

  This indicates that your current user (kfukaya) does not have the necessary permissions to communicate
  with the Docker daemon on your system. This is a common security measure on Linux.

  How to Fix It:

  You need to add your user to the docker group. This will grant your user the permissions needed to
  interact with the Docker daemon.

   1. Add your user to the docker group:
      Open your terminal and run the following command. You'll need to enter your password.

   1     sudo usermod -aG docker $USER

   2. Apply the group changes:
      For the group changes to take effect, you need to either:
       * Log out and log back in. This is the most reliable method.
       * Or, run newgrp docker in your current terminal session. This starts a new shell with the updated
         group membership.
   1         newgrp docker
          (You might need to re-run ./run_local.sh in this new shell).

  After completing these steps, try running ./run_local.sh again. It should now be able to pull the
  postgres:16-alpine image and start your application and database.

### Case 2: Port 80 conflict
   Error response from daemon: failed to set up container networking: driver failed programming external
   connectivity on endpoint stateful-app-for-vdecent-app-1
   (adbb889e63fe8670e4d753a4d9b18ad8216d24984926cf5b0e52bfacf77524f9): failed to bind host port
   0.0.0.0:80/tcp: address already in use

✦ This error means that port 80 on your host machine is already in use by another process:

  failed to bind host port 0.0.0.0:80/tcp: address already in use

  This is preventing the Docker container from binding to port 80.

  How to Resolve This:

  Option 1: Find and Stop the Conflicting Process (Recommended)

   1. Identify the process: Run this command in your terminal to see what's using port 80:
   1     sudo netstat -tulnp | grep ':80'
      This will show you the process ID (PID) and name of the application using port 80.

   2. Stop the conflicting process: Once you know the process, you can stop it. For example, if it's a
      web server like Apache or Nginx, you might use:
   1     sudo systemctl stop apache2  # Or nginx, or whatever process it is
      If it's a different application, you might need to find its specific stop command or use kill <PID>
  (where <PID> is the process ID you found).

  Option 2: Use a Different Host Port (Workaround)

  If you don't want to stop the other process, you can change the port mapping in the temporary
  docker-compose.local.yaml file that run_local.sh creates.

   1. Edit run_local.sh:
      Find the cat <<OVERRIDE > docker-compose.local.yaml section and change the port mapping from
  "80:80" to something else, like "8080:80":

   1     -    ports:
   2     -      - "80:80"
   3     +    ports:
   4     +      - "8080:80" # Changed from 80 to 8080

   2. Rerun run_local.sh:
      After making this change, save the script and run ./run_local.sh again. You will then access the
  app at http://localhost:8080 or http://<host_ip>:8080.
