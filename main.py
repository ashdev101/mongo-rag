"""
Tata Play Main Application
Supports both FastAPI (for Teams chat) and Gradio UI
"""
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
import uuid

from app import QueryProcessor
from backend.config import get_settings
from backend.routes import router
from backend.logging_config import setup_logging, get_logger

# Get application settings
settings = get_settings()

# Setup production-ready logging
setup_logging(
    environment=settings.ENVIRONMENT,
    log_level=settings.LOG_LEVEL,
    log_dir=settings.LOG_DIR,
    app_name="tataplay"
)

# Get loggers
logger = get_logger(__name__)
access_logger = get_logger("access")

# =====================================================================
# FastAPI Application Setup
# =====================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("=" * 60)
    logger.info("Tata Play Chat Backend Starting (v2.0)...")
    logger.info("Authentication and API routes configured")
    logger.info("=" * 60)
    yield
    # Shutdown
    logger.info("Tata Play Chat Backend Shutting Down...")


app = FastAPI(
    title="Tata Play Chat Backend",
    description="Backend API for Teams HR bot application",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests and responses with structured logging."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log incoming request
    access_logger.info(
        f"Incoming request: {request.method} {request.url.path}",
        extra={
            "request_id": request_id,
            "method": request.method,
            "endpoint": request.url.path,
            "user_agent": request.headers.get("user-agent", "unknown"),
            "content_type": request.headers.get("content-type", ""),
        }
    )
    
    # Store request_id in request state for use in routes
    request.state.request_id = request_id
    
    # Process the request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response
        access_logger.info(
            f"Request completed: {request.method} {request.url.path} - Status: {response.status_code}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "endpoint": request.url.path,
                "status_code": response.status_code,
                "duration": round(process_time, 3),
            }
        )
        
        # Add custom headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        
        # Log error
        logger.error(
            f"Request failed: {request.method} {request.url.path}",
            exc_info=True,
            extra={
                "request_id": request_id,
                "method": request.method,
                "endpoint": request.url.path,
                "duration": round(process_time, 3),
            }
        )
        raise

# Include API routes
app.include_router(router)


# =====================================================================
# Gradio UI Setup
# =====================================================================
from app import QueryProcessor, run_query as app_run_query, run_policy_query, combined_execute

processor = QueryProcessor()


def run_query_wrapper(email, question):
    """
    Wrapper for Gradio UI - returns 5 values including agg_pipeline.
    """
    try:
        status, agent_out_str, mql, db_results, agg_pipeline = app_run_query(email, question)
        return status, agent_out_str, mql, db_results
    except Exception as e:
        return "Error", str(e), None, None


with gr.Blocks(title="MQL Access Agent UI (robust)") as demo:

    gr.Markdown("# 🚀 Natural Language → MQL Query + Policy Q&A + Combined Router")

    with gr.Tabs():

        # =============================================================
        # TAB 1 — MQL Access Agent UI
        # =============================================================
        with gr.Tab("MQL Agent"):
            gr.Markdown("### Enter your email and natural language query.")

            with gr.Row():
                email_in = gr.Textbox(label="Email")
                query_in = gr.Textbox(
                    label="Natural Language Query",
                    lines=2,
                    value="give me the name of the people who have resigned in the year 2022 in march?"
                )

            run_btn = gr.Button("Run Query")

            with gr.Row():
                status_out = gr.Textbox(label="Decision (Allowed / Denied / Error)")
                mql_out = gr.Textbox(label="Generated MQL Query")

            with gr.Accordion("Agent Raw Output (JSON-ish)", open=False):
                agent_out = gr.Textbox(lines=8)

            db_out = gr.Textbox(label="Database Results / Converter Output", lines=12)

            run_btn.click(
                run_query_wrapper,
                inputs=[email_in, query_in],
                outputs=[status_out, agent_out, mql_out, db_out]
            )

        # =============================================================
        # TAB 2 — Policy Documentation Q&A
        # =============================================================
        with gr.Tab("Policy Docs"):
            gr.Markdown("### Ask a question about policy documents.")

            policy_question = gr.Textbox(label="Policy Question", lines=2)
            policy_btn = gr.Button("Ask Policy Engine")
            policy_output = gr.Textbox(label="Answer", lines=10)

            policy_btn.click(
                run_policy_query,
                inputs=policy_question,
                outputs=policy_output
            )

        # =============================================================
        # TAB 3 — Combined Router
        # =============================================================
        with gr.Tab("Combined"):
            gr.Markdown("### Unified Query Interface (Router → Document/Policy)")

            with gr.Row():
                combined_email = gr.Textbox(label="Email")
                combined_question = gr.Textbox(label="Your Question", lines=2)

            combined_btn = gr.Button("Run Combined Router")

            router_output = gr.Textbox(label="Router Output (JSON)", lines=6)

            final_text = gr.Textbox(
                label="Final Result (Text)",
                lines=6,
                visible=False
            )

            final_file = gr.File(
                label="Final Result (File)",
                visible=False
            )

            combined_btn.click(
                combined_execute,
                inputs=[combined_email, combined_question],
                outputs=[router_output, final_text, final_file]
            )

# Mount Gradio app to FastAPI
app = gr.mount_gradio_app(app, demo, path="/gradio")


# =====================================================================
# Main entry point
# =====================================================================
if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on port {settings.PORT}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("Server ready - check /docs for API documentation")
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,  # Auto-reload only in development
    )