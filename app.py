from flask import Flask, jsonify
import pymongo
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import os

# MongoDB connection setup
DB_USER = "sidharthee1905"
DB_PASSWORD = "foodappserver"
DB_NAME = "test"
COLLECTION_SESSION = "session_email"
COLLECTION_CARTS = "cleaned_carts"
COLLECTION_MENUS = "menus"
COLLECTION_SUGGESTED = "suggested_items"

connection_string = f"mongodb+srv://{DB_USER}:{DB_PASSWORD}@cluster0.av3yj.mongodb.net/{DB_NAME}?retryWrites=true&w=majority"
client = pymongo.MongoClient(connection_string)
db = client[DB_NAME]

# Flask setup
app = Flask(__name__)

def store_recommendations():
    session = db[COLLECTION_SESSION].find_one(sort=[("_id", -1)]) 
    if not session:
        print("No session found")
        return
    
    email = session.get("email")
    
    carts = db[COLLECTION_CARTS].find({})
    cart_items = list(carts) 

    if not cart_items:
        print("No cart items found")
        return

    user_item_matrix = {}

    for item in cart_items:
        user_item_matrix.setdefault(item['email'], {})[item['name']] = 1 

    user_item_df = pd.DataFrame.from_dict(user_item_matrix, orient='index').fillna(0)
    item_similarity = cosine_similarity(user_item_df.T)
    item_similarity_df = pd.DataFrame(item_similarity, index=user_item_df.columns, columns=user_item_df.columns)
    user_cart_items = [item.get('name') for item in db[COLLECTION_CARTS].find({"email": email})]
    

    recommendations = {}
    for item in user_cart_items:
        if item in item_similarity_df.index:
            similar_items = item_similarity_df[item]
            similar_items_sorted = similar_items.sort_values(ascending=False)
            
            for similar_item, similarity in similar_items_sorted.items():
                if similar_item not in user_cart_items and similar_item not in recommendations:
                    recommendations[similar_item] = similarity

    sorted_recommendations = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)

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
    
    db[COLLECTION_SUGGESTED].delete_many({"email": email})
    
    if recommended_items:
        db[COLLECTION_SUGGESTED].insert_many(recommended_items)
        print(f"Recommendations stored for {email}")
        return recommended_items
    else:
        print("No recommendations generated")
        return []

@app.route('/recommend', methods=['GET'])
def recommend():
    try:
        recommendations = store_recommendations()
        return jsonify({"message": "Recommendations generated successfully", "recommendations": recommendations}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Use Render's PORT or default to 5000
    app.run(host="0.0.0.0", port=port)
