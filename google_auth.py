from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


# SCOPES define what permissions your app requires
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def authenticate(scopes):
    """
    Authenticate and return credentials for the given scopes.
    Generates a refreshable token for offline access.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials/credentials.json', scopes
        )
        creds = flow.run_local_server(port=0, access_type='offline', prompt='consent')
        return creds
    except FileNotFoundError:
        print("Error: 'credentials.json' not found. Please ensure it exists in the same directory.")
        raise


def load_or_authenticate(scopes, token_file='credentials/token.json'):
    """
    Try to load credentials from a file. If invalid or expired, reauthenticate.
    """
    from google.auth.exceptions import RefreshError

    try:
        # Load existing credentials
        creds = load_credentials(token_file)
        if creds and creds.valid:  # If credentials are valid
            return creds

        if creds and creds.expired and creds.refresh_token:  
            # Try refreshing the token
            creds.refresh(Request())
            save_credentials(creds, token_file)
            return creds
    except (FileNotFoundError, RefreshError):
        # If credentials are missing or invalid, fall back to reauthentication
        print("Credentials missing or invalid. Reauthenticating...")
    
    # Authenticate and save new credentials
    creds = authenticate(scopes)
    save_credentials(creds, token_file)
    return creds


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
