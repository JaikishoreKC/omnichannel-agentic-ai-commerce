from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import require_admin
from app.container import admin_service, inventory_service, product_service
from app.models.schemas import InventoryUpdateRequest, ProductWriteRequest

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def stats(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return admin_service.stats()


@router.get("/categories")
def categories(_: dict[str, object] = Depends(require_admin)) -> dict[str, object]:
    return product_service.list_categories()


@router.post("/products", status_code=201)
def create_product(
    payload: ProductWriteRequest,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    product = product_service.create_product(payload.model_dump())
    return {"product": product}


@router.put("/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductWriteRequest,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    product = product_service.update_product(product_id=product_id, patch=payload.model_dump())
    return {"product": product}


@router.delete("/products/{product_id}", status_code=204, response_class=Response)
def delete_product(product_id: str, _: dict[str, object] = Depends(require_admin)) -> Response:
    product_service.delete_product(product_id=product_id)
    return Response(status_code=204)


@router.get("/inventory/{variant_id}")
def get_inventory(
    variant_id: str,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    return {"inventory": inventory_service.get_variant_inventory(variant_id=variant_id)}


@router.put("/inventory/{variant_id}")
def update_inventory(
    variant_id: str,
    payload: InventoryUpdateRequest,
    _: dict[str, object] = Depends(require_admin),
) -> dict[str, object]:
    if payload.totalQuantity is None and payload.availableQuantity is None:
        raise HTTPException(status_code=400, detail="Provide at least one inventory field")
    inventory = inventory_service.update_variant_inventory(
        variant_id=variant_id,
        total_quantity=payload.totalQuantity,
        available_quantity=payload.availableQuantity,
    )
    return {"inventory": inventory}
