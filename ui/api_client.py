import requests
from typing import Dict, Any, Optional

BACKEND_URL = "http://localhost:5000"

def req(method: str, path: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Dict[str, Any]:
    """
    Make an HTTP request to the backend.
    
    Args:
        method: HTTP method (GET, POST)
        path: API endpoint path
        json_data: JSON body for POST requests
        params: Query parameters for GET requests
        timeout: Request timeout in seconds (default 10, use higher for long operations)
    """
    url = f"{BACKEND_URL}{path}"
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=timeout)
        elif method.upper() == "POST":
            response = requests.post(url, json=json_data, timeout=timeout)
        else:
            return {"success": False, "message": f"Unsupported method: {method}"}
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": str(e)}
