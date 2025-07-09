from incident_service import get_incident_details  # assuming you saved it as incident_service.py
import json

incident_id = 12345
details = get_incident_details(incident_id)
print(json.dumps(details, indent=2))
