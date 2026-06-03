"""
Keycloak-style federated identity (simulated).

A deliberately tiny API-key check standing in for cross-cloud SSO + Trino ACLs.
Two demo identities are provided. The backend uses this to gate write-ish
actions like access requests, demonstrating the governance/IAM layer without a
full OIDC server.
"""

# api_key -> identity profile (role drives access level)
USERS = {
    "analyst-key": {"user": "ana.analyst@company.com", "role": "analyst"},
    "admin-key": {"user": "platform.admin@company.com", "role": "admin"},
}


def authenticate(api_key: str):
    """Return the identity for an API key, or None if unknown."""
    return USERS.get(api_key)
