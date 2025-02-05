import pymongo
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

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

def store_recommendations():
    # Retrieve the latest session email
    session = db[COLLECTION_SESSION].find_one(sort=[("_id", -1)])  # Get the most recent entry
    if not session:
        print("No session found")
        return
    
    email = session.get("email")
    
    # Fetch all cart items for all users to build a collaborative filtering model
    carts = db[COLLECTION_CARTS].find({})
    cart_items = list(carts)  # Convert cursor to list

    if not cart_items:
        print("No cart items found")
        return

    # Create a DataFrame to represent user-item interactions (sparse matrix)
    user_item_matrix = {}

    for item in cart_items:
        user_item_matrix.setdefault(item['email'], {})[item['name']] = 1  # 1 indicates that the user has added this item to the cart

    # Convert the user-item matrix to a DataFrame
    user_item_df = pd.DataFrame.from_dict(user_item_matrix, orient='index').fillna(0)

    # Calculate cosine similarity between items (transposed matrix for item-to-item similarity)
    item_similarity = cosine_similarity(user_item_df.T)

    # Convert similarity matrix into a DataFrame for easier access
    item_similarity_df = pd.DataFrame(item_similarity, index=user_item_df.columns, columns=user_item_df.columns)
    
    # Fetch the user's cart items
    user_cart_items = [item.get('name') for item in db[COLLECTION_CARTS].find({"email": email})]
    
    # Recommend items based on the similarity between the items the user already has in their cart
    recommendations = {}

    for item in user_cart_items:
        # Get the similarity of the current item with all other items
        if item in item_similarity_df.index:
            similar_items = item_similarity_df[item]
            
            # Sort the similarity values in descending order
            similar_items_sorted = similar_items.sort_values(ascending=False)
            
            # Add similar items to recommendations if they are not already in the user's cart
            for similar_item, similarity in similar_items_sorted.items():
                if similar_item not in user_cart_items and similar_item not in recommendations:
                    recommendations[similar_item] = similarity

    # Sort recommendations by similarity score
    sorted_recommendations = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)

    # Prepare the final list of recommended items with additional details from the "menus" collection
    recommended_items = []
    for item, similarity in sorted_recommendations[:5]:  # Top 5 items
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
    
    # Remove existing recommendations for the user before inserting new ones
    db[COLLECTION_SUGGESTED].delete_many({"email": email})
    
    # Insert the new recommendations into the suggested_items collection
    if recommended_items:
        db[COLLECTION_SUGGESTED].insert_many(recommended_items)
        print(f"Recommendations stored for {email}")
    else:
        print("No recommendations generated")

if __name__ == "__main__":
    print("Generating recommendations...")
    store_recommendations()
