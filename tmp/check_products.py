import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv('d:/Projects/omnichannel-agentic-commerce/backend/.env')

uri = os.getenv('MONGODB_URI', 'mongodb://mongo:27017/commerce')
if 'mongo:27017' in uri:
    uri = uri.replace('mongo', 'localhost')

client = MongoClient(uri)
db = client['commerce']

product = db['products'].find_one()
if product:
    print("Sample Product Keys:", product.keys())
    print("Sample Product Category:", product.get('category'))
    print("Sample Product Price:", product.get('price'))
else:
    print("No products found in DB.")

count = db['products'].count_documents({})
print(f"Total Products: {count}")

client.close()
