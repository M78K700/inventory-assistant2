import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from PIL import Image
import io
import os
from dotenv import load_dotenv
import openai
from vision_utils import process_product_image
from chatbot import get_chatbot_response
from database import (
    authenticate_user, add_product, 
    get_user_inventory, update_inventory_quantity, get_low_stock_items, delete_product, get_product_usage_history
)
import re

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    st.error("OPENAI_API_KEY environment variable is not set. Please add it to your .env file.")
    st.stop()

# Set page config
st.set_page_config(
    page_title="Inventory Management System",
    page_icon="🛒",
    layout="wide"
)

# Categories
CATEGORIES = [
    'Fresh Produce', 'Meat & Eggs', 'Grocery', 'Household Supplies',
    'Dairy & Alternatives', 'Beverages', 'Frozen Foods', 'Bakery'
]

def initialize_session_state():
    """Initialize all session state variables"""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "View Inventory"

def main():
    """Main application function"""
    initialize_session_state()
    
    st.title("🛒 Inventory Management System")
    
    # User authentication
    if st.session_state.user_id is None:
        show_login_page()
    else:
        show_main_interface()

def show_login_page():
    """Display login page"""
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Login"):
        user_id = authenticate_user(username, password)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.chat_history = []
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid username or password")

def show_main_interface():
    """Display main application interface"""
    st.sidebar.header("Navigation")
    
    # Navigation
    page = st.sidebar.selectbox(
        "Choose Page",
        ["View Inventory", "Add Product", "Use Product", "Reports"]
    )
    
    if st.sidebar.button("Logout"):
        st.session_state.user_id = None
        st.session_state.chat_history = []
        st.rerun()
    
    # Display selected page
    if page == "View Inventory":
        show_inventory_page()
    elif page == "Add Product":
        show_add_product_page()
    elif page == "Use Product":
        show_use_product_page()
    elif page == "Reports":
        show_reports_page()

def show_inventory_page():
    """Display inventory page"""
    st.header("Current Inventory")
    display_inventory_table(st.session_state.user_id)
    display_chatbot()

def show_add_product_page():
    """Display add product page"""
    add_product_ui(st.session_state.user_id)
    display_chatbot()

def show_use_product_page():
    """Display use product page with usage history"""
    st.header("Use Product")
    
    inventory = get_user_inventory(st.session_state.user_id)
    if inventory:
        # Product selection and usage
        col1, col2 = st.columns(2)
        with col1:
            product_name = st.selectbox(
                "Select Product",
                [item['product_name'] for item in inventory]
            )
            
            # Get current quantity
            current_product = next((item for item in inventory if item['product_name'] == product_name), None)
            if current_product:
                st.info(f"Current quantity: {current_product['quantity']} {current_product['unit']}")
            
            quantity_used = st.number_input("Quantity Used", min_value=0.0, step=0.1)
            
            if st.button("Update Inventory"):
                if current_product:
                    # Calculate new quantity by subtracting used quantity
                    new_quantity = current_product['quantity'] - quantity_used
                    if new_quantity < 0:
                        st.error("Cannot use more than available quantity")
                    else:
                        if update_inventory_quantity(st.session_state.user_id, product_name, new_quantity):
                            st.success(f"Updated {product_name} quantity to {new_quantity} {current_product['unit']}")
                            st.rerun()
                        else:
                            st.error("Failed to update inventory")
        
        # Show usage history
        with col2:
            st.subheader("Recent Usage History")
            usage_history = get_product_usage_history(st.session_state.user_id, product_name)
            if usage_history:
                history_df = pd.DataFrame([dict(item) for item in usage_history])
                history_df['usage_date'] = pd.to_datetime(history_df['usage_date']).dt.strftime('%Y-%m-%d %H:%M')
                st.dataframe(
                    history_df[['usage_date', 'quantity_used', 'operation_type']].rename(
                        columns={
                            'usage_date': 'Date',
                            'quantity_used': 'Quantity',
                            'operation_type': 'Operation'
                        }
                    ),
                    use_container_width=True
                )
            else:
                st.info("No usage history available")
    else:
        st.info("No products in inventory yet")
    
    display_chatbot()

def show_reports_page():
    """Display reports page"""
    st.header("Inventory Reports")
    
    report_type = st.selectbox(
        "Select Report Type",
        ["Inventory Summary", "Low Stock Alert", "Recent Activity", "Custom Report"]
    )
    
    if st.button("Generate Report"):
        inventory = get_user_inventory(st.session_state.user_id)
        if inventory:
            inventory_df = pd.DataFrame([dict(item) for item in inventory])
            report = generate_inventory_report(inventory_df, report_type)
            st.markdown(report)
        else:
            st.info("No inventory data available for report generation")
    
    display_chatbot()

