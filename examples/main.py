from fastapi import FastAPI, Depends, HTTPException
from fastapi_payments import FastAPIPayments, create_payment_module
import json
import os
import uvicorn
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("payment_app")

# Create FastAPI app
app = FastAPI(title="Payment API", description="FastAPI Payment Service")

# Load payment configuration
config_path = os.environ.get("PAYMENT_CONFIG", "config/payment_config.json")
try:
    with open(config_path) as f:
        config = json.load(f)

    # Initialize payments module
    payments = FastAPIPayments(config)

    # Include payment routes
    payments.include_router(app, prefix="/api")

    logger.info("Payment module initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize payment module: {str(e)}")
    # Continue without payment module, it will be initialized during startup


# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up payment application")
    # Additional startup tasks can be added here


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down payment application")
    # Cleanup tasks can be added here


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Base route
@app.get("/")
async def root():
    return {
        "message": "Welcome to the Payment API",
        "docs": "/docs",
        "version": "0.1.1",
    }


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
