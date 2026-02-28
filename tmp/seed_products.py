import os
import random
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def seed_products():
    # Load env from backend/.env if possible
    backend_env = "d:/Projects/omnichannel-agentic-commerce/backend/.env"
    if os.path.exists(backend_env):
        load_dotenv(backend_env)
    
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/commerce")
    client = MongoClient(mongo_uri)
    db = client.get_default_database()
    if db is None:
        db = client["commerce"]

    product_col = db["products"]
    inventory_col = db["inventory"]
    category_col = db["categories"]

    categories = ["shoes", "clothing", "accessories", "electronics", "home"]
    subcategories = {
        "shoes": ["running", "trail", "casual", "formal"],
        "clothing": ["tops", "bottoms", "outerwear", "activewear"],
        "accessories": ["bags", "watches", "jewelry", "hats"],
        "electronics": ["audio", "wearables", "office", "photography"],
        "home": ["kitchen", "decor", "bedding", "lighting"]
    }
    brands = ["StrideForge", "PeakRoute", "AeroThread", "CarryWorks", "LuminaHome", "TechPulse", "ZenithGear"]
    colors = ["black", "white", "navy", "charcoal", "forest", "crimson", "ocean"]
    sizes_clothing = ["S", "M", "L", "XL", "XXL"]
    sizes_shoes = ["8", "9", "10", "11", "12"]

    existing_count = product_col.count_documents({})
    target_total = 100
    to_create = target_total - existing_count

    print(f"Current products in DB: {existing_count}. Goal: {target_total}.")

    if to_create <= 0:
        print("Target reached.")
        client.close()
        return

    added = 0
    for i in range(to_create):
        # Generate a truly unique ID to avoid any overlaps
        p_id = f"prod_ext_{uuid.uuid4().hex[:12]}"
        cat = random.choice(categories)
        subcat = random.choice(subcategories[cat])
        brand = random.choice(brands)
        name = f"{brand} {subcat.title()} {random.choice(['Pro', 'Max', 'Ultra', 'Elite', 'Basic', 'X'])}"
        price = round(random.uniform(15.0, 499.0), 2)
        
        # Variants
        variants = []
        num_variants = random.randint(1, 3)
        for j in range(num_variants):
            v_id = f"var_ext_{uuid.uuid4().hex[:12]}"
            color = random.choice(colors)
            size = random.choice(sizes_shoes if cat == "shoes" else sizes_clothing if cat == "clothing" else ["one-size"])
            variants.append({
                "id": v_id,
                "size": size,
                "color": color,
                "inStock": True
            })

            # Inventory
            qty = random.randint(50, 500)
            inventory_col.update_one(
                {"variantId": v_id},
                {"$set": {
                    "variantId": v_id,
                    "productId": p_id,
                    "totalQuantity": qty,
                    "reservedQuantity": 0,
                    "availableQuantity": qty,
                    "updatedAt": utc_now()
                }},
                upsert=True
            )

        product = {
            "id": p_id,
            "productId": p_id,
            "name": name,
            "description": f"Premium {subcat} {cat} by {brand}, designed for maximum comfort and style.",
            "category": cat,
            "subcategory": subcat,
            "brand": brand,
            "price": price,
            "currency": "USD",
            "images": [f"https://placehold.co/600x800?text={name.replace(' ', '+')}"],
            "variants": variants,
            "rating": round(random.uniform(3.5, 5.0), 1),
            "reviewCount": random.randint(10, 500),
            "tags": [cat, subcat, "new-arrival"],
            "features": ["High-quality material", "Modern design", "Durability-tested"],
            "specifications": {"origin": "Imported", "care": "Hand wash recommended"},
            "status": "active",
            "createdAt": utc_now(),
            "updatedAt": utc_now()
        }

        product_col.update_one({"productId": p_id}, {"$set": product}, upsert=True)
        
        # Ensure category exists
        cat_row = category_col.find_one({"slug": cat})
        if not cat_row:
             category_col.update_one(
                {"slug": cat},
                {"$set": {
                    "categoryId": cat,
                    "slug": cat,
                    "name": cat.title(),
                    "description": f"{cat.title()} products",
                    "status": "active",
                    "createdAt": utc_now(),
                    "updatedAt": utc_now()
                }},
                upsert=True
            )
        added += 1

    print(f"Added {added} items. Final product count: {product_col.count_documents({})}")
    client.close()

if __name__ == "__main__":
    seed_products()
