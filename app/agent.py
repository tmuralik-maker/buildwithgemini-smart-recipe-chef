# ruff: noqa
import datetime
from zoneinfo import ZoneInfo
from google.cloud import firestore
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

import os
import json
import base64
import urllib.request
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.cloud import storage
from google.adk.tools import ToolContext
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor

# HARDCODED GCP PROJECT ID & BUCKET NAME (as required for Agent Platform deployment safety)
PROJECT_ID = "qwiklabs-gcp-01-899d7fa5a36d"
BUCKET_NAME = "qwiklabs-gcp-01-899d7fa5a36d-static-assets-bucket"

db = firestore.Client(project=PROJECT_ID)

# Load Agent Engine resource name from deployment_metadata.json if present
METADATA_FILE = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
agent_engine_resource_name = None
if os.path.exists(METADATA_FILE):
    try:
        with open(METADATA_FILE, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

if not agent_engine_resource_name:
    agent_engine_resource_name = f"projects/{PROJECT_ID}/locations/us-east1/reasoningEngines/240298266250444800"

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


def search_recipes(query: str = "", cuisine: str = "", dietary_tag: str = "") -> str:
    """Searches the Firestore recipe collection by keyword, cuisine, or dietary tag.

    Args:
        query: Optional search keyword in title or ingredients.
        cuisine: Optional cuisine filter (e.g. Italian, Mediterranean, Thai).
        dietary_tag: Optional tag filter (e.g. vegan, vegetarian, gluten-free).

    Returns:
        A list of matching recipe summaries.
    """
    recipes_ref = db.collection("recipes")
    docs = recipes_ref.stream()
    
    results = []
    for doc in docs:
        data = doc.to_dict()
        title = data.get("title", "")
        rec_cuisine = data.get("cuisine", "")
        tags = [t.lower() for t in data.get("dietary_tags", [])]
        ingredients_text = " ".join(data.get("ingredients", [])).lower()
        
        if cuisine and cuisine.lower() not in rec_cuisine.lower():
            continue
        if dietary_tag and dietary_tag.lower() not in tags:
            continue
        if query and (query.lower() not in title.lower() and query.lower() not in ingredients_text):
            continue
            
        results.append({
            "id": doc.id,
            "title": title,
            "cuisine": rec_cuisine,
            "servings": data.get("servings"),
            "prep_time_minutes": data.get("prep_time_minutes"),
            "dietary_tags": data.get("dietary_tags", []),
        })
        
    if not results:
        return "No recipes found matching your criteria."
    
    formatted = [f"- {r['title']} (ID: {r['id']}, Cuisine: {r['cuisine']}, Prep: {r['prep_time_minutes']}m, Tags: {', '.join(r['dietary_tags'])})" for r in results]
    return "Found recipes:\n" + "\n".join(formatted)


def get_recipe_details(recipe_id: str) -> str:
    """Gets the full details of a specific recipe from Firestore.

    Args:
        recipe_id: The document ID of the recipe (e.g. 'classic_carbonara', 'thai_green_curry').

    Returns:
        Detailed recipe information including ingredients and instructions.
    """
    doc_ref = db.collection("recipes").document(recipe_id)
    doc = doc_ref.get()
    
    if not doc.exists:
        return f"Recipe with ID '{recipe_id}' not found."
    
    data = doc.to_dict()
    ingredients_str = "\n".join([f"  - {ing}" for ing in data.get("ingredients", [])])
    instructions_str = "\n".join([f"  {idx+1}. {step}" for idx, step in enumerate(data.get("instructions", []))])
    
    return f"""Recipe: {data.get('title')} (ID: {doc.id})
Cuisine: {data.get('cuisine')}
Servings: {data.get('servings')}
Prep Time: {data.get('prep_time_minutes')} minutes
Dietary Tags: {', '.join(data.get('dietary_tags', []))}

Ingredients:
{ingredients_str}

Instructions:
{instructions_str}
"""


def save_recipe(recipe_id: str, title: str, cuisine: str, servings: int, prep_time_minutes: int, ingredients: list[str], instructions: list[str], dietary_tags: list[str] = None) -> str:
    """Saves a new recipe or updates an existing recipe in the Firestore database.

    Args:
        recipe_id: Unique ID for the recipe document (slug format, e.g. 'avocado_toast').
        title: Title of the recipe.
        cuisine: Cuisine style (e.g. Mexican, Italian, Fusion).
        servings: Number of servings.
        prep_time_minutes: Preparation time in minutes.
        ingredients: List of ingredient strings.
        instructions: List of step-by-step instruction strings.
        dietary_tags: Optional list of dietary tags (e.g. ['vegan', 'nut-free']).

    Returns:
        Confirmation message with saved recipe details.
    """
    if dietary_tags is None:
        dietary_tags = []
        
    recipe_data = {
        "id": recipe_id,
        "title": title,
        "cuisine": cuisine,
        "servings": servings,
        "prep_time_minutes": prep_time_minutes,
        "ingredients": ingredients,
        "instructions": instructions,
        "dietary_tags": dietary_tags,
    }
    
    db.collection("recipes").document(recipe_id).set(recipe_data)
    return f"Successfully saved recipe '{title}' (ID: {recipe_id}) to Firestore."


def generate_shopping_list(recipe_ids: list[str]) -> str:
    """Generates a consolidated grocery shopping list for a list of recipe IDs.

    Args:
        recipe_ids: List of recipe document IDs (e.g. ['classic_carbonara', 'mediterranean_chickpea_salad']).

    Returns:
        A consolidated shopping list grouped by recipe title.
    """
    if not recipe_ids:
        return "Please provide at least one recipe ID to generate a shopping list."

    shopping_items = []
    found_titles = []
    
    for r_id in recipe_ids:
        doc = db.collection("recipes").document(r_id).get()
        if doc.exists:
            data = doc.to_dict()
            title = data.get("title", r_id)
            found_titles.append(title)
            for item in data.get("ingredients", []):
                shopping_items.append(f"- {item} (for {title})")
        else:
            shopping_items.append(f"- [Note: Recipe ID '{r_id}' not found]")

    if not found_titles:
        return "None of the specified recipe IDs were found in Firestore."

    header = f"Shopping List for {', '.join(found_titles)}:\n"
    return header + "\n".join(shopping_items)


def search_online_recipes_api(query: str) -> str:
    """Searches real online recipes using TheMealDB free public API.

    Args:
        query: Food item or dish name to search online (e.g. 'pasta', 'arrabiata', 'curry').

    Returns:
        A list of matching online recipes with category, area, and main instructions.
    """
    api_key = os.environ.get("THEMEALDB_API_KEY", "1")
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.themealdb.com/api/json/v1/{api_key}/search.php?s={encoded_query}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartRecipeChef/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            meals = data.get("meals")
            if not meals:
                return f"No online recipes found for query: '{query}'."
            
            results = []
            for meal in meals[:3]:
                title = meal.get("strMeal")
                category = meal.get("strCategory")
                area = meal.get("strArea")
                instructions = (meal.get("strInstructions") or "")[:150] + "..."
                results.append(f"- {title} ({area} {category}): {instructions}")
                
            return f"Online recipes for '{query}':\n" + "\n".join(results)
    except Exception as e:
        return f"Failed to fetch online recipes: {str(e)}"


def geocode_address(address: str) -> str:
    """Turns an address or location name into geographical coordinates (latitude and longitude) using the Google Maps Geocoding API.

    Args:
        address: The location or street address to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'New York, NY').

    Returns:
        Formatted address and coordinates (latitude, longitude).
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not set in environment."

    encoded_address = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("status") != "OK" or not data.get("results"):
                return f"Geocoding failed for address '{address}': status {data.get('status')}."

            first_res = data["results"][0]
            fmt_address = first_res.get("formatted_address")
            loc = first_res.get("geometry", {}).get("location", {})
            lat = loc.get("lat")
            lng = loc.get("lng")
            return f"Geocoded Location:\nAddress: {fmt_address}\nCoordinates: Latitude {lat}, Longitude {lng}"
    except Exception as e:
        return f"Geocoding request error: {str(e)}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "supermarket", radius_meters: float = 1000.0) -> str:
    """Finds nearby places (e.g. supermarkets, grocery stores, bakeries) around coordinates using the Places API (New).

    Args:
        latitude: Latitude of the center point.
        longitude: Longitude of the center point.
        place_type: Type of place to search for (e.g. 'supermarket', 'grocery_store', 'bakery').
        radius_meters: Radius in meters around center point (default 1000 meters).

    Returns:
        List of nearby places with name, formatted address, and location.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY is not set in environment."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    payload = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "radius": radius_meters
            }
        }
    }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            places = data.get("places")
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters}m."

            results = []
            for place in places[:5]:
                name = place.get("displayName", {}).get("text", "Unknown Place")
                addr = place.get("formattedAddress", "No address")
                loc = place.get("location", {})
                plat = loc.get("latitude")
                plng = loc.get("longitude")
                results.append(f"- Name: {name}\n  Address: {addr}\n  Location: Lat {plat}, Lng {plng}")

            return f"Nearby '{place_type}' locations:\n" + "\n\n".join(results)
    except Exception as e:
        return f"Places API request error: {str(e)}"


