from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import logging

from services.gemini_service import GeminiService
from services.supabase_service import SupabaseService
from services.n8n_service import N8nService
from services.proxy_service import ProxyService

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
n8n_service = N8nService()
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
    workflow_id: str
    user_id: str
    bearer_token: str
    parameters: Optional[Dict[str, Any]] = None


class ExecuteWorkflowResponse(BaseModel):
    status: str
    message: str
    execution_id: Optional[str] = None
    workflow_result: Optional[Dict[str, Any]] = None


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
    body: Optional[Dict[str, Any]] = None


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
            "supabase": "operational",
            "n8n": "operational"
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
        logger.info("Fetching all workflow templates from Supabase")
        templates = await supabase_service.get_all_workflow_templates()
        print(templates)
        
        # Step 1: Send prompt to Gemini for analysis
        logger.info("Sending prompt to Gemini 2.5 Flash")
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
        n8n_credential_id = await n8n_service.create_user_credential(
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
    Execute n8n workflow via webhook with user-specific credentials
    
    Flow:
    1. Fetch workflow webhook URL from database
    2. Retrieve user's credentials from Supabase
    3. Trigger n8n workflow via webhook GET request
    4. Save workflow execution to Supabase
    5. Return execution status
    """
    try:
        logger.info(f"Executing workflow {request.workflow_id} for user: {request.user_id}")
        
        logger.info(f"Fetching webhook URL for workflow: {request.workflow_id}")
        webhook_url = await supabase_service.get_workflow_webhook_url(request.workflow_id)
        
        if not webhook_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook URL not found for workflow: {request.workflow_id}"
            )
        
        logger.info(f"Triggering n8n workflow via webhook: {webhook_url}")
        execution_result = await n8n_service.trigger_workflow_webhook(
            webhook_url=webhook_url,
            user_id=request.user_id,
            parameters=request.parameters or {}
        )
        
        if not execution_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to execute n8n workflow: {execution_result.get('error')}"
            )
        
        execution_id = execution_result.get("execution_id")
        
        # Step 3: Save workflow execution to Supabase
        logger.info(f"Saving workflow execution to database: {execution_id}")
        await supabase_service.save_workflow_execution(
            user_id=request.user_id,
            workflow_id=request.workflow_id,
            execution_id=execution_id,
            status="running",
            parameters=request.parameters
        )
        
        logger.info(f"Workflow execution initiated successfully: {execution_id}")
        
        return ExecuteWorkflowResponse(
            status="success",
            message="Workflow execution initiated successfully",
            execution_id=execution_id,
            workflow_result=execution_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing workflow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing workflow: {str(e)}"
        )


@app.get("/workflow/{workflow_id}/status")
async def get_workflow_status(workflow_id: str, user_id: str):
    """Get the status of a workflow execution"""
    try:
        logger.info(f"Fetching workflow status: {workflow_id}")
        
        # Get status from n8n
        n8n_status = await n8n_service.get_execution_status(workflow_id)
        
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
        logger.info(f"Proxy request: {request} -> {app_name}/{action} for user: {request.user_id}")

        
        result = await proxy_service.proxy_request(
            user_id=request.user_id,
            app_name=app_name,
            action=action,
            payload=request.body
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
        return ProxyResponse(
            success=False,
            error=str(e)
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
