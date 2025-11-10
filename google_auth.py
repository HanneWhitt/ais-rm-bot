#!/usr/bin/env python3
"""
Unified Google API authentication for Drive, Docs, and Calendar
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# All scopes needed for the bot
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/calendar.readonly'
]


def authenticate(scopes=None):
    """
    Authenticate with Google APIs - handles Drive, Docs, and Calendar

    Args:
        scopes (list): List of scopes to request. If None, uses all scopes.

    Returns:
        Credentials object or None on failure
    """
    if scopes is None:
        scopes = SCOPES

    creds = None

    # Check if token.json exists (stored credentials)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', scopes)

    # If there are no valid credentials, get them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed credentials
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
                print("✅ Credentials refreshed successfully!")
            except Exception as e:
                print(f"⚠️  Token refresh failed: {e}")
                print("Will need to re-authenticate...")
                creds = None

        if not creds:
            # Authenticate with all scopes
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', scopes)

                print("\n" + "="*60)
                print("🔐 GOOGLE API AUTHENTICATION")
                print("="*60)
                print("A browser window will open for authentication.")
                print("You'll be asked to grant access to:")
                print("  - Google Drive (copy/manage documents)")
                print("  - Google Docs (edit documents)")
                print("  - Google Calendar (read events)")
                print("="*60 + "\n")

                # This will start a local server and open a browser
                creds = flow.run_local_server(port=0)

                print("\n✅ Authentication successful!")

            except Exception as e:
                print(f"❌ Authentication failed: {e}")
                print("\nTroubleshooting:")
                print("1. Make sure credentials.json exists in this directory")
                print("2. Verify it's configured as 'Desktop app' in Google Cloud Console")
                print("3. Check that http://localhost is in the authorized redirect URIs")
                return None

        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            print("💾 Credentials saved to token.json")

    return creds


if __name__ == '__main__':
    print("Testing Google API authentication...\n")
    creds = authenticate()

    if creds:
        print("\n✅ Authentication successful!")
        print(f"📝 Token saved and ready to use")
        print(f"🔑 Scopes granted: {len(SCOPES)}")
        for scope in SCOPES:
            print(f"   - {scope}")
    else:
        print("\n❌ Authentication failed")
