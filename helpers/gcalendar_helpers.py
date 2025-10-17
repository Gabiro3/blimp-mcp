"""
Google Calendar helper functions using Google API Python Client.
Provides CRUD operations for calendar events.
"""

from typing import Dict, List, Any, Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class GCalendarHelpers:
    """Helper class for Google Calendar operations."""
    
    @staticmethod
    def _get_service(access_token: str):
        """Create Calendar API service with access token."""
        credentials = Credentials(token=access_token)
        return build('calendar', 'v3', credentials=credentials)
    
    @staticmethod
    async def list_events(
        access_token: str,
        calendar_id: str = "primary",
        time_min: Optional[str] = None,
        time_max: Optional[str] = None,
        max_results: int = 10,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List calendar events.
        
        Args:
            access_token: User's Google Calendar access token
            calendar_id: Calendar ID (default: "primary")
            time_min: Lower bound for event start time (ISO 8601)
            time_max: Upper bound for event start time (ISO 8601)
            max_results: Maximum number of events to return
            query: Free text search query
            
        Returns:
            Dict with events list
        """
        try:
            service = GCalendarHelpers._get_service(access_token)
            
            params = {
                'calendarId': calendar_id,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            if time_min:
                params['timeMin'] = time_min
            if time_max:
                params['timeMax'] = time_max
            if query:
                params['q'] = query
            
            events_result = service.events().list(**params).execute()
            events = events_result.get('items', [])
            
            return {
                "success": True,
                "events": events,
                "count": len(events)
            }
            
        except HttpError as error:
            logger.error(f"Calendar API error listing events: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def create_event(
        access_token: str,
        summary: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC"
    ) -> Dict[str, Any]:
        """
        Create a calendar event.
        
        Args:
            access_token: User's Google Calendar access token
            summary: Event title
            start_time: Event start time (ISO 8601)
            end_time: Event end time (ISO 8601)
            calendar_id: Calendar ID (default: "primary")
            description: Event description
            location: Event location
            attendees: List of attendee email addresses
            timezone: Timezone for the event
            
        Returns:
            Dict with created event data
        """
        try:
            service = GCalendarHelpers._get_service(access_token)
            
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time,
                    'timeZone': timezone
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': timezone
                }
            }
            
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            created_event = service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            return {
                "success": True,
                "event": created_event
            }
            
        except HttpError as error:
            logger.error(f"Calendar API error creating event: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def get_event(
        access_token: str,
        event_id: str,
        calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        """
        Get a specific calendar event.
        
        Args:
            access_token: User's Google Calendar access token
            event_id: ID of the event to retrieve
            calendar_id: Calendar ID (default: "primary")
            
        Returns:
            Dict with event data
        """
        try:
            service = GCalendarHelpers._get_service(access_token)
            
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return {
                "success": True,
                "event": event
            }
            
        except HttpError as error:
            logger.error(f"Calendar API error getting event: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def update_event(
        access_token: str,
        event_id: str,
        calendar_id: str = "primary",
        summary: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC"
    ) -> Dict[str, Any]:
        """
        Update a calendar event.
        
        Args:
            access_token: User's Google Calendar access token
            event_id: ID of the event to update
            calendar_id: Calendar ID (default: "primary")
            summary: Event title
            start_time: Event start time (ISO 8601)
            end_time: Event end time (ISO 8601)
            description: Event description
            location: Event location
            attendees: List of attendee email addresses
            timezone: Timezone for the event
            
        Returns:
            Dict with updated event data
        """
        try:
            service = GCalendarHelpers._get_service(access_token)
            
            # Get existing event
            event = service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields
            if summary:
                event['summary'] = summary
            if start_time:
                event['start'] = {'dateTime': start_time, 'timeZone': timezone}
            if end_time:
                event['end'] = {'dateTime': end_time, 'timeZone': timezone}
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            updated_event = service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            return {
                "success": True,
                "event": updated_event
            }
            
        except HttpError as error:
            logger.error(f"Calendar API error updating event: {error}")
            return {
                "success": False,
                "error": str(error)
            }
    
    @staticmethod
    async def delete_event(
        access_token: str,
        event_id: str,
        calendar_id: str = "primary"
    ) -> Dict[str, Any]:
        """
        Delete a calendar event.
        
        Args:
            access_token: User's Google Calendar access token
            event_id: ID of the event to delete
            calendar_id: Calendar ID (default: "primary")
            
        Returns:
            Dict with success status
        """
        try:
            service = GCalendarHelpers._get_service(access_token)
            
            service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return {
                "success": True,
                "event_id": event_id
            }
            
        except HttpError as error:
            logger.error(f"Calendar API error deleting event: {error}")
            return {
                "success": False,
                "error": str(error)
            }


# Function registry for Gemini
GCALENDAR_FUNCTIONS = {
    "list_events": {
        "name": "list_events",
        "description": "List calendar events with optional filters",
        "parameters": {
            "calendar_id": "Calendar ID (default: 'primary')",
            "time_min": "Lower bound for event start time (ISO 8601, optional)",
            "time_max": "Upper bound for event start time (ISO 8601, optional)",
            "max_results": "Maximum number of events to return (default: 10)",
            "query": "Free text search query (optional)"
        }
    },
    "create_event": {
        "name": "create_event",
        "description": "Create a calendar event",
        "parameters": {
            "summary": "Event title",
            "start_time": "Event start time (ISO 8601)",
            "end_time": "Event end time (ISO 8601)",
            "calendar_id": "Calendar ID (default: 'primary')",
            "description": "Event description (optional)",
            "location": "Event location (optional)",
            "attendees": "List of attendee email addresses (optional)",
            "timezone": "Timezone for the event (default: 'UTC')"
        }
    },
    "get_event": {
        "name": "get_event",
        "description": "Get a specific calendar event by ID",
        "parameters": {
            "event_id": "ID of the event to retrieve",
            "calendar_id": "Calendar ID (default: 'primary')"
        }
    },
    "update_event": {
        "name": "update_event",
        "description": "Update a calendar event",
        "parameters": {
            "event_id": "ID of the event to update",
            "calendar_id": "Calendar ID (default: 'primary')",
            "summary": "Event title (optional)",
            "start_time": "Event start time (ISO 8601, optional)",
            "end_time": "Event end time (ISO 8601, optional)",
            "description": "Event description (optional)",
            "location": "Event location (optional)",
            "attendees": "List of attendee email addresses (optional)",
            "timezone": "Timezone for the event (default: 'UTC')"
        }
    },
    "delete_event": {
        "name": "delete_event",
        "description": "Delete a calendar event",
        "parameters": {
            "event_id": "ID of the event to delete",
            "calendar_id": "Calendar ID (default: 'primary')"
        }
    }
}
