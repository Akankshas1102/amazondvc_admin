"""
Admin API Routes
================
Handles all admin panel operations including:
- Authentication (login/logout)
- Query configuration management
- User management
- System settings

All routes require JWT authentication except /login
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from contextlib import contextmanager

from auth import (
    hash_password, 
    verify_password, 
    create_access_token, 
    decode_access_token,
    get_current_user
)
from query_config import (
    get_query,
    set_query,
    get_all_queries,
    get_query_with_sql,
    delete_query,
    validate_query_syntax,
    get_default_query
)
from logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

SQLITE_DB_PATH = "building_schedules.db"


@contextmanager
def get_sqlite_connection():
    """Context manager for SQLite database connections."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite transaction error: {e}")
        raise
    else:
        conn.commit()
    finally:
        conn.close()


# ==================== REQUEST/RESPONSE MODELS ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool


class QueryRequest(BaseModel):
    query_name: str
    query_sql: str
    description: Optional[str] = ""


class QueryResponse(BaseModel):
    query_name: str
    query_sql: str
    description: str
    created_at: Optional[str]
    updated_at: Optional[str]


class QueryUpdateResponse(BaseModel):
    success: bool
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    is_admin: Optional[bool] = None
    new_password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: str
    updated_at: str


# ==================== AUTHENTICATION DEPENDENCY ====================

