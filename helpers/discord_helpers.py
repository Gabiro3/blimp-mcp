"""
Discord helper functions using Discord API.
Provides operations for sending messages, managing channels, etc.
"""

from typing import Dict, List, Any, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


class DiscordHelpers:
    """Helper class for Discord operations."""
    
    BASE_URL = "https://discord.com/api/v10"
    
    @staticmethod
    async def send_message(
        access_token: str,
        channel_id: str,
        content: str,
        embeds: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send a Discord message.
        
        Args:
            access_token: User's Discord access token
            channel_id: Channel ID
            content: Message content
            embeds: Message embeds for rich formatting
            
        Returns:
            Dict with sent message data
        """
        try:
            headers = {
                "Authorization": f"Bot {access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {"content": content}
            if embeds:
                payload["embeds"] = embeds
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{DiscordHelpers.BASE_URL}/channels/{channel_id}/messages",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                return {
                    "success": True,
                    "message": response.json()
                }
                
        except httpx.HTTPError as error:
            logger.error(f"Discord API error sending message: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def get_channel(
        access_token: str,
        channel_id: str
    ) -> Dict[str, Any]:
        """
        Get Discord channel information.
        
        Args:
            access_token: User's Discord access token
            channel_id: Channel ID
            
        Returns:
            Dict with channel data
        """
        try:
            headers = {
                "Authorization": f"Bot {access_token}"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{DiscordHelpers.BASE_URL}/channels/{channel_id}",
                    headers=headers
                )
                response.raise_for_status()
                
                return {
                    "success": True,
                    "channel": response.json()
                }
                
        except httpx.HTTPError as error:
            logger.error(f"Discord API error getting channel: {error}")
            return {
                "success": False,
                "error": str(error)
            }


# Function registry for Gemini
DISCORD_FUNCTIONS = {
    "send_message": {
        "name": "send_message",
        "description": "Send a Discord message",
        "parameters": {
            "channel_id": "Channel ID",
            "content": "Message content",
            "embeds": "Message embeds for rich formatting (optional)"
        }
    },
    "get_channel": {
        "name": "get_channel",
        "description": "Get Discord channel information",
        "parameters": {
            "channel_id": "Channel ID"
        }
    }
}
