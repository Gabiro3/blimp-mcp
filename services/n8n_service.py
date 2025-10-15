import os
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class N8nService:
    """Service for interacting with n8n workflows via webhooks"""
    
    def __init__(self):
        self.base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678")
        logger.info("N8nService initialized for webhook-based workflow triggering")
    
    async def trigger_workflow_webhook(
        self,
        webhook_url: str,
        user_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger an n8n workflow via webhook URL (GET request)
        
        Args:
            webhook_url: Full webhook URL for the workflow
            user_id: User's unique identifier
            parameters: Workflow parameters to pass as query params
            
        Returns:
            Dictionary containing execution result
        """
        try:
            query_params = {
                "user_id": user_id,
                **parameters
            }
            
            logger.info(f"Triggering workflow webhook: {webhook_url}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    webhook_url,
                    params=query_params,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text}
                    logger.info(f"Workflow webhook triggered successfully")
                    return {
                        "success": True,
                        "execution_id": result.get("executionId", f"webhook_{user_id}_{hash(webhook_url)}"),
                        "data": result
                    }
                else:
                    logger.error(f"Failed to trigger workflow webhook: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error triggering n8n workflow webhook: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def trigger_workflow(
        self,
        workflow_id: str,
        user_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger an n8n workflow
        
        Args:
            workflow_id: n8n workflow identifier
            user_id: User's unique identifier
            parameters: Workflow parameters
            
        Returns:
            Dictionary containing execution result
        """
        try:
            # Prepare webhook URL or API endpoint
            # n8n supports both webhook triggers and API-based execution
            url = f"{self.base_url}/api/v1/workflows/{workflow_id}/execute"
            
            payload = {
                "user_id": user_id,
                "parameters": parameters
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Workflow triggered successfully: {workflow_id}")
                    return {
                        "success": True,
                        "execution_id": result.get("data", {}).get("executionId"),
                        "data": result
                    }
                else:
                    logger.error(f"Failed to trigger workflow: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error triggering n8n workflow: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Get the status of a workflow execution
        
        Args:
            execution_id: Execution identifier
            
        Returns:
            Dictionary containing execution status
        """
        try:
            url = f"{self.base_url}/api/v1/executions/{execution_id}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "status": result.get("data", {}).get("status"),
                        "data": result
                    }
                else:
                    logger.error(f"Failed to get execution status: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error getting execution status: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_workflow_details(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get workflow details from n8n
        
        Args:
            workflow_id: Workflow identifier
            
        Returns:
            Workflow details or None
        """
        try:
            url = f"{self.base_url}/api/v1/workflows/{workflow_id}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get workflow details: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting workflow details: {str(e)}")
            return None
    
    async def create_user_credential(
        self,
        user_id: str,
        app_type: str,
        credentials: Dict[str, Any],
        credential_name: str
    ) -> Optional[str]:
        """
        Create or update user-specific credentials in n8n
        
        Args:
            user_id: User's unique identifier
            app_type: Type of app (e.g., "gmail", "slack")
            credentials: OAuth credentials
            credential_name: Name for the credential in n8n
            
        Returns:
            n8n credential ID or None
        """
        try:
            # Map app_type to n8n credential type
            credential_type_map = {
                "gmail": "gmailOAuth2",
                "slack": "slackOAuth2",
                "google_sheets": "googleSheetsOAuth2",
                "google_drive": "googleDriveOAuth2",
                "trello": "trelloOAuth2",
                "notion": "notionOAuth2",
                # Add more mappings as needed
            }
            
            n8n_credential_type = credential_type_map.get(app_type)
            if not n8n_credential_type:
                logger.warning(f"No n8n credential type mapping for {app_type}")
                return None
            
            # Prepare credential data for n8n
            credential_data = {
                "name": credential_name,
                "type": n8n_credential_type,
                "data": {
                    "oauthTokenData": {
                        "access_token": credentials.get("access_token"),
                        "refresh_token": credentials.get("refresh_token"),
                        "token_type": credentials.get("token_type", "Bearer"),
                        "expires_in": credentials.get("expiry_date"),
                        "scope": credentials.get("scope")
                    }
                }
            }
            
            # Check if credential already exists
            url = f"{self.base_url}/api/v1/credentials"
            
            async with httpx.AsyncClient() as client:
                # Try to find existing credential
                get_response = await client.get(
                    url,
                    params={"filter": f'{{"name": "{credential_name}"}}'},
                    timeout=10.0
                )
                
                if get_response.status_code == 200:
                    existing_creds = get_response.json().get("data", [])
                    
                    if existing_creds:
                        # Update existing credential
                        credential_id = existing_creds[0]["id"]
                        update_url = f"{url}/{credential_id}"
                        
                        update_response = await client.patch(
                            update_url,
                            json=credential_data,
                            timeout=10.0
                        )
                        
                        if update_response.status_code == 200:
                            logger.info(f"Updated n8n credential: {credential_id}")
                            return credential_id
                    else:
                        # Create new credential
                        create_response = await client.post(
                            url,
                            json=credential_data,
                            timeout=10.0
                        )
                        
                        if create_response.status_code == 201:
                            result = create_response.json()
                            credential_id = result.get("data", {}).get("id")
                            logger.info(f"Created n8n credential: {credential_id}")
                            return credential_id
                
                logger.error(f"Failed to create/update n8n credential")
                return None
                
        except Exception as e:
            logger.error(f"Error creating n8n credential: {str(e)}")
            return None
    
    async def trigger_workflow_with_credentials(
        self,
        workflow_id: str,
        user_id: str,
        user_credentials: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Trigger an n8n workflow with user-specific credentials
        
        Args:
            workflow_id: n8n workflow identifier
            user_id: User's unique identifier
            user_credentials: User's app credentials
            parameters: Workflow parameters
            
        Returns:
            Dictionary containing execution result
        """
        try:
            # Prepare webhook URL or API endpoint
            url = f"{self.base_url}/api/v1/workflows/{workflow_id}/execute"
            
            # Include user credentials in the payload
            payload = {
                "user_id": user_id,
                "parameters": parameters,
                "user_credentials": user_credentials  # Pass credentials to workflow
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Workflow triggered successfully with user credentials: {workflow_id}")
                    return {
                        "success": True,
                        "execution_id": result.get("data", {}).get("executionId"),
                        "data": result
                    }
                else:
                    logger.error(f"Failed to trigger workflow: {response.status_code}")
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}"
                    }
                    
        except Exception as e:
            logger.error(f"Error triggering n8n workflow: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
