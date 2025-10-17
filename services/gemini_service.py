import os
import json
import logging
import re
from typing import Dict, Any, List, Optional
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
    
    async def analyze_prompt(
        self, 
        prompt: str,
        workflow_templates: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Send prompt to Gemini and analyze what apps are needed.
        Returns either a matching workflow_id or generates a custom workflow JSON.
        
        Args:
            prompt: User's automation request
            workflow_templates: List of available workflow templates from database
            
        Returns:
            Dictionary containing either workflow_id (for existing templates) or workflow_json (for custom workflows)
        """
        try:
            templates_section = ""
            if workflow_templates and len(workflow_templates) > 0:
                templates_section = "\n\nAVAILABLE WORKFLOW TEMPLATES:\n"
                for template in workflow_templates:
                    templates_section += f"""
- ID: {template['id']}
  Name: {template['name']}
  Description: {template['description']}
  Required Apps: {', '.join(template['required_apps'])}
  Category: {template.get('category', 'general')}
"""
            
            workflow_example = """{
  "name": "Workflow Name",
  "nodes": [
    {
      "parameters": {
        "path": "webhook-path",
        "responseMode": "lastNode"
      },
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "position": [240, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "{{ $env.MCP_SERVER_URL }}/proxy/app/action"
      },
      "name": "API Call Node",
      "type": "n8n-nodes-base.httpRequest",
      "position": [460, 300]
    }
  ],
  "connections": {
    "Webhook Trigger": {
      "main": [[{"node": "API Call Node", "type": "main", "index": 0}]]
    }
  }
}"""
            
            system_prompt = f"""You are an AI assistant for an automation platform called Blimp. 
Analyze the user's request and determine the best workflow solution.

{templates_section}

TASK:
1. If the user's request matches one of the available workflow templates above, return the workflow_id
2. If the request is more complex or doesn't match existing templates, generate a custom n8n workflow JSON

IMPORTANT: Respond ONLY with valid JSON. No markdown, no explanations, just the JSON object.

RESPONSE FORMAT:

For matching existing template:
{{
  "match_type": "existing_template",
  "workflow_id": "template-id-here",
  "required_apps": ["app1", "app2"],
  "confidence": 0.95,
  "reasoning": "Brief explanation of why this template matches"
}}

For custom workflow (complex requests):
{{
  "match_type": "custom_workflow",
  "workflow_json": {{
    "name": "Workflow Name",
    "description": "What this workflow does",
    "required_apps": ["app1", "app2"],
    "nodes": [...],
    "connections": {{...}}
  }},
  "required_apps": ["app1", "app2"],
  "reasoning": "Brief explanation of the workflow design"
}}

N8N WORKFLOW STRUCTURE EXAMPLE:
{workflow_example}

GUIDELINES:
- Use match_type "existing_template" if confidence > 0.7 that a template matches
- Use match_type "custom_workflow" for complex multi-step automations
- For custom workflows, include proper n8n node structure with webhook triggers
- Common apps: Gmail, Slack, Google Sheets, Google Drive, Trello, Asana, Notion, Discord, Twitter, LinkedIn, Salesforce, HubSpot, Mailchimp, Stripe, PayPal, Zoom, Google Calendar, Dropbox, GitHub, Jira
- Ensure all nodes have proper connections and parameters

User request: {prompt}"""
            
            response = self.model.generate_content(
                system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                )
            )
            
            response_text = response.text.strip()
            
            logger.info(f"Raw Gemini response: {response_text[:500]}")
            
            parsed_response = self._extract_and_parse_json(response_text)
            
            parsed_response = self._validate_workflow_response(parsed_response, prompt)
            
            logger.info(f"Gemini analysis complete: {json.dumps(parsed_response, indent=2)[:500]}")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True)
            return {
                "match_type": "error",
                "required_apps": [],
                "error": str(e),
                "reasoning": "Error occurred during analysis"
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
            "match_type": "error",
            "required_apps": self._extract_apps_from_text(text),
            "error": "Failed to parse JSON response",
            "reasoning": text[:500]
        }
    
    def _validate_workflow_response(self, response: Dict[str, Any], original_prompt: str) -> Dict[str, Any]:
        """
        Validate and ensure response has all required fields based on match_type
        """
        match_type = response.get("match_type", "error")
        
        if match_type == "existing_template":
            return {
                "match_type": "existing_template",
                "workflow_id": response.get("workflow_id"),
                "required_apps": response.get("required_apps", []),
                "confidence": response.get("confidence", 0.8),
                "reasoning": response.get("reasoning", "Template matched")
            }
        elif match_type == "custom_workflow":
            return {
                "match_type": "custom_workflow",
                "workflow_json": response.get("workflow_json", {}),
                "required_apps": response.get("required_apps", []),
                "reasoning": response.get("reasoning", "Custom workflow generated")
            }
        else:
            # Fallback for old format or errors
            return {
                "match_type": "error",
                "required_apps": response.get("required_apps", []),
                "error": response.get("error", "Unknown response format"),
                "reasoning": response.get("reasoning", "Could not determine workflow type")
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
        
        return list(set(found_apps))
