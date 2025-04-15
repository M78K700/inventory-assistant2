from google.cloud import vision
import os
from PIL import Image
import io
import tempfile
import json
import re
from dotenv import load_dotenv
import openai
from google.oauth2 import service_account

# Load environment variables
load_dotenv()

# Initialize OpenAI
openai.api_key = os.getenv("OPENAI_API_KEY")

def clean_json_string(s):
    """Clean JSON string by removing control characters and properly escaping newlines"""
    # Remove control characters
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    # Properly escape newlines in private key
    s = s.replace('\\n', '\\\\n')
    # Remove any extra whitespace
    s = ' '.join(s.split())
    return s

def get_vision_client():
    """Initialize and return a Vision API client with proper credentials"""
    try:
        # Get credentials from Streamlit secrets
        credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        
        if not credentials_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON not found in environment variables")
        
        try:
            # Parse the credentials JSON
            credentials_dict = json.loads(credentials_json)
            
            # Create credentials object
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            
            # Initialize the client with credentials
            client = vision.ImageAnnotatorClient(credentials=credentials)
            return client
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in GOOGLE_CREDENTIALS_JSON: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error creating credentials: {str(e)}")
            
    except Exception as e:
        raise Exception(f"Failed to initialize Vision API client: {str(e)}")

def analyze_with_openai(vision_results):
    """Use OpenAI to analyze and enhance the vision results"""
    try:
        if not vision_results:
            return {
                "product_name": "Unknown Product",
                "category": "Grocery",
                "unit": "pcs",
                "quantity": 1.0,
                "notes": "No vision results available"
            }

        # Prepare the prompt with vision results
        prompt = f"""You are an expert in product identification and inventory management. 
Analyze the following product image detection results and provide detailed information:

Vision API Results:
- Labels: {', '.join(vision_results.get('labels', []))}
- Detected Text: {', '.join(vision_results.get('texts', []))}
- Objects: {', '.join(vision_results.get('objects', []))}

Please provide a detailed analysis including:
1. Product Name: [specific and accurate name]
2. Category: [suggest the most appropriate category, you can create new categories if needed]
3. Unit: [must be one of: kg, g, L, ml, pcs, box, pack]
4. Quantity: [estimated typical quantity as a number]
5. Detailed Analysis: [comprehensive description of the product]

Format your response as a JSON object with these exact keys: product_name, category, unit, quantity, notes.
The unit must match exactly with the options provided above."""

        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in product identification and inventory management. Provide accurate and detailed analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        # Parse the response
        try:
            result = json.loads(response.choices[0].message.content)
            
            # Validate required fields
            required_fields = ['product_name', 'category', 'unit', 'quantity', 'notes']
            for field in required_fields:
                if field not in result:
                    result[field] = "Unknown" if field != 'quantity' else 1.0
            
            # Validate unit
            valid_units = ['kg', 'g', 'L', 'ml', 'pcs', 'box', 'pack']
            if result['unit'] not in valid_units:
                result['unit'] = 'pcs'
            
            # Ensure quantity is a number
            try:
                result['quantity'] = float(result['quantity'])
            except (ValueError, TypeError):
                result['quantity'] = 1.0
            
            return result
            
        except json.JSONDecodeError:
            # If JSON parsing fails, return a structured response
            return {
                "product_name": vision_results.get('labels', ['Unknown Product'])[0],
                "category": "Grocery",
                "unit": "pcs",
                "quantity": 1.0,
                "notes": "Could not parse detailed analysis"
            }
            
    except Exception as e:
        print(f"Error in OpenAI analysis: {str(e)}")
        # Return a default response if OpenAI analysis fails
        return {
            "product_name": vision_results.get('labels', ['Unknown Product'])[0] if vision_results.get('labels') else "Unknown Product",
            "category": "Grocery",
            "unit": "pcs",
            "quantity": 1.0,
            "notes": f"Error in analysis: {str(e)}"
        }

def process_product_image(image):
    """Process product image using Google Cloud Vision API and OpenAI"""
    try:
        # Convert PIL Image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Create Vision API image object
        vision_image = vision.Image(content=img_byte_arr)
        
        # Get the client
        client = get_vision_client()
        
        # Perform detections
        response = client.annotate_image({
            'image': vision_image,
            'features': [
                {'type_': vision.Feature.Type.LABEL_DETECTION},
                {'type_': vision.Feature.Type.TEXT_DETECTION},
                {'type_': vision.Feature.Type.OBJECT_LOCALIZATION}
            ]
        })
        
        # Process results
        vision_results = {
            'labels': [label.description for label in response.label_annotations],
            'texts': [text.description for text in response.text_annotations],
            'objects': [obj.name for obj in response.localized_object_annotations]
        }
        
        # Enhance with OpenAI
        enhanced_results = analyze_with_openai(vision_results)
        
        return {
            'vision_results': vision_results,
            'enhanced_results': enhanced_results
        }
        
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        raise Exception(f"Could not analyze the image: {str(e)}")

def detect_labels(image_path):
    """Detect labels in an image using Google Cloud Vision API"""
    client = vision.ImageAnnotatorClient()
    
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    response = client.label_detection(image=image)
    labels = response.label_annotations
    
    # Sort labels by confidence score
    sorted_labels = sorted(labels, key=lambda x: x.score, reverse=True)
    return [label.description for label in sorted_labels]

def detect_text(image_path):
    """Detect text in an image using Google Cloud Vision API"""
    client = vision.ImageAnnotatorClient()
    
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    
    if texts:
        return texts[0].description
    return ""

def detect_objects(image_path):
    """Detect objects in an image using Google Cloud Vision API"""
    client = vision.ImageAnnotatorClient()
    
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    response = client.object_localization(image=image)
    objects = response.localized_object_annotations
    
    # Sort objects by confidence score
    sorted_objects = sorted(objects, key=lambda x: x.score, reverse=True)
    return [obj.name for obj in sorted_objects] 