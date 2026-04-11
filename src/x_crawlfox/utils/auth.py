import json
from pathlib import Path
from loguru import logger
from typing import List, Dict, Any, Union

def is_cookie_editor_format(data: Union[List, Dict]) -> bool:
    """
    识别是否为 Cookie-Editor 导出的 JSON 格式。
    特征：是一个列表，且元素包含 'expirationDate' 字段。
    """
    if isinstance(data, list) and len(data) > 0:
        # 检查第一个元素是否有 Cookie-Editor 特有的字段
        first = data[0]
        return isinstance(first, dict) and "expirationDate" in first
    return False

def convert_to_playwright_format(cookies_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    将 Cookie-Editor 格式转换为 Playwright (Storage State) 格式。
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
        
        # 字段映射: expirationDate -> expires
        if "expirationDate" in c:
            cookie["expires"] = c["expirationDate"]
            
        # SameSite 映射
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
    确保文件是 Playwright 格式。如果是 Cookie-Editor 格式，则自动转换并覆盖。
    """
    if not file_path.exists():
        return file_path

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if is_cookie_editor_format(data):
            logger.info(f"Detected {file_path.name} in Cookie-Editor format, converting automatically...")
            converted_data = convert_to_playwright_format(data)
            
            # 自动备份并覆盖
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(converted_data, f, indent=4)
            logger.success(f"Conversion successful! Updated {file_path}")
        elif isinstance(data, dict) and "cookies" in data:
            # 已经是 Playwright 格式
            pass
        else:
            logger.warning(f"Unknown format for file {file_path.name}, which may cause browser loading failure.")
            
    except Exception as e:
        logger.error(f"Failed to parse auth file: {e}")
    
    return file_path
