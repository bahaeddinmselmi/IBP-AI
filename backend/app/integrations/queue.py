import json
from typing import Any, Dict

from kafka import KafkaProducer


class KafkaEventBus:
    def __init__(self, bootstrap_servers: str = "localhost:9092") -> None:
        self.producer = KafkaProducer(bootstrap_servers=bootstrap_servers)

    def publish(self, topic: str, event: Dict[str, Any]) -> None:
        payload = json.dumps(event).encode("utf-8")
        self.producer.send(topic, payload)
