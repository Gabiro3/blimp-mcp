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
        This is the PRIMARY method for workflow execution - it generates the complete execution plan.
        
        Args:
            prompt: User's automation request
            available_functions: Dict of available functions for user's connected apps
            
        Returns:
            Dictionary containing:
            - workflow_type: "simple" or "complex"
            - function_calls: Array of function calls to execute in sequence
            - required_apps: List of apps needed for this workflow
            - reasoning: Explanation of the workflow logic
        """
        try:
            if not prompt or prompt.strip() == "":
                logger.error("Empty prompt provided to analyze_prompt_with_functions")
                return {
                    "workflow_type": "error",
                    "function_calls": [],
                    "required_apps": [],
                    "reasoning": "No prompt provided. Please describe what you want to automate."
                }
            
            functions_description = "\n\nAVAILABLE FUNCTIONS (based on user's connected apps):\n"
            
            if not available_functions:
                logger.warning("No available functions provided - user may not have connected apps")
                functions_description += "\nNOTE: User has no connected apps. Workflow cannot be executed.\n"
            else:
                for app_name, functions in available_functions.items():
                    functions_description += f"\n{app_name.upper()} Functions:\n"
                    for func_name, func_info in functions.items():
                        functions_description += f"""
- {func_name}:
  Description: {func_info['description']}
  Parameters: {json.dumps(func_info['parameters'], indent=4)}
  Returns: {func_info.get('returns', 'Result object')}
"""
            
            system_prompt = f"""You are an AI assistant for an automation platform called Blimp.
Analyze the user's request and determine which function calls to make to fulfill their request.

{functions_description}

IMPORTANT RULES:
1. ONLY use functions from the AVAILABLE FUNCTIONS list above
2. If the user's request requires apps they haven't connected, return an error in reasoning
3. Break complex requests into logical steps with clear data flow
4. Use realistic parameter values based on the user's request
5. For time-based parameters, use ISO 8601 format (e.g., "2025-01-20T10:00:00Z")
6. ALWAYS generate at least one function call if the request is valid
7. When fetching lists (like emails), FIRST fetch the list of IDs, THEN fetch individual items
8. Store intermediate results with descriptive names for use in later steps

RESPONSE FORMAT (JSON only, no markdown, no code blocks):
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
      "store_result_as": "recent_emails",
      "description": "Fetch list of recent email IDs"
    }},
    {{
      "step": 2,
      "app": "gmail",
      "function": "get_message",
      "parameters": {{
        "message_id": "{{{{ recent_emails.messages[0].id }}}}"
      }},
      "store_result_as": "first_email_details",
      "use_results_from": ["recent_emails"],
      "description": "Get details of first email"
    }},
    {{
      "step": 3,
      "app": "calendar",
      "function": "create_event",
      "parameters": {{
        "summary": "{{{{ first_email_details.subject }}}}",
        "description": "{{{{ first_email_details.body }}}}",
        "start_time": "2025-01-20T10:00:00Z",
        "end_time": "2025-01-20T11:00:00Z"
      }},
      "use_results_from": ["first_email_details"],
      "description": "Create calendar event from email"
    }}
  ],
  "required_apps": ["gmail", "calendar"],
  "reasoning": "Fetch unread emails, get details of first email, create calendar event with email content"
}}

FIELD EXPLANATIONS:
- workflow_type: "simple" for single action, "complex" for multi-step workflows
- function_calls: Array of function calls in execution order
  - step: Sequential number (1, 2, 3...)
  - app: App name (must match available functions)
  - function: Function name (must exist in that app's functions)
  - parameters: Object with function parameters (use actual values from user's request)
  - store_result_as: (optional) Variable name to store result for later use
  - use_results_from: (optional) Array of variable names this step depends on
  - description: Brief explanation of what this step does
- required_apps: Array of all apps used in the workflow
- reasoning: Brief explanation of the overall workflow logic

PARAMETER REFERENCE SYNTAX:
Use {{{{ variable_name.field }}}} or {{{{ variable_name.array[index].field }}}} to reference stored results.
Examples:
- {{{{ recent_emails.messages[0].id }}}} - First email's ID from messages array
- {{{{ first_email_details.subject }}}} - Email subject from stored details
- {{{{ user_data.email }}}} - User's email from stored data

IMPORTANT: When working with list operations (like emails):
1. FIRST call list_messages to get message IDs
2. THEN call get_message for each specific message ID you need
3. The list_messages returns: {{success: true, messages: [{{id: "...", threadId: "..."}}, ...]}}
4. Access message IDs with: {{{{ recent_emails.messages[0].id }}}}

===== USER REQUEST =====
{prompt}
========================

Analyze the above user request and generate the appropriate function calls. Respond with ONLY the JSON object."""
            
            logger.info(f"Sending prompt to Gemini (length: {len(prompt)} chars)")
            
            response = self.model.generate_content(
                system_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                )
            )
            
            response_text = response.text.strip()
            logger.info(f"Raw Gemini response (first 500 chars): {response_text[:500]}")
            
            parsed_response = self._extract_and_parse_json(response_text)
            
            parsed_response = self._validate_function_call_response(parsed_response)
            
            logger.info(f"Gemini function call analysis complete: {len(parsed_response.get('function_calls', []))} steps generated")
            return parsed_response
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}", exc_info=True)
            return {
                "workflow_type": "error",
                "function_calls": [],
                "required_apps": [],
                "error": str(e),
                "reasoning": f"Error occurred during analysis: {str(e)}"
            }

    def _validate_function_call_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and ensure response has all required fields for function call execution.
        Adds missing fields with sensible defaults.
        """
        validated = {
            "workflow_type": response.get("workflow_type", "simple"),
            "function_calls": response.get("function_calls", []),
            "required_apps": response.get("required_apps", []),
            "reasoning": response.get("reasoning", "Workflow execution plan")
        }
        
        if not validated["function_calls"]:
            logger.warning("No function calls in response")
            validated["reasoning"] = "No function calls generated. " + validated["reasoning"]
        
        for i, call in enumerate(validated["function_calls"]):
            # Ensure step number
            if "step" not in call:
                call["step"] = i + 1
            
            # Validate required fields
            if "app" not in call or "function" not in call:
                logger.error(f"Function call {i+1} missing required 'app' or 'function' field: {call}")
                call["app"] = call.get("app", "unknown")
                call["function"] = call.get("function", "unknown")
            
            # Ensure parameters exist
            if "parameters" not in call:
                call["parameters"] = {}
            
            # Add description if missing
            if "description" not in call:
                call["description"] = f"Execute {call.get('function', 'unknown')} on {call.get('app', 'unknown')}"
            
            # Extract required app if not in list
            app_name = call.get("app")
            if app_name and app_name not in validated["required_apps"]:
                validated["required_apps"].append(app_name)
        
        return validated

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
