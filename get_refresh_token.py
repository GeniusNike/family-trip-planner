"""
1) Google Cloud Console에서 OAuth Client ID(데스크톱 앱) 생성
2) 아래 CLIENT_ID/CLIENT_SECRET 채우기
3) 실행:
   pip install google-auth-oauthlib
   python get_refresh_token.py
4) 출력된 refresh_token을 Streamlit Secrets에 넣기
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]

CLIENT_ID = "PUT_YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "PUT_YOUR_CLIENT_SECRET_HERE"

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=SCOPES,
)

creds = flow.run_local_server(port=0)
print("\n=== COPY THESE INTO STREAMLIT SECRETS ===")
print("client_id =", CLIENT_ID)
print("client_secret =", CLIENT_SECRET)
print("refresh_token =", creds.refresh_token)
print("token_uri = https://oauth2.googleapis.com/token")
