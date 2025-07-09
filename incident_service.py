import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Set

from dotenv import load_dotenv
from resilient import SimpleClient

# ——— Load configuration from .env ———
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

def _load_config() -> Dict[str, Any]:
    base_url       = os.getenv("SOAR_BASE_URL")
    org_name       = os.getenv("SOAR_ORG")
    api_key_id     = os.getenv("SOAR_API_KEY_ID")
    api_key_secret = os.getenv("SOAR_API_KEY_SECRET")
    verify_env     = os.getenv("SOAR_VERIFY", "True")

    missing = [n for n,v in [
        ("SOAR_BASE_URL",       base_url),
        ("SOAR_ORG",            org_name),
        ("SOAR_API_KEY_ID",     api_key_id),
        ("SOAR_API_KEY_SECRET", api_key_secret)
    ] if not v]
    if missing:
        raise RuntimeError(f"Missing required config: {', '.join(missing)}")

    if verify_env.lower() in ("false","0","no"):
        verify = False
    else:
        verify = verify_env

    return {
        "base_url":       base_url,
        "org_name":       org_name,
        "api_key_id":     api_key_id,
        "api_key_secret": api_key_secret,
        "verify":         verify
    }

# ——— Initialize SOAR client once ———
_cfg = _load_config()
_client = SimpleClient(
    base_url   = _cfg["base_url"],
    org_name   = _cfg["org_name"],
    verify     = _cfg["verify"]
)
_client.set_api_key(
    api_key_id     = _cfg["api_key_id"],
    api_key_secret = _cfg["api_key_secret"]
)

# optional: configure module‐level logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

def get_incident_details(incident_number: int) -> Dict[str, Any]:
    """
    Retrieve a SOAR incident with:
      1) Full incident JSON (all fields)
      2) Ensured 'description' and 'additional_information'
      3) Embedded list of this incident's artifacts
      4) Related incidents (sharing any artifact value), with minimal details

    :param incident_number: ID of the incident to fetch
    :return: A dict containing all the above data
    :raises RuntimeError on any failure
    """
    client = _client

    # 1) Fetch full incident
    try:
        resp = client.get(f"/incidents/{incident_number}?return_level=full")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch incident {incident_number}: {e}")
    data = resp.get("data", resp)

    # 2) Ensure required fields exist
    data.setdefault("description", "")
    ai = data.get("properties", {}).get("additional_information")
    data["additional_information"] = ai or ""

    # 3) Fetch all artifacts for this incident
    try:
        art_resp = client.post(
            f"/incidents/{incident_number}/artifacts/query_paged",
            {"from": 0, "size": 200}
        )
        artifacts = art_resp.get("data", [])
    except Exception as e:
        raise RuntimeError(f"Failed to fetch artifacts for {incident_number}: {e}")
    data["artifacts"] = artifacts

    # 4) Correlate artifacts to find related incidents
    related_ids: Set[int] = set()
    for art in artifacts:
        val = art.get("value")
        if not val:
            continue
        try:
            cross = client.post(
                "/artifacts/query_paged",
                {"filters":[{"field_name":"value","method":"equals","value":val}],
                 "from":0,"size":100}
            )
        except Exception:
            continue
        for a in cross.get("data", []):
            rid = a.get("incident_id")
            if rid and rid != incident_number:
                related_ids.add(rid)

    # Fetch minimal details of each related incident
    related: List[Dict[str, Any]] = []
    for rid in sorted(related_ids):
        try:
            r = client.get(f"/incidents/{rid}?return_level=minimal").get("data", {})
            related.append(r)
        except Exception:
            continue
    data["related_incidents"] = related

    return data
