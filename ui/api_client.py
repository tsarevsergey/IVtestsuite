import requests
from typing import Dict, Any, Optional

BACKEND_URL = "http://localhost:5000"

def req(method: str, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Make an HTTP request to the backend.
    """
    url = f"{BACKEND_URL}{path}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=json_data, timeout=10)
        else:
            return {"success": False, "message": f"Unsupported method: {method}"}
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": str(e)}
