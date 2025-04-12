.PHONY: clean build test lint upload-test upload docs

PYTHON := python3
PIP := pip
PYTEST := pytest
TWINE := twine

clean:
	@echo "Cleaning up build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +

deps:
	@echo "Installing dependencies..."
	$(PIP) install -e ".[dev]"
	$(PIP) install -e ".[test]"
	$(PIP) install build twine

build: clean
	@echo "Building package..."
	$(PYTHON) -m build

test:
	@echo "Running tests..."
	$(PYTEST) tests/ -v

lint:
	@echo "Checking code quality..."
	flake8 src/ tests/
	mypy src/ --ignore-missing-imports

coverage:
	@echo "Running tests with coverage..."
	$(PYTEST) --cov=fastapi_payments tests/ --cov-report=html

upload-test: build
	@echo "Uploading to TestPyPI..."
	$(TWINE) upload --repository-url https://test.pypi.org/legacy/ dist/*

upload: build
	@echo "Uploading to PyPI..."
	$(TWINE) upload dist/*

docs:
	@echo "Building documentation..."
	cd docs && make html

dev-install: clean
	@echo "Installing in development mode..."
	$(PIP) install -e .

bump-version:
	@echo "Bumping version..."
	$(PYTHON) scripts/bump_version.py

check-release: build
	$(TWINE) check dist/*

# release: test lint check-release upload
# 	@echo "Release complete"

release: clean test check-release upload
	@echo "Release complete"

install-test-deps:
	@echo "Installing test dependencies..."
	$(PIP) install email-validator faststream[memory]
	$(PIP) install -e ".[dev]"
	
help:
	@echo "Available commands:"
	@echo "  clean         - Remove build artifacts"
	@echo "  deps          - Install development dependencies"
	@echo "  build         - Build package"
	@echo "  test          - Run tests"
	@echo "  lint          - Check code quality"
	@echo "  coverage      - Generate test coverage report"
	@echo "  upload-test   - Upload to TestPyPI"
	@echo "  upload        - Upload to PyPI"
	@echo "  docs          - Build documentation"
	@echo "  dev-install   - Install package in development mode"
	@echo "  bump-version  - Increment version number"
	@echo "  check-release - Check if the package is ready for release"
	@echo "  release       - Run tests, lint, check, and upload to PyPI"