def display_inventory_table(user_id):
    """Display inventory in a table format with filters and delete option"""
    inventory = get_user_inventory(user_id)
    if not inventory:
        st.info("No items in inventory")
        return
    
    # Convert to DataFrame for easier filtering
    df = pd.DataFrame([dict(item) for item in inventory])
    
    # Format date columns to DD-MM-YY HH:mm
    df['date_added'] = pd.to_datetime(df['date_added']).dt.strftime('%d-%m-%y %H:%M')
    df['last_used'] = pd.to_datetime(df['last_used']).dt.strftime('%d-%m-%y %H:%M')
    
    # Add filters
    col1, col2 = st.columns(2)
    with col1:
        category_filter = st.selectbox("Filter by Category", ["All"] + CATEGORIES)
    with col2:
        low_stock_filter = st.checkbox("Show only low stock items")
    
    # Apply filters
    if category_filter != "All":
        df = df[df['category'] == category_filter]
    if low_stock_filter:
        df = df[df['quantity'] <= df['min_stock_level']]
    
    # Reset index to start from 1
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    
    # Select and rename columns for display
    display_columns = {
        'product_name': 'Product Name',
        'category': 'Category',
        'quantity': 'Quantity',
        'unit': 'Unit',
        'min_stock_level': 'Min Stock Level',
        'date_added': 'Date Added',
        'last_used': 'Last Used'
    }
    
    # Create editable DataFrame
    edited_df = st.data_editor(
        df[list(display_columns.keys())].rename(columns=display_columns),
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Product Name": st.column_config.TextColumn(
                "Product Name",
                help="Name of the product",
                required=True
            ),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                help="Product category",
                options=CATEGORIES,
                required=True
            ),
            "Quantity": st.column_config.NumberColumn(
                "Quantity",
                help="Current quantity",
                min_value=0.0,
                step=0.1,
                required=True
            ),
            "Unit": st.column_config.TextColumn(
                "Unit",
                help="Unit of measurement",
                required=True
            ),
            "Min Stock Level": st.column_config.NumberColumn(
                "Min Stock Level",
                help="Minimum stock level",
                min_value=0.0,
                step=0.1,
                required=True
            ),
            "Date Added": st.column_config.DatetimeColumn(
                "Date Added",
                help="Date when the product was added",
                format="DD-MM-YY HH:mm",
                disabled=True
            ),
            "Last Used": st.column_config.DatetimeColumn(
                "Last Used",
                help="Date when the product was last used",
                format="DD-MM-YY HH:mm",
                disabled=True
            )
        }
    )
    
    # Update button
    if st.button("Update Inventory"):
        try:
            # Convert edited DataFrame back to original format
            edited_df = edited_df.rename(columns={v: k for k, v in display_columns.items()})
            
            # Update each product in the database
            for _, row in edited_df.iterrows():
                update_inventory_quantity(
                    user_id,
                    row['product_name'],
                    row['quantity'],
                    row['min_stock_level']
                )
            
            st.success("Inventory updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Error updating inventory: {str(e)}")
    
    # Add delete product option
    st.subheader("Delete Product")
    product_to_delete = st.selectbox(
        "Select Product to Delete",
        [""] + list(df['product_name'])
    )
    
    if product_to_delete and st.button("Delete Product"):
        if delete_product(user_id, product_to_delete):
            st.success(f"Product '{product_to_delete}' deleted successfully!")
            st.rerun()
        else:
            st.error("Failed to delete product")

