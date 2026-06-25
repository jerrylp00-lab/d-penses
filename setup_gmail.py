"""Script one-shot pour obtenir le refresh token Gmail OAuth.
Lance-le une fois en local, copie les 3 valeurs dans Render.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_SECRETS = "/Users/jeremylepetit/Downloads/client_secret_326269005574-3d31k0ukdgbjru37fq1ogis5heu5e6q0.apps.googleusercontent.com.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
creds = flow.run_local_server(port=0)

print("\n=== COPIEZ CES 3 VARIABLES DANS RENDER ===\n")
print(f"GMAIL_CLIENT_ID={creds.client_id}")
print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
