#!/bin/bash

# Test Runner Script for Discord IP Monitor Bot
# Runs comprehensive test suite with coverage reporting

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_PATH="./.venv"
COVERAGE_THRESHOLD=80
PARALLEL_WORKERS="auto"
VERBOSE=false
COVERAGE_REPORT="term-missing"
SPECIFIC_TEST=""
QUICK_MODE=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -v, --verbose           Run tests with verbose output
    -q, --quick             Quick mode: skip coverage and run basic tests only
    -p, --parallel WORKERS  Number of parallel workers (default: auto)
    -c, --coverage FORMAT   Coverage report format: term, term-missing, html, xml (default: term-missing)
    -t, --test PATH         Run specific test file or directory
    --threshold NUM         Coverage threshold percentage (default: 80)
    --no-coverage           Skip coverage reporting entirely

Examples:
    $0                                          # Run all tests with coverage
    $0 -v                                       # Run all tests verbosely
    $0 -q                                       # Quick test run without coverage
    $0 -t tests/unit/bot/                      # Run only bot tests
    $0 -t tests/unit/config/                   # Run only configuration tests
    $0 -t tests/unit/test_storage.py          # Run specific test file
    $0 -c html --threshold 85                 # Generate HTML coverage report with 85% threshold
    $0 -p 4 -v                                 # Run with 4 parallel workers, verbose output
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quick)
            QUICK_MODE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL_WORKERS="$2"
            shift 2
            ;;
        -c|--coverage)
            COVERAGE_REPORT="$2"
            shift 2
            ;;
        -t|--test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        --threshold)
            COVERAGE_THRESHOLD="$2"
            shift 2
            ;;
        --no-coverage)
            COVERAGE_REPORT=""
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Function to check if virtual environment exists
check_venv() {
    if [[ ! -d "$VENV_PATH" ]]; then
        print_error "Virtual environment not found at $VENV_PATH"
        print_status "Please run: python3 -m venv $VENV_PATH && source $VENV_PATH/bin/activate && pip install -r requirements.txt"
        exit 1
    fi
}

# Function to activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    
    # Verify pytest is available
    if ! command -v pytest &> /dev/null; then
        print_error "pytest not found in virtual environment"
        print_status "Please install testing dependencies: pip install pytest pytest-asyncio pytest-mock pytest-cov"
        exit 1
    fi
}

# Function to run linting before tests
run_linting() {
    if [[ "$QUICK_MODE" == "true" ]]; then
        return 0
    fi
    
    print_status "Running code linting and formatting checks..."
    
    # Check if ruff is available
    if command -v ruff &> /dev/null; then
        print_status "Running ruff format check..."
        if ! ruff format --check --exclude .venv .; then
            print_warning "Code formatting issues found. Run: ruff format ."
        fi
        
        print_status "Running ruff linting..."
        if ! ruff check --exclude .venv .; then
            print_warning "Linting issues found. Run: ruff check --fix --exclude .venv ."
        fi
    else
        print_warning "ruff not found, skipping linting checks"
    fi
    
    # Check if isort is available
    if command -v isort &> /dev/null; then
        print_status "Running import sorting check..."
        if ! isort --check-only .; then
            print_warning "Import sorting issues found. Run: isort ."
        fi
    else
        print_warning "isort not found, skipping import sorting check"
    fi
}

# Function to run unit tests
run_unit_tests() {
    print_status "Running unit tests..."
    
    local pytest_args=()
    
    # Add test path
    if [[ -n "$SPECIFIC_TEST" ]]; then
        pytest_args+=("$SPECIFIC_TEST")
    else
        pytest_args+=("tests/unit/")
    fi
    
    # Add verbosity
    if [[ "$VERBOSE" == "true" ]]; then
        pytest_args+=("-v")
    fi
    
    # Add parallel execution
    if command -v pytest-xdist &> /dev/null && [[ "$PARALLEL_WORKERS" != "1" ]]; then
        pytest_args+=("-n" "$PARALLEL_WORKERS")
    fi
    
    # Add coverage options
    if [[ -n "$COVERAGE_REPORT" && "$QUICK_MODE" != "true" ]]; then
        pytest_args+=("--cov=ip_monitor" "--cov=main")
        pytest_args+=("--cov-report=$COVERAGE_REPORT")
        pytest_args+=("--cov-fail-under=$COVERAGE_THRESHOLD")
        
        # Add HTML coverage if requested
        if [[ "$COVERAGE_REPORT" == "html" ]]; then
            pytest_args+=("--cov-report=html:htmlcov")
        fi
        
        # Add XML coverage if requested
        if [[ "$COVERAGE_REPORT" == "xml" ]]; then
            pytest_args+=("--cov-report=xml:coverage.xml")
        fi
    fi
    
    # Add other useful options
    pytest_args+=("--tb=short")  # Shorter traceback format
    pytest_args+=("--strict-markers")  # Strict marker checking
    
    print_status "Running: pytest ${pytest_args[*]}"
    pytest "${pytest_args[@]}"
}

