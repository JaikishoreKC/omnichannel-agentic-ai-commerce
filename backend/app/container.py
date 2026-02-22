from __future__ import annotations

from app.core.config import Settings
from app.services.admin_service import AdminService
from app.services.auth_service import AuthService
from app.services.cart_service import CartService
from app.services.memory_service import MemoryService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.session_service import SessionService
from app.store.in_memory import InMemoryStore

settings = Settings.from_env()
store = InMemoryStore()

auth_service = AuthService(store=store, settings=settings)
product_service = ProductService(store=store)
session_service = SessionService(store=store)
cart_service = CartService(store=store, settings=settings)
order_service = OrderService(store=store, cart_service=cart_service)
memory_service = MemoryService(store=store)
admin_service = AdminService(store=store)

