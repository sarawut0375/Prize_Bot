"""
Shopee Affiliate Open API (Thailand) - Shopee's OFFICIAL API for affiliates.
This is permitted access with your own keys, unlike scraping the website.

How to get keys:
  1. Join the Shopee Affiliate Program: https://affiliate.shopee.co.th
  2. Once approved, request "Open API" access in the affiliate dashboard.
  3. Copy the AppID and Secret into the /manage page.

Request signing (per Shopee's affiliate API docs):
  Authorization: SHA256 Credential={AppID}, Timestamp={unix}, Signature={sig}
  sig = sha256(AppID + Timestamp + <exact request body> + Secret)

NOTE: written against Shopee's published GraphQL schema (productOfferV2) but
not yet tested against the live API (no keys available while building).
The "ทดสอบการเชื่อมต่อ" button on /manage shows Shopee's raw error message
if a field name or the endpoint needs adjusting.
"""
import hashlib
import json
import time
from dataclasses import dataclass

import requests

ENDPOINT = "https://open-api.affiliate.shopee.co.th/graphql"


class ShopeeApiError(Exception):
    pass


@dataclass
class ApiItem:
    title: str
    price: float
    url: str | None
    seller: str | None
    image_url: str | None


def search(keyword: str, app_id: str, secret: str, limit: int = 10) -> list[ApiItem]:
    if not app_id or not secret:
        raise ShopeeApiError("ยังไม่ได้ใส่ AppID / Secret ของ Shopee Affiliate")

    limit = max(1, min(int(limit), 50))
    query = (
        "query{productOfferV2(keyword:%s,limit:%d,page:1){"
        "nodes{itemId productName priceMin priceMax shopName productLink offerLink "
        "imageUrl}}}" % (json.dumps(keyword), limit)
    )
    body = json.dumps({"query": query}, separators=(",", ":"))
    timestamp = str(int(time.time()))
    signature = hashlib.sha256(f"{app_id}{timestamp}{body}{secret}".encode()).hexdigest()

    try:
        resp = requests.post(
            ENDPOINT,
            data=body.encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"SHA256 Credential={app_id}, Timestamp={timestamp}, Signature={signature}",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ShopeeApiError(f"เชื่อมต่อ Shopee API ไม่ได้: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise ShopeeApiError(f"Shopee API ตอบกลับไม่ใช่ JSON (HTTP {resp.status_code}): {resp.text[:300]}") from exc

    if data.get("errors"):
        messages = "; ".join(str(e.get("message", e)) for e in data["errors"])
        raise ShopeeApiError(f"Shopee API error: {messages}")
    if resp.status_code != 200:
        raise ShopeeApiError(f"Shopee API HTTP {resp.status_code}: {resp.text[:300]}")

    nodes = (((data.get("data") or {}).get("productOfferV2") or {}).get("nodes")) or []
    items: list[ApiItem] = []
    for n in nodes:
        try:
            price = float(n.get("priceMin") or n.get("priceMax"))
        except (TypeError, ValueError):
            continue
        items.append(
            ApiItem(
                title=n.get("productName") or "",
                price=price,
                url=n.get("productLink") or n.get("offerLink"),
                seller=n.get("shopName"),
                image_url=n.get("imageUrl"),
            )
        )
    return items