def display_chatbot():
    """Display chatbot interface with enhanced capabilities"""
    st.subheader("Inventory Assistant")
    st.write("I can help you manage your inventory. You can ask me to:")
    st.write("- Add new products")
    st.write("- Update product quantities")
    st.write("- Check inventory levels")
    st.write("- Generate reports")
    
    # Get current inventory data
    inventory_df = get_inventory_data()
    
    # Chat interface
    user_input = st.text_input("Your question:")
    if user_input:
        try:
            # Call OpenAI with inventory context
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"""You are an inventory management assistant. You have access to the following inventory data:
{inventory_df.to_string()}

You can:
1. Add new products to the inventory
2. Update quantities of existing products
3. Check inventory levels
4. Generate reports
5. Suggest new categories if needed

When adding or updating products, provide the information in this format:
- Product Name: [name]
- Category: [category]
- Unit: [unit]
- Quantity: [quantity]

Available categories: {', '.join(CATEGORIES)}
Available units: kg, g, L, ml, pcs, box, pack"""},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            assistant_response = response.choices[0].message.content
            
            # Process the response and take actions
            if "Product Name:" in assistant_response:
                # Extract product details
                product_name = re.search(r"Product Name: (.*?)(?:\n|$)", assistant_response)
                category = re.search(r"Category: (.*?)(?:\n|$)", assistant_response)
                unit = re.search(r"Unit: (.*?)(?:\n|$)", assistant_response)
                quantity = re.search(r"Quantity: (.*?)(?:\n|$)", assistant_response)
                
                if all([product_name, category, unit, quantity]):
                    # Add or update product
                    if category.group(1) not in CATEGORIES:
                        CATEGORIES.append(category.group(1))
                    
                    add_product(
                        st.session_state.user_id,
                        product_name.group(1),
                        category.group(1),
                        float(quantity.group(1)),
                        unit.group(1),
                        None,
                        0
                    )
                    st.success(f"Added/Updated product: {product_name.group(1)}")
            
            st.write("Assistant:", assistant_response)
        except Exception as e:
            st.error(f"Error processing request: {str(e)}")

def generate_inventory_report(inventory_df, report_type):
    """Generate user-friendly inventory reports with insights"""
    try:
        if inventory_df.empty:
            return "No inventory data available for report generation."
        
        # Get usage history for the report
        usage_history = get_product_usage_history(st.session_state.user_id)
        history_df = pd.DataFrame([dict(item) for item in usage_history])
        
        # Prepare data for OpenAI
        inventory_summary = inventory_df.to_dict('records')
        history_summary = history_df.to_dict('records')
        
        # Create a prompt based on the report type
        if report_type == "Inventory Summary":
            prompt = f"""
            Generate a summary report for the following inventory data:
            {inventory_summary}
            
            Recent usage history:
            {history_summary}
            
            Please provide:
            1. Total number of unique products
            2. Total inventory value
            3. Products with highest and lowest quantities
            4. Any products approaching their minimum stock level
            5. Recent inventory changes and trends
            """
        elif report_type == "Low Stock Alert":
            prompt = f"""
            Analyze the following inventory data for low stock items:
            {inventory_summary}
            
            Recent usage history:
            {history_summary}
            
            Please identify:
            1. Products below their minimum stock level
            2. Products close to their minimum stock level
            3. Recommended reorder quantities
            4. Priority items that need immediate attention
            5. Usage patterns that might affect stock levels
            """
        elif report_type == "Recent Activity":
            prompt = f"""
            Analyze the following inventory data for recent changes:
            {inventory_summary}
            
            Recent usage history:
            {history_summary}
            
            Please provide:
            1. Recently added products
            2. Products with significant quantity changes
            3. Any unusual patterns in inventory levels
            4. Recommendations for inventory management
            5. Usage trends and patterns
            """
        else:  # Custom Report
            prompt = f"""
            Provide a comprehensive analysis of the following inventory data:
            {inventory_summary}
            
            Recent usage history:
            {history_summary}
            
            Please include:
            1. Overall inventory health assessment
            2. Key trends and patterns
            3. Risk areas and opportunities
            4. Specific recommendations for improvement
            5. Analysis of usage patterns and inventory changes
            """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an inventory management expert. Provide clear, actionable insights in a professional tone."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error with OpenAI API: {str(e)}"
            
    except Exception as e:
        return f"Error generating report: {str(e)}. Please check your OpenAI API key and internet connection."

def get_inventory_data():
    """Get inventory data for the current user"""
    if 'user_id' not in st.session_state:
        return pd.DataFrame()
    inventory = get_user_inventory(st.session_state.user_id)
    if not inventory:
        return pd.DataFrame()
    return pd.DataFrame(inventory)

