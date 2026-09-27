import json
from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-01-899d7fa5a36d"

def seed_database():
    db = firestore.Client(project=PROJECT_ID)
    recipes_ref = db.collection("recipes")

    sample_recipes = [
        {
            "id": "classic_carbonara",
            "title": "Classic Spaghetti Carbonara",
            "cuisine": "Italian",
            "servings": 4,
            "prep_time_minutes": 20,
            "dietary_tags": ["dairy-contains", "nut-free"],
            "ingredients": [
                "400g spaghetti",
                "150g guanciale or pancetta, diced",
                "4 large egg yolks",
                "1 large egg",
                "100g Pecorino Romano, freshly grated",
                "Freshly cracked black pepper",
            ],
            "instructions": [
                "Boil spaghetti in salted water until al dente.",
                "Fry guanciale in a pan until crispy.",
                "Whisk egg yolks, egg, and Pecorino Romano in a bowl with pepper.",
                "Combine hot pasta with guanciale and egg mixture off heat, stirring rapidly until creamy.",
            ],
        },
        {
            "id": "mediterranean_chickpea_salad",
            "title": "Mediterranean Chickpea Salad",
            "cuisine": "Mediterranean",
            "servings": 2,
            "prep_time_minutes": 15,
            "dietary_tags": ["vegetarian", "vegan", "gluten-free", "dairy-free"],
            "ingredients": [
                "1 can (400g) chickpeas, drained and rinsed",
                "1 English cucumber, diced",
                "1 cup cherry tomatoes, halved",
                "1/2 red onion, finely chopped",
                "1/4 cup kalamata olives, pitted",
                "2 tbsp extra virgin olive oil",
                "1 tbsp fresh lemon juice",
                "Salt and oregano to taste",
            ],
            "instructions": [
                "Combine chickpeas, cucumber, tomatoes, red onion, and olives in a bowl.",
                "Drizzle with olive oil and lemon juice.",
                "Season with salt and oregano, toss well, and serve chilled.",
            ],
        },
        {
            "id": "thai_green_curry",
            "title": "Thai Green Curry with Tofu",
            "cuisine": "Thai",
            "servings": 3,
            "prep_time_minutes": 25,
            "dietary_tags": ["vegetarian", "vegan", "gluten-free"],
            "ingredients": [
                "300g firm tofu, cubed and pressed",
                "1 can (400ml) coconut milk",
                "2 tbsp Thai green curry paste",
                "1 cup bamboo shoots",
                "1 red bell pepper, sliced",
                "1 cup Thai basil leaves",
                "1 tbsp soy sauce or tamari",
            ],
            "instructions": [
                "Sauté green curry paste in a splash of coconut milk until fragrant.",
                "Pour in remaining coconut milk and bring to a simmer.",
                "Add tofu, bell pepper, and bamboo shoots; cook for 10 minutes.",
                "Stir in tamari and Thai basil before serving with jasmine rice.",
            ],
        },
    ]

    for recipe in sample_recipes:
        doc_id = recipe["id"]
        recipes_ref.document(doc_id).set(recipe)
        print(f"Seeded recipe: {recipe['title']} (ID: {doc_id})")

    print(f"\nSuccessfully seeded {len(sample_recipes)} recipes to Firestore project '{PROJECT_ID}'.")

if __name__ == "__main__":
    seed_database()
