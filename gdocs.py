import os
from datetime import datetime
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes needed for Google Drive and Docs APIs
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def authenticate():
    """Authenticate with Google APIs"""
    creds = None
    
    # Check if token.json exists (stored credentials)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no valid credentials, get them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Download credentials.json from Google Cloud Console
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
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

def replace_text_in_document(docs_service, document_id, replacements):
    """Replace placeholder text in a Google Doc"""
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

def main():
    # Configuration
    TEMPLATE_DOC_ID = '1rrgQCAJdA6AZWC6jaK3tLCegYb9eC760kaYSZTuRs6s'  # Replace with your template doc ID
    DESTINATION_FOLDER_ID = '1P6aEnsW76y4IFiU181hz8g33Bj9zQGJJ'  # Replace with folder ID (optional)
    NEW_DOC_NAME = f"Generated Document - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    # Define your replacements
    replacements = {
        '{Date}': datetime.now().strftime('%B %d, %Y'),
        '{Time}': datetime.now().strftime('%I:%M %p'),
        '{Year}': str(datetime.now().year),
        '{Month}': datetime.now().strftime('%B'),
        '{Day}': str(datetime.now().day),
        # Add more replacements as needed
        '{CompanyName}': 'Your Company Name',
        '{UserName}': 'John Doe',
        '{ProjectName}': 'Sample Project'
    }
    
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
            TEMPLATE_DOC_ID, 
            NEW_DOC_NAME,
            DESTINATION_FOLDER_ID if DESTINATION_FOLDER_ID != 'your_destination_folder_id_here' else None
        )
        print(f"Document copied successfully. New document ID: {new_doc_id}")
        
        # Apply text replacements
        print("Applying text replacements...")
        replace_text_in_document(docs_service, new_doc_id, replacements)
        print("Text replacements completed!")
        
        # Get the document URL
        doc_url = f"https://docs.google.com/document/d/{new_doc_id}"
        print(f"New document URL: {doc_url}")
        
        return new_doc_id, doc_url
        
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None

if __name__ == "__main__":
    main()