import json
from pathlib import Path
from loguru import logger
from typing import List, Dict, Any, Union

def is_cookie_editor_format(data: Union[List, Dict]) -> bool:
    """
    Identify if the JSON format is exported from Cookie-Editor.
    Characteristics: It is a list, and elements contain an 'expirationDate' field.
    """
    if isinstance(data, list) and len(data) > 0:
        # Check if the first element has Cookie-Editor specific fields
        first = data[0]
        return isinstance(first, dict) and "expirationDate" in first
    return False

def convert_to_playwright_format(cookies_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convert Cookie-Editor format to Playwright (Storage State) format.
    """
    new_cookies = []
    for c in cookies_list:
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c["path"],
            "httpOnly": c.get("httpOnly", False),
            "secure": c.get("secure", False),
        }
        
        # Field mapping: expirationDate -> expires
        if "expirationDate" in c:
            cookie["expires"] = c["expirationDate"]
            
        # SameSite mapping
        same_site = str(c.get("sameSite", "Lax")).lower()
        if same_site == "no_restriction":
            cookie["sameSite"] = "None"
        elif same_site in ["lax", "strict"]:
            cookie["sameSite"] = same_site.capitalize()
        else:
            cookie["sameSite"] = "Lax"
            
        new_cookies.append(cookie)

    return {
        "cookies": new_cookies,
        "origins": []
    }

def ensure_storage_state(file_path: Path) -> Path:
    """
    Ensure the file is in Playwright format. If it is Cookie-Editor format, convert and overwrite automatically.
    """
    if not file_path.exists():
        return file_path

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if is_cookie_editor_format(data):
            logger.info(f"Detected {file_path.name} in Cookie-Editor format, converting automatically...")
            converted_data = convert_to_playwright_format(data)
            
            # Automatically backup and overwrite
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(converted_data, f, indent=4)
            logger.success(f"Conversion successful! Updated {file_path}")
        elif isinstance(data, dict) and "cookies" in data:
            # Already in Playwright format
            pass
        else:
            logger.warning(f"Unknown format for file {file_path.name}, which may cause browser loading failure.")
            
    except Exception as e:
        logger.error(f"Failed to parse auth file: {e}")
    
    return file_path
