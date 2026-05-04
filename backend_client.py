import os
import httpx
import logging

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("HOSTAY_BACKEND_URL", "http://localhost:8000")

async def fetch_user_context(token: str) -> str:
    """
    Fetches real context data (properties, reservations, roles, tasks) 
    from the main Hostay backend API.
    """
    if not token:
        return ""
        
    url = f"{BACKEND_URL}/api/v1/chatbot/context"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                import json
                return json.dumps(data, ensure_ascii=False)
            else:
                logger.warning(f"⚠️ Failed to fetch context from {url} - Status: {response.status_code}")
                return ""
                
    except httpx.RequestError as e:
        logger.warning(f"⚠️ HTTPX Request Error while fetching context: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching real context: {e}")
        return ""
