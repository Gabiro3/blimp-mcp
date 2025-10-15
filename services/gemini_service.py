import os
import json
import logging
import re
from typing import Dict, Any, List
import google.generativeai as genai

logger = logging.getLogger(__name__)


class GeminiService:
    """Service for interacting with Gemini 2.5 Flash API"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    async def analyze_prompt(self, prompt: str) -> Dict[str, Any]:
        """
        Send prompt to Gemini and analyze what apps are needed
        
        Args:
            prompt: User's automation request
            
        Returns:
            Dictionary containing required apps and workflow information
        """
        try:
            system_prompt = """You are an AI assistant for an automation platform called Blimp. 
Analyze the user's request and determine what apps/services are needed.

IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanations, just the JSON object.

Required JSON structure:
{
  "required_apps": ["app1", "app2"],
  "workflow_type": "description of workflow type",
  "workflow_id": "suggested_workflow_id",
  "workflow_description": "detailed description of what this workflow does",
  "suggested_actions": ["action1", "action2"]
}

Common apps to consider: Gmail, Slack, Google Sheets, Google Drive, Trello, Asana, Notion, Discord, Twitter, LinkedIn, Salesforce, HubSpot, Mailchimp, Stripe, PayPal, Zoom, Google Calendar, Dropbox, GitHub, Jira.

User request: """ + prompt
            
            response = self.model.generate_content(
                system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,  # Lower temperature for more consistent JSON
                )
            )
            
            # Get the response text
            response_text = response.text.strip()
            
            logger.info(f"Raw Gemini response: {response_text[:500]}")  # Log first 500 chars
            
            parsed_response = self._extract_and_parse_json(response_text)
            
            parsed_response = self._validate_response(parsed_response, prompt)
            
            logger.info(f"Gemini analysis complete: {json.dumps(parsed_response, indent=2)}")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True)
            # Return a fallback response
            return {
                "required_apps": [],
                "workflow_type": "unknown",
                "workflow_id": None,
                "workflow_description": f"Error analyzing prompt with Gemini",
                "suggested_actions": [],
                "error": str(e)
            }
    
    def _extract_and_parse_json(self, text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from Gemini response with multiple strategies
        """
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        try:
            if "```json" in text:
                json_text = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_text)
            elif "```" in text:
                json_text = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_text)
        except (json.JSONDecodeError, IndexError):
            pass
        
        try:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                json_text = json_match.group(0)
                return json.loads(json_text)
        except json.JSONDecodeError:
            pass
        
        logger.warning("All JSON parsing strategies failed, using text extraction fallback")
        return {
            "required_apps": self._extract_apps_from_text(text),
            "workflow_type": "general_automation",
            "workflow_id": f"workflow_{abs(hash(text)) % 10000}",
            "workflow_description": text[:500],  # Limit description length
            "suggested_actions": []
        }
    
    def _validate_response(self, response: Dict[str, Any], original_prompt: str) -> Dict[str, Any]:
        """
        Validate and ensure response has all required fields
        """
        validated = {
            "required_apps": response.get("required_apps", []),
            "workflow_type": response.get("workflow_type", "general_automation"),
            "workflow_id": response.get("workflow_id") or f"workflow_{abs(hash(original_prompt)) % 10000}",
            "workflow_description": response.get("workflow_description", "Automated workflow"),
            "suggested_actions": response.get("suggested_actions", [])
        }
        
        if not isinstance(validated["required_apps"], list):
            validated["required_apps"] = []
        
        if not isinstance(validated["suggested_actions"], list):
            validated["suggested_actions"] = []
        
        return validated
    
    def _extract_apps_from_text(self, text: str) -> List[str]:
        """Extract app names from text as fallback"""
        common_apps = [
            "Gmail", "Slack", "Google Sheets", "Google Drive", "Trello",
            "Asana", "Notion", "Discord", "Twitter", "LinkedIn", "Salesforce",
            "HubSpot", "Mailchimp", "Stripe", "PayPal", "Zoom", "Google Calendar",
            "Dropbox", "GitHub", "Jira", "Airtable", "Zapier", "Monday.com"
        ]
        
        found_apps = []
        text_lower = text.lower()
        
        for app in common_apps:
            if app.lower() in text_lower:
                found_apps.append(app)
        
        return list(set(found_apps))  # Remove duplicates
