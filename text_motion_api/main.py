"""
Text-to-Motion API Gateway Service

This FastAPI service acts as a bridge between the browser frontend and the remote
WebSocket motion generation server. It handles:
- Multi-user session management
- Data format conversion (NPZ -> JSON)
- Temporary data storage with automatic cleanup
- Concurrent request handling
"""

import asyncio
import io
import json
import os
import time
import uuid
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import numpy as np
import websockets
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== Configuration ====================

class Config:
    """Service configuration"""
    # Remote WebSocket server settings (the actual motion generation server)
    REMOTE_WS_HOST = os.getenv("REMOTE_WS_HOST", "127.0.0.1")
    REMOTE_WS_PORT = int(os.getenv("REMOTE_WS_PORT", "8000"))
    REMOTE_WS_PATH = os.getenv("REMOTE_WS_PATH", "/ws")
    
    # Connection settings
    WS_MAX_SIZE = 50 * 1024 * 1024  # 50MB for large motion data
    WS_TIMEOUT = 60.0  # 60 seconds timeout for generation
    
    # Data storage settings
    DATA_RETENTION_MINUTES = int(os.getenv("DATA_RETENTION_MINUTES", "30"))
    CLEANUP_INTERVAL_MINUTES = int(os.getenv("CLEANUP_INTERVAL_MINUTES", "5"))
    MAX_STORED_MOTIONS_PER_USER = int(os.getenv("MAX_STORED_MOTIONS_PER_USER", "10"))
    
    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "10"))
    MAX_REQUESTS_PER_MINUTE_PER_IP = int(os.getenv("MAX_REQUESTS_PER_MINUTE_PER_IP", "60"))
    
    # CORS settings
    ALLOWED_ORIGINS = [origin.strip().rstrip("/") for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]
    STRICT_ORIGIN_CHECK = os.getenv("STRICT_ORIGIN_CHECK", "1") == "1"

    # Request/session security
    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0") == "1"
    REQUIRE_SESSION_FOR_API = os.getenv("REQUIRE_SESSION_FOR_API", "1") == "1"
    SERIALIZE_REMOTE_REQUESTS = os.getenv("SERIALIZE_REMOTE_REQUESTS", "1") == "1"
    # 允许同一 session_id 在不同 IP/设备上复用（更新 fingerprint），避免“Session does not belong to this client”
    ALLOW_SESSION_REBIND = os.getenv("ALLOW_SESSION_REBIND", "1") == "1"


# ==================== Data Models ====================

class TextToMotionRequest(BaseModel):
    """Request model for text-to-motion generation"""
    text: str = Field(..., min_length=1, max_length=500, description="Text description of the motion")
    motion_length: float = Field(default=4.0, ge=0.1, le=9.0, description="Motion duration in seconds")
    num_inference_steps: int = Field(default=10, ge=1, le=1000, description="Number of denoising steps")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")
    smooth: Optional[bool] = Field(default=None, description="Enable basic smoothing")
    smooth_window: int = Field(default=5, ge=3, description="Smoothing window size")
    adaptive_smooth: bool = Field(default=True, description="Enable adaptive smoothing")
    static_start: bool = Field(default=True, description="Force static start")
    static_frames: int = Field(default=2, ge=0, description="Number of static frames at start")
    blend_frames: int = Field(default=8, ge=0, description="Number of blend frames")
    transition_steps: int = Field(default=100, ge=0, le=300, description="Transition steps for smooth blending")


class MotionData(BaseModel):
    """Motion data response model"""
    name: str
    fps: float
    joint_pos: list  # List of lists, each inner list is a frame of joint positions
    root_pos: list   # List of [x, y, z] positions
    root_quat: list  # List of [w, x, y, z] quaternions
    frame_count: int
    duration: float
    created_at: str


class GenerationResponse(BaseModel):
    """Response model for successful generation"""
    success: bool
    motion_id: str
    motion: MotionData
    message: str


class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = False
    error: str
    code: str


@dataclass
class UserSession:
    """User session data"""
    session_id: str
    created_at: datetime
    last_activity: datetime
    motions: Dict[str, dict] = field(default_factory=dict)
    request_count: int = 0
    request_window_start: datetime = field(default_factory=datetime.now)
    client_fingerprint: str = ""


