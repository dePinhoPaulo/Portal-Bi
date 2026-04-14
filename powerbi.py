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

def get_user_value(user, filter_source):
    """Retorna o valor do campo do usuário conforme filter_source."""
    if filter_source == "empresa_revenda":
        return user.empresa_revenda
    elif filter_source == "departamento":
        return user.departamento
    elif filter_source == "email":
        return user.email
    return None

def get_embed_token(workspace_id: str, report_id: str,
                    user=None, has_rls: bool = False, rls_configs=None) -> dict:
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

    if has_rls and rls_configs and user:
        user_role   = user.role if not user.is_admin else "admin"
        matched_rls = [r for r in rls_configs if r.system_role == user_role]

        if matched_rls:
            # Monta todas as roles e usa o username correto para cada filtro
            roles    = []
            username = user.email  # fallback

            for rls in matched_rls:
                if rls.role_name not in roles:
                    roles.append(rls.role_name)

                # Pega o valor do campo mais relevante
                # Prioriza o primeiro que tiver valor preenchido no usuário
                val = get_user_value(user, rls.filter_source)
                if val and username == user.email:
                    username = val

            # Power BI só aceita um username por identidade
            # Para múltiplos filtros diferentes (revenda E departamento)
            # precisamos de identidades separadas por role
            identities = []
            for rls in matched_rls:
                val = get_user_value(user, rls.filter_source) or user.email
                identities.append({
                    "username": val,
                    "roles":    [rls.role_name],
                    "datasets": [dataset_id]
                })

            body["identities"] = identities
            print(f"RLS aplicado: {[(i['roles'], i['username']) for i in identities]}")

        else:
            # Role não filtrada → envia role que vê tudo
            body["identities"] = [{
                "username": user.email,
                "roles":    ["diretor"],
                "datasets": [dataset_id]
            }]
            print(f"Acesso livre via role diretor: {user.email}")

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