def add_product_ui(user_id):
    """UI for adding new products with smart suggestions"""
    st.header("Add New Product")
    
    col1, col2 = st.columns(2)
    
    with col1:
        uploaded_image = st.file_uploader("Upload Product Image", type=["jpg", "jpeg", "png"])
        if uploaded_image is not None:
            image = Image.open(uploaded_image)
            st.image(image, caption="Uploaded Image", use_container_width=True)
            
            # Process image with Google Cloud Vision and OpenAI
            try:
                analysis_results = process_product_image(image)
                enhanced_results = analysis_results['enhanced_results']
                
                # Display enhanced analysis
                if enhanced_results:
                    st.subheader("Product Analysis")
                    st.write(f"Suggested Product: {enhanced_results['product_name']}")
                    st.write(f"Suggested Category: {enhanced_results['category']}")
                    st.write(f"Suggested Unit: {enhanced_results['unit']}")
                    st.write(f"Suggested Quantity: {enhanced_results['quantity']}")
                    if enhanced_results['notes']:
                        st.write(f"Notes: {enhanced_results['notes']}")
                    
                    # Set default values for the form
                    suggested_name = enhanced_results['product_name']
                    suggested_category = enhanced_results['category']
                    suggested_unit = enhanced_results['unit']
                    suggested_quantity = enhanced_results['quantity']
                else:
                    st.warning("Could not analyze the image")
                    suggested_name = ""
                    suggested_category = "Grocery"
                    suggested_unit = "pcs"
                    suggested_quantity = 1.0
            except Exception as e:
                st.error(f"Error processing image: {str(e)}")
                suggested_name = ""
                suggested_category = "Grocery"
                suggested_unit = "pcs"
                suggested_quantity = 1.0
    
    with col2:
        # Get existing products for suggestions
        existing_products = get_user_inventory(user_id)
        existing_names = [p['product_name'] for p in existing_products] if existing_products else []
        
        # Product name input with autocomplete
        product_name = st.text_input("Product Name", value=suggested_name if 'suggested_name' in locals() else "")
        
        # Get all unique categories from existing products
        existing_categories = list(set(p['category'] for p in existing_products))
        all_categories = list(set(CATEGORIES + existing_categories))
        
        # If product exists, show its details but allow changes
        matching_products = [p for p in existing_products if p['product_name'].lower() == product_name.lower()]
        if matching_products:
            existing_product = matching_products[0]
            st.info(f"Product already exists:")
            st.write(f"Current Category: {existing_product['category']}")
            st.write(f"Current Unit: {existing_product['unit']}")
            st.write(f"Current Quantity: {existing_product['quantity']}")
            
            # Allow changing category and unit
            category = st.selectbox("Category", all_categories, 
                                  index=all_categories.index(existing_product['category']) if existing_product['category'] in all_categories else 0)
            unit = st.selectbox("Unit", ["kg", "g", "L", "ml", "pcs", "box", "pack"],
                              index=["kg", "g", "L", "ml", "pcs", "box", "pack"].index(existing_product['unit']) if existing_product['unit'] in ["kg", "g", "L", "ml", "pcs", "box", "pack"] else 0)
            
            # Show current quantity and allow updating
            current_quantity = st.number_input("Current Quantity", min_value=0.0, step=0.1, value=existing_product['quantity'])
            quantity_change = st.number_input("Quantity Change", step=0.1, value=0.0)
            new_quantity = current_quantity + quantity_change
        else:
            # New product inputs with suggested values
            category = st.selectbox("Category", all_categories, 
                                  index=all_categories.index(suggested_category) if 'suggested_category' in locals() and suggested_category in all_categories else 0)
            unit = st.selectbox("Unit", ["kg", "g", "L", "ml", "pcs", "box", "pack"],
                              index=["kg", "g", "L", "ml", "pcs", "box", "pack"].index(suggested_unit) if 'suggested_unit' in locals() and suggested_unit in ["kg", "g", "L", "ml", "pcs", "box", "pack"] else 0)
            new_quantity = st.number_input("Quantity", min_value=0.0, step=0.1, value=suggested_quantity if 'suggested_quantity' in locals() else 1.0)
    
    if st.button("Add/Update Product"):
        if product_name:
            if uploaded_image:
                # Save image
                current_time = datetime.now(pytz.UTC)
                image_path = f"images/{product_name}_{current_time.timestamp()}.jpg"
                os.makedirs("images", exist_ok=True)
                image.save(image_path)
            else:
                image_path = None
            
            # Add or update product
            if matching_products:
                # Update existing product
                if update_inventory_quantity(user_id, product_name, new_quantity):
                    st.success(f"Updated {product_name} quantity to {new_quantity} {unit}")
                else:
                    st.error("Failed to update product")
            else:
                # Add new product
                add_product(user_id, product_name, category, new_quantity, unit, image_path, min_stock_level=0)
                st.success(f"Product {product_name} added successfully!")
            
            # Update categories list if new category was added
            if category not in CATEGORIES:
                CATEGORIES.append(category)
            
            st.rerun()  # Refresh the page to show the updated product
        else:
            st.error("Please enter a product name")

# Run the application
if __name__ == "__main__":
    main() 