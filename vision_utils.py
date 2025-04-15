from google.cloud import vision
import os
from PIL import Image
import io
import tempfile
import json
import re
from dotenv import load_dotenv
import openai

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
        # Try to get credentials from Streamlit secrets first
        credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        
        if credentials_json:
            # Create a temporary directory for the credentials file
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, 'google-credentials.json')
            
            try:
                # Write the credentials to the temporary file
                with open(temp_file_path, 'w') as f:
                    f.write(credentials_json)
                
                # Set the environment variable
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_file_path
                
                # Initialize the client
                client = vision.ImageAnnotatorClient()
                return client
            finally:
                # Clean up the temporary directory and file
                try:
                    os.remove(temp_file_path)
                    os.rmdir(temp_dir)
                except:
                    pass
        else:
            # Fall back to local credentials file
            credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path and os.path.exists(credentials_path):
                return vision.ImageAnnotatorClient()
            else:
                raise ValueError("No valid Google Cloud credentials found")
    except Exception as e:
        raise Exception(f"Error initializing Vision API client: {str(e)}")

def analyze_with_openai(vision_results):
    """Use OpenAI to analyze and enhance the vision results"""
    try:
        # Prepare the prompt with vision results
        prompt = f"""You are an expert in product identification and inventory management. 
Analyze the following product image detection results and provide detailed information:

Vision API Results:
- Labels: {', '.join(vision_results['labels'])}
- Detected Text: {', '.join(vision_results['texts'])}
- Objects: {', '.join(vision_results['objects'])}

Please provide a detailed analysis including:
1. Product Name: [specific and accurate name]
2. Category: [suggest the most appropriate category, you can create new categories if needed]
3. Unit: [must be one of: kg, g, L, ml, pcs, box, pack]
4. Quantity: [estimated typical quantity as a number]
5. Detailed Analysis: [comprehensive description of the product, including:
   - Brand or manufacturer (if identifiable)
   - Size or volume
   - Packaging type
   - Any special features or characteristics
   - Typical usage or storage requirements
   - Any relevant warnings or handling instructions
   - Why you chose this category and unit]

Format your response as a JSON object with these exact keys: product_name, category, unit, quantity, notes.
The unit must match exactly with the options provided above, but you can suggest any appropriate category."""

        # Call OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert in product identification and inventory management. Provide accurate and detailed analysis. Feel free to suggest new categories if they better describe the product."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent results
            max_tokens=1000  # Increased tokens for more detailed analysis
        )
        
        # Parse the response
        try:
            result = json.loads(response.choices[0].message.content)
            
            # Validate unit
            valid_units = ['kg', 'g', 'L', 'ml', 'pcs', 'box', 'pack']
            if result['unit'] not in valid_units:
                result['unit'] = 'pcs'  # Default unit
            
            # Ensure quantity is a number
            try:
                result['quantity'] = float(result['quantity'])
            except (ValueError, TypeError):
                result['quantity'] = 1.0
            
            return result
        except json.JSONDecodeError:
            # If JSON parsing fails, return a structured response
            return {
                "product_name": vision_results['labels'][0] if vision_results['labels'] else "Unknown Product",
                "category": "Grocery",  # Default category
                "unit": "pcs",  # Default unit
                "quantity": 1.0,  # Default quantity
                "notes": "Could not parse detailed analysis"
            }
    except Exception as e:
        print(f"Error in OpenAI analysis: {str(e)}")
        return None

def process_product_image(image):
    """Process product image using Google Cloud Vision API and OpenAI"""
    try:
        client = get_vision_client()
        
        # Convert PIL Image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        # Create Vision API image object
        vision_image = vision.Image(content=img_byte_arr)
        
        # Perform multiple detections
        response = client.annotate_image({
            'image': vision_image,
            'features': [
                {'type_': vision.Feature.Type.LABEL_DETECTION},
                {'type_': vision.Feature.Type.TEXT_DETECTION},
                {'type_': vision.Feature.Type.OBJECT_LOCALIZATION}
            ]
        })
        
        # Process Vision API results
        vision_results = {
            'labels': [label.description for label in response.label_annotations],
            'texts': [text.description for text in response.text_annotations],
            'objects': [obj.name for obj in response.localized_object_annotations]
        }
        
        # Enhance results with OpenAI analysis
        enhanced_results = analyze_with_openai(vision_results)
        
        # Combine both results
        return {
            'vision_results': vision_results,
            'enhanced_results': enhanced_results
        }
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")

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