# ==================== Global State ====================

class AppState:
    """Application state manager"""
    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}
        self.lock = asyncio.Lock()
        self.cleanup_task: Optional[asyncio.Task] = None
        self.ip_rate: Dict[str, Dict[str, Any]] = {}

    async def get_or_create_session(self, session_id: Optional[str], client_fingerprint: str) -> UserSession:
        """Get existing session or create new one"""
        async with self.lock:
            if session_id:
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    if session.client_fingerprint and session.client_fingerprint != client_fingerprint:
                        if Config.ALLOW_SESSION_REBIND:
                            session.client_fingerprint = client_fingerprint
                            session.last_activity = datetime.now()
                            logger.info(f"Session {session_id} rebound to new client")
                            return session
                        raise PermissionError("Session fingerprint mismatch")
                    session.last_activity = datetime.now()
                    return session
            
            # Create new session
            new_session_id = str(uuid.uuid4())
            now = datetime.now()
            session = UserSession(
                session_id=new_session_id,
                created_at=now,
                last_activity=now,
                client_fingerprint=client_fingerprint
            )
            self.sessions[new_session_id] = session
            logger.info(f"Created new session: {new_session_id}")
            return session
    
    async def cleanup_expired_sessions(self):
        """Remove expired sessions and their data"""
        async with self.lock:
            now = datetime.now()
            expired_sessions = []
            
            for session_id, session in self.sessions.items():
                inactive_duration = now - session.last_activity
                session_age = now - session.created_at
                
                # Remove sessions inactive for too long or too old
                if (inactive_duration > timedelta(minutes=Config.DATA_RETENTION_MINUTES) or
                    session_age > timedelta(hours=2)):
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
                logger.info(f"Cleaned up expired session: {session_id}")
    
    def check_rate_limit(self, session: UserSession) -> bool:
        """Check if user has exceeded rate limit"""
        now = datetime.now()
        window_duration = now - session.request_window_start
        
        # Reset window if expired
        if window_duration > timedelta(minutes=1):
            session.request_count = 0
            session.request_window_start = now
        
        # Check limit
        if session.request_count >= Config.MAX_REQUESTS_PER_MINUTE:
            return False
        
        session.request_count += 1
        return True

    async def check_ip_rate_limit(self, client_ip: str) -> bool:
        now = datetime.now()
        async with self.lock:
            bucket = self.ip_rate.get(client_ip)
            if not bucket:
                self.ip_rate[client_ip] = {"count": 1, "start": now}
                return True

            window_duration = now - bucket["start"]
            if window_duration > timedelta(minutes=1):
                bucket["count"] = 1
                bucket["start"] = now
                return True

            if bucket["count"] >= Config.MAX_REQUESTS_PER_MINUTE_PER_IP:
                return False

            bucket["count"] += 1
            return True


app_state = AppState()
remote_generation_lock = asyncio.Lock()


def get_client_ip(http_request: Request) -> str:
    if Config.TRUST_PROXY_HEADERS:
        xff = http_request.headers.get("x-forwarded-for", "").strip()
        if xff:
            return xff.split(",")[0].strip()
    return (http_request.client.host if http_request.client else "unknown")


def get_client_fingerprint(http_request: Request) -> str:
    client_ip = get_client_ip(http_request)
    user_agent = http_request.headers.get("user-agent", "")
    raw = f"{client_ip}|{user_agent}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_allowed_origin(http_request: Request) -> None:
    if not Config.STRICT_ORIGIN_CHECK:
        return
    if not Config.ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=500,
            detail={"error": "Server misconfigured: ALLOWED_ORIGINS is empty", "code": "SERVER_CONFIG_ERROR"}
        )
    origin = (http_request.headers.get("origin") or "").strip().rstrip("/")
    if not origin or origin not in Config.ALLOWED_ORIGINS:
        raise HTTPException(
            status_code=403,
            detail={"error": "Origin not allowed", "code": "ORIGIN_FORBIDDEN"}
        )


def _is_valid_session_id(s: Optional[str]) -> bool:
    """只接受 UUID 格式的 session_id，避免非法头注入或异常 key。"""
    if not s or not isinstance(s, str) or len(s) > 64:
        return False
    try:
        uuid.UUID(s)
        return True
    except (ValueError, TypeError):
        return False


