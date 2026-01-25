import io
import json
import ssl
import time
from typing import Optional, Dict, Any, List

import streamlit as st

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
DB_FILENAME = "trips.json"
IMAGES_FOLDER_NAME = "images"


def _drive_service_uncached():
    oauth = st.secrets["oauth"]
    creds = Credentials(
        token=None,
        refresh_token=oauth["refresh_token"],
        token_uri=oauth.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=oauth["client_id"],
        client_secret=oauth["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def find_file_in_folder(service, folder_id: str, name: str) -> Optional[str]:
    q = f"'{folder_id}' in parents and name='{name}' and trashed=false"
    res = _execute_with_retry(service.files().list(q=q, fields="files(id,name)"))
    files = res.get("files", [])
    return files[0]["id"] if files else None


def ensure_subfolder(service, parent_id: str, name: str) -> str:
    q = (
        f"'{parent_id}' in parents and name='{name}' "
        f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    res = _execute_with_retry(service.files().list(q=q, fields="files(id,name)"))
    files = res.get("files", [])
    if files:
        return files[0]["id"]

    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    created = _execute_with_retry(service.files().create(body=meta, fields="id"))
    return created["id"]


def download_bytes(service, file_id: str) -> bytes:
    req = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read()


def download_json(service, file_id: str) -> Dict[str, Any]:
    raw = download_bytes(service, file_id)
    return json.loads(raw.decode("utf-8"))


def upload_json(service, folder_id: str, name: str, data: Dict[str, Any]) -> str:
    content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json", resumable=False)

    existing = find_file_in_folder(service, folder_id, name)
    if existing:
        _execute_with_retry(service.files().update(fileId=existing, media_body=media))
        return existing

    meta = {"name": name, "parents": [folder_id]}
    created = _execute_with_retry(service.files().create(body=meta, media_body=media, fields="id"))
    return created["id"]


def upload_image_bytes(service, folder_id: str, filename: str, img_bytes: bytes, mime: str) -> str:
    media = MediaIoBaseUpload(io.BytesIO(img_bytes), mimetype=mime, resumable=False)
    meta = {"name": filename, "parents": [folder_id]}
    created = _execute_with_retry(service.files().create(body=meta, media_body=media, fields="id"))
    return created["id"]


def load_db(root_folder_id: str) -> Dict[str, Any]:
    service = _drive_service()
    fid = find_file_in_folder(service, root_folder_id, DB_FILENAME)
    if not fid:
        return {"trips": []}
    try:
        return download_json(service, fid)
    except Exception:
        return {"trips": []}


def save_db(root_folder_id: str, db: Dict[str, Any]) -> None:
    service = _drive_service()
    upload_json(service, root_folder_id, DB_FILENAME, db)


def get_image_bytes(image_file_id: str) -> Optional[bytes]:
    if not image_file_id:
        return None
    try:
        service = _drive_service()
        return download_bytes(service, image_file_id)
    except Exception:
        return None


def list_trip_names(db: Dict[str, Any]) -> List[str]:
    return [t.get("name", "") for t in db.get("trips", []) if t.get("name")]


def get_trip(db: Dict[str, Any], trip_name: str) -> Optional[Dict[str, Any]]:
    for t in db.get("trips", []):
        if t.get("name") == trip_name:
            return t
    return None


@st.cache_resource(show_spinner=False)
def _drive_service_cached():
    """Cache Drive service client across reruns."""
    return _drive_service_uncached()

def _drive_service():
    return _drive_service_cached()





def _execute_with_retry(request, retries: int = 5, base_delay: float = 0.5):
    """Execute googleapiclient request with retries for transient SSL/network issues."""
    last_err = None
    for i in range(retries):
        try:
            return request.execute(num_retries=3)
        except ssl.SSLError as e:
            last_err = e
        except Exception as e:
            # Some transient network errors come as generic exceptions from httplib2
            msg = str(e).lower()
            if "ssl" in msg or "timed out" in msg or "connection" in msg or "recv" in msg:
                last_err = e
            else:
                raise
        time.sleep(base_delay * (2 ** i))
    raise last_err
