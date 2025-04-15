import sqlite3
import os
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get predefined users from environment variables
PREDEFINED_USERS = {
    os.getenv('ADMIN_USERNAME', 'admin'): os.getenv('ADMIN_PASSWORD', 'admin123'),
    os.getenv('USER1_USERNAME', 'user1'): os.getenv('USER1_PASSWORD', 'user123'),
    os.getenv('USER2_USERNAME', 'user2'): os.getenv('USER2_PASSWORD', 'user123')
}

def get_db_connection():
    """Create a connection to the SQLite database."""
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with the required tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Create inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            image_path TEXT,
            min_stock_level REAL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create product usage history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity_used REAL NOT NULL,
            usage_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            operation_type TEXT NOT NULL,  -- 'add' or 'remove'
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES inventory (id)
        )
    ''')
    
    # Insert predefined users if they don't exist
    for username, password in PREDEFINED_USERS.items():
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password)
            VALUES (?, ?)
        ''', (username, password))
    
    conn.commit()
    conn.close()

def add_user(username, password):
    """Add a new user to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                      (username, password))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(username, password):
    """Authenticate a user against predefined users."""
    if username in PREDEFINED_USERS and PREDEFINED_USERS[username] == password:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        return user['id'] if user else None
    return None

def add_product(user_id, name, category, quantity, unit, image_path, min_stock_level):
    """Add a new product to the inventory or update existing one."""
    conn = get_db_connection()
    cursor = conn.cursor()
    current_time = datetime.now(pytz.UTC)
    
    try:
        # Check if product already exists
        cursor.execute('''
            SELECT id, quantity FROM inventory 
            WHERE user_id = ? AND product_name = ? AND category = ?
        ''', (user_id, name, category))
        existing_product = cursor.fetchone()
        
        if existing_product:
            # Update existing product
            new_quantity = existing_product['quantity'] + quantity
            cursor.execute('''
                UPDATE inventory 
                SET quantity = ?, date_added = ?
                WHERE id = ?
            ''', (new_quantity, current_time, existing_product['id']))
            
            # Record usage history
            cursor.execute('''
                INSERT INTO product_usage_history 
                (user_id, product_id, quantity_used, usage_date, operation_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, existing_product['id'], quantity, current_time, 'add'))
            
        else:
            # Add new product
            cursor.execute('''
                INSERT INTO inventory (user_id, product_name, category, quantity, unit, 
                                     date_added, image_path, min_stock_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, category, quantity, unit, current_time, image_path, min_stock_level))
            
            # Get the new product ID
            product_id = cursor.lastrowid
            
            # Record usage history
            cursor.execute('''
                INSERT INTO product_usage_history 
                (user_id, product_id, quantity_used, usage_date, operation_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, product_id, quantity, current_time, 'add'))
        
        conn.commit()
        return True
    finally:
        conn.close()

def get_user_inventory(user_id):
    """Get all inventory items for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory WHERE user_id = ?', (user_id,))
    items = cursor.fetchall()
    conn.close()
    return items

def update_inventory_quantity(user_id, product_name, quantity, min_stock_level=None):
    """Update product quantity and other fields in the inventory"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get current time in UTC
        current_time = datetime.now(pytz.UTC)
        
        # Prepare the update query
        update_fields = ["quantity = ?", "last_used = ?"]
        update_values = [quantity, current_time]
        
        if min_stock_level is not None:
            update_fields.append("min_stock_level = ?")
            update_values.append(min_stock_level)
        
        # Add the WHERE clause values
        update_values.extend([user_id, product_name])
        
        # Execute the update
        cursor.execute(
            f"""
            UPDATE inventory 
            SET {', '.join(update_fields)}
            WHERE user_id = ? AND product_name = ?
            """,
            update_values
        )
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating inventory: {str(e)}")
        return False
    finally:
        conn.close()

def get_low_stock_items(user_id):
    """Get items that are below their minimum stock level."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM inventory 
        WHERE user_id = ? AND quantity <= min_stock_level
    ''', (user_id,))
    items = cursor.fetchall()
    conn.close()
    return items

def delete_product(user_id, product_name):
    """Delete a product from the inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # First, get the product ID
        cursor.execute('''
            SELECT id FROM inventory 
            WHERE user_id = ? AND product_name = ?
        ''', (user_id, product_name))
        product = cursor.fetchone()
        
        if product:
            # Delete from inventory
            cursor.execute('''
                DELETE FROM inventory 
                WHERE user_id = ? AND product_name = ?
            ''', (user_id, product_name))
            
            # Delete associated usage history
            cursor.execute('''
                DELETE FROM product_usage_history 
                WHERE user_id = ? AND product_id = ?
            ''', (user_id, product['id']))
            
            conn.commit()
            return True
        return False
    finally:
        conn.close()

def get_product_usage_history(user_id, product_name=None, limit=5):
    """Get product usage history."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        if product_name:
            # Get history for specific product
            cursor.execute('''
                SELECT h.*, i.product_name 
                FROM product_usage_history h
                JOIN inventory i ON h.product_id = i.id
                WHERE h.user_id = ? AND i.product_name = ?
                ORDER BY h.usage_date DESC
                LIMIT ?
            ''', (user_id, product_name, limit))
        else:
            # Get all recent history
            cursor.execute('''
                SELECT h.*, i.product_name 
                FROM product_usage_history h
                JOIN inventory i ON h.product_id = i.id
                WHERE h.user_id = ?
                ORDER BY h.usage_date DESC
                LIMIT ?
            ''', (user_id, limit))
        
        return cursor.fetchall()
    finally:
        conn.close()

# Initialize the database when the module is imported
init_db() 