def generate_dish_image(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates an image of a food dish or recipe using gemini-3.1-flash-lite-image in the global region.

    Saves the image as a session artifact and uploads it to Google Cloud Storage.

    Args:
        prompt: Description of the food dish image to generate (e.g. 'A bowl of freshly cooked spaghetti carbonara with parsley').

    Returns:
        The public HTTPS URL of the uploaded image.
    """
    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    
    try:
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
        )
        
        part = response.candidates[0].content.parts[0]
        image_bytes = part.inline_data.data
        mime_type = part.inline_data.mime_type or "image/jpeg"
        ext = "jpeg" if "jpeg" in mime_type else "png"
        
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dish_{timestamp_str}.{ext}"
        
        # (1) Save artifact for Playground Artifacts panel if tool_context available
        if tool_context:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename, artifact_part)
            
        # (2) Upload image bytes directly to GCS bucket
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        object_name = f"recipe_images/{filename}"
        blob = bucket.blob(object_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"
        return f"Generated dish image successfully!\nPublic URL: {public_url}"
    except Exception as e:
        return f"Failed to generate dish image: {str(e)}"


def generate_dish_video(prompt: str, tool_context: ToolContext = None) -> str:
    """Generates a short video of a food dish, recipe, or cooking process using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the video as a session artifact for the Playground's Artifacts panel and uploads it to Google Cloud Storage.

    Args:
        prompt: Description of the food dish video or cooking process to generate (e.g. 'A chef sizzling garlic and olive oil in a pan').

    Returns:
        The public HTTPS URL of the uploaded video.
    """
    genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    
    try:
        interaction = genai_client.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )
        
        video_bytes = None
        if hasattr(interaction, "output_video") and interaction.output_video:
            raw_data = getattr(interaction.output_video, "data", None)
            if raw_data:
                if isinstance(raw_data, str):
                    video_bytes = base64.b64decode(raw_data)
                elif isinstance(raw_data, bytes):
                    video_bytes = raw_data

        if not video_bytes and hasattr(interaction, "steps"):
            for step in interaction.steps:
                content_list = getattr(step, "content", []) or []
                for item in content_list:
                    if getattr(item, "type", None) == "video" or getattr(item, "mime_type", "").startswith("video/"):
                        data_val = getattr(item, "data", None)
                        if data_val:
                            if isinstance(data_val, str):
                                video_bytes = base64.b64decode(data_val)
                            elif isinstance(data_val, bytes):
                                video_bytes = data_val
                            break

        if not video_bytes:
            return "Failed to extract video bytes from gemini-omni-flash-preview response."

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dish_video_{timestamp_str}.mp4"

        # (1) Save video as artifact for Playground Artifacts panel if tool_context available
        if tool_context:
            artifact_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")
            tool_context.save_artifact(filename, artifact_part)

        # (2) Upload video bytes directly to GCS public bucket
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        object_name = f"recipe_videos/{filename}"
        blob = bucket.blob(object_name)
        blob.upload_from_string(video_bytes, content_type="video/mp4")

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{object_name}"
        return f"Generated dish video successfully!\nPublic URL: {public_url}"
    except Exception as e:
        return f"Failed to generate dish video: {str(e)}"


from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.adk.memory import VertexAiMemoryBankService

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

MEMORY_BANK_ID = agent_engine_resource_name.split("/")[-1]

async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None

def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )

# Memory service instance available for deployment wiring
memory_service = memory_bank_service_builder()

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="You are Smart Recipe Chef, an intelligent AI culinary assistant. You help users discover recipes, look up ingredient lists, generate dish images, generate dish cooking videos, find local supermarkets, save custom recipes, and generate shopping lists.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "CRITICAL ALLERGY & DIETARY MEMORY INSTRUCTIONS:\n"
        "- Check preloaded memory on every turn for remembered user food allergies, dietary restrictions, or medical sensitivities.\n"
        "- Always remember any food allergies or sensitivities mentioned by the user (e.g. peanuts, tree nuts, shellfish, gluten, dairy, eggs, soy).\n"
        "- Never recommend recipes, ingredients, or shopping lists containing a user's allergen without explicit warnings and safe substitute options."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    tools=[PreloadMemoryTool(), search_recipes, get_recipe_details, save_recipe, generate_shopping_list, search_online_recipes_api, geocode_address, find_nearby_places, generate_dish_image, generate_dish_video],
    code_executor=code_executor,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
