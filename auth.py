import streamlit as st
from typing import Optional

# User credentials - In production, use proper authentication
CREDENTIALS = {
    "authority_user": "password123",
    "normal_user": "userpass",
    "admin": "admin123",
    "traffic_controller": "traffic456"
}

# User roles and permissions
USER_ROLES = {
    "authority_user": {
        "role": "authority",
        "permissions": ["view_all", "modify_settings", "export_data"]
    },
    "admin": {
        "role": "authority", 
        "permissions": ["view_all", "modify_settings", "export_data", "user_management"]
    },
    "normal_user": {
        "role": "user",
        "permissions": ["view_basic"]
    },
    "traffic_controller": {
        "role": "controller",
        "permissions": ["view_all", "modify_signals"]
    }
}

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials"""
    return username in CREDENTIALS and CREDENTIALS[username] == password

def get_user_role(username: str) -> Optional[str]:
    """Get user role from username"""
    if username in USER_ROLES:
        return USER_ROLES[username]["role"]
    return None

def get_user_permissions(username: str) -> list:
    """Get user permissions from username"""
    if username in USER_ROLES:
        return USER_ROLES[username]["permissions"]
    return []

def login() -> Optional[str]:
    """Handle user authentication and return user role"""
    
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = None
    if "username" not in st.session_state:
        st.session_state.username = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = None

    # Show login form if not authenticated
    if st.session_state.authenticated is None:
        st.sidebar.subheader("🔐 Login")
        
        # Login form
        with st.sidebar.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_clicked = st.form_submit_button("Login")
            
            # Show available test accounts
            with st.sidebar.expander("🧪 Test Accounts"):
                st.write("**Authority Users:**")
                st.write("- authority_user : password123")
                st.write("- admin : admin123")
                st.write("**Regular Users:**")
                st.write("- normal_user : userpass")
                st.write("- traffic_controller : traffic456")

        if login_clicked:
            if authenticate_user(username, password):
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.user_role = get_user_role(username)
                st.sidebar.success("✅ Login successful!")
                st.rerun()
            else:
                st.sidebar.error("❌ Invalid credentials")
        
        return None  # Stop app execution until login

    else:
        # Show user info and logout option
        role_emoji = "👑" if st.session_state.user_role == "authority" else "👤"
        st.sidebar.success(f"{role_emoji} **{st.session_state.username}**")
        st.sidebar.caption(f"Role: {st.session_state.user_role}")
        
        # Show user permissions
        permissions = get_user_permissions(st.session_state.username)
        with st.sidebar.expander("🔑 Permissions"):
            for perm in permissions:
                st.write(f"✅ {perm.replace('_', ' ').title()}")
        
        # Logout button
        if st.sidebar.button("🚪 Logout"):
            st.session_state.authenticated = None
            st.session_state.username = None
            st.session_state.user_role = None
            st.rerun()
        
        return st.session_state.user_role

def require_permission(permission: str) -> bool:
    """Check if current user has required permission"""
    if not st.session_state.authenticated:
        return False
    
    permissions = get_user_permissions(st.session_state.username)
    return permission in permissions

def get_current_user() -> Optional[str]:
    """Get current authenticated username"""
    return st.session_state.get("username")

def is_authenticated() -> bool:
    """Check if user is authenticated"""
    return st.session_state.get("authenticated", False)