async def get_bound_session(http_request: Request, allow_create: bool) -> UserSession:
    session_id_raw = http_request.headers.get("X-Session-ID")
    session_id = (session_id_raw or "").strip() or None
    if session_id and not _is_valid_session_id(session_id):
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid X-Session-ID format", "code": "INVALID_SESSION_ID"}
        )
    fingerprint = get_client_fingerprint(http_request)
    if not session_id and Config.REQUIRE_SESSION_FOR_API and not allow_create:
        raise HTTPException(
            status_code=401,
            detail={"error": "Missing X-Session-ID", "code": "SESSION_REQUIRED"}
        )
    try:
        if allow_create:
            return await app_state.get_or_create_session(session_id=session_id, client_fingerprint=fingerprint)
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail={"error": "Missing X-Session-ID", "code": "SESSION_REQUIRED"}
            )
        return await app_state.get_or_create_session(session_id=session_id, client_fingerprint=fingerprint)
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail={"error": "Session does not belong to this client", "code": "SESSION_FORBIDDEN"}
        )


# ==================== Background Tasks ====================

async def periodic_cleanup():
    """Periodically clean up expired sessions"""
    while True:
        try:
            await asyncio.sleep(Config.CLEANUP_INTERVAL_MINUTES * 60)
            await app_state.cleanup_expired_sessions()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Text-to-Motion API Gateway")
    app_state.cleanup_task = asyncio.create_task(periodic_cleanup())
    yield
    # Shutdown
    logger.info("Shutting down Text-to-Motion API Gateway")
    if app_state.cleanup_task:
        app_state.cleanup_task.cancel()
        try:
            await app_state.cleanup_task
        except asyncio.CancelledError:
            pass


# ==================== FastAPI App ====================

app = FastAPI(
    title="Text-to-Motion API Gateway",
    description="Bridge service between browser frontend and remote motion generation server",
    version="1.0.0",
    lifespan=lifespan
)

# CORS: allow_credentials=True 时浏览器不允许 allow_origins=["*"]，需配置具体域名。
_origins = list(Config.ALLOWED_ORIGINS) if Config.ALLOWED_ORIGINS else []
if "*" in _origins and len(_origins) == 1:
    logger.warning("ALLOWED_ORIGINS=* is incompatible with credentials; CORS will allow no origins. Set explicit origins.")
    _origins = []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Session-ID"],
)


# ==================== Helper Functions ====================

def convert_npz_to_motion_data(npz_bytes: bytes, motion_name: str) -> dict:
    """
    Convert NPZ binary data to JSON-serializable motion data
    
    The input NPZ contains (38D format):
    - fps: (1,) int32
    - joint_pos: (T, 29) float32 [Isaac order]
    - root_pos: (T, 3) float32
    - root_rot: (T, 4) float32 [w, x, y, z]
    
    Output format matches what TrackingHelper expects:
    - joint_pos: array of arrays (T frames x 29 joints)
    - root_pos: array of [x, y, z]
    - root_quat: array of [w, x, y, z]
    """
    data = np.load(io.BytesIO(npz_bytes))
    
    fps = int(data['fps'][0]) if isinstance(data['fps'], np.ndarray) else int(data['fps'])
    joint_pos = data['joint_pos'].astype(np.float32)
    root_pos = data['root_pos'].astype(np.float32)
    root_rot = data['root_rot'].astype(np.float32)  # [w, x, y, z]
    
    frame_count = joint_pos.shape[0]
    duration = frame_count / fps
    
    # Convert to lists for JSON serialization
    motion_data = {
        'name': motion_name,
        'fps': float(fps),
        'joint_pos': joint_pos.tolist(),
        'root_pos': root_pos.tolist(),
        'root_quat': root_rot.tolist(),  # Already in wxyz format
        'frame_count': frame_count,
        'duration': duration,
        'created_at': datetime.now().isoformat()
    }
    
    return motion_data


