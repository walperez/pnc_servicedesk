# watsonx Orchestrate Agents: 1E DEX Telemetry + Microsoft Intune Management

This directory contains everything needed to create and configure two AI agents in
**watsonx Orchestrate** that work together to identify unhealthy devices via 1E DEX
and trigger remote restarts via Microsoft Intune.

---

## Directory Structure

```
watsonx-orchestrate-agents/
├── agent-1-dex-telemetry/
│   ├── openapi.yaml        ← OpenAPI 3.0 spec for the 1E DEX REST API
│   └── system-prompt.md    ← Agent role, behavior guidelines, and output format
│
├── agent-2-intune-management/
│   ├── openapi.yaml        ← OpenAPI 3.0 spec for Microsoft Graph / Intune API
│   └── system-prompt.md    ← Agent role, behavior guidelines, and output format
│
└── auth/
    ├── auth_helper.py      ← Python helpers for DEX (API key) and Graph (OAuth2) auth
    └── .env.example        ← Template for required environment variables
```

---

## Architecture

```
User / Supervisor Agent
        │
        ├──► DEX Telemetry Agent ──► 1E DEX API  (API Key auth)
        │       • List devices
        │       • Get health scores
        │       • Find unhealthy devices
        │       • Get device events
        │
        └──► Intune Management Agent ──► Microsoft Graph API  (OAuth2 client credentials)
                • Find device by name
                • Restart device
                • Sync device policy
                • Get compliance state
```

---

## Setup

### 1. Configure Secrets

```bash
cp auth/.env.example auth/.env
# Edit auth/.env with your actual credentials
```

Required credentials:

| Variable | Where to find it |
|---|---|
| `DEX_TENANT` | Your 1E tenant subdomain |
| `DEX_API_KEY` | 1E Console → Settings → API Keys |
| `AZURE_TENANT_ID` | Entra ID → Overview |
| `AZURE_CLIENT_ID` | Entra ID → App registrations → your app → Overview |
| `AZURE_CLIENT_SECRET` | Entra ID → App registrations → your app → Certificates & secrets |

### 2. Grant Intune API Permissions in Microsoft Entra ID

1. Go to **Microsoft Entra ID** → **App registrations** → create or select your app
2. Click **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions**
3. Add the following permissions:
   - `DeviceManagementManagedDevices.Read.All`
   - `DeviceManagementManagedDevices.PrivilegedOperations.All`
4. Click **Grant admin consent for [your tenant]**

### 3. Test Connectivity (Optional)

```bash
cd auth
pip install requests python-dotenv
python -c "from dotenv import load_dotenv; load_dotenv('.env'); import auth_helper; auth_helper.test_dex_connection(); auth_helper.test_graph_connection()"
```

---

## Importing into watsonx Orchestrate

### Agent 1 — DEX Telemetry Agent

1. Open **watsonx Orchestrate** and navigate to **AI agent builder**
2. Click **Create agent**
3. Set the agent name: `DEX Telemetry Agent`
4. Paste the contents of `agent-1-dex-telemetry/system-prompt.md` as the **Instructions / System prompt**
5. Under **Tools**, click **Add tool** → **Import from OpenAPI spec**
6. Upload `agent-1-dex-telemetry/openapi.yaml`
7. Configure the authentication:
   - Auth type: **API Key**
   - Header name: `X-API-Key`
   - Value: your `DEX_API_KEY`
8. Save and publish the agent

### Agent 2 — Intune Management Agent

1. Click **Create agent**
2. Set the agent name: `Intune Management Agent`
3. Paste the contents of `agent-2-intune-management/system-prompt.md` as the **Instructions / System prompt**
4. Under **Tools**, click **Add tool** → **Import from OpenAPI spec**
5. Upload `agent-2-intune-management/openapi.yaml`
6. Configure the authentication:
   - Auth type: **OAuth 2.0 — Client Credentials**
   - Token URL: `https://login.microsoftonline.com/{your-tenant-id}/oauth2/v2.0/token`
   - Client ID: your `AZURE_CLIENT_ID`
   - Client Secret: your `AZURE_CLIENT_SECRET`
   - Scope: `https://graph.microsoft.com/.default`
7. Save and publish the agent

### Optional: Supervisor / Orchestration Agent

Create a third agent that:
- Has both the `DEX Telemetry Agent` and `Intune Management Agent` as **collaborator agents**
- Uses a system prompt such as:
  > "You coordinate device health remediation. When asked to fix unhealthy devices,
  > first call the DEX Telemetry Agent to identify devices with low health scores,
  > then call the Intune Management Agent to restart each identified device."

---

## Example Conversation Flow

```
User:     "Restart any Windows devices with a DEX score below 50"

Orchestrator → DEX Telemetry Agent:
              "Get all Windows devices with health score below 50"
              ← Returns: [DESKTOP-A (score 42), LAPTOP-B (score 38)]

Orchestrator → Intune Management Agent:
              "Restart DESKTOP-A and LAPTOP-B"
              ← Looks up Intune IDs by device name
              ← Sends rebootNow to each
              ← Reports: "Restart commands sent to 2 devices"

Orchestrator → User:
              "Restart commands have been sent to DESKTOP-A and LAPTOP-B.
               Both had DEX scores below 50. Commands will execute on next check-in."
```

---

## Security Notes

- Never commit `auth/.env` to source control — it is listed in `.gitignore`
- Rotate the Azure client secret before expiry (set a calendar reminder)
- Apply least-privilege: the app registration only needs the two Graph permissions listed above
- The DEX API key should be scoped to read-only operations if your 1E console supports it

---

## References

- [1E DEX documentation](https://help.1e.com/)
- [Microsoft Graph — managedDevices API](https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-manageddevice)
- [Microsoft Graph — rebootNow action](https://learn.microsoft.com/en-us/graph/api/manageddevice-rebootnow)
- [watsonx Orchestrate AI agent builder](https://www.ibm.com/products/watsonx-orchestrate/ai-agent-builder)
