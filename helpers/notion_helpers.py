"""
Notion helper functions using Notion SDK.
Provides CRUD operations for Notion pages, databases, and blocks.
"""

from typing import Dict, List, Any, Optional
from notion_client import Client
from notion_client.errors import APIResponseError
import logging

logger = logging.getLogger(__name__)


class NotionHelpers:
    """Helper class for Notion operations."""
    
    @staticmethod
    def _get_client(access_token: str) -> Client:
        """Create Notion client with access token."""
        return Client(auth=access_token)
    
    @staticmethod
    async def create_page(
        access_token: str,
        parent_id: str,
        title: str,
        properties: Optional[Dict[str, Any]] = None,
        children: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Create a Notion page.
        
        Args:
            access_token: User's Notion access token
            parent_id: ID of the parent page or database
            title: Page title
            properties: Additional page properties
            children: Page content blocks
            
        Returns:
            Dict with created page data
        """
        try:
            client = NotionHelpers._get_client(access_token)
            
            page_properties = {
                "title": {
                    "title": [{"text": {"content": title}}]
                }
            }
            
            if properties:
                page_properties.update(properties)
            
            page_data = {
                "parent": {"page_id": parent_id} if not parent_id.startswith("database") else {"database_id": parent_id},
                "properties": page_properties
            }
            
            if children:
                page_data["children"] = children
            
            page = client.pages.create(**page_data)
            
            return {
                "success": True,
                "page": page
            }
            
        except APIResponseError as error:
            logger.error(f"Notion API error creating page: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def get_page(
        access_token: str,
        page_id: str
    ) -> Dict[str, Any]:
        """
        Get a Notion page.
        
        Args:
            access_token: User's Notion access token
            page_id: ID of the page to retrieve
            
        Returns:
            Dict with page data
        """
        try:
            client = NotionHelpers._get_client(access_token)
            page = client.pages.retrieve(page_id=page_id)
            
            return {
                "success": True,
                "page": page
            }
            
        except APIResponseError as error:
            logger.error(f"Notion API error getting page: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def update_page(
        access_token: str,
        page_id: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a Notion page.
        
        Args:
            access_token: User's Notion access token
            page_id: ID of the page to update
            properties: Properties to update
            
        Returns:
            Dict with updated page data
        """
        try:
            client = NotionHelpers._get_client(access_token)
            page = client.pages.update(page_id=page_id, properties=properties)
            
            return {
                "success": True,
                "page": page
            }
            
        except APIResponseError as error:
            logger.error(f"Notion API error updating page: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def query_database(
        access_token: str,
        database_id: str,
        filter: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Query a Notion database.
        
        Args:
            access_token: User's Notion access token
            database_id: ID of the database to query
            filter: Filter conditions
            sorts: Sort conditions
            page_size: Number of results per page
            
        Returns:
            Dict with query results
        """
        try:
            client = NotionHelpers._get_client(access_token)
            
            query_params = {"database_id": database_id, "page_size": page_size}
            if filter:
                query_params["filter"] = filter
            if sorts:
                query_params["sorts"] = sorts
            
            results = client.databases.query(**query_params)
            
            return {
                "success": True,
                "results": results.get("results", []),
                "has_more": results.get("has_more", False)
            }
            
        except APIResponseError as error:
            logger.error(f"Notion API error querying database: {error}")
            return {
                "success": False,
                "error": str(error)
            }


# Function registry for Gemini
NOTION_FUNCTIONS = {
    "create_page": {
        "name": "create_page",
        "description": "Create a Notion page",
        "parameters": {
            "parent_id": "ID of the parent page or database",
            "title": "Page title",
            "properties": "Additional page properties (optional)",
            "children": "Page content blocks (optional)"
        }
    },
    "get_page": {
        "name": "get_page",
        "description": "Get a Notion page by ID",
        "parameters": {
            "page_id": "ID of the page to retrieve"
        }
    },
    "update_page": {
        "name": "update_page",
        "description": "Update a Notion page",
        "parameters": {
            "page_id": "ID of the page to update",
            "properties": "Properties to update"
        }
    },
    "query_database": {
        "name": "query_database",
        "description": "Query a Notion database",
        "parameters": {
            "database_id": "ID of the database to query",
            "filter": "Filter conditions (optional)",
            "sorts": "Sort conditions (optional)",
            "page_size": "Number of results per page (default: 100)"
        }
    }
}
