from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic import BaseModel, Field, field_validator

from .env import *

# system prompt for model
IMAGE_SYSTEM_PROMPT = """
You are a cooking assistant. Be concise and precise.

GOAL
Given a recipe and an image with the cooked recipe from the user, your job is to rate the image based on how closely it follows the recipe, as well as how well it seems to be cooked.
You don't need to concern the image with how well it looks, as long as it looks edible and correct.
Return a rating from 1 to 5 flames.
Return a response that explains the justification for the rating, as well as tips on how to improve, if any.
Also, validate that the image is valid or not. For example, if the meal called for a bowl of rice, and the image had no rice, return False in valid_image to mark that the image is invalid.
Make sure to mark any images that seem inappropriate or not related to cooking as an invalid image.
"""


class ImageOutput(BaseModel):
    rating: int = Field(...)
    response: str = Field(...)
    valid_image: bool = Field(...)

    @field_validator('rating')
    @classmethod
    def validate_username(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Rating must be between 1 and 5")
        return v


# search agent creation
image_agent: Agent = Agent(
    model=GoogleModel(model_name="gemini-2.5-flash"),
    system_prompt=IMAGE_SYSTEM_PROMPT,
    output_type=ImageOutput
)
