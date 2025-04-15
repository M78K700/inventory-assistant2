import os
import openai
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, timedelta
from database import add_product, update_inventory_quantity, get_user_inventory

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

def get_inventory_context(inventory_df):
    """Generate context string from inventory DataFrame"""
    if inventory_df.empty:
        return "The inventory is currently empty."
    
    context = "Current inventory status:\n"
    for _, row in inventory_df.iterrows():
        context += f"- {row['name']}: {row['quantity']} units (Category: {row['category']})\n"
    return context

def process_inventory_command(command, inventory_df):
    """Process inventory-related commands"""
    if "add" in command.lower():
        return "To add items to inventory, please use the 'Add Inventory' page."
    elif "use" in command.lower():
        return "To use items from inventory, please use the 'Use Inventory' page."
    elif "status" in command.lower() or "check" in command.lower():
        return get_inventory_context(inventory_df)
    return None

def get_chatbot_response(user_input, inventory_df):
    """Get response from OpenAI chatbot with inventory context"""
    try:
        # Process inventory-specific commands first
        inventory_response = process_inventory_command(user_input, inventory_df)
        if inventory_response:
            return inventory_response

        # Get inventory context
        inventory_context = get_inventory_context(inventory_df)
        
        # Prepare the prompt with inventory context
        prompt = f"""You are an inventory management assistant. Here is the current inventory status:
{inventory_context}

User: {user_input}
Assistant:"""

        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful inventory management assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"Error getting chatbot response: {str(e)}" 