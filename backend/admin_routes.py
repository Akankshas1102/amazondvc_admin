"""
Admin API Routes
================
Handles all admin panel operations including:
- Authentication (login/logout)
- Query configuration management
- System settings

All routes require JWT authentication except /login
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
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


# ==================== AUTHENTICATION DEPENDENCY ====================

def get_current_admin_user(authorization: Optional[str] = Header(None)) -> str:
    """
    Dependency to extract and validate JWT token from Authorization header.
    
    Usage in routes:
        @router.get("/protected")
        def protected_route(username: str = Depends(get_current_admin_user)):
            # username is now available
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    username = get_current_user(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return username


# ==================== AUTHENTICATION ROUTES ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Admin login endpoint.
    Validates credentials and returns JWT token.
    """
    logger.info(f"Login attempt for user: {request.username}")
    
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT username, password_hash FROM admin_users WHERE username = ?",
                (request.username,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"Login failed: user '{request.username}' not found")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            stored_password_hash = row['password_hash']
            
            # Verify password
            if not verify_password(request.password, stored_password_hash):
                logger.warning(f"Login failed: invalid password for user '{request.username}'")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            # Create access token
            access_token = create_access_token(data={"sub": request.username})
            
            logger.info(f"✅ Login successful for user: {request.username}")
            
            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                username=request.username
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    username: str = Depends(get_current_admin_user)
):
    """
    Change admin password.
    Requires current password for verification.
    """
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


# ==================== QUERY MANAGEMENT ROUTES ====================

@router.get("/queries")
async def list_queries(username: str = Depends(get_current_admin_user)):
    """
    Get list of all configured queries (metadata only, no SQL).
    """
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
        
        return {"queries": queries}
        
    except Exception as e:
        logger.error(f"Error fetching queries: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch queries")


@router.get("/queries/{query_name}", response_model=QueryResponse)
async def get_query_details(
    query_name: str,
    username: str = Depends(get_current_admin_user)
):
    """
    Get full details of a specific query including SQL.
    """
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
    username: str = Depends(get_current_admin_user)
):
    """
    Create or update a query configuration.
    Validates SQL before saving.
    """
    logger.info(f"Update query request for '{request.query_name}' by user: {username}")
    
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
    username: str = Depends(get_current_admin_user)
):
    """
    Delete a query configuration (will revert to default).
    """
    logger.info(f"Delete query request for '{query_name}' by user: {username}")
    
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
    username: str = Depends(get_current_admin_user)
):
    """
    Test a query by executing it with sample parameters.
    ⚠️ Use with caution - only for validation!
    """
    logger.info(f"Test query request for '{query_name}' by user: {username}")
    
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
    username: str = Depends(get_current_admin_user)
):
    """
    Get the default (hardcoded) query for a given query name.
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