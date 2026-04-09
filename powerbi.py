import requests
import os
import msal

TENANT_ID    = os.getenv("TENANT_ID")
CLIENT_ID    = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

AUTHORITY    = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE        = ["https://analysis.windows.net/powerbi/api/.default"]
PBI_API      = "https://api.powerbi.com/v1.0/myorg"

def get_access_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" in result:
        return result["access_token"]
    raise Exception(f"Erro ao obter token: {result.get('error_description')}")

def get_embed_token(workspace_id: str, report_id: str) -> dict:
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Busca detalhes do relatório
    report_url = f"{PBI_API}/groups/{workspace_id}/reports/{report_id}"
    report_resp = requests.get(report_url, headers=headers)
    print("STATUS REPORT:", report_resp.status_code)
    print("REPORT JSON:", report_resp.json())
    report_info = report_resp.json()
    embed_url = report_info.get("embedUrl")

    # Gera o embed token
    token_url = f"{PBI_API}/groups/{workspace_id}/reports/{report_id}/GenerateToken"
    body = {"accessLevel": "view"}
    token_resp = requests.post(token_url, headers=headers, json=body)
    print("STATUS TOKEN:", token_resp.status_code)
    print("TOKEN JSON:", token_resp.json())
    embed_token = token_resp.json().get("token")

    return {
        "embed_token": embed_token,
        "embed_url": embed_url,
        "report_id": report_id
    }