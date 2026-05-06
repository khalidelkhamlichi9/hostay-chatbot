import os
import httpx
import logging
from cache import cache

logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("HOSTAY_BACKEND_URL", "http://localhost:8000")

async def fetch_user_context(token: str) -> str:
    """
    Fetches real context data (properties, reservations, roles, tasks) 
    from the main Hostay backend API.
    """
    if not token:
        return ""
        
    cache_key = f"user_context_{token[-10:]}" # Use last 10 chars of token as part of key
    cached_data = await cache.get(cache_key)
    if cached_data:
        logger.info(f"💾 Returning cached context for {cache_key}")
        return cached_data

    url = f"{BACKEND_URL}/api/v1/chatbot/context"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Automatically fetch status for all properties
                if "properties" in data:
                    data["property_statuses"] = []
                    for prop in data["properties"]:
                        prop_id = prop.get("id")
                        if prop_id:
                            status_url = f"{BACKEND_URL}/api/v1/chatbot/property/{prop_id}/status"
                            status_res = await client.get(status_url, headers=headers)
                            if status_res.status_code == 200:
                                data["property_statuses"].append(status_res.json())

                import json
                result_str = json.dumps(data, ensure_ascii=False)
                # Cache for 10 minutes
                await cache.set(cache_key, result_str, expire=600)
                return result_str
            else:
                logger.warning(f"⚠️ Failed to fetch context from {url} - Status: {response.status_code}")
                return ""
                
    except httpx.RequestError as e:
        logger.warning(f"⚠️ HTTPX Request Error while fetching context: {e}")
        return ""
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching real context: {e}")
        return ""