def get_current_admin_user(authorization: Optional[str] = Header(None)) -> tuple:
    """
    Dependency to extract and validate JWT token from Authorization header.
    Returns (username, is_admin) tuple.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    username = get_current_user(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # Check if user is admin
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT is_admin FROM admin_users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=401, detail="User not found")
            
            is_admin = bool(row['is_admin'])
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return username, is_admin


def require_admin(auth_info: tuple = Depends(get_current_admin_user)) -> str:
    """
    Dependency that requires admin privileges.
    """
    username, is_admin = auth_info
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return username


# ==================== AUTHENTICATION ROUTES ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Admin/User login endpoint.
    Validates credentials and returns JWT token.
    """
    logger.info(f"Login attempt for user: {request.username}")
    
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT username, password_hash, is_admin FROM admin_users WHERE username = ?",
                (request.username,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Login failed: user '{request.username}' not found")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            stored_password_hash = row['password_hash']
            is_admin = bool(row['is_admin'])
            
            # Verify password
            if not verify_password(request.password, stored_password_hash):
                logger.warning(f"Login failed: invalid password for user '{request.username}'")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Create access token
            access_token = create_access_token(data={"sub": request.username})
            
            logger.info(f"✅ Login successful for user: {request.username} (admin: {is_admin})")
            
            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                username=request.username,
                is_admin=is_admin
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    auth_info: tuple = Depends(get_current_admin_user)
):
    """
    Change user password.
    Requires current password for verification.
    """
    username, _ = auth_info
    logger.info(f"Password change request for user: {username}")
    
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT password_hash FROM admin_users WHERE username = ?",
                (username,)
            )
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Verify current password
            if not verify_password(request.current_password, row['password_hash']):
                raise HTTPException(status_code=401, detail="Current password is incorrect")
            
            # Hash new password
            new_password_hash = hash_password(request.new_password)
            
            # Update password
            conn.execute(
                "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
                (new_password_hash, username)
            )
            
            logger.info(f"✅ Password changed successfully for user: {username}")
            return {"success": True, "message": "Password changed successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ==================== USER MANAGEMENT ROUTES (ADMIN ONLY) ====================

@router.get("/users", response_model=List[UserResponse])
async def list_users(admin_username: str = Depends(require_admin)):
    """
    Get list of all users (admin only).
    """
    logger.info(f"Fetching user list for admin: {admin_username}")
    
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute("""
                SELECT id, username, is_admin, created_at, updated_at 
                FROM admin_users 
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            users = [
                UserResponse(
                    id=row['id'],
                    username=row['username'],
                    is_admin=bool(row['is_admin']),
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                for row in rows
            ]
            
            return users
            
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
    admin_username: str = Depends(require_admin)
):
    """
    Create a new user (admin only).
    """
    logger.info(f"Create user request by admin: {admin_username}")
    
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    try:
        with get_sqlite_connection() as conn:
            # Check if username already exists
            cursor = conn.execute(
                "SELECT username FROM admin_users WHERE username = ?",
                (request.username,)
            )
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username already exists")
            
            # Hash password and create user
            password_hash = hash_password(request.password)
            
            conn.execute("""
                INSERT INTO admin_users (username, password_hash, is_admin)
                VALUES (?, ?, ?)
            """, (request.username, password_hash, request.is_admin))
            
            logger.info(f"✅ User '{request.username}' created successfully by {admin_username}")
            return {"success": True, "message": f"User '{request.username}' created successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    admin_username: str = Depends(require_admin)
):
    """
    Update user (admin only).
    Can update admin status and/or password.
    """
    logger.info(f"Update user request for user_id {user_id} by admin: {admin_username}")
    
    try:
        with get_sqlite_connection() as conn:
            # Check if user exists
            cursor = conn.execute("SELECT username FROM admin_users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            username = user['username']
            
            # Prevent admin from removing their own admin privileges
            if username == admin_username and request.is_admin is False:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot remove your own admin privileges"
                )
            
            # Update fields
            updates = []
            params = []
            
            if request.is_admin is not None:
                updates.append("is_admin = ?")
                params.append(request.is_admin)
            
            if request.new_password:
                if len(request.new_password) < 6:
                    raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
                updates.append("password_hash = ?")
                params.append(hash_password(request.new_password))
            
            if not updates:
                raise HTTPException(status_code=400, detail="No updates provided")
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(user_id)
            
            query = f"UPDATE admin_users SET {', '.join(updates)} WHERE id = ?"
            conn.execute(query, params)
            
            logger.info(f"✅ User '{username}' updated successfully by {admin_username}")
            return {"success": True, "message": f"User '{username}' updated successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(status_code=500, detail="Failed to update user")


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_username: str = Depends(require_admin)
):
    """
    Delete a user (admin only).
    Cannot delete yourself.
    """
    logger.info(f"Delete user request for user_id {user_id} by admin: {admin_username}")
    
    try:
        with get_sqlite_connection() as conn:
            # Check if user exists
            cursor = conn.execute("SELECT username FROM admin_users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            username = user['username']
            
            # Prevent admin from deleting themselves
            if username == admin_username:
                raise HTTPException(status_code=400, detail="Cannot delete your own account")
            
            # Delete user
            conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
            
            logger.info(f"✅ User '{username}' deleted successfully by {admin_username}")
            return {"success": True, "message": f"User '{username}' deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user")


# ==================== QUERY MANAGEMENT ROUTES (ADMIN ONLY) ====================

@router.get("/queries")
async def list_queries(auth_info: tuple = Depends(get_current_admin_user)):
    """
    Get list of all configured queries (metadata only, no SQL).
    Available to all authenticated users, but only admins can modify.
    """
    username, is_admin = auth_info
    logger.info(f"Fetching query list for user: {username}")
    
    try:
        queries = get_all_queries()
        
        # Add default queries that aren't in database
        default_query_names = ['panel_devices', 'building_name', 'proevents', 'buildings']
        existing_names = {q['query_name'] for q in queries}
        
        for name in default_query_names:
            if name not in existing_names:
                queries.append({
                    'query_name': name,
                    'description': f'Default {name} query',
                    'created_at': None,
                    'updated_at': None
                })
        
        return {"queries": queries, "is_admin": is_admin}
        
    except Exception as e:
        logger.error(f"Error fetching queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch queries")


@router.get("/queries/{query_name}", response_model=QueryResponse)
async def get_query_details(
    query_name: str,
    auth_info: tuple = Depends(get_current_admin_user)
):
    """
    Get full details of a specific query including SQL.
    """
    username, _ = auth_info
    logger.info(f"Fetching query '{query_name}' for user: {username}")
    
    try:
        query_data = get_query_with_sql(query_name)
        
        if not query_data:
            raise HTTPException(status_code=404, detail=f"Query '{query_name}' not found")
        
        return QueryResponse(**query_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching query '{query_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch query")


@router.post("/queries", response_model=QueryUpdateResponse)
async def update_query(
    request: QueryRequest,
    admin_username: str = Depends(require_admin)
):
    """
    Create or update a query configuration (admin only).
    Validates SQL before saving.
    """
    logger.info(f"Update query request for '{request.query_name}' by admin: {admin_username}")
    
    # Validate query syntax
    is_valid, error_message = validate_query_syntax(request.query_sql)
    if not is_valid:
        logger.warning(f"Query validation failed: {error_message}")
        raise HTTPException(status_code=400, detail=f"Invalid query: {error_message}")
    
    try:
        success = set_query(request.query_name, request.query_sql, request.description)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save query")
        
        return QueryUpdateResponse(
            success=True,
            message=f"Query '{request.query_name}' saved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving query '{request.query_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to save query")


@router.delete("/queries/{query_name}", response_model=QueryUpdateResponse)
async def delete_query_endpoint(
    query_name: str,
    admin_username: str = Depends(require_admin)
):
    """
    Delete a query configuration (will revert to default) - admin only.
    """
    logger.info(f"Delete query request for '{query_name}' by admin: {admin_username}")
    
    try:
        success = delete_query(query_name)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete query")
        
        return QueryUpdateResponse(
            success=True,
            message=f"Query '{query_name}' deleted successfully (reverted to default)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting query '{query_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to delete query")


@router.post("/queries/{query_name}/test")
async def test_query(
    query_name: str,
    admin_username: str = Depends(require_admin)
):
    """
    Test a query by validating its syntax (admin only).
    """
    logger.info(f"Test query request for '{query_name}' by admin: {admin_username}")
    
    try:
        query_sql = get_query(query_name)
        
        if not query_sql:
            raise HTTPException(status_code=404, detail=f"Query '{query_name}' not found")
        
        # Validate syntax
        is_valid, error_message = validate_query_syntax(query_sql)
        if not is_valid:
            return {
                "success": False,
                "message": f"Query validation failed: {error_message}"
            }
        
        return {
            "success": True,
            "message": "Query syntax is valid",
            "query_sql": query_sql
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing query '{query_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to test query")


@router.get("/queries/{query_name}/default")
async def get_default_query_endpoint(
    query_name: str,
    admin_username: str = Depends(require_admin)
):
    """
    Get the default (hardcoded) query for a given query name (admin only).
    Useful for resetting to defaults.
    """
    logger.info(f"Fetching default query for '{query_name}'")
    
    try:
        default_query = get_default_query(query_name)
        
        if not default_query:
            raise HTTPException(
                status_code=404,
                detail=f"No default query found for '{query_name}'"
            )
        
        return {
            "query_name": query_name,
            "query_sql": default_query,
            "description": f"Default {query_name} query"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching default query '{query_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch default query")