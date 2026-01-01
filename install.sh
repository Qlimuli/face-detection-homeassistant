#!/bin/bash
# ==============================================================================
# Local Face Secure - Installation and Verification Script
# ==============================================================================
# This script helps install and verify the Local Face Secure component
# 
# Usage:
#   ./install.sh                    - Install component
#   ./install.sh --verify           - Verify installation
#   ./install.sh --uninstall        - Remove component
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPONENT_NAME="local_face_secure"
HA_CONFIG_DIR="${HOME_ASSISTANT_CONFIG:-/config}"
CUSTOM_COMPONENTS_DIR="$HA_CONFIG_DIR/custom_components"
TARGET_DIR="$CUSTOM_COMPONENTS_DIR/$COMPONENT_NAME"

# Helper functions
print_header() {
    echo -e "${BLUE}===============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===============================================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Check if running on Home Assistant OS
check_environment() {
    if [ ! -d "$HA_CONFIG_DIR" ]; then
        print_error "Home Assistant config directory not found: $HA_CONFIG_DIR"
        print_info "Set HOME_ASSISTANT_CONFIG environment variable if using custom path"
        exit 1
    fi
    print_success "Home Assistant config directory found: $HA_CONFIG_DIR"
}

# Install component
install_component() {
    print_header "Installing Local Face Secure Component"
    
    # Check environment
    check_environment
    
    # Create custom_components directory if it doesn't exist
    if [ ! -d "$CUSTOM_COMPONENTS_DIR" ]; then
        print_info "Creating custom_components directory..."
        mkdir -p "$CUSTOM_COMPONENTS_DIR"
        print_success "Directory created"
    fi
    
    # Check if component already exists
    if [ -d "$TARGET_DIR" ]; then
        print_warning "Component already exists at: $TARGET_DIR"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled"
            exit 0
        fi
        print_info "Removing existing installation..."
        rm -rf "$TARGET_DIR"
    fi
    
    # Copy component files
    print_info "Copying component files..."
    
    # Get the directory where this script is located
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    
    # Copy the entire component directory
    cp -r "$SCRIPT_DIR" "$TARGET_DIR"
    
    # Remove non-component files
    rm -f "$TARGET_DIR/install.sh"
    rm -f "$TARGET_DIR/configuration.yaml.example"
    rm -f "$TARGET_DIR/TESTING.md"
    
    print_success "Component files copied"
    
    # Check if component is in configuration.yaml
    if grep -q "^$COMPONENT_NAME:" "$HA_CONFIG_DIR/configuration.yaml" 2>/dev/null; then
        print_success "Component already configured in configuration.yaml"
    else
        print_warning "Component not found in configuration.yaml"
        read -p "Add to configuration.yaml? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "" >> "$HA_CONFIG_DIR/configuration.yaml"
            echo "# Local Face Secure" >> "$HA_CONFIG_DIR/configuration.yaml"
            echo "$COMPONENT_NAME:" >> "$HA_CONFIG_DIR/configuration.yaml"
            print_success "Added to configuration.yaml"
        else
            print_info "You'll need to manually add '$COMPONENT_NAME:' to configuration.yaml"
        fi
    fi
    
    # Installation complete
    print_success "Installation complete!"
    echo ""
    print_info "Next steps:"
    echo "  1. Ensure '$COMPONENT_NAME:' is in your configuration.yaml"
    echo "  2. Restart Home Assistant"
    echo "  3. Check logs for any errors"
    echo "  4. Services should appear in Developer Tools → Services"
    echo ""
    print_info "System dependencies (if needed):"
    echo "  sudo apt-get install build-essential cmake libopenblas-dev liblapack-dev"
    echo ""
}

# Verify installation
verify_installation() {
    print_header "Verifying Local Face Secure Installation"
    
    check_environment
    
    local errors=0
    
    # Check if directory exists
    print_info "Checking component directory..."
    if [ -d "$TARGET_DIR" ]; then
        print_success "Component directory exists: $TARGET_DIR"
    else
        print_error "Component directory not found: $TARGET_DIR"
        ((errors++))
    fi
    
    # Check required files
    local required_files=(
        "__init__.py"
        "manifest.json"
        "const.py"
        "face_service.py"
        "storage.py"
        "services.yaml"
        "strings.json"
    )
    
    print_info "Checking required files..."
    for file in "${required_files[@]}"; do
        if [ -f "$TARGET_DIR/$file" ]; then
            print_success "$file"
        else
            print_error "$file is missing"
            ((errors++))
        fi
    done
    
    # Check configuration.yaml
    print_info "Checking configuration.yaml..."
    if grep -q "^$COMPONENT_NAME:" "$HA_CONFIG_DIR/configuration.yaml" 2>/dev/null; then
        print_success "Component configured in configuration.yaml"
    else
        print_warning "Component not found in configuration.yaml"
        print_info "Add this line: $COMPONENT_NAME:"
    fi
    
    # Check storage directory
    print_info "Checking storage..."
    if [ -d "$HA_CONFIG_DIR/.storage" ]; then
        print_success "Storage directory exists"
        if [ -f "$HA_CONFIG_DIR/.storage/$COMPONENT_NAME.faces" ]; then
            print_success "Face storage file exists (faces have been taught)"
        else
            print_info "No face storage file yet (no faces taught)"
        fi
    else
        print_warning "Storage directory not found (will be created on first run)"
    fi
    
    # Check Home Assistant is running
    print_info "Checking Home Assistant status..."
    if pgrep -f "home-assistant" > /dev/null; then
        print_success "Home Assistant is running"
    else
        print_warning "Home Assistant doesn't appear to be running"
    fi
    
    # Summary
    echo ""
    if [ $errors -eq 0 ]; then
        print_success "Verification passed! Installation looks good."
        echo ""
        print_info "To test the component:"
        echo "  1. Go to Developer Tools → Services"
        echo "  2. Look for local_face_secure.teach_face"
        echo "  3. Try teaching a face with your camera"
    else
        print_error "Verification failed with $errors error(s)"
        print_info "Please check the errors above and reinstall if necessary"
        exit 1
    fi
}

# Uninstall component
uninstall_component() {
    print_header "Uninstalling Local Face Secure Component"
    
    check_environment
    
    if [ ! -d "$TARGET_DIR" ]; then
        print_warning "Component not found at: $TARGET_DIR"
        print_info "Nothing to uninstall"
        exit 0
    fi
    
    print_warning "This will remove the component and all face data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstall cancelled"
        exit 0
    fi
    
    # Remove component directory
    print_info "Removing component files..."
    rm -rf "$TARGET_DIR"
    print_success "Component files removed"
    
    # Remove storage (optional)
    if [ -f "$HA_CONFIG_DIR/.storage/$COMPONENT_NAME.faces" ]; then
        read -p "Remove face data storage? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "$HA_CONFIG_DIR/.storage/$COMPONENT_NAME.faces"
            print_success "Face data removed"
        else
            print_info "Face data preserved"
        fi
    fi
    
    # Remove from configuration.yaml (optional)
    if grep -q "^$COMPONENT_NAME:" "$HA_CONFIG_DIR/configuration.yaml" 2>/dev/null; then
        read -p "Remove from configuration.yaml? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # This is a simple removal - may leave blank lines
            sed -i "/^$COMPONENT_NAME:/d" "$HA_CONFIG_DIR/configuration.yaml"
            print_success "Removed from configuration.yaml"
        else
            print_info "Left in configuration.yaml (you may want to remove it manually)"
        fi
    fi
    
    print_success "Uninstall complete!"
    print_info "Remember to restart Home Assistant"
}

# Show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "Options:"
    echo "  (none)        Install the component"
    echo "  --verify      Verify the installation"
    echo "  --uninstall   Remove the component"
    echo "  --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0              # Install component"
    echo "  $0 --verify     # Verify installation"
    echo "  $0 --uninstall  # Remove component"
}

# Main
main() {
    case "${1:-}" in
        --verify)
            verify_installation
            ;;
        --uninstall)
            uninstall_component
            ;;
        --help|-h)
            show_usage
            ;;
        "")
            install_component
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
}

main "$@"
