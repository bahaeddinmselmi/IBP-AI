from typing import Any, Dict, List


class OdooConnector:
    def __init__(self, url: str, db: str, username: str, password: str) -> None:
        self.url = url
        self.db = db
        self.username = username
        self.password = password

    def fetch_sales_orders(self) -> List[Dict[str, Any]]:
        return []


class SAPConnector:
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    def fetch_sales_orders(self) -> List[Dict[str, Any]]:
        return []
