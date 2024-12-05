from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# SCOPES define what permissions your app requires
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authenticate(scopes):
    """Authenticate and return credentials for the given scopes."""
    try:
        flow = InstalledAppFlow.from_client_secrets_file('credentials/credentials.json', scopes)
        creds = flow.run_local_server(port=0)
        return creds
    except FileNotFoundError:
        print("Error: 'credentials.json' not found. Please ensure it exists in the same directory.")
        raise

def save_credentials(creds, filename='credentials/token.json'):
    """Save the credentials to a file for future use."""
    with open(filename, 'w') as token_file:
        token_file.write(creds.to_json())

def load_credentials(filename='credentials/token.json'):
    """Load credentials from a file."""
    try:
        return Credentials.from_authorized_user_file(filename)
    except FileNotFoundError:
        return None

# Authenticate for Drive
#if __name__ == "__main__":
    #creds = authenticate(DRIVE_SCOPES)
    #save_credentials(creds, 'credentials/drive_token.json')
    #creds = authenticate(GMAIL_SCOPES)
    #save_credentials(creds, 'credentials/gmail_token.json')
