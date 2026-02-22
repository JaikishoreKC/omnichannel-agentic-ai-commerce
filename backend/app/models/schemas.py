from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=12)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


class AuthUser(BaseModel):
    id: str
    email: str
    name: str
    role: str
    createdAt: str


class AuthResponse(BaseModel):
    user: AuthUser
    accessToken: str
    refreshToken: str
    expiresIn: int


class ProductListQuery(BaseModel):
    query: str | None = None
    category: str | None = None
    minPrice: float | None = None
    maxPrice: float | None = None
    page: int = 1
    limit: int = 20


class AddCartItemRequest(BaseModel):
    productId: str
    variantId: str
    quantity: int = Field(ge=1, le=50)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(ge=1, le=50)


class ApplyDiscountRequest(BaseModel):
    code: str


class ShippingAddress(BaseModel):
    name: str
    line1: str
    city: str
    state: str
    postalCode: str
    country: str
    line2: str | None = None


class PaymentMethod(BaseModel):
    type: str
    token: str


class CreateOrderRequest(BaseModel):
    shippingAddress: ShippingAddress
    paymentMethod: PaymentMethod


class CancelOrderRequest(BaseModel):
    reason: str | None = None


class CreateSessionRequest(BaseModel):
    channel: str = "web"
    initialContext: dict[str, Any] = Field(default_factory=dict)


class UpdatePreferencesRequest(BaseModel):
    size: str | None = None
    brandPreferences: list[str] | None = None
    categories: list[str] | None = None
    priceRange: dict[str, float] | None = None


class InteractionMessageRequest(BaseModel):
    sessionId: str
    content: str = Field(min_length=1, max_length=2000)
    channel: str = "web"


class ProductVariantWrite(BaseModel):
    id: str
    size: str
    color: str
    inStock: bool = True
    inventory: dict[str, int] | None = None


class ProductWriteRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    category: str
    price: float = Field(gt=0)
    currency: str = "USD"
    images: list[str] = Field(default_factory=list)
    variants: list[ProductVariantWrite] = Field(default_factory=list)
    rating: float = 0
    reviewCount: int = 0


class InventoryUpdateRequest(BaseModel):
    totalQuantity: int | None = Field(default=None, ge=0)
    availableQuantity: int | None = Field(default=None, ge=0)
