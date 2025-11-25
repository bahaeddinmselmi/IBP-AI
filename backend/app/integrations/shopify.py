from typing import Any, Dict, List


class ShopifyClient:
    def __init__(self, api_key: str, password: str, shop_name: str) -> None:
        self.api_key = api_key
        self.password = password
        self.shop_name = shop_name

    def fetch_orders(self) -> List[Dict[str, Any]]:
        return []
