import asyncio
import json
import logging

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


async def _fetch_property_status(client: httpx.AsyncClient, url: str, headers: dict) -> dict | None:
    try:
        res = await client.get(url, headers=headers)
        return res.json() if res.status_code == 200 else None
    except Exception:
        return None


async def fetch_user_context(token: str) -> str:
    """
    Fetches real context data (properties, reservations, roles, tasks)
    from the main Hostay backend API. Property statuses are fetched in parallel.
    """
    if not token:
        return ""

    base = get_settings().hostay_backend_url.rstrip("/")
    url = f"{base}/api/v1/chatbot/context"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.warning("Failed to fetch context from %s — status %s", url, response.status_code)
                return ""

            data = response.json()

            # Fetch all property statuses in parallel instead of sequentially
            if "properties" in data:
                prop_ids = [p.get("id") for p in data["properties"] if p.get("id")]
                if prop_ids:
                    status_urls = [f"{base}/api/v1/chatbot/property/{pid}/status" for pid in prop_ids]
                    statuses = await asyncio.gather(
                        *[_fetch_property_status(client, su, headers) for su in status_urls]
                    )
                    data["property_statuses"] = [s for s in statuses if s is not None]

            return json.dumps(data, ensure_ascii=False)

    except httpx.RequestError as e:
        logger.warning("HTTPX error fetching user context: %s", e)
        return ""
    except Exception as e:
        logger.error("Unexpected error fetching user context: %s", e)
        return ""
