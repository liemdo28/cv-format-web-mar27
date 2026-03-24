"""
Google Drive utilities for CV Format Tool.
Uploads processed DOCX files to a Shared Drive using OAuth refresh token.
"""

import os
from typing import Optional

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False


SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _build_creds(refresh_token: str, client_id: str, client_secret: str) -> Optional[Credentials]:
    """Build OAuth2 credentials from refresh token."""
    if not all([refresh_token, client_id, client_secret]):
        return None
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri=TOKEN_URL,
        scopes=SCOPES,
    )


def get_drive_service(refresh_token: str, client_id: str, client_secret: str):
    """Returns a Google Drive service instance, or None if auth fails."""
    if not HAS_GDRIVE:
        return None
    creds = _build_creds(refresh_token, client_id, client_secret)
    if creds is None:
        return None
    try:
        # Refresh token to get valid access token
        creds.refresh(Request())
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def upload_file(
    file_path: str,
    filename: str,
    folder_id: str,
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> Optional[str]:
    """
    Upload a file to Google Drive Shared Drive.

    Returns:
        Google Drive direct download URL on success, None on failure.
    """
    service = get_drive_service(refresh_token, client_id, client_secret)
    if service is None:
        return None

    try:
        file_metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        media = MediaFileUpload(file_path, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        uploaded = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        ).execute()

        file_id = uploaded.get("id")
        if not file_id:
            return None

        # Make the file publicly accessible (reader role for anyone)
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()

        # Return direct download URL
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    except HttpError as e:
        print(f"[GDrive] HttpError uploading {filename}: {e}")
        return None
    except Exception as e:
        print(f"[GDrive] Error uploading {filename}: {e}")
        return None
