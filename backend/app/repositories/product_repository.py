from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.infrastructure.persistence_clients import MongoClientManager, RedisClientManager
from app.store.in_memory import InMemoryStore


class ProductRepository:
    def __init__(
        self,
        *,
        store: InMemoryStore,
        mongo_manager: MongoClientManager,
        redis_manager: RedisClientManager,
    ) -> None:
        self.store = store
        self.mongo_manager = mongo_manager
        self.redis_manager = redis_manager

    def list_all(self) -> list[dict[str, Any]]:
        with self.store.lock:
            cached = [deepcopy(product) for product in self.store.products_by_id.values()]
        if cached:
            return cached

        collection = self._mongo_collection()
        if collection is None:
            return []
        rows = list(collection.find({}).sort("name", 1))
        products: list[dict[str, Any]] = []
        for row in rows:
            row.pop("_id", None)
            row.pop("productId", None)
            if isinstance(row, dict):
                products.append(row)
                with self.store.lock:
                    self.store.products_by_id[row["id"]] = deepcopy(row)
                self._write_to_redis(row)
        return [deepcopy(product) for product in products]

    def get(self, product_id: str) -> dict[str, Any] | None:
        with self.store.lock:
            product = self.store.products_by_id.get(product_id)
            if product is not None:
                return deepcopy(product)

        cached = self._read_from_redis(product_id)
        if cached is not None:
            with self.store.lock:
                self.store.products_by_id[product_id] = deepcopy(cached)
            return deepcopy(cached)

        collection = self._mongo_collection()
        if collection is None:
            return None
        payload = collection.find_one({"productId": product_id})
        if not payload:
            return None
        payload.pop("_id", None)
        payload.pop("productId", None)
        if not isinstance(payload, dict):
            return None
        with self.store.lock:
            self.store.products_by_id[product_id] = deepcopy(payload)
        self._write_to_redis(payload)
        return deepcopy(payload)

    def create(self, product: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.products_by_id[product["id"]] = deepcopy(product)
        self._write_to_redis(product)
        self._write_to_mongo(product)
        return deepcopy(product)

    def update(self, product: dict[str, Any]) -> dict[str, Any]:
        with self.store.lock:
            self.store.products_by_id[product["id"]] = deepcopy(product)
        self._write_to_redis(product)
        self._write_to_mongo(product)
        return deepcopy(product)

    def delete(self, product_id: str) -> None:
        with self.store.lock:
            self.store.products_by_id.pop(product_id, None)
        self._delete_from_redis(product_id)
        self._delete_from_mongo(product_id)

    def list_categories(self) -> list[str]:
        products = self.list_all()
        categories = sorted({str(product.get("category", "")).strip() for product in products if product.get("category")})
        return categories

    def set_variant_stock_flag(self, *, variant_id: str, in_stock: bool) -> None:
        target: dict[str, Any] | None = None
        with self.store.lock:
            for product in self.store.products_by_id.values():
                variants = product.get("variants", [])
                if not isinstance(variants, list):
                    continue
                for variant in variants:
                    if not isinstance(variant, dict):
                        continue
                    if str(variant.get("id", "")) == variant_id:
                        variant["inStock"] = in_stock
                        target = deepcopy(product)
                        break
                if target is not None:
                    break
        if target is not None:
            self._write_to_redis(target)
            self._write_to_mongo(target)

    def name_map(self) -> dict[str, str]:
        products = self.list_all()
        return {str(product["id"]): str(product.get("name", "Unknown")) for product in products if product.get("id")}

    def _redis_client(self) -> Any | None:
        return self.redis_manager.client

    def _mongo_collection(self) -> Any | None:
        client = self.mongo_manager.client
        if client is None:
            return None
        database = client.get_default_database()
        if database is None:
            database = client["commerce"]
        return database["products"]

    def _redis_key(self, product_id: str) -> str:
        return f"product:{product_id}"

    def _write_to_redis(self, product: dict[str, Any]) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.set(self._redis_key(str(product["id"])), json.dumps(product), ex=60 * 60)

    def _read_from_redis(self, product_id: str) -> dict[str, Any] | None:
        client = self._redis_client()
        if client is None:
            return None
        payload = client.get(self._redis_key(product_id))
        if not payload:
            return None
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    def _delete_from_redis(self, product_id: str) -> None:
        client = self._redis_client()
        if client is None:
            return
        client.delete(self._redis_key(product_id))

    def _write_to_mongo(self, product: dict[str, Any]) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.update_one(
            {"productId": product["id"]},
            {"$set": {"productId": product["id"], **deepcopy(product)}},
            upsert=True,
        )

    def _delete_from_mongo(self, product_id: str) -> None:
        collection = self._mongo_collection()
        if collection is None:
            return
        collection.delete_one({"productId": product_id})
