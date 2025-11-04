from __future__ import annotations

from pydantic_ai import Agent, Tool
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic import BaseModel, Field

from typing import Annotated
import requests
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
THEMEALDB_API_KEY = os.getenv("THEMEALDB_API_KEY", "1")
THEMEALDB_PREMIUM = THEMEALDB_API_KEY != "1"
THEMEALDB_VERSION = "v2" if THEMEALDB_PREMIUM else "v1"
THEMEALDB = f"https://www.themealdb.com/api/json/{THEMEALDB_VERSION}/{THEMEALDB_API_KEY}"

# make sure the google api key is defined
if not GOOGLE_API_KEY:
    raise EnvironmentError("No GOOGLE_API_KEY defined.")

# system prompt for model
SYSTEM = """
You are a cooking assistant. Be concise, precise, and tool-driven.

GOAL
Given a user request about dishes or ingredients, return 1 well-matched recipe with ingredients (and amounts), clear steps, and helpful notes.

TOOL USE
1) If the user names a dish (even approximately), CALL search_meal_by_name(name).
2) If the user does NOT name a dish:
   - If they give one main ingredient, CALL search_meal_by_main_ingredient(ingredient).
   - If they give multiple ingredients AND search_meal_by_multiple_ingredients is available, CALL search_meal_by_multiple_ingredients(list_of_ingredients). Otherwise fall back to search_meal_by_main_ingredient on the strongest ingredient.
3) From the candidates, pick the top 1-3 most relevant by matching cuisine, keywords (e.g., “spicy”, “vegan”), and prep method.
4) For each chosen candidate, CALL lookup_meal_details_by_id(id) to get full details before answering.

MATCHING & ADJUSTMENTS
- If no exact match: pick the closest dish and adapt it. Clearly label changes under “Modifications”.
- If a constraint is stated (diet, spice level, equipment, time), prefer matches that satisfy it; otherwise adapt and explain.

CLARITY RULES
- Ask at most ONE clarifying question only if you cannot proceed (e.g., ambiguous multiple cuisines). Otherwise, make a best reasonable assumption and continue.
- Do not invent ingredients or steps not present in the looked-up details unless clearly labeled under “Modifications”.

OUTPUT FORMAT
### {Meal Name}

**Ingredients**
- {ingredient} — {amount}
- ...

**Instructions**
1. Step...
2. Step...
3. ...

**Modifications** (include only if you adjusted the recipe)
- What changed and why.

ERROR & EMPTY STATES
- If no results: say so briefly and suggest 2-3 alternative searches (by dish name or main ingredient).
- If TheMealDB data is missing amounts, state “amount not provided” rather than guessing.

STYLE
- Keep responses practical, friendly, and under ~250 words per recipe.
- Use bullet lists and numbered steps. Avoid fluff.
"""

class PartialMealResponse(BaseModel):
    meal_id: int = Field(...)
    meal_name: str = Field(...)


class FullMealResponse(BaseModel):
    meal_id: int = Field(...)
    meal_name: str = Field(...)
    meal_type: str = Field(...)
    instructions: str = Field(...)
    ingredients: list[tuple[str, str]] = Field(...)
    thumbnail: str
    video: str


@Tool
def search_meal_by_name(
    name: Annotated[str, "Meal name, case insensitive, fuzzy OK"]
) -> list[PartialMealResponse]:
    """Takes in the name of a meal and returns a list of potentially matching meals, 
    along with their id's for finding full details later"""

    # send a request to the mealdb api to find a meal by its name
    request = requests.get(f"{THEMEALDB}/search.php", params={"s": name}, timeout=5)
    # throw error if status code is bad
    request.raise_for_status()
    # get the json
    result: dict = request.json()

    # return nothing if no meals found
    if "meals" not in result or not result["meals"]:
        return []
    
    # get meals list
    meals: list[dict] = result["meals"]

    # turn meals into PartialMealResponse objects
    parsed_meals: list[PartialMealResponse] = [
        PartialMealResponse(
            meal_id=meal["idMeal"],
            meal_name=meal["strMeal"]
        )
        for meal in meals
    ]

    return parsed_meals


