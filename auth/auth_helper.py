"""
auth_helper.py
==============
Helper utilities for obtaining authentication tokens/headers for:
  - 1E DEX API  (API Key)
  - Microsoft Graph API / Intune  (OAuth 2.0 Client Credentials)

Usage:
  from auth_helper import get_dex_headers, get_graph_token

These helpers are intended for use when testing the OpenAPI specs locally
or when building a custom tool wrapper for watsonx Orchestrate.
"""

import os
import time
import requests

# ---------------------------------------------------------------------------
# 1E DEX — API Key authentication
# ---------------------------------------------------------------------------

def get_dex_headers() -> dict:
    """
    Returns the HTTP headers required to authenticate with the 1E DEX API.

    Environment variables required:
      DEX_API_KEY    — API key generated from the 1E console (Settings > API Keys)
      DEX_TENANT     — Your 1E tenant subdomain (e.g. 'contoso' for contoso.1e.com)

    Returns:
        dict: Headers dict ready to pass to requests.get/post
    """
    api_key = os.environ.get("DEX_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "DEX_API_KEY environment variable is not set. "
            "Generate an API key from the 1E console under Settings > API Keys."
        )
    return {
        "X-API-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def get_dex_base_url() -> str:
    """Returns the base URL for the 1E DEX API using the configured tenant."""
    tenant = os.environ.get("DEX_TENANT")
    if not tenant:
        raise EnvironmentError(
            "DEX_TENANT environment variable is not set. "
            "Set it to your 1E tenant subdomain (e.g. 'contoso')."
        )
    return f"https://{tenant}.1e.com/api/v1"


# ---------------------------------------------------------------------------
# Microsoft Graph API / Intune — OAuth 2.0 Client Credentials
# ---------------------------------------------------------------------------

# Simple in-memory token cache to avoid fetching a new token on every call
_graph_token_cache: dict = {"token": None, "expires_at": 0}


def get_graph_token() -> str:
    """
    Obtains an OAuth 2.0 access token for the Microsoft Graph API using
    the client credentials flow (app-only, no user sign-in required).

    Environment variables required:
      AZURE_TENANT_ID       — Your Entra ID (Azure AD) tenant ID (GUID)
      AZURE_CLIENT_ID       — App registration client ID (GUID)
      AZURE_CLIENT_SECRET   — App registration client secret

    Required app permissions (granted with admin consent in Entra ID):
      - DeviceManagementManagedDevices.Read.All
      - DeviceManagementManagedDevices.PrivilegedOperations.All

    Returns:
        str: Bearer token string (without 'Bearer ' prefix)
    """
    now = time.time()

    # Return cached token if still valid (with 60-second buffer)
    if _graph_token_cache["token"] and now < _graph_token_cache["expires_at"] - 60:
        return _graph_token_cache["token"]

    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")

    missing = [k for k, v in {
        "AZURE_TENANT_ID": tenant_id,
        "AZURE_CLIENT_ID": client_id,
        "AZURE_CLIENT_SECRET": client_secret,
    }.items() if not v]

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Register an app in Microsoft Entra ID and set these variables."
        )

    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }

    response = requests.post(token_url, data=payload, timeout=15)
    response.raise_for_status()
    data = response.json()

    token = data["access_token"]
    expires_in = data.get("expires_in", 3600)

    _graph_token_cache["token"] = token
    _graph_token_cache["expires_at"] = now + expires_in

    return token


def get_graph_headers() -> dict:
    """
    Returns the HTTP headers required to authenticate with the Microsoft Graph API.

    Returns:
        dict: Headers dict ready to pass to requests.get/post
    """
    return {
        "Authorization": f"Bearer {get_graph_token()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Quick connectivity smoke tests
# ---------------------------------------------------------------------------

def test_dex_connection():
    """Verifies the DEX API key is valid by listing the first device."""
    url = f"{get_dex_base_url()}/devices?limit=1"
    response = requests.get(url, headers=get_dex_headers(), timeout=10)
    if response.status_code == 200:
        print("✅ 1E DEX connection successful")
    else:
        print(f"❌ 1E DEX connection failed: {response.status_code} — {response.text}")


def test_graph_connection():
    """Verifies the Graph token is valid by listing the first managed device."""
    url = "https://graph.microsoft.com/v1.0/deviceManagement/managedDevices?$top=1"
    response = requests.get(url, headers=get_graph_headers(), timeout=10)
    if response.status_code == 200:
        print("✅ Microsoft Graph / Intune connection successful")
    else:
        print(f"❌ Microsoft Graph connection failed: {response.status_code} — {response.text}")


if __name__ == "__main__":
    print("Running connectivity tests...\n")
    test_dex_connection()
    test_graph_connection()
