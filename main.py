from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import logging
from dotenv import load_dotenv

from services.gemini_service import GeminiService
from services.supabase_service import SupabaseService
from services.proxy_service import ProxyService
from helpers.function_registry import get_functions_for_apps

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Blimp MCP Server",
    description="AI-powered automation platform MCP server",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Initialize services
gemini_service = GeminiService()
supabase_service = SupabaseService()
proxy_service = ProxyService()

# Request/Response Models
class PromptRequest(BaseModel):
    prompt: str
    user_id: str
    bearer_token: str


class AppStatus(BaseModel):
    app_name: str
    is_connected: bool


class PromptResponse(BaseModel):
    status: str
    message: str
    required_apps: List[AppStatus]
    workflow_id: Optional[str] = None
    gemini_analysis: Dict[str, Any]


class ExecuteWorkflowRequest(BaseModel):
    user_id: str
    workflow_id: Optional[str] = None
    prompt: Optional[str] = None
    bearer_token: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None


class ExecuteWorkflowResponse(BaseModel):
    status: str
    message: str
    results: List[Dict[str, Any]]
    reasoning: Optional[str] = None


class AppCredentials(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str
    expiry_date: Optional[int] = None
    scope: Optional[str] = None


class AppMetadata(BaseModel):
    email: Optional[str] = None
    connected_at: str
    scopes: Optional[List[str]] = None


class ConnectAppRequest(BaseModel):
    user_id: str
    app_name: str
    app_type: str
    credentials: AppCredentials
    metadata: AppMetadata


class ConnectAppResponse(BaseModel):
    success: bool
    message: str
    credential_id: Optional[str] = None
    app_name: str
    error: Optional[str] = None

class ProxyRequest(BaseModel):
    user_id: str
    payload: Dict[str, Any] = {}


class ProxyResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Authentication dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify bearer token from request header"""
    token = credentials.credentials
    # Add your token verification logic here
    # For now, we'll just check if token exists
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Blimp MCP Server",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "services": {
            "gemini": "operational",
            "supabase": "operational"
        }
    }


@app.post("/prompt", response_model=PromptResponse)
async def process_prompt(request: PromptRequest):
    """
    Process user prompt through Gemini, check connected apps, and prepare workflow
    
    Flow:
    1. Receive user prompt
    2. Send to Gemini 2.5 Flash for analysis
    3. Extract required apps from Gemini response
    4. Check Supabase for user's connected apps
    5. Return status with app connection information
    """
    try:
        logger.info(f"Processing prompt for user: {request.user_id}")
        
        # Step 1: Send prompt to Gemini for analysis
        logger.info("Sending prompt to Gemini 2.5 Flash")
        templates = await supabase_service.get_all_workflow_templates()
        gemini_response = await gemini_service.analyze_prompt(request.prompt, templates)
        
        if not gemini_response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get response from Gemini"
            )
        
        # Step 2: Extract required apps from Gemini response
        required_apps = gemini_response.get("required_apps", [])
        logger.info(f"Required apps identified: {required_apps}")
        
        # Step 3: Check user's connected apps in Supabase
        logger.info(f"Checking connected apps for user: {request.user_id}")
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        
        # Step 4: Build app status list
        app_statuses = []
        all_apps_connected = True
        
        for app_name in required_apps:
            is_connected = app_name in connected_apps
            app_statuses.append(AppStatus(
                app_name=app_name,
                is_connected=is_connected
            ))
            if not is_connected:
                all_apps_connected = False
        
        # Step 5: Prepare response
        if all_apps_connected and required_apps:
            response_status = "ready"
            message = "All required apps are connected. Ready to execute workflow."
        elif not required_apps:
            response_status = "no_apps_required"
            message = "No external apps required for this workflow."
        else:
            response_status = "missing_apps"
            missing_apps = [app.app_name for app in app_statuses if not app.is_connected]
            message = f"Missing connections: {', '.join(missing_apps)}. Please connect these apps first."
        
        logger.info(f"Prompt processing complete. Status: {response_status}")
        
        return PromptResponse(
            status=response_status,
            message=message,
            required_apps=app_statuses,
            workflow_id=gemini_response.get("workflow_id"),
            gemini_analysis=gemini_response
        )
        
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing prompt: {str(e)}"
        )


@app.post("/api/mcp/connect-app", response_model=ConnectAppResponse)
async def connect_app(request: ConnectAppRequest):
    """
    Receive OAuth tokens from UI and store user's app credentials
    
    Flow:
    1. Receive app credentials from UI
    2. Validate credentials
    3. Store in Supabase with encryption
    4. Create/update n8n credentials for this user
    5. Return credential ID
    """
    try:
        logger.info(f"Connecting app {request.app_name} for user: {request.user_id}")
        
        # Step 1: Validate credentials
        if not request.credentials.access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access token is required"
            )
        
        # Step 2: Store credentials in Supabase
        logger.info(f"Storing credentials for {request.app_name}")
        credential_id = await supabase_service.store_user_credentials(
            user_id=request.user_id,
            app_name=request.app_name,
            app_type=request.app_type,
            credentials=request.credentials.dict(),
            metadata=request.metadata.dict()
        )
        
        if not credential_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store credentials"
            )
        
        # Step 3: Create/update n8n credentials for this user
        logger.info(f"Creating n8n credentials for user {request.user_id}")
        n8n_credential_id = await proxy_service.create_user_credential(
            user_id=request.user_id,
            app_type=request.app_type,
            credentials=request.credentials.dict(),
            credential_name=f"{request.user_id}_{request.app_type}"
        )
        
        if not n8n_credential_id:
            logger.warning(f"Failed to create n8n credential, but Supabase storage succeeded")
        
        logger.info(f"App connected successfully: {request.app_name}")
        
        return ConnectAppResponse(
            success=True,
            message="App connected successfully",
            credential_id=credential_id,
            app_name=request.app_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting app: {str(e)}")
        return ConnectAppResponse(
            success=False,
            message="Failed to connect app",
            credential_id=None,
            app_name=request.app_name,
            error=str(e)
        )


@app.post("/execute-workflow", response_model=ExecuteWorkflowResponse)
async def execute_workflow(request: ExecuteWorkflowRequest):
    """
    Execute workflow by analyzing prompt with Gemini and calling helper functions directly.
    No n8n dependency - everything runs in the MCP server.
    
    Flow:
    1. If workflow_id provided, fetch workflow from database
    2. If workflow found in DB, use its stored structure
    3. If not found or no workflow_id, analyze prompt with Gemini to get function calls
    4. Execute function calls in sequence
    5. Save workflow to user_workflows if it was newly generated
    """
    try:
        logger.info(f"Executing workflow for user: {request.user_id}")
        
        workflow_found = False
        workflow_data = None
        prompt = None
        
        if request.workflow_id:
            logger.info(f"Attempting to fetch workflow by ID: {request.workflow_id}")
            workflow = await supabase_service.get_workflow(request.workflow_id, request.user_id)
            if workflow:
                workflow_found = True
                workflow_data = workflow
                prompt = workflow.get("description", "")
                logger.info(f"Workflow {request.workflow_id} found in database")
            else:
                logger.warning(f"Workflow {request.workflow_id} not found in database")
        
        # If no workflow found and no prompt provided, error
        if not workflow_found and not request.prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either workflow_id must exist in database or prompt must be provided"
            )
        
        # Use provided prompt if workflow not found
        if not workflow_found:
            prompt = request.prompt
            logger.info("Using provided prompt for workflow generation")
        
        logger.info("Analyzing prompt and generating function calls with Gemini")
        
        # Get connected apps for this user to determine available functions
        connected_apps = await supabase_service.get_user_connected_apps(request.user_id)
        logger.info(f"User has {len(connected_apps)} connected apps: {connected_apps}")
        
        # Get available functions for connected apps
        available_functions = get_functions_for_apps(connected_apps)
        
        # Single call to Gemini to get the complete execution plan
        function_plan = await gemini_service.analyze_prompt_with_functions(
            prompt,
            available_functions
        )
        
        function_calls = function_plan.get("function_calls", [])
        reasoning = function_plan.get("reasoning", "")
        required_apps = function_plan.get("required_apps", [])
        
        if not function_calls:
            return ExecuteWorkflowResponse(
                status="error",
                message="No function calls generated. Please provide more details in your prompt.",
                results=[],
                reasoning=reasoning
            )
        
        logger.info(f"Generated {len(function_calls)} function calls to execute")
        
        results = []
        stored_results = {}
        
        for i, call in enumerate(function_calls):
            app = call.get("app")
            function = call.get("function")
            parameters = call.get("parameters", {})
            
            # Merge request parameters if provided
            if request.parameters:
                parameters = {**parameters, **request.parameters}
            
            store_as = call.get("store_result_as")
            
            logger.info(f"Executing step {i+1}/{len(function_calls)}: {app}.{function}")
            
            # Replace parameter references with stored results
            parameters = _resolve_parameters(parameters, stored_results)
            
            try:
                # Execute function
                result = await proxy_service.execute_function_call(
                    user_id=request.user_id,
                    app_name=app,
                    function_name=function,
                    parameters=parameters
                )
                
                results.append({
                    "step": i + 1,
                    "call": f"{app}.{function}",
                    "status": "success",
                    "result": result
                })
                
                # Store result if needed for next steps
                if store_as:
                    stored_results[store_as] = result
                    logger.info(f"Stored result as '{store_as}' for future steps")
                    
            except Exception as e:
                logger.error(f"Error executing {app}.{function}: {str(e)}")
                results.append({
                    "step": i + 1,
                    "call": f"{app}.{function}",
                    "status": "error",
                    "error": str(e)
                })
                # Continue with remaining steps even if one fails
        
        if not workflow_found and request.workflow_id:
            logger.info(f"Saving newly generated workflow {request.workflow_id} to user_workflows")
            
            # Generate workflow name from prompt
            workflow_name = prompt[:50] + "..." if len(prompt) > 50 else prompt
            workflow_description = f"Custom workflow: {prompt[:200]}"
            
            await supabase_service.save_user_workflow(
                user_id=request.user_id,
                workflow_id=request.workflow_id,
                name=workflow_name,
                description=workflow_description,
                prompt=prompt,
                required_apps=required_apps,
                category="custom"
            )
            logger.info("Workflow saved successfully for future reuse")
        
        # Count successful executions
        successful_steps = sum(1 for r in results if r.get("status") == "success")
        
        logger.info(f"Workflow execution complete: {successful_steps}/{len(results)} steps successful")
        
        return ExecuteWorkflowResponse(
            status="success" if successful_steps == len(results) else "partial_success",
            message=f"Executed {successful_steps}/{len(results)} steps successfully",
            results=results,
            reasoning=reasoning
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing workflow: {str(e)}"
        )
def _resolve_parameters(parameters: Dict[str, Any], stored_results: Dict[str, Any]) -> Dict[str, Any]:
    import re

    resolved = {}

    for key, value in parameters.items():
        if isinstance(value, str) and "{{" in value and "}}" in value:
            pattern = r'\{\{\s*([^}]+)\s*\}\}'
            matches = re.findall(pattern, value)

            for match in matches:
                try:
                    parts = re.split(r'\.|\[|\]', match)
                    parts = [p for p in parts if p]  # remove empty strings

                    result = stored_results
                    for part in parts:
                        if isinstance(result, dict):
                            if part in result:
                                result = result[part]
                            else:
                                # Try common list fields inside this dict
                                list_keys = ['messages', 'items', 'data', 'results']
                                found = False
                                for lk in list_keys:
                                    if lk in result and isinstance(result[lk], list):
                                        try:
                                            index = int(part)
                                            result = result[lk][index]
                                            found = True
                                            break
                                        except (ValueError, IndexError):
                                            continue
                                if not found:
                                    result = None
                                    break
                        elif isinstance(result, list):
                            try:
                                index = int(part)
                                result = result[index]
                            except (ValueError, IndexError):
                                result = None
                                break
                        else:
                            result = None
                            break

                    if result is not None:
                        value = value.replace(f"{{{{ {match} }}}}", str(result))

                except Exception as e:
                    logger.error(f"Error resolving parameter '{match}': {str(e)}")

            resolved[key] = value
        else:
            resolved[key] = value

    return resolved


@app.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str, user_id: str):
    """Get the status of a workflow execution"""
    try:
        logger.info(f"Fetching workflow status: {workflow_id}")
        
        # Get status from n8n
        n8n_status = await proxy_service.get_execution_status(workflow_id)
        
        # Get saved execution from Supabase
        db_execution = await supabase_service.get_workflow_execution(workflow_id, user_id)
        
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "n8n_status": n8n_status,
            "database_record": db_execution
        }
        
    except Exception as e:
        logger.error(f"Error fetching workflow status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching workflow status: {str(e)}"
        )


@app.post("/proxy/{app_name}/{action}", response_model=ProxyResponse)
async def proxy_app_request(
    app_name: str,
    action: str,
    request: ProxyRequest
):
    """
    Proxy requests to third-party APIs using user-specific OAuth tokens
    
    This endpoint is called by n8n workflows to interact with user's connected apps.
    
    Flow:
    1. Extract user_id and payload from request
    2. Fetch user's credentials for the specified app from Supabase
    3. Make API call to third-party service using user's OAuth tokens
    4. Return response to n8n workflow
    
    Supported apps and actions:
    - gmail: fetchEmails, sendEmail
    - slack: postMessage, listChannels
    - notion: createPage, searchPages
    - calendar: createEvent, listEvents
    - gdrive: listFiles, uploadFile
    """
    try:
        logger.info(f"[DEBUG] Received proxy request - app_name: '{app_name}', action: '{action}'")
        logger.info(f"[DEBUG] Request body - user_id: '{request.user_id}', payload: {request.payload}")
        
        if not request.user_id or request.user_id.strip() == "":
            logger.error(f"[ERROR] user_id is missing from request body!")
            return ProxyResponse(
                success=False,
                error="user_id is required in request body"
            )
        
        logger.info(f"Proxy request: {app_name}/{action} for user: {request.user_id}")
        
        result = await proxy_service.proxy_request(
            user_id=request.user_id,
            app_name=app_name,
            action=action,
            payload=request.payload
        )
        
        if result.get("success"):
            return ProxyResponse(
                success=True,
                data=result
            )
        else:
            return ProxyResponse(
                success=False,
                error=result.get("error", "Unknown error occurred")
            )
            
    except Exception as e:
        logger.error(f"Error in proxy request: {str(e)}")
        logger.exception(e)  # Add full exception traceback
        return ProxyResponse(
            success=False,
            error=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
