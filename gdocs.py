import os
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from replacements import get_default_replacements

# Scopes needed for Google Drive and Docs APIs
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]


def authenticate():
    """Authenticate with Google APIs - handles both local and headless environments"""
    creds = None
    
    # Check if token.json exists (stored credentials)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no valid credentials, get them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed credentials
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                print("Credentials refreshed successfully!")
            except Exception as e:
                print(f"Token refresh failed: {e}")
                creds = None
        
        if not creds:
            # Try headless flow for desktop app credentials
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                
                # Get authorization URL (no redirect_uri needed for desktop apps)
                auth_url, _ = flow.authorization_url(prompt='consent')
                
                print("\n" + "="*60)
                print("MANUAL AUTHENTICATION REQUIRED")
                print("="*60)
                print(f"1. Open this URL in a browser on ANY device:")
                print(f"\n{auth_url}\n")
                print("2. Complete the authentication process")
                print("3. Copy the authorization code from the browser")
                print("4. Paste it below")
                print("="*60)
                
                code = input("Enter the authorization code: ").strip()
                
                flow.fetch_token(code=code)
                creds = flow.credentials
                
                print("Authentication successful!")
                
            except Exception as e:
                print(f"Manual authentication failed: {e}")
                return None
        
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return creds
    

def copy_document(drive_service, template_id, new_name, destination_folder_id=None):
    """Copy a Google Doc to a new location"""
    copy_metadata = {
        'name': new_name
    }
    
    # If destination folder specified, set it
    if destination_folder_id:
        copy_metadata['parents'] = [destination_folder_id]
    
    # Create the copy
    copied_doc = drive_service.files().copy(
        fileId=template_id,
        body=copy_metadata
    ).execute()
    
    return copied_doc['id']

def replace_text_in_document(docs_service, document_id, replacements=None):
    """Replace placeholder text in a Google Doc"""

    if replacements is None:
        replacements = {}

    replacements = {**get_default_replacements(), **replacements}

    requests = []
    
    # Create replace requests for each placeholder
    for placeholder, replacement in replacements.items():
        requests.append({
            'replaceAllText': {
                'containsText': {
                    'text': placeholder,
                    'matchCase': True
                },
                'replaceText': replacement
            }
        })
    
    # Execute all replacements in a batch
    if requests:
        docs_service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()


def copy_document_and_edit(template_id, new_name, destination_folder_id=None, replacements=None):

    try:
        # Authenticate
        print("Authenticating with Google APIs...")
        creds = authenticate()
        
        # Build service objects
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        
        # Copy the template document
        print(f"Copying template document...")
        new_doc_id = copy_document(
            drive_service, 
            template_id, 
            new_name,
            destination_folder_id
        )
        print(f"Document copied successfully. New document ID: {new_doc_id}")
        
        # Apply text replacements
        print("Applying text replacements...")
        replace_text_in_document(docs_service, new_doc_id, replacements)
        print("Text replacements completed!")
        
        # Get the document URL
        new_doc_url = f"https://docs.google.com/document/d/{new_doc_id}"
        print(f"New document URL: {new_doc_url}")
        
        return new_doc_id, new_doc_url
        
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None