async def generate_motion_from_remote(request_data: dict) -> bytes:
    """
    Connect to remote WebSocket server and generate motion
    
    Returns raw NPZ bytes on success
    """
    uri = f"ws://{Config.REMOTE_WS_HOST}:{Config.REMOTE_WS_PORT}{Config.REMOTE_WS_PATH}"
    
    async def _request_remote() -> bytes:
        async with websockets.connect(
            uri,
            max_size=Config.WS_MAX_SIZE,
            open_timeout=10.0
        ) as ws:
            # Send request
            await ws.send(json.dumps(request_data))
            logger.info(f"Sent request to remote server: {request_data.get('text', '')[:50]}...")
            
            # Receive response with timeout
            response = await asyncio.wait_for(
                ws.recv(),
                timeout=Config.WS_TIMEOUT
            )
            
            # Check if error response (JSON string)
            if isinstance(response, str):
                try:
                    error_data = json.loads(response)
                    error_msg = error_data.get('error', 'Unknown error')
                    error_code = error_data.get('code', 'SERVER_ERROR')
                    raise HTTPException(
                        status_code=500,
                        detail={"error": error_msg, "code": error_code}
                    )
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500,
                        detail={"error": "Invalid response from server", "code": "INVALID_RESPONSE"}
                    )
            return response

    try:
        if Config.SERIALIZE_REMOTE_REQUESTS:
            async with remote_generation_lock:
                return await _request_remote()
        return await _request_remote()
            
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"error": "Request timeout - generation took too long", "code": "TIMEOUT"}
        )
    except websockets.exceptions.ConnectionRefused:
        raise HTTPException(
            status_code=503,
            detail={"error": "Motion generation server unavailable", "code": "SERVER_UNAVAILABLE"}
        )
    except websockets.exceptions.WebSocketException as e:
        raise HTTPException(
            status_code=502,
            detail={"error": f"WebSocket error: {str(e)}", "code": "WEBSOCKET_ERROR"}
        )


def enforce_motion_limit(session: UserSession):
    """Enforce maximum number of stored motions per user"""
    if len(session.motions) >= Config.MAX_STORED_MOTIONS_PER_USER:
        # Remove oldest motion
        oldest_id = min(session.motions.keys(), 
                       key=lambda k: session.motions[k].get('created_at', ''))
        del session.motions[oldest_id]
        logger.info(f"Removed oldest motion {oldest_id} for session {session.session_id}")


# ==================== API Endpoints ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Text-to-Motion API Gateway",
        "version": "1.0.0",
        "remote_server": f"{Config.REMOTE_WS_HOST}:{Config.REMOTE_WS_PORT}",
        "active_sessions": len(app_state.sessions)
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "active_sessions": len(app_state.sessions),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/generate", response_model=GenerationResponse)
async def generate_motion(
    request: TextToMotionRequest,
    background_tasks: BackgroundTasks,
    http_request: Request
):
    """
    Generate motion from text description
    
    This endpoint:
    1. Receives text description and parameters
    2. Forwards to remote WebSocket server
    3. Converts NPZ response to JSON
    4. Stores motion data for the session
    5. Returns motion data to client
    """
    require_allowed_origin(http_request)
    session = await get_bound_session(http_request, allow_create=False)
    client_ip = get_client_ip(http_request)
    
    # Check rate limit
    if not app_state.check_rate_limit(session):
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded - max 10 requests per minute", "code": "RATE_LIMIT"}
        )
    if not await app_state.check_ip_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded for IP", "code": "IP_RATE_LIMIT"}
        )
    
    # Prepare request for remote server
    request_data = {
        "text": request.text,
        "motion_length": request.motion_length,
        "num_inference_steps": request.num_inference_steps,
        "seed": request.seed if request.seed is not None else int(time.time() % 10000),
        "smooth": request.smooth,
        "smooth_window": request.smooth_window,
        "adaptive_smooth": request.adaptive_smooth,
        "static_start": request.static_start,
        "static_frames": request.static_frames,
        "blend_frames": request.blend_frames
    }
    
    # Remove None values
    request_data = {k: v for k, v in request_data.items() if v is not None}
    
    try:
        # Generate motion from remote server
        npz_bytes = await generate_motion_from_remote(request_data)
        
        # Generate motion ID
        motion_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        motion_name = f"[AI] {request.text[:30]}"
        
        # Convert to motion data
        motion_data = convert_npz_to_motion_data(npz_bytes, motion_name)
        motion_data['motion_id'] = motion_id
        motion_data['text_prompt'] = request.text
        motion_data['parameters'] = {
            "motion_length": request.motion_length,
            "num_inference_steps": request.num_inference_steps,
            "adaptive_smooth": request.adaptive_smooth,
            "static_start": request.static_start,
            "transition_steps": request.transition_steps
        }
        
        # Store in session (enforce limit)
        enforce_motion_limit(session)
        session.motions[motion_id] = motion_data
        
        logger.info(f"Generated motion {motion_id} for session {session.session_id}")
        
        return GenerationResponse(
            success=True,
            motion_id=motion_id,
            motion=MotionData(**{k: v for k, v in motion_data.items() 
                                if k in ['name', 'fps', 'joint_pos', 'root_pos', 'root_quat', 
                                        'frame_count', 'duration', 'created_at']}),
            message="Motion generated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation error: {e}")
        # 不向客户端返回内部异常详情，避免信息泄露
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to generate motion", "code": "GENERATION_FAILED"}
        )


