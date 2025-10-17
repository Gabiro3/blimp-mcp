import os
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from datetime import datetime

logger = logging.getLogger(__name__)


class SupabaseService:
    """Service for interacting with Supabase database"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not self.url or not self.key:
            logger.warning("Supabase credentials not found in environment variables")
            self.client = None
        else:
            self.client: Client = create_client(self.url, self.key)
    
    async def get_user_connected_apps(self, user_id: str) -> List[str]:
        """
        Get list of apps that user has connected
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            List of connected app names
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return []
            
            # Query the user_connected_apps table
            response = self.client.table("user_connected_apps").select("app_name").eq("user_id", user_id).eq("is_active", True).execute()
            
            if response.data:
                connected_apps = [row["app_name"] for row in response.data]
                logger.info(f"Found {len(connected_apps)} connected apps for user {user_id}")
                return connected_apps
            
            logger.info(f"No connected apps found for user {user_id}")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching connected apps: {str(e)}")
            return []
    
    async def save_workflow_execution(
        self,
        user_id: str,
        workflow_id: str,
        execution_id: str,
        status: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Save workflow execution to database
        
        Args:
            user_id: User's unique identifier
            workflow_id: Workflow identifier
            execution_id: Execution identifier from n8n
            status: Execution status
            parameters: Workflow parameters
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False
            
            data = {
                "user_id": user_id,
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "status": status,
                "parameters": parameters or {},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self.client.table("workflow_executions").insert(data).execute()
            
            if response.data:
                logger.info(f"Workflow execution saved: {execution_id}")
                return True
            
            logger.error("Failed to save workflow execution")
            return False
            
        except Exception as e:
            logger.error(f"Error saving workflow execution: {str(e)}")
            return False
    
    async def get_workflow_execution(
        self,
        execution_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get workflow execution details from database
        
        Args:
            execution_id: Execution identifier
            user_id: User's unique identifier
            
        Returns:
            Workflow execution data or None
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            response = self.client.table("workflow_executions").select("*").eq("execution_id", execution_id).eq("user_id", user_id).single().execute()
            
            if response.data:
                return response.data
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching workflow execution: {str(e)}")
            return None
    
    async def update_workflow_status(
        self,
        execution_id: str,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update workflow execution status
        
        Args:
            execution_id: Execution identifier
            status: New status
            result: Execution result data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False
            
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if result:
                update_data["result"] = result
            
            response = self.client.table("workflow_executions").update(update_data).eq("execution_id", execution_id).execute()
            
            if response.data:
                logger.info(f"Workflow status updated: {execution_id} -> {status}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating workflow status: {str(e)}")
            return False
    
    async def store_user_credentials(
        self,
        user_id: str,
        app_name: str,
        app_type: str,
        credentials: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Store user's OAuth credentials for an app
        
        Args:
            user_id: User's unique identifier
            app_name: Name of the app (e.g., "Gmail")
            app_type: Type of the app (e.g., "gmail")
            credentials: OAuth credentials (access_token, refresh_token, etc.)
            metadata: Additional metadata (email, scopes, etc.)
            
        Returns:
            Credential ID if successful, None otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            # Check if credential already exists
            existing = self.client.table("user_credentials").select("id").eq("user_id", user_id).eq("app_type", app_type).execute()
            
            data = {
                "user_id": user_id,
                "app_name": app_name,
                "app_type": app_type,
                "credentials": credentials,  # Store encrypted in production
                "metadata": metadata,
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if existing.data:
                # Update existing credential
                credential_id = existing.data[0]["id"]
                response = self.client.table("user_credentials").update(data).eq("id", credential_id).execute()
                logger.info(f"Updated credentials for {app_name}: {credential_id}")
            else:
                # Insert new credential
                data["created_at"] = datetime.utcnow().isoformat()
                response = self.client.table("user_credentials").insert(data).execute()
                credential_id = response.data[0]["id"] if response.data else None
                logger.info(f"Stored new credentials for {app_name}: {credential_id}")
            
            # Also update user_connected_apps table for quick lookup
            await self._update_connected_apps(user_id, app_name, app_type)
            
            return credential_id
            
        except Exception as e:
            logger.error(f"Error storing user credentials: {str(e)}")
            return None
    
    async def _update_connected_apps(
        self,
        user_id: str,
        app_name: str,
        app_type: str
    ) -> bool:
        """Update the user_connected_apps table for quick lookup"""
        try:
            if not self.client:
                return False
            
            existing = self.client.table("user_connected_apps").select("id").eq("user_id", user_id).eq("app_type", app_type).execute()
            
            data = {
                "user_id": user_id,
                "app_name": app_name,
                "app_type": app_type,
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if existing.data:
                self.client.table("user_connected_apps").update(data).eq("id", existing.data[0]["id"]).execute()
            else:
                data["created_at"] = datetime.utcnow().isoformat()
                self.client.table("user_connected_apps").insert(data).execute()
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating connected apps: {str(e)}")
            return False
    
    async def get_user_workflow_credentials(
        self,
        user_id: str,
        workflow_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's credentials needed for a specific workflow
        
        Args:
            user_id: User's unique identifier
            workflow_id: Workflow identifier
            
        Returns:
            Dictionary mapping app_type to credentials
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            # Get all active credentials for user
            response = self.client.table("user_credentials").select("app_type, credentials, metadata").eq("user_id", user_id).eq("is_active", True).execute()
            
            if not response.data:
                logger.warning(f"No credentials found for user {user_id}")
                return None
            
            # Build credentials dictionary
            credentials_map = {}
            for row in response.data:
                credentials_map[row["app_type"]] = {
                    "credentials": row["credentials"],
                    "metadata": row["metadata"]
                }
            
            logger.info(f"Retrieved {len(credentials_map)} credentials for user {user_id}")
            return credentials_map
            
        except Exception as e:
            logger.error(f"Error fetching user workflow credentials: {str(e)}")
            return None
    
    async def get_user_app_credentials(
        self,
        user_id: str,
        app_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get user's credentials for a specific app
        
        Args:
            user_id: User's unique identifier
            app_name: Name of app (e.g., "gmail", "slack", "notion")
            
        Returns:
            Credentials dictionary with access_token and other OAuth data, or None
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            logger.info(f"[DEBUG] Fetching credentials - user_id: '{user_id}', app_name: '{app_name}'")
            
            # Validate user_id is not empty
            if not user_id or user_id.strip() == "":
                logger.error(f"[ERROR] user_id is empty or None! user_id value: '{user_id}'")
                return None
            
            # Normalize app_name to app_type (lowercase)
            app_type = app_name.lower()
            
            logger.info(f"[DEBUG] Querying Supabase with user_id='{user_id}', app_type='{app_type}'")
            
            response = self.client.table("user_credentials").select("credentials, metadata").eq("user_id", user_id).eq("app_type", app_type).eq("is_active", True).single().execute()
            
            logger.info(f"[DEBUG] Supabase response status: {response.status_code if hasattr(response, 'status_code') else 'N/A'}")
            logger.info(f"[DEBUG] Supabase response data: {response.data}")
            
            if response.data and response.data.get("credentials"):
                logger.info(f"Retrieved credentials for {app_name} for user {user_id}")
                return response.data["credentials"]
            
            logger.warning(f"No credentials found for {app_name} for user {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching app credentials: {str(e)}")
            logger.exception(e)  # Add full exception traceback
            return None
    
    async def get_workflow_webhook_url(
        self,
        workflow_id: str
    ) -> Optional[str]:
        """
        Get webhook URL for a workflow template by its ID
        
        Args:
            workflow_id: Workflow template identifier
            
        Returns:
            Webhook URL string or None if not found
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            response = self.client.table("workflow_templates").select("webhook_url").eq("id", workflow_id).eq("is_active", True).single().execute()
            
            if response.data and response.data.get("webhook_url"):
                webhook_url = response.data["webhook_url"]
                logger.info(f"Retrieved webhook URL for workflow {workflow_id}")
                return webhook_url
            
            logger.warning(f"No webhook URL found for workflow {workflow_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching workflow webhook URL: {str(e)}")
            return None
    
    async def update_user_credentials(
        self,
        user_id: str,
        app_name: str,
        credentials: Dict[str, Any]
    ) -> bool:
        """
        Update user's credentials in the database (e.g., after token refresh)
        
        Args:
            user_id: User's unique identifier
            app_name: Name of the app (e.g., "gmail", "slack")
            credentials: Updated credentials dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False
            
            app_type = app_name.lower()
            
            update_data = {
                "credentials": credentials,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self.client.table("user_credentials").update(update_data).eq("user_id", user_id).eq("app_type", app_type).execute()
            
            if response.data:
                logger.info(f"Updated credentials for {app_name} for user {user_id}")
                return True
            
            logger.error(f"Failed to update credentials for {app_name}")
            return False
            
        except Exception as e:
            logger.error(f"Error updating user credentials: {str(e)}")
            return False
    
    async def get_all_workflow_templates(self) -> List[Dict[str, Any]]:
        """
        Get all active workflow templates from the database
        
        Returns:
            List of workflow template dictionaries with id, name, description, and required_apps
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return []
            
            response = self.client.table("workflow_templates").select("id, name, description, required_apps, category").eq("is_active", True).execute()
            
            if response.data:
                logger.info(f"Retrieved {len(response.data)} workflow templates")
                return response.data
            
            logger.info("No workflow templates found")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching workflow templates: {str(e)}")
            return []
    
    async def get_workflow(
        self,
        workflow_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific workflow by ID for a user
        
        Args:
            workflow_id: Workflow identifier
            user_id: User's unique identifier
            
        Returns:
            Workflow data dictionary or None if not found
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            logger.info(f"Fetching workflow {workflow_id} for user {user_id}")
            
            # Try to fetch from workflow_templates first (for predefined workflows)
            response = self.client.table("workflow_templates").select("*").eq("id", workflow_id).eq("is_active", True).single().execute()
            
            if response.data:
                logger.info(f"Found workflow template: {workflow_id}")
                return response.data
            
            # If not found in templates, try user-specific workflows
            response = self.client.table("user_workflows").select("*").eq("id", workflow_id).eq("user_id", user_id).eq("is_active", True).single().execute()
            
            if response.data:
                logger.info(f"Found user workflow: {workflow_id}")
                return response.data
            
            logger.warning(f"Workflow {workflow_id} not found for user {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching workflow: {str(e)}")
            logger.exception(e)
            return None
    
    async def save_user_workflow(
        self,
        user_id: str,
        workflow_id: str,
        name: str,
        description: str,
        prompt: str,
        required_apps: List[str],
        category: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> bool:
        """
        Save a user-specific workflow to the database
        
        Args:
            user_id: User's unique identifier
            workflow_id: Workflow identifier
            name: Workflow name
            description: Workflow description
            prompt: Original prompt that created this workflow
            required_apps: List of required app names
            category: Optional category
            webhook_url: Optional webhook URL
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return False
            
            data = {
                "id": workflow_id,
                "user_id": user_id,
                "name": name,
                "description": description,
                "prompt": prompt,
                "required_apps": required_apps,
                "category": category or "custom",
                "webhook_url": webhook_url,
                "is_active": True,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Check if workflow already exists
            existing = self.client.table("user_workflows").select("id").eq("id", workflow_id).eq("user_id", user_id).execute()
            
            if existing.data:
                # Update existing workflow
                response = self.client.table("user_workflows").update(data).eq("id", workflow_id).eq("user_id", user_id).execute()
                logger.info(f"Updated user workflow: {workflow_id}")
            else:
                # Insert new workflow
                response = self.client.table("user_workflows").insert(data).execute()
                logger.info(f"Saved new user workflow: {workflow_id}")
            
            return bool(response.data)
            
        except Exception as e:
            logger.error(f"Error saving user workflow: {str(e)}")
            logger.exception(e)
            return False


    async def store_user_credentials(
        self,
        user_id: str,
        app_name: str,
        app_type: str,
        credentials: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Store user's OAuth credentials for an app
        
        Args:
            user_id: User's unique identifier
            app_name: Name of the app (e.g., "Gmail")
            app_type: Type of the app (e.g., "gmail")
            credentials: OAuth credentials (access_token, refresh_token, etc.)
            metadata: Additional metadata (email, scopes, etc.)
            
        Returns:
            Credential ID if successful, None otherwise
        """
        try:
            if not self.client:
                logger.error("Supabase client not initialized")
                return None
            
            # Check if credential already exists
            existing = self.client.table("user_credentials").select("id").eq("user_id", user_id).eq("app_type", app_type).execute()
            
            data = {
                "user_id": user_id,
                "app_name": app_name,
                "app_type": app_type,
                "credentials": credentials,  # Store encrypted in production
                "metadata": metadata,
                "is_active": True,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if existing.data:
                # Update existing credential
                credential_id = existing.data[0]["id"]
                response = self.client.table("user_credentials").update(data).eq("id", credential_id).execute()
                logger.info(f"Updated credentials for {app_name}: {credential_id}")
            else:
                # Insert new credential
                data["created_at"] = datetime.utcnow().isoformat()
                response = self.client.table("user_credentials").insert(data).execute()
                credential_id = response.data[0]["id"] if response.data else None
                logger.info(f"Stored new credentials for {app_name}: {credential_id}")
            
            # Also update user_connected_apps table for quick lookup
            await self._update_connected_apps(user_id, app_name, app_type)
            
            return credential_id
            
        except Exception as e:
            logger.error(f"Error storing user credentials: {str(e)}")
            return None