import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

class AIModelGateway:
    """
    Central gateway responsible for routing agent requests 
    to specific open-source models via Groq.
    """
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("CRITICAL: GROQ_API_KEY is missing from environment variables.")
        
        # Define model routing maps
        self.models = {
            "fast": "llama-3.1-8b-instant",
            "reasoning": "llama-3.3-70b-versatile",
            "vision": "meta-llama/llama-4-scout-17b-16e-instruct"# Note: Swap this out if using a specialized open-source VLM wrapper
        }

    def get_model(self, tier: str, temperature: float = 0.0) -> ChatGroq:
        """
        Returns an initialized LangChain chat model wrapper based on the requested tier.
        """
        if tier not in self.models:
            raise ValueError(f"Unknown model tier: {tier}. Choose from {list(self.models.keys())}")
        
        model_name = self.models[tier]
        return ChatGroq(
            groq_api_key=self.api_key,
            model_name=model_name,
            temperature=temperature
        )

# Simple verification block
if __name__ == "__main__":
    print("Testing AI Model Gateway initialization...")
    try:
        gateway = AIModelGateway()
        fast_model = gateway.get_model("fast")
        print(f"Successfully configured Gateway. Fast Tier mapped to: {fast_model.model_name}")
    except Exception as e:
        print(f"Initialization failed: {e}")