@app.get("/api/motions")
async def list_motions(http_request: Request):
    """List all motions for the current session"""
    require_allowed_origin(http_request)
    session = await get_bound_session(http_request, allow_create=False)
    session.last_activity = datetime.now()
    
    motions_list = [
        {
            "motion_id": mid,
            "name": mdata.get("name", "Unknown"),
            "frame_count": mdata.get("frame_count", 0),
            "duration": mdata.get("duration", 0),
            "created_at": mdata.get("created_at", ""),
            "text_prompt": mdata.get("text_prompt", "")[:100]
        }
        for mid, mdata in session.motions.items()
    ]
    
    return {
        "motions": sorted(motions_list, key=lambda x: x["created_at"], reverse=True),
        "session_id": session.session_id
    }


@app.get("/api/motions/{motion_id}")
async def get_motion(motion_id: str, http_request: Request):
    """Get specific motion data by ID"""
    require_allowed_origin(http_request)
    session = await get_bound_session(http_request, allow_create=False)
    session.last_activity = datetime.now()
    
    if motion_id not in session.motions:
        raise HTTPException(status_code=404, detail="Motion not found")
    
    return session.motions[motion_id]


@app.delete("/api/motions/{motion_id}")
async def delete_motion(motion_id: str, http_request: Request):
    """Delete a specific motion"""
    require_allowed_origin(http_request)
    session = await get_bound_session(http_request, allow_create=False)
    
    if motion_id not in session.motions:
        raise HTTPException(status_code=404, detail="Motion not found")
    
    del session.motions[motion_id]
    logger.info(f"Deleted motion {motion_id} from session {session.session_id}")
    
    return {"success": True, "message": "Motion deleted"}


@app.delete("/api/motions")
async def clear_motions(http_request: Request):
    """Clear all generated motions for the current session"""
    require_allowed_origin(http_request)
    session = await get_bound_session(http_request, allow_create=False)
    count = len(session.motions)
    session.motions.clear()
    logger.info(f"Cleared {count} motions for session {session.session_id}")
    return {"success": True, "cleared": count}


@app.post("/api/session")
async def create_session(http_request: Request):
    """Create or resume a bound session for current client"""
    require_allowed_origin(http_request)
    session = await get_bound_session(http_request, allow_create=True)
    return {
        "session_id": session.session_id,
        "created_at": session.created_at.isoformat(),
        "message": "Session created successfully"
    }


@app.get("/api/config")
async def get_config():
    """Get service configuration (safe values only)"""
    return {
        "max_motion_length": 9.0,
        "min_motion_length": 0.1,
        "max_inference_steps": 1000,
        "min_inference_steps": 1,
        "default_motion_length": 4.0,
        "default_inference_steps": 10,
        "max_stored_motions": Config.MAX_STORED_MOTIONS_PER_USER,
        "data_retention_minutes": Config.DATA_RETENTION_MINUTES
    }


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail.get("error", str(exc.detail)) if isinstance(exc.detail, dict) else str(exc.detail),
            "code": exc.detail.get("code", "UNKNOWN") if isinstance(exc.detail, dict) else "UNKNOWN"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "code": "INTERNAL_ERROR"
        }
    )


# ==================== Main Entry Point ====================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Remote WebSocket: {Config.REMOTE_WS_HOST}:{Config.REMOTE_WS_PORT}")
    
    uvicorn.run(app, host=host, port=port)
