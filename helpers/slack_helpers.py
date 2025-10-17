"""
Slack helper functions using Slack SDK.
Provides operations for sending messages, managing channels, etc.
"""

from typing import Dict, List, Any, Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import logging

logger = logging.getLogger(__name__)


class SlackHelpers:
    """Helper class for Slack operations."""
    
    @staticmethod
    def _get_client(access_token: str) -> WebClient:
        """Create Slack client with access token."""
        return WebClient(token=access_token)
    
    @staticmethod
    async def send_message(
        access_token: str,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a Slack message.
        
        Args:
            access_token: User's Slack access token
            channel: Channel ID or name
            text: Message text
            blocks: Message blocks for rich formatting
            thread_ts: Thread timestamp to reply to
            
        Returns:
            Dict with sent message data
        """
        try:
            client = SlackHelpers._get_client(access_token)
            
            params = {
                "channel": channel,
                "text": text
            }
            
            if blocks:
                params["blocks"] = blocks
            if thread_ts:
                params["thread_ts"] = thread_ts
            
            response = client.chat_postMessage(**params)
            
            return {
                "success": True,
                "message": response.data
            }
            
        except SlackApiError as error:
            logger.error(f"Slack API error sending message: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def list_channels(
        access_token: str,
        types: str = "public_channel,private_channel",
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        List Slack channels.
        
        Args:
            access_token: User's Slack access token
            types: Channel types to include
            limit: Maximum number of channels to return
            
        Returns:
            Dict with channels list
        """
        try:
            client = SlackHelpers._get_client(access_token)
            
            response = client.conversations_list(
                types=types,
                limit=limit
            )
            
            return {
                "success": True,
                "channels": response.data.get("channels", [])
            }
            
        except SlackApiError as error:
            logger.error(f"Slack API error listing channels: {error}")
            return {
                "success": False,
                "error": str(error)
            }


# Function registry for Gemini
SLACK_FUNCTIONS = {
    "send_message": {
        "name": "send_message",
        "description": "Send a Slack message",
        "parameters": {
            "channel": "Channel ID or name",
            "text": "Message text",
            "blocks": "Message blocks for rich formatting (optional)",
            "thread_ts": "Thread timestamp to reply to (optional)"
        }
    },
    "list_channels": {
        "name": "list_channels",
        "description": "List Slack channels",
        "parameters": {
            "types": "Channel types to include (default: 'public_channel,private_channel')",
            "limit": "Maximum number of channels to return (default: 100)"
        }
    }
}
