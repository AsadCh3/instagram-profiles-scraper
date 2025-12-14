import asyncio
from typing import Any, Dict, List, Optional

import httpx
from apify import Actor

BASE_HEADERS = {
    "x-ig-app-id": "936619743392459",
}

SOCK_CONNECT_TIMEOUT = 4
SOCK_READ_TIMEOUT = 8
TOTAL_TIMEOUT = 15

HTTPX_TIMEOUT = httpx.Timeout(
    timeout=TOTAL_TIMEOUT,
    connect=SOCK_CONNECT_TIMEOUT,
    read=SOCK_READ_TIMEOUT,
)


async def fetch_profile(
    username: str,
    headers: Dict[str, str],
    timeout: httpx.Timeout,
    proxy_config: Optional[Any],
) -> Dict[str, Any]:
    """Fetch profile details for a single username (similar to /userdetails)."""
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    proxy_url = proxy_config.new_url() if proxy_config else None

    async with httpx.AsyncClient(proxy=proxy_url, timeout=timeout) as client:
        try:
            resp = await client.get(url=url, headers=headers, cookies={})
        except httpx.ConnectTimeout:
            return {"username": username, "error": "Proxy connect timeout", "proxy": proxy_url}
        except httpx.ConnectError:
            return {"username": username, "error": "Proxy connect error", "proxy": proxy_url}
        except httpx.WriteTimeout:
            return {"username": username, "error": "Proxy write timeout", "proxy": proxy_url}
        except httpx.ReadTimeout:
            return {"username": username, "error": "Proxy read timeout", "proxy": proxy_url}
        except Exception as exc:
            return {"username": username, "error": str(exc), "proxy": proxy_url}

    if resp.status_code == 401:
        return {"username": username, "error": "Unauthorized error", "status_code": 401, "proxy": proxy_url}

    if resp.status_code != 200:
        return {
            "username": username,
            "error": f"Failed to fetch user details: {resp.status_code}",
            "status_code": resp.status_code,
            "proxy": proxy_url,
        }

    try:
        data = resp.json()
    except Exception as exc:
        return {"username": username, "error": f"Invalid JSON: {exc}", "proxy": proxy_url}

    if data.get("error"):
        return {
            "username": username,
            "error": f"Failed to fetch user details: {data['error']}",
            "status_code": data.get("status_code", 500),
            "proxy": proxy_url,
        }

    user = data.get("data", {}).get("user", {}) if isinstance(data, dict) else {}
    return {
        "username": username,
        "user_id": user.get("id"),
        "followers_count": user.get("edge_followed_by", {}).get("count"),
        "following_count": user.get("edge_follow", {}).get("count"),
        "full_name": user.get("full_name"),
        "is_private": user.get("is_private"),
        "is_verified": user.get("is_verified"),
        "profile_pic_url": user.get("profile_pic_url_hd") or user.get("profile_pic_url"),
        "raw": data,
        "status": "ok",
        "proxy": proxy_url,
    }


async def run_scrape(
    usernames: List[str],
    headers: Dict[str, str],
    timeout: httpx.Timeout,
    proxy_config: Optional[Any],
    max_concurrency: int = 10,
) -> Dict[str, Any]:
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def wrapped(u: str):
        async with sem:
            return await fetch_profile(u, headers=headers, timeout=timeout, proxy_config=proxy_config)

    tasks = [wrapped(u) for u in usernames]
    results = await asyncio.gather(*tasks)
    return {"results": results}


async def main():
    async with Actor() as actor:
        actor.log.info("Starting Instagram profiles scraper (Apify actor mode)")
        input_payload = await actor.get_input() or {}

        raw_usernames = input_payload.get("usernames") or []
        print(raw_usernames)
        usernames = [u.strip() for u in raw_usernames if isinstance(u, str) and u.strip()]
        if not usernames:
            await actor.set_value("OUTPUT", {"error": "usernames list is required"})
            actor.log.error("No usernames provided in input.")
            return

        headers = dict(BASE_HEADERS)
        proxy_config = actor.config.get("proxyConfiguration")
        max_concurrency = 10

        results = await run_scrape(
            usernames=usernames,
            headers=headers,
            timeout=HTTPX_TIMEOUT,
            proxy_config=proxy_config,
            max_concurrency=max_concurrency,
        )

        await actor.set_value("OUTPUT", results)
        actor.log.info("Scraping completed", extra={"count": len(usernames)})


if __name__ == "__main__":
    asyncio.run(main())
