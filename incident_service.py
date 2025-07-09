iimport os
import logging
from pathlib import Path
from typing import Dict, Any, List, Set

from dotenv import load_dotenv
from resilient import SimpleClient

# ——— Load .env and configure logging ———
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

# ——— Build the SOAR client once ———
_base_url   = os.getenv("SOAR_BASE_URL")
_org_name   = os.getenv("SOAR_ORG")
_api_id     = os.getenv("SOAR_API_KEY_ID")
_api_secret = os.getenv("SOAR_API_KEY_SECRET")
_verify_env = os.getenv("SOAR_VERIFY", "True")
_verify = False if _verify_env.lower() in ("false","0","no") else _verify_env

_client = SimpleClient(
    base_url = _base_url,
    org_name = _org_name,
    verify   = _verify
)
_client.set_api_key(api_key_id=_api_id, api_key_secret=_api_secret)


def get_incident_details(incident_number: int) -> Dict[str, Any]:
    """
    1) Fetch full incident JSON (all fields).
    2) Ensure description & additional_information exist.
    3) Fetch all artifacts via GET /incidents/{id}/artifacts.
    4) Correlate each artifact value across all incidents via
       POST /artifacts/query_paged (using start/size).
    5) Fetch minimal info for each related incident.
    """
    client = _client

    # 1) Full incident
    logging.info("Fetching incident %s (full)", incident_number)
    resp = client.get(f"/incidents/{incident_number}?return_level=full")
    data = resp.get("data", resp)

    # 2) Ensure key fields
    data.setdefault("description", "")
    ai = data.get("properties", {}).get("additional_information")
    data["additional_information"] = ai or ""

    # 3) Fetch this incident’s artifacts
    logging.info("Listing artifacts for %s", incident_number)
    art_resp = client.get(f"/incidents/{incident_number}/artifacts")
    artifacts = art_resp.get("data", [])
    data["artifacts"] = artifacts

    # 4) Correlate by artifact value
    related_ids: Set[int] = set()
    for art in artifacts:
        val = art.get("value")
        if not val:
            continue

        query = {
            "filters": [{"field_name":"value", "method":"equals", "value":val}],
            "start":   0,
            "size":    100
        }
        cross = client.post("/artifacts/query_paged", query)
        for hit in cross.get("data", []):
            rid = hit.get("incident_id")
            if rid and rid != incident_number:
                related_ids.add(rid)

    # 5) Fetch minimal details for related incidents
    related: List[Dict[str,Any]] = []
    for rid in sorted(related_ids):
        logging.info("Fetching related incident %s (minimal)", rid)
        r = client.get(f"/incidents/{rid}?return_level=minimal").get("data", {})
        related.append(r)

    data["related_incidents"] = related
    return data
