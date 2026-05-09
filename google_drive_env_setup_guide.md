# Google Drive Environment Variables Setup Guide

This document explains how to retrieve and configure the required environment variables for an application that accesses Google Drive.

---

# 1. `RESTORE_AUTH_TOKEN`

```env
RESTORE_AUTH_TOKEN=change-me-to-a-secure-token
```

## What it is
This is **not provided by Google**.

It is an application-specific secret token used to authenticate restore operations or API requests in your app.

## What you should do
Generate a long random string yourself.

### Good examples
You can generate one with:

Linux/macOS:

```bash
openssl rand -hex 32
```

Example output:

```text
8f1c3e9d7a4b6c2f8d1a9e0b4c7d2f6a8b1c3d5e7f9a0b2c4d6e8f1a3b5c7d9
```

Then:

```env
RESTORE_AUTH_TOKEN=8f1c3e9d7a4b6c2f8d1a9e0b4c7d2f6a8b1c3d5e7f9a0b2c4d6e8f1a3b5c7d9
```

---

# 2. `GOOGLE_DRIVE_FOLDER_ID`

```env
GOOGLE_DRIVE_FOLDER_ID=your-google-drive-folder-id
```

## What it is
This is the ID of the Google Drive folder your application will access.

## How to retrieve it

1. Open Google Drive:
   https://drive.google.com

2. Create a folder or open an existing one.

3. Look at the URL in your browser.

Example:

```text
https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz123456
```

The folder ID is:

```text
1AbCdEfGhIjKlMnOpQrStUvWxYz123456
```

Then set:

```env
GOOGLE_DRIVE_FOLDER_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz123456
```

---

# 3. `GOOGLE_CREDENTIALS_PATH`

```env
GOOGLE_CREDENTIALS_PATH=credentials.json
```

## What it is
This points to the OAuth client credentials file downloaded from Google Cloud.

This file contains:
- Client ID
- Client Secret
- OAuth configuration

It is usually named:

```text
credentials.json
```

---

## How to create and download it

### Step 1 — Open Google Cloud Console

Go to:

https://console.cloud.google.com

---

### Step 2 — Create a Project

1. Click the project selector at the top
2. Click:
   - “New Project”
3. Create a project name
4. Create the project

---

### Step 3 — Enable Google Drive API

1. Open:

https://console.cloud.google.com/apis/library/drive.googleapis.com

2. Click:
   - “Enable”

---

### Step 4 — Configure OAuth Consent Screen

Open:

https://console.cloud.google.com/apis/credentials/consent

Choose:
- External (usually easiest for personal use)

Fill:
- App name
- Your email

Add scopes:
- Google Drive API scopes if requested

Add your Google account as a test user if Google asks.

---

### Step 5 — Create OAuth Client Credentials

Open:

https://console.cloud.google.com/apis/credentials

1. Click:
   - “Create Credentials”
   - “OAuth client ID”

2. Application type:
   - Desktop App (usually easiest for CLI/server tools)

3. Create it.

---

### Step 6 — Download credentials.json

After creation:
1. Click the download button
2. Save the file as:

```text
credentials.json
```

Place it where your app expects it.

Example:

```text
/app/sidecar/credentials.json
```

Then:

```env
GOOGLE_CREDENTIALS_PATH=credentials.json
```

Or absolute path:

```env
GOOGLE_CREDENTIALS_PATH=/opt/myapp/credentials.json
```

---

# 4. `GOOGLE_TOKEN_PATH`

```env
GOOGLE_TOKEN_PATH=token.json
```

## What it is
This is the OAuth access/refresh token generated **after login authorization**.

Usually:
- Your application generates this automatically
- The first time you run the app, it opens a browser login
- You sign into Google
- Google asks permission
- The app saves `token.json`

---

## Typical flow

### First run

Your app may show something like:

```text
Please visit this URL to authorize this application:
https://accounts.google.com/o/oauth2/auth?...
```

You:
1. Open the URL
2. Login with Google
3. Approve access

Then the app creates:

```text
token.json
```

Automatically.

---

## Where to place it

Usually in the same folder:

```text
/app/sidecar/token.json
```

Then:

```env
GOOGLE_TOKEN_PATH=token.json
```

Or:

```env
GOOGLE_TOKEN_PATH=/opt/myapp/token.json
```

---

# Important Security Notes

## Never commit these files to Git

Do NOT upload:
- `credentials.json`
- `token.json`

to GitHub.

Add to `.gitignore`:

```gitignore
credentials.json
token.json
```

---

## `token.json` is sensitive

It can grant access to your Google Drive.

Treat it like a password.

---

# Typical Final Example

```env
RESTORE_AUTH_TOKEN=8f1c3e9d7a4b6c2f8d1a9e0b4c7d2f6a8b1c3d5e7f9a0b2c4d6e8f1a3b5c7d9

GOOGLE_DRIVE_FOLDER_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz123456

GOOGLE_CREDENTIALS_PATH=/opt/myapp/credentials.json
GOOGLE_TOKEN_PATH=/opt/myapp/token.json
```