@Tool
def search_meal_by_main_ingredient(
    ingredient: Annotated[str, "Main ingredient of a meal"]
) -> list[PartialMealResponse]:
    """Takes in the main ingredient of a meal and returns a list of potentially matching meals, 
    along with their id's for finding full details later"""

    # send a request to the mealdb api to find a meal by its main ingredient
    request = requests.get(f"{THEMEALDB}/filter.php", params={"i": ingredient}, timeout=5)
    # throw error if status code is bad
    request.raise_for_status()
    # get the json
    result: dict = request.json()

    # return nothing if no meals found
    if "meals" not in result or not result["meals"]:
        return []
    
    # get meals list
    meals: list[dict] = result["meals"]

    # turn meals into PartialMealResponse objects
    parsed_meals: list[PartialMealResponse] = [
        PartialMealResponse(
            meal_id=meal["idMeal"],
            meal_name=meal["strMeal"]
        )
        for meal in meals
    ]

    return parsed_meals


@Tool
def search_meal_by_multiple_ingredients(
    ingredients: Annotated[list[str], "List of ingredients to search for"]
) -> list[PartialMealResponse]:
    """Takes in a list of ingredients and returns a list of potentially matching meals, 
    along with their id's for finding full details later"""

    # send a request to the mealdb api to find a meal by multiple ingredients in it
    request = requests.get(f"{THEMEALDB}/filter.php", params={"i": ",".join(ingredients)}, timeout=5)
    # throw error if status code is bad
    request.raise_for_status()
    # get the json
    result: dict = request.json()

    # return nothing if no meals found
    if "meals" not in result or not result["meals"]:
        return []
    
    # get meals list
    meals: list[dict] = result["meals"]

    # turn meals into PartialMealResponse objects
    parsed_meals: list[PartialMealResponse] = [
        PartialMealResponse(
            meal_id=meal["idMeal"],
            meal_name=meal["strMeal"]
        )
        for meal in meals
    ]

    return parsed_meals


@Tool
def lookup_meal_details_by_id(
    id: Annotated[int, "Meal id, must match exactly"]
) -> FullMealResponse | None:
    """Takes in the exact id of the meal and returns its full details,
     including the meal name, type, instructions, ingredients (along with serving sizes),
     image thumbnail url, and youtube video link"""

    # send a request to the mealdb api to lookup a meal by its id
    request = requests.get(f"{THEMEALDB}/lookup.php", params={"i": id}, timeout=5)
    # throw error if status code is bad
    request.raise_for_status()
    # get the json
    result: dict = request.json()

    # return nothing if no meals found
    if "meals" not in result or not result["meals"]:
        return []
    
    # get meals list
    meals: list[dict] = result["meals"]

    # return nothing if theres no meals
    if len(meals) == 0:
        return None

    # get the meal
    meal = meals[0]

    # package the ingredients in a better format
    ingredients: list[tuple[str, str]] = []

    # get each ingredient and its corresponding measure
    for i in range(1, 21):
        ingredient = meal.get(f"strIngredient{i}")
        measure = meal.get(f"strMeasure{i}")
        
        # if theyre empty or dont exist, skip it
        if not ingredient or not measure:
            continue
            
        # if they do, package it in a tuple
        ingredients.append((ingredient, measure))

    # return the meal's full details along with the ingredients
    return FullMealResponse(
            meal_id=meal["idMeal"],
            meal_name=meal["strMeal"],
            meal_type=meal["strArea"],
            instructions=meal["strInstructions"],
            ingredients=ingredients,
            thumbnail=f"{meal["strMealThumb"]}/medium",
            video=meal["strYoutube"]
        )


# Provider for Gemini API
provider = GoogleProvider(api_key=GOOGLE_API_KEY)
# search agent creation
search_agent: Agent = Agent(
    model=GoogleModel(model_name="gemini-2.5-flash"),
    system_prompt=SYSTEM,
    # If the user does not specify a premium key,
    # the search_meal_by_multiple_ingredients function is not available
    tools=[search_meal_by_name, search_meal_by_main_ingredient,search_meal_by_multiple_ingredients ,lookup_meal_details_by_id] 
    if THEMEALDB_PREMIUM else [search_meal_by_name, search_meal_by_main_ingredient, lookup_meal_details_by_id]
)


