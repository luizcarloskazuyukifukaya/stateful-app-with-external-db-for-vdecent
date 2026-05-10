import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Scopes for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def generate_token():
    creds_path = 'credentials.json'
    token_path = 'token.json'

    if not os.path.exists(creds_path):
        print(f"Error: {creds_path} not found in current directory.")
        return

    print("Starting Google OAuth flow...")
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    # This will open a browser locally on your machine
    creds = flow.run_local_server(port=0)
    
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    
    print(f"Successfully generated {token_path}")

if __name__ == '__main__':
    generate_token()
