from flask import Flask, jsonify
import pymongo
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# MongoDB connection details
DB_USER = "sidharthee1905"
DB_PASSWORD = "foodappserver"
DB_NAME = "test"
COLLECTION_SESSION = "session_email"
COLLECTION_CARTS = "cleaned_carts"
COLLECTION_MENUS = "menus"
COLLECTION_SUGGESTED = "suggested_items"

# MongoDB connection string
connection_string = f"mongodb+srv://{DB_USER}:{DB_PASSWORD}@cluster0.av3yj.mongodb.net/{DB_NAME}?retryWrites=true&w=majority"
client = pymongo.MongoClient(connection_string)
db = client[DB_NAME]

def generate_recommendations():
    # Retrieve the latest session email
    session = db[COLLECTION_SESSION].find_one(sort=[("_id", -1)])
    if not session:
        return {"error": "No session found"}
    
    email = session.get("email")
    
    # Fetch all cart items
    carts = db[COLLECTION_CARTS].find({})
    cart_items = list(carts)
    if not cart_items:
        return {"error": "No cart items found"}

    # Create a user-item matrix
    user_item_matrix = {}
    for item in cart_items:
        user_item_matrix.setdefault(item['email'], {})[item['name']] = 1
    user_item_df = pd.DataFrame.from_dict(user_item_matrix, orient='index').fillna(0)

    # Calculate cosine similarity between items
    item_similarity = cosine_similarity(user_item_df.T)
    item_similarity_df = pd.DataFrame(item_similarity, index=user_item_df.columns, columns=user_item_df.columns)
    
    # Fetch user's cart items
    user_cart_items = [item.get('name') for item in db[COLLECTION_CARTS].find({"email": email})]
    
    # Generate recommendations
    recommendations = {}
    for item in user_cart_items:
        if item in item_similarity_df.index:
            similar_items = item_similarity_df[item].sort_values(ascending=False)
            for similar_item, similarity in similar_items.items():
                if similar_item not in user_cart_items and similar_item not in recommendations:
                    recommendations[similar_item] = similarity
    
    # Sort recommendations
    sorted_recommendations = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    
    # Fetch item details
    recommended_items = []
    for item, similarity in sorted_recommendations[:5]:
        menu_item = db[COLLECTION_MENUS].find_one({"name": item})
        if menu_item:
            recommended_items.append({
                "name": menu_item.get("name"),
                "recipe": menu_item.get("recipe"),
                "image": menu_item.get("image"),
                "category": menu_item.get("category"),
                "price": menu_item.get("price"),
                "similarity": similarity,
                "email": email
            })
    
    # Store recommendations
    db[COLLECTION_SUGGESTED].delete_many({"email": email})
    if recommended_items:
        db[COLLECTION_SUGGESTED].insert_many(recommended_items)
        return {"message": "Recommendations stored", "recommendations": recommended_items}
    return {"message": "No recommendations generated"}

@app.route("/recommend", methods=["GET"])
def recommend():
    return jsonify(generate_recommendations())

if __name__ == "__main__":
    print("Generating recommendations...")
    store_recommendations()
    app.run(host="0.0.0.0", port=10000)
