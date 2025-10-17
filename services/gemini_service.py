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
            
            system_prompt = f"""You are an AI assistant for an automation platform called Blimp. 
Analyze the user's request and determine the best workflow solution.

{templates_section}

TASK:
1. If the user's request matches one of the available workflow templates above, return the workflow_id
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
    
    async def analyze_prompt_with_functions(
        self, 
        prompt: str,
        available_functions: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze user prompt and return function calls to execute.
        
        Args:
            prompt: User's automation request
            available_functions: Dict of available functions for required apps
            
        Returns:
            Dictionary containing function calls to execute
        """
        try:
            functions_description = "\n\nAVAILABLE FUNCTIONS:\n"
            for app_name, functions in available_functions.items():
                functions_description += f"\n{app_name.upper()} Functions:\n"
                for func_name, func_info in functions.items():
                    functions_description += f"""
- {func_name}:
  Description: {func_info['description']}
  Parameters: {json.dumps(func_info['parameters'], indent=4)}
"""
            
            system_prompt = f"""You are an AI assistant for an automation platform called Blimp.
Analyze the user's request and determine which function calls to make to fulfill their request.

{functions_description}

TASK:
Based on the user's request, return a JSON array of function calls to execute in sequence.
For simple requests, return a single function call. For complex workflows, return multiple function calls with proper data flow.

RESPONSE FORMAT (JSON only, no markdown):
{{
  "workflow_type": "simple" | "complex",
  "function_calls": [
    {{
      "step": 1,
      "app": "gmail",
      "function": "list_messages",
      "parameters": {{
        "query": "is:unread",
        "max_results": 10
      }},
      "store_result_as": "unread_emails",
      "description": "Fetch unread emails"
    }},
    {{
      "step": 2,
      "app": "gcalendar",
      "function": "create_event",
      "parameters": {{
        "summary": "Meeting from {{{{ unread_emails[0].subject }}}}",
        "start_time": "2025-01-20T10:00:00Z",
        "end_time": "2025-01-20T11:00:00Z"
      }},
      "use_results_from": ["unread_emails"],
      "description": "Create calendar event from first email"
    }}
  ],
  "required_apps": ["gmail", "gcalendar"],
  "reasoning": "Brief explanation of the workflow logic"
}}

GUIDELINES:
- Set workflow_type to "simple" for single function calls, "complex" for multi-step workflows
- Return function calls in the order they should be executed (use "step" field)
- Use "store_result_as" to save results for later function calls
- Use "use_results_from" to reference previous results
- Use {{{{ variable_name }}}} syntax to reference stored results in parameters
- Be specific with parameters - use actual values when possible
- Include a brief "description" for each step
- For complex workflows, break them into logical steps with clear data flow
- Always include "required_apps" array with all apps used

EXAMPLES:

Simple workflow (single action):
{{
  "workflow_type": "simple",
  "function_calls": [
    {{
      "step": 1,
      "app": "gmail",
      "function": "send_email",
      "parameters": {{
        "to": "user@example.com",
        "subject": "Hello",
        "body": "Test email"
      }},
      "description": "Send email to user"
    }}
  ],
  "required_apps": ["gmail"],
  "reasoning": "Simple email send operation"
}}

Complex workflow (multi-step):
{{
  "workflow_type": "complex",
  "function_calls": [
    {{
      "step": 1,
      "app": "gmail",
      "function": "list_messages",
      "parameters": {{"query": "is:unread", "max_results": 5}},
      "store_result_as": "emails",
      "description": "Get unread emails"
    }},
    {{
      "step": 2,
      "app": "notion",
      "function": "create_page",
      "parameters": {{
        "title": "Email Summary",
        "content": "{{{{ emails }}}}"
      }},
      "use_results_from": ["emails"],
      "description": "Create Notion page with email summary"
    }}
  ],
  "required_apps": ["gmail", "notion"],
  "reasoning": "Fetch emails and log them to Notion"
}}

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
            
            parsed_response = self._validate_function_call_response(parsed_response)
            
            logger.info(f"Gemini function call analysis complete: {len(parsed_response.get('function_calls', []))} steps")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True)
            return {
                "workflow_type": "error",
                "function_calls": [],
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
        
        logger.warning("All JSON parsing strategies failed")
        return {
            "workflow_type": "error",
            "function_calls": [],
            "required_apps": [],
            "error": "Failed to parse JSON response",
            "reasoning": text[:500]
        }
    
    def _validate_function_call_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and ensure response has all required fields for function call execution
        """
        validated = {
            "workflow_type": response.get("workflow_type", "simple"),
            "function_calls": response.get("function_calls", []),
            "required_apps": response.get("required_apps", []),
            "reasoning": response.get("reasoning", "Workflow execution plan")
        }
        
        for i, call in enumerate(validated["function_calls"]):
            if "step" not in call:
                call["step"] = i + 1
            if "app" not in call or "function" not in call:
                logger.warning(f"Function call {i+1} missing required fields")
            if "parameters" not in call:
                call["parameters"] = {}
            if "description" not in call:
                call["description"] = f"Execute {call.get('function', 'unknown')} on {call.get('app', 'unknown')}"
        
        return validated
    
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
