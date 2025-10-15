import logging
import httpx
from typing import Dict, Any, Optional
from services.supabase_service import SupabaseService

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
    
    async def _handle_gmail(
        self,
        action: str,
        credentials: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle Gmail API requests"""
        try:
            access_token = credentials.get("access_token")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            if action == "fetchEmails":
                query = payload.get("query", "is:unread")
                url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}"
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url, headers=headers)
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
            access_token = credentials.get("access_token")
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
            access_token = credentials.get("access_token")
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
            access_token = credentials.get("access_token")
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            if action == "createEvent":
                events = payload.get("events", [])
                calendar_id = payload.get("calendar_id", "primary")
                
                url = f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
                
                created_events = []
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    for event in events:
                        response = await client.post(url, headers=headers, json=event)
                        response.raise_for_status()
                        created_events.append(response.json())
                
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
            access_token = credentials.get("access_token")
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
                
        except Exception as e:
            logger.error(f"Google Drive API error: {str(e)}")
            return {
                "success": False,
                "error": f"Google Drive API error: {str(e)}"
            }