# Function to run integration tests
run_integration_tests() {
    if [[ "$QUICK_MODE" == "true" ]]; then
        return 0
    fi
    
    print_status "Running integration tests..."
    
    local pytest_args=("tests/integration/")
    
    if [[ "$VERBOSE" == "true" ]]; then
        pytest_args+=("-v")
    fi
    
    pytest_args+=("--tb=short")
    
    # Run integration tests (these might take longer)
    if [[ -d "tests/integration" ]]; then
        print_status "Running: pytest ${pytest_args[*]}"
        pytest "${pytest_args[@]}" || {
            print_warning "Some integration tests failed, but continuing..."
        }
    else
        print_warning "Integration tests directory not found, skipping..."
    fi
}

# Function to run specific test categories
run_test_categories() {
    if [[ -n "$SPECIFIC_TEST" ]]; then
        return 0  # Skip category tests if specific test is requested
    fi
    
    print_status "Running test categories..."
    
    # Bot tests
    if [[ -d "tests/unit/bot" ]]; then
        print_status "Running bot tests..."
        pytest tests/unit/bot/ -v --tb=short
    fi
    
    # Configuration tests (refactored modular structure)
    if [[ -d "tests/unit/config" ]]; then
        print_status "Running configuration tests..."
        pytest tests/unit/config/ -v --tb=short
    fi
    
    # Admin command tests
    if [[ -d "tests/unit/commands/admin_commands" ]]; then
        print_status "Running admin command tests..."
        pytest tests/unit/commands/admin_commands/ -v --tb=short
    fi
    
    # Core service tests
    for test_file in tests/unit/test_storage.py tests/unit/test_ip_service.py; do
        if [[ -f "$test_file" ]]; then
            print_status "Running $(basename $test_file)..."
            pytest "$test_file" -v --tb=short
        fi
    done
}

# Function to generate test summary
generate_summary() {
    print_status "Test execution completed!"
    
    if [[ -f "htmlcov/index.html" ]]; then
        print_success "HTML coverage report generated: htmlcov/index.html"
    fi
    
    if [[ -f "coverage.xml" ]]; then
        print_success "XML coverage report generated: coverage.xml"
    fi
    
    print_status "Test summary:"
    echo "  - Virtual environment: $VENV_PATH"
    echo "  - Coverage threshold: $COVERAGE_THRESHOLD%"
    echo "  - Parallel workers: $PARALLEL_WORKERS"
    echo "  - Coverage format: ${COVERAGE_REPORT:-disabled}"
    echo "  - Quick mode: $QUICK_MODE"
    echo "  - Verbose output: $VERBOSE"
    
    if [[ -n "$SPECIFIC_TEST" ]]; then
        echo "  - Specific test: $SPECIFIC_TEST"
    fi
}

# Function to cleanup on exit
cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        print_error "Tests failed with exit code $exit_code"
    else
        print_success "All tests completed successfully!"
    fi
    
    # Deactivate virtual environment if it was activated
    if [[ -n "$VIRTUAL_ENV" ]]; then
        deactivate 2>/dev/null || true
    fi
    
    exit $exit_code
}

# Set up trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    print_status "Starting Discord IP Monitor Bot test suite..."
    print_status "Working directory: $(pwd)"
    
    # Check prerequisites
    check_venv
    activate_venv
    
    # Run linting if not in quick mode
    run_linting
    
    # Run tests based on mode
    if [[ "$QUICK_MODE" == "true" ]]; then
        print_status "Quick mode: Running basic unit tests only..."
        local test_path="${SPECIFIC_TEST:-tests/unit/}"
        local pytest_args=("$test_path" "-x" "--tb=short")
        
        # Disable coverage in quick mode by overriding pytest.ini
        pytest_args+=("--override-ini=addopts=")
        
        # Add verbosity if requested
        if [[ "$VERBOSE" == "true" ]]; then
            pytest_args+=("-v")
        fi
        
        pytest "${pytest_args[@]}"
    else
        # Full test suite
        run_unit_tests
        
        # Run integration tests if they exist
        run_integration_tests
        
        # Run specific test categories for detailed reporting
        if [[ "$VERBOSE" == "true" && -z "$SPECIFIC_TEST" ]]; then
            run_test_categories
        fi
    fi
    
    # Generate summary
    generate_summary
}

# Run main function
main "$@"