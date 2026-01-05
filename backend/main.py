import os
import sys
import logging

from utils.logging import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Check if development mode
is_development = os.environ.get("NODE_ENV") != "production"

import uvicorn


if __name__ == "__main__":
    from const.config import Config
    
    logger.info(f"Starting {Config.APP_NAME} API on port {Config.PORT}")
    logger.info(f"Environment: {Config.ENVIRONMENT}")
    
    # Run the FastAPI app with uvicorn
    try:
        uvicorn.run(
            "api:app",
            host="0.0.0.0",
            port=Config.PORT,
            reload=is_development,
            reload_excludes=["**/logs/*", "**/__pycache__/*", "**/*.pyc"] if is_development else None,
            log_config=None,  # Use our logging configuration instead of uvicorn's default
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.exception("Server startup error details:")
        raise
