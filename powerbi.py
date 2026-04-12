import requests
import os
import msal

TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY     = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE         = ["https://analysis.windows.net/powerbi/api/.default"]
PBI_API       = "https://api.powerbi.com/v1.0/myorg"

def get_access_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" in result:
        return result["access_token"]
    raise Exception(f"Erro ao obter token: {result.get('error_description')}")

def get_embed_token(workspace_id: str, report_id: str,
                    user=None, has_rls: bool = False, rls_config=None) -> dict:
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    report_url  = f"{PBI_API}/groups/{workspace_id}/reports/{report_id}"
    report_resp = requests.get(report_url, headers=headers)
    report_info = report_resp.json()
    embed_url   = report_info.get("embedUrl")
    dataset_id  = report_info.get("datasetId")

    body = {"accessLevel": "view"}

    if has_rls and rls_config and user:
        # Pega o valor do campo correto no usuário
        filter_source = rls_config.filter_source
        if filter_source == "empresa_revenda":
            username = user.empresa_revenda or user.email
        elif filter_source == "departamento":
            username = user.departamento or user.email
        else:
            username = user.email

        # Admin e diretor: veem tudo via role sem filtro de username
        if user.is_admin or user.role == "diretor":
            username = user.email

        body["identities"] = [{
            "username": username,
            "roles":    [rls_config.role_name],
            "datasets": [dataset_id]
        }]

    print("BODY ENVIADO:", body)

    token_url   = f"{PBI_API}/groups/{workspace_id}/reports/{report_id}/GenerateToken"
    token_resp  = requests.post(token_url, headers=headers, json=body)
    print("TOKEN JSON:", token_resp.json())
    embed_token = token_resp.json().get("token")

    return {
        "embed_token": embed_token,
        "embed_url":   embed_url,
        "report_id":   report_id
    }