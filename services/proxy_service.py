import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from services.supabase_service import SupabaseService
import os

logger = logging.getLogger(__name__)

class ProxyService:
    """
    Service to handle proxy requests to third-party APIs using user-specific OAuth tokens
    """
    
    def __init__(self):
        self.supabase_service = SupabaseService()
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
    async def proxy_request(
        self,
        user_id: str,
        app_name: str,
        action: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Main proxy method that routes requests to appropriate app handlers
        """
        try:
            logger.info(f"[DEBUG] proxy_request called with user_id: '{user_id}', app_name: '{app_name}', action: '{action}'")
            
            if not user_id or user_id.strip() == "":
                logger.error(f"[ERROR] user_id is empty or None in proxy_request!")
                return {
                    "success": False,
                    "error": "user_id is required but was not provided"
                }
            
            logger.info(f"Proxying {app_name}/{action} for user: {user_id}")
            
            # Fetch user credentials for the app
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
                logger.info(f"Access token expired for user {user_id} and app {app_name}, attempting refresh...")
                
                refresh_result = await self._refresh_access_token(user_id, app_name, credentials)
                
                if not refresh_result["success"]:
                    return {
                        "success": False,
                        "error": refresh_result.get("error", "Failed to refresh token"),
                        "error_code": "TOKEN_REFRESH_FAILED",
                        "requires_reconnect": True
                    }
                
                # Use the new credentials
                credentials = refresh_result["credentials"]
                logger.info(f"Successfully refreshed token for {app_name}")
            
            # Extract access token from credentials (handle nested structure)
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                logger.error(f"No access token found in credentials for {app_name}")
                logger.error(f"Credentials structure: {credentials}")
                return {
                    "success": False,
                    "error": f"Invalid credentials for {app_name}. Please reconnect your account.",
                    "error_code": "INVALID_CREDENTIALS"
                }
            
            logger.info(f"[DEBUG] Access token found for {app_name}, length: {len(access_token)}")
            
            # Route to appropriate handler based on app_name
            if app_name == "gmail":
                return await self._handle_gmail(action, credentials, payload)
            elif app_name == "slack":
                return await self._handle_slack(action, credentials, payload)
            elif app_name == "notion":
                return await self._handle_notion(action, credentials, payload)
            elif app_name == "calendar":
                return await self._handle_calendar(action, credentials, payload)
            elif app_name == "gdrive":
                return await self._handle_gdrive(action, credentials, payload)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported app: {app_name}"
                }
                
        except Exception as e:
            logger.error(f"Error in proxy request: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
            
            # Determine OAuth provider and token endpoint
            token_endpoint = None
            client_id = None
            client_secret = None
            
            app_type = app_name.lower()
            
            # Google apps (Gmail, Calendar, Drive)
            if app_type in ["gmail", "calendar", "gdrive"]:
                token_endpoint = "https://oauth2.googleapis.com/token"
                client_id = credentials.get("client_id") or os.getenv("GOOGLE_CLIENT_ID")
                client_secret = credentials.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET")
            
            # Slack
            elif app_type == "slack":
                token_endpoint = "https://slack.com/api/oauth.v2.access"
                client_id = credentials.get("client_id") or os.getenv("SLACK_CLIENT_ID")
                client_secret = credentials.get("client_secret") or os.getenv("SLACK_CLIENT_SECRET")
            
            # Notion
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
            
            # Make token refresh request
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
                
                # Extract new access token
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token", refresh_token)  # Some providers don't return new refresh token
                expires_in = token_data.get("expires_in", 3600)
                
                if not new_access_token:
                    return {
                        "success": False,
                        "error": "Failed to obtain new access token"
                    }
                
                # Calculate expiration time
                expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                
                # Update credentials
                new_credentials = {
                    **credentials,
                    "access_token": new_access_token,
                    "refresh_token": new_refresh_token,
                    "expires_at": expires_at,
                    "expires_in": expires_in
                }
                
                # Save updated credentials to database
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
        """
        Extract access token from credentials object.
        Handles various credential structures.
        """
        # Try direct access
        if "access_token" in credentials:
            return credentials["access_token"]
        
        # Try nested in 'credentials' key
        if "credentials" in credentials and isinstance(credentials["credentials"], dict):
            if "access_token" in credentials["credentials"]:
                return credentials["credentials"]["access_token"]
        
        # Try nested in 'data' key
        if "data" in credentials and isinstance(credentials["data"], dict):
            if "access_token" in credentials["data"]:
                return credentials["data"]["access_token"]
        
        return None
    
    def _is_token_expired(self, credentials: Dict[str, Any]) -> bool:
        """
        Check if the access token is expired based on expires_at timestamp
        """
        try:
            # Check for expires_at in various locations
            expires_at = None
            
            if "expires_at" in credentials:
                expires_at = credentials["expires_at"]
            elif "credentials" in credentials and isinstance(credentials["credentials"], dict):
                expires_at = credentials["credentials"].get("expires_at")
            elif "metadata" in credentials and isinstance(credentials["metadata"], dict):
                expires_at = credentials["metadata"].get("expires_at")
            
            if not expires_at:
                # If no expiration info, assume token is valid
                logger.warning("No expiration info found in credentials, assuming token is valid")
                return False
            
            # Parse expiration timestamp
            if isinstance(expires_at, str):
                # Remove 'Z' and parse as UTC
                expires_at_str = expires_at.replace('Z', '')
                if '+' in expires_at_str or expires_at_str.endswith('+00:00'):
                    expires_at_dt = datetime.fromisoformat(expires_at_str.replace('+00:00', ''))
                else:
                    expires_at_dt = datetime.fromisoformat(expires_at_str)
            elif isinstance(expires_at, (int, float)):
                expires_at_dt = datetime.utcfromtimestamp(expires_at)
            else:
                expires_at_dt = expires_at
            
            # Get current time in UTC
            current_time = datetime.utcnow()
            
            # Add a 5-minute buffer to refresh tokens before they actually expire
            buffer_minutes = 5
            is_expired = current_time >= (expires_at_dt - timedelta(minutes=buffer_minutes))
            
            if is_expired:
                logger.info(f"Token is expired or expiring soon. Current time (UTC): {current_time}, Expires at: {expires_at_dt}")
            
            return is_expired
            
        except Exception as e:
            logger.warning(f"Error checking token expiration: {str(e)}")
            # If we can't determine expiration, assume token needs refresh to be safe
            return True
    
    async def _handle_gmail(
        self,
        action: str,
        credentials: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Gmail API requests"""
        try:
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                return {
                    "success": False,
                    "error": "No access token found for Gmail",
                    "error_code": "MISSING_TOKEN"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"[DEBUG] Making Gmail API request with token (first 10 chars): {access_token[:10]}...")
            
            if action == "fetchEmails":
                query = payload.get("query", "is:unread")
                url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}"
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)
                    
                    if response.status_code == 401:
                        logger.error(f"Gmail API returned 401 Unauthorized. Token may be invalid or expired.")
                        return {
                            "success": False,
                            "error": "Gmail access token is invalid or expired. Please reconnect your Gmail account.",
                            "error_code": "TOKEN_INVALID",
                            "requires_reconnect": True
                        }
                    
                    response.raise_for_status()
                    
                    messages = response.json().get("messages", [])
                    
                    # Fetch details for each message
                    emails = []
                    for msg in messages[:10]:  # Limit to 10 emails
                        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg['id']}"
                        msg_response = await client.get(msg_url, headers=headers)
                        msg_response.raise_for_status()
                        emails.append(msg_response.json())
                    
                    return {
                        "success": True,
                        "emails": emails,
                        "count": len(emails)
                    }
            
            elif action == "sendEmail":
                # Implement send email logic
                to = payload.get("to")
                subject = payload.get("subject")
                body = payload.get("body")
                
                import base64
                from email.mime.text import MIMEText
                
                message = MIMEText(body)
                message['to'] = to
                message['subject'] = subject
                raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
                
                url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json={"raw": raw}
                    )
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "message": "Email sent successfully",
                        "data": response.json()
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported Gmail action: {action}"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"Gmail API 401 error: {str(e)}")
                return {
                    "success": False,
                    "error": "Gmail access token is invalid or expired. Please reconnect your Gmail account.",
                    "error_code": "TOKEN_INVALID",
                    "requires_reconnect": True
                }
            logger.error(f"Gmail API HTTP error: {str(e)}")
            return {
                "success": False,
                "error": f"Gmail API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Gmail API error: {str(e)}")
            return {
                "success": False,
                "error": f"Gmail API error: {str(e)}"
            }
    
    async def _handle_slack(
        self,
        action: str,
        credentials: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Slack API requests"""
        try:
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                return {
                    "success": False,
                    "error": "No access token found for Slack",
                    "error_code": "MISSING_TOKEN"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            if action == "postMessage":
                message = payload.get("message")
                channel = payload.get("channel", "#general")
                
                url = "https://slack.com/api/chat.postMessage"
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json={
                            "channel": channel,
                            "text": message
                        }
                    )
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "message": "Message posted to Slack",
                        "data": response.json()
                    }
            
            elif action == "listChannels":
                url = "https://slack.com/api/conversations.list"
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "channels": response.json().get("channels", [])
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported Slack action: {action}"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {
                    "success": False,
                    "error": "Slack access token is invalid or expired. Please reconnect your Slack account.",
                    "error_code": "TOKEN_INVALID",
                    "requires_reconnect": True
                }
            logger.error(f"Slack API error: {str(e)}")
            return {
                "success": False,
                "error": f"Slack API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Slack API error: {str(e)}")
            return {
                "success": False,
                "error": f"Slack API error: {str(e)}"
            }
    
    async def _handle_notion(
        self,
        action: str,
        credentials: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Notion API requests"""
        try:
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                return {
                    "success": False,
                    "error": "No access token found for Notion",
                    "error_code": "MISSING_TOKEN"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            }
            
            if action == "createPage":
                parent_id = payload.get("parent_id")
                content = payload.get("content", "")
                title = payload.get("title", "New Page")
                
                url = "https://api.notion.com/v1/pages"
                
                body = {
                    "parent": {"page_id": parent_id} if parent_id else {"type": "workspace"},
                    "properties": {
                        "title": {
                            "title": [
                                {
                                    "text": {
                                        "content": title
                                    }
                                }
                            ]
                        }
                    },
                    "children": [
                        {
                            "object": "block",
                            "type": "paragraph",
                            "paragraph": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": content
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=body)
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "message": "Notion page created",
                        "data": response.json()
                    }
            
            elif action == "searchPages":
                query = payload.get("query", "")
                url = "https://api.notion.com/v1/search"
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json={"query": query}
                    )
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "pages": response.json().get("results", [])
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported Notion action: {action}"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {
                    "success": False,
                    "error": "Notion access token is invalid or expired. Please reconnect your Notion account.",
                    "error_code": "TOKEN_INVALID",
                    "requires_reconnect": True
                }
            logger.error(f"Notion API error: {str(e)}")
            return {
                "success": False,
                "error": f"Notion API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Notion API error: {str(e)}")
            return {
                "success": False,
                "error": f"Notion API error: {str(e)}"
            }
    
    async def _handle_calendar(
        self,
        action: str,
        credentials: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Google Calendar API requests"""
        try:
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                return {
                    "success": False,
                    "error": "No access token found for Google Calendar",
                    "error_code": "MISSING_TOKEN"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            if action == "createEvent":
                events = payload
                print(events)
                
                # If no events array, check if this is a single event at the top level
                if not events and payload.get("summary"):
                    events = [payload]
                
                calendar_id = payload.get("calendar_id", "primary")
                
                logger.info(f"[v0] Creating {len(events)} calendar events")
                
                url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
                
                created_events = []
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    for event_data in events:
                        calendar_event = {
                            "summary": event_data.get("summary", "No Title"),
                            "description": event_data.get("description", ""),
                            "start": {
                                "dateTime": event_data.get("start_time"),
                                "timeZone": event_data.get("timezone", "UTC")
                            },
                            "end": {
                                "dateTime": event_data.get("end_time"),
                                "timeZone": event_data.get("timezone", "UTC")
                            }
                        }
                        
                        attendees = event_data.get("attendees", [])
                        if attendees:
                            calendar_event["attendees"] = [
                                {"email": email} if isinstance(email, str) else email
                                for email in attendees
                            ]
                        
                        logger.info(f"[v0] Creating event: {calendar_event['summary']}")
                        
                        response = await client.post(url, headers=headers, json=calendar_event)
                        response.raise_for_status()
                        created_events.append(response.json())
                
                logger.info(f"[v0] Successfully created {len(created_events)} events")
                
                return {
                    "success": True,
                    "message": f"Created {len(created_events)} events",
                    "events": created_events
                }
            
            elif action == "listEvents":
                calendar_id = payload.get("calendar_id", "primary")
                time_min = payload.get("time_min")
                time_max = payload.get("time_max")
                
                url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
                params = {}
                if time_min:
                    params["timeMin"] = time_min
                if time_max:
                    params["timeMax"] = time_max
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "events": response.json().get("items", [])
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported Calendar action: {action}"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {
                    "success": False,
                    "error": "Google Calendar access token is invalid or expired. Please reconnect your Google account.",
                    "error_code": "TOKEN_INVALID",
                    "requires_reconnect": True
                }
            logger.error(f"Calendar API error: {str(e)}")
            return {
                "success": False,
                "error": f"Calendar API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Calendar API error: {str(e)}")
            return {
                "success": False,
                "error": f"Calendar API error: {str(e)}"
            }
    
    async def _handle_gdrive(
        self,
        action: str,
        credentials: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Google Drive API requests"""
        try:
            access_token = self._extract_access_token(credentials)
            
            if not access_token:
                return {
                    "success": False,
                    "error": "No access token found for Google Drive",
                    "error_code": "MISSING_TOKEN"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            if action == "listFiles":
                query = payload.get("query", "")
                page_size = payload.get("page_size", 10)
                
                url = "https://www.googleapis.com/drive/v3/files"
                params = {
                    "pageSize": page_size,
                    "fields": "files(id, name, mimeType, createdTime, modifiedTime)"
                }
                if query:
                    params["q"] = query
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "files": response.json().get("files", [])
                    }
            
            elif action == "uploadFile":
                file_name = payload.get("file_name")
                file_content = payload.get("file_content")
                mime_type = payload.get("mime_type", "text/plain")
                
                # This is a simplified version - actual file upload would need multipart
                url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart"
                
                metadata = {
                    "name": file_name,
                    "mimeType": mime_type
                }
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=metadata
                    )
                    response.raise_for_status()
                    
                    return {
                        "success": True,
                        "message": "File uploaded",
                        "data": response.json()
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported Google Drive action: {action}"
                }
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {
                    "success": False,
                    "error": "Google Drive access token is invalid or expired. Please reconnect your Google account.",
                    "error_code": "TOKEN_INVALID",
                    "requires_reconnect": True
                }
            logger.error(f"Google Drive API error: {str(e)}")
            return {
                "success": False,
                "error": f"Google Drive API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Google Drive API error: {str(e)}")
            return {
                "success": False,
                "error": f"Google Drive API error: {str(e)}"
            }
