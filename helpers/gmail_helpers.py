"""
Gmail helper functions using Google API Python Client.
Provides CRUD operations for Gmail messages, labels, drafts, etc.
"""

from typing import Dict, List, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)


class GmailHelpers:
    """Helper class for Gmail operations."""
    
    @staticmethod
    def _get_service(access_token: str):
        """Create Gmail API service with access token."""
        credentials = Credentials(token=access_token)
        return build('gmail', 'v1', credentials=credentials)
    
    @staticmethod
    async def list_messages(
        access_token: str,
        query: str = "",
        max_results: int = 10,
        label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        List Gmail messages.
        
        Args:
            access_token: User's Gmail access token
            query: Gmail search query (e.g., "is:unread", "from:example@gmail.com")
            max_results: Maximum number of messages to return
            label_ids: List of label IDs to filter by
            
        Returns:
            Dict with messages list and metadata
        """
        try:
            service = GmailHelpers._get_service(access_token)
            
            params = {
                'userId': 'me',
                'maxResults': max_results
            }
            
            if query:
                params['q'] = query
            if label_ids:
                params['labelIds'] = label_ids
            
            results = service.users().messages().list(**params).execute()
            messages = results.get('messages', [])
            
            return {
                "success": True,
                "messages": messages,
                "result_size_estimate": results.get('resultSizeEstimate', 0)
            }
            
        except HttpError as error:
            logger.error(f"Gmail API error listing messages: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def get_message(
        access_token: str,
        message_id: str,
        format: str = "full"
    ) -> Dict[str, Any]:
        """
        Get a specific Gmail message.
        
        Args:
            access_token: User's Gmail access token
            message_id: ID of the message to retrieve
            format: Format of the message (full, metadata, minimal, raw)
            
        Returns:
            Dict with message data
        """
        try:
            service = GmailHelpers._get_service(access_token)
            
            message = service.users().messages().get(
                userId='me',
                id=message_id,
                format=format
            ).execute()

            
            return {
                "success": True,
                "message": message
            }
            
        except HttpError as error:
            logger.error(f"Gmail API error getting message: {message_id} {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def send_message(
        access_token: str,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        html: bool = False
    ) -> Dict[str, Any]:
        """
        Send a Gmail message.
        
        Args:
            access_token: User's Gmail access token
            to: Recipient email address
            subject: Email subject
            body: Email body content
            cc: CC recipients (comma-separated)
            bcc: BCC recipients (comma-separated)
            html: Whether body is HTML
            
        Returns:
            Dict with sent message data
        """
        try:
            service = GmailHelpers._get_service(access_token)
            
            message = MIMEMultipart() if html else MIMEText(body)
            message['to'] = to
            message['subject'] = subject
            
            if cc:
                message['cc'] = cc
            if bcc:
                message['bcc'] = bcc
            
            if html:
                message.attach(MIMEText(body, 'html'))
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            sent_message = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return {
                "success": True,
                "message": sent_message
            }
            
        except HttpError as error:
            logger.error(f"Gmail API error sending message: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def delete_message(
        access_token: str,
        message_id: str
    ) -> Dict[str, Any]:
        """
        Delete a Gmail message.
        
        Args:
            access_token: User's Gmail access token
            message_id: ID of the message to delete
            
        Returns:
            Dict with success status
        """
        try:
            service = GmailHelpers._get_service(access_token)
            
            service.users().messages().delete(
                userId='me',
                id=message_id
            ).execute()
            
            return {
                "success": True,
                "message_id": message_id
            }
            
        except HttpError as error:
            logger.error(f"Gmail API error deleting message: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def modify_message(
        access_token: str,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Modify Gmail message labels (mark as read/unread, archive, etc.).
        
        Args:
            access_token: User's Gmail access token
            message_id: ID of the message to modify
            add_label_ids: Label IDs to add
            remove_label_ids: Label IDs to remove
            
        Returns:
            Dict with modified message data
        """
        try:
            service = GmailHelpers._get_service(access_token)
            
            body = {}
            if add_label_ids:
                body['addLabelIds'] = add_label_ids
            if remove_label_ids:
                body['removeLabelIds'] = remove_label_ids
            
            modified_message = service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()
            
            return {
                "success": True,
                "message": modified_message
            }
            
        except HttpError as error:
            logger.error(f"Gmail API error modifying message: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def create_draft(
        access_token: str,
        to: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> Dict[str, Any]:
        """
        Create a Gmail draft.
        
        Args:
            access_token: User's Gmail access token
            to: Recipient email address
            subject: Email subject
            body: Email body content
            html: Whether body is HTML
            
        Returns:
            Dict with draft data
        """
        try:
            service = GmailHelpers._get_service(access_token)
            
            message = MIMEText(body, 'html' if html else 'plain')
            message['to'] = to
            message['subject'] = subject
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            draft = service.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw_message}}
            ).execute()
            
            return {
                "success": True,
                "draft": draft
            }
            
        except HttpError as error:
            logger.error(f"Gmail API error creating draft: {error}")
            return {
                "success": False,
                "error": str(error)
            }


# Function registry for Gemini
GMAIL_FUNCTIONS = {
    "list_messages": {
        "name": "list_messages",
        "description": "List Gmail messages with optional filters",
        "parameters": {
            "query": "Gmail search query (e.g., 'is:unread', 'from:example@gmail.com')",
            "max_results": "Maximum number of messages to return (default: 10)",
            "label_ids": "List of label IDs to filter by (optional)"
        }
    },
    "get_message": {
        "name": "get_message",
        "description": "Get a specific Gmail message by ID",
        "parameters": {
            "message_id": "ID of the message to retrieve",
            "format": "Format of the message (full, metadata, minimal, raw)"
        }
    },
    "send_message": {
        "name": "send_message",
        "description": "Send a Gmail message",
        "parameters": {
            "to": "Recipient email address",
            "subject": "Email subject",
            "body": "Email body content",
            "cc": "CC recipients (comma-separated, optional)",
            "bcc": "BCC recipients (comma-separated, optional)",
            "html": "Whether body is HTML (default: false)"
        }
    },
    "delete_message": {
        "name": "delete_message",
        "description": "Delete a Gmail message",
        "parameters": {
            "message_id": "ID of the message to delete"
        }
    },
    "modify_message": {
        "name": "modify_message",
        "description": "Modify Gmail message labels (mark as read/unread, archive, etc.)",
        "parameters": {
            "message_id": "ID of the message to modify",
            "add_label_ids": "Label IDs to add (optional)",
            "remove_label_ids": "Label IDs to remove (optional)"
        }
    },
    "create_draft": {
        "name": "create_draft",
        "description": "Create a Gmail draft",
        "parameters": {
            "to": "Recipient email address",
            "subject": "Email subject",
            "body": "Email body content",
            "html": "Whether body is HTML (default: false)"
        }
    }
}
