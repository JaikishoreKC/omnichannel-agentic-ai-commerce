import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load .env from backend
load_dotenv('d:/Projects/omnichannel-agentic-commerce/backend/.env')

uri = os.getenv('MONGODB_URI', 'mongodb://mongo:27017/commerce')
if 'mongo:27017' in uri:
    uri = uri.replace('mongo', 'localhost')

client = MongoClient(uri)
# Try to get db from uri if possible, else use 'commerce'
try:
    db = client.get_default_database()
except:
    db = client['commerce']

email = 'user1@example.com'
user = db['users'].find_one({'email': email})

if not user:
    print(f"User {email} not found.")
else:
    user_id = user['id']
    print(f"User ID: {user_id}")
    # Note: OrderRepository.get uses 'orderId' field for some reason in the actual document? 
    # Let's check the orders collection.
    orders = list(db['orders'].find({'userId': user_id}))
    print(f"Found {len(orders)} orders for user {user_id}")
    for order in orders:
        print(f"Order ID: {order.get('id', 'N/A')}, Status: {order.get('status', 'N/A')}, Created: {order.get('createdAt', 'N/A')}")

client.close()
