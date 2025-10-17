import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from services.supabase_service import SupabaseService
from helpers import GmailHelpers, GCalendarHelpers, NotionHelpers, SlackHelpers, DiscordHelpers
import os

logger = logging.getLogger(__name__)

class ProxyService:
    """
    Service to handle proxy requests to third-party APIs using user-specific OAuth tokens.
    Now uses helper functions with official SDKs instead of raw API calls.
    """
    
    def __init__(self):
        self.supabase_service = SupabaseService()
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.gmail_helpers = GmailHelpers()
        self.gcalendar_helpers = GCalendarHelpers()
        self.notion_helpers = NotionHelpers()
        self.slack_helpers = SlackHelpers()
        self.discord_helpers = DiscordHelpers()
    
    async def execute_function_call(
        self,
        user_id: str,
        app_name: str,
        function_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single function call using helper functions.
        
        Args:
            user_id: User's unique identifier
            app_name: Name of the app (gmail, gcalendar, etc.)
            function_name: Name of the function to call
            parameters: Function parameters
            
        Returns:
            Dict with function execution result
        """
        try:
            logger.info(f"Executing {app_name}.{function_name} for user: {user_id}")
            
            credentials = await self.supabase_service.get_user_app_credentials(
                user_id=user_id,
                app_name=app_name
            )
            
            if not credentials:
                return {
                    "success": False,
                    "error": f"No credentials found for {app_name}. Please connect your account first."
                }
            
            if self._is_token_expired(credentials):
                logger.info(f"Token expired, refreshing for {app_name}")
                refresh_result = await self._refresh_access_token(user_id, app_name, credentials)
                
                if not refresh_result["success"]:
                    return {
                        "success": False,
                        "error": refresh_result.get("error", "Failed to refresh token")
                    }
                
                credentials = refresh_result["credentials"]
            
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                return {
                    "success": False,
                    "error": f"Invalid credentials for {app_name}"
                }
            
            if app_name == "gmail":
                return await self._execute_gmail_function(access_token, function_name, parameters)
            elif app_name == "gcalendar":
                return await self._execute_gcalendar_function(access_token, function_name, parameters)
            elif app_name == "notion":
                return await self._execute_notion_function(access_token, function_name, parameters)
            elif app_name == "slack":
                return await self._execute_slack_function(access_token, function_name, parameters)
            elif app_name == "discord":
                return await self._execute_discord_function(access_token, function_name, parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported app: {app_name}"
                }
                
        except Exception as e:
            logger.error(f"Error executing function call: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _execute_gmail_function(
        self,
        access_token: str,
        function_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Gmail helper function."""
        try:
            if function_name == "list_messages":
                return await self.gmail_helpers.list_messages(access_token, **parameters)
            elif function_name == "get_message":
                return await self.gmail_helpers.get_message(access_token, **parameters)
            elif function_name == "send_message":
                return await self.gmail_helpers.send_message(access_token, **parameters)
            elif function_name == "delete_message":
                return await self.gmail_helpers.delete_message(access_token, **parameters)
            elif function_name == "modify_message":
                return await self.gmail_helpers.modify_message(access_token, **parameters)
            elif function_name == "create_draft":
                return await self.gmail_helpers.create_draft(access_token, **parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown Gmail function: {function_name}"
                }
        except Exception as e:
            logger.error(f"Gmail function error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_gcalendar_function(
        self,
        access_token: str,
        function_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Google Calendar helper function."""
        try:
            if function_name == "list_events":
                return await self.gcalendar_helpers.list_events(access_token, **parameters)
            elif function_name == "create_event":
                return await self.gcalendar_helpers.create_event(access_token, **parameters)
            elif function_name == "get_event":
                return await self.gcalendar_helpers.get_event(access_token, **parameters)
            elif function_name == "update_event":
                return await self.gcalendar_helpers.update_event(access_token, **parameters)
            elif function_name == "delete_event":
                return await self.gcalendar_helpers.delete_event(access_token, **parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown Google Calendar function: {function_name}"
                }
        except Exception as e:
            logger.error(f"Google Calendar function error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_notion_function(
        self,
        access_token: str,
        function_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Notion helper function."""
        try:
            if function_name == "create_page":
                return await self.notion_helpers.create_page(access_token, **parameters)
            elif function_name == "get_page":
                return await self.notion_helpers.get_page(access_token, **parameters)
            elif function_name == "update_page":
                return await self.notion_helpers.update_page(access_token, **parameters)
            elif function_name == "query_database":
                return await self.notion_helpers.query_database(access_token, **parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown Notion function: {function_name}"
                }
        except Exception as e:
            logger.error(f"Notion function error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_slack_function(
        self,
        access_token: str,
        function_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Slack helper function."""
        try:
            if function_name == "send_message":
                return await self.slack_helpers.send_message(access_token, **parameters)
            elif function_name == "list_channels":
                return await self.slack_helpers.list_channels(access_token, **parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown Slack function: {function_name}"
                }
        except Exception as e:
            logger.error(f"Slack function error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_discord_function(
        self,
        access_token: str,
        function_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Discord helper function."""
        try:
            if function_name == "send_message":
                return await self.discord_helpers.send_message(access_token, **parameters)
            elif function_name == "get_channel":
                return await self.discord_helpers.get_channel(access_token, **parameters)
            else:
                return {
                    "success": False,
                    "error": f"Unknown Discord function: {function_name}"
                }
        except Exception as e:
            logger.error(f"Discord function error: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _refresh_access_token(
        self,
        user_id: str,
        app_name: str,
        credentials: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Refresh expired access token using refresh token
        
        Args:
            user_id: User's unique identifier
            app_name: Name of the app
            credentials: Current credentials with refresh_token
            
        Returns:
            Dict with success status and new credentials
        """
        try:
            refresh_token = credentials.get("refresh_token")
            
            if not refresh_token:
                logger.error(f"No refresh token found for {app_name}")
                return {
                    "success": False,
                    "error": "No refresh token available. Please reconnect your account."
                }
            
            token_endpoint = None
            client_id = None
            client_secret = None
            
            app_type = app_name.lower()
            
            if app_type in ["gmail", "calendar", "gdrive"]:
                token_endpoint = "https://oauth2.googleapis.com/token"
                client_id = credentials.get("client_id") or os.getenv("GOOGLE_CLIENT_ID")
                client_secret = credentials.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET")
            
            elif app_type == "slack":
                token_endpoint = "https://slack.com/api/oauth.v2.access"
                client_id = credentials.get("client_id") or os.getenv("SLACK_CLIENT_ID")
                client_secret = credentials.get("client_secret") or os.getenv("SLACK_CLIENT_SECRET")
            
            elif app_type == "notion":
                token_endpoint = "https://api.notion.com/v1/oauth/token"
                client_id = credentials.get("client_id") or os.getenv("NOTION_CLIENT_ID")
                client_secret = credentials.get("client_secret") or os.getenv("NOTION_CLIENT_SECRET")
            
            else:
                return {
                    "success": False,
                    "error": f"Token refresh not supported for {app_name}"
                }
            
            if not token_endpoint or not client_id or not client_secret:
                logger.error(f"Missing OAuth configuration for {app_name}")
                return {
                    "success": False,
                    "error": "OAuth configuration missing. Please reconnect your account."
                }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                data = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret
                }
                
                response = await client.post(token_endpoint, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data.get("expires_in", 3600)
                
                if not new_access_token:
                    return {
                        "success": False,
                        "error": "Failed to obtain new access token"
                    }
                
                expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                
                new_credentials = {
                    **credentials,
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_at": expires_at,
                    "expires_in": expires_in
                }
                
                await self.supabase_service.update_user_credentials(
                    user_id=user_id,
                    app_name=app_name,
                    credentials=new_credentials
                )
                
                logger.info(f"Successfully refreshed token for {app_name}, expires at {expires_at}")
                
                return {
                    "success": True,
                    "credentials": new_credentials
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error refreshing token: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"Failed to refresh token: {e.response.status_code}"
            }
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return {
                "success": False,
                "error": f"Token refresh error: {str(e)}"
            }
    
    def _extract_access_token(self, credentials: Dict[str, Any]) -> Optional[str]:
        if "access_token" in credentials:
            return credentials["access_token"]
        
        if "credentials" in credentials and isinstance(credentials["credentials"], dict):
            if "access_token" in credentials["credentials"]:
                return credentials["credentials"]["access_token"]
        
        if "data" in credentials and isinstance(credentials["data"], dict):
            if "access_token" in credentials["data"]:
                return credentials["data"]["access_token"]
        
        return None
    
    def _is_token_expired(self, credentials: Dict[str, Any]) -> bool:
        try:
            expires_at = None
            
            if "expires_at" in credentials:
                expires_at = credentials["expires_at"]
            elif "credentials" in credentials and isinstance(credentials["credentials"], dict):
                expires_at = credentials["credentials"].get("expires_at")
            elif "metadata" in credentials and isinstance(credentials["metadata"], dict):
                expires_at = credentials["metadata"].get("expires_at")
            
            if not expires_at:
                logger.warning("No expiration info found in credentials, assuming token is valid")
                return False
            
            if isinstance(expires_at, str):
                expires_at_str = expires_at.replace('Z', '')
                if '+' in expires_at_str or expires_at_str.endswith('+00:00'):
                    expires_at_dt = datetime.fromisoformat(expires_at_str.replace('+00:00', ''))
                else:
                    expires_at_dt = datetime.fromisoformat(expires_at_str)
            elif isinstance(expires_at, (int, float)):
                expires_at_dt = datetime.utcfromtimestamp(expires_at)
            else:
                expires_at_dt = expires_at
            
            current_time = datetime.utcnow()
            buffer_minutes = 5
            is_expired = current_time >= (expires_at_dt - timedelta(minutes=buffer_minutes))
            
            if is_expired:
                logger.info(f"Token is expired or expiring soon. Current time (UTC): {current_time}, Expires at: {expires_at_dt}")
            
            return is_expired
            
        except Exception as e:
            logger.warning(f"Error checking token expiration: {str(e)}")
            return True
