#!/bin/bash
# Install test dependencies

pip install email-validator
pip install "faststream[memory]>=0.2.0"
pip install pytest pytest-asyncio
pip install aiosqlite

# Install development version of package
pip install -e .

echo "Test dependencies installed successfully!"