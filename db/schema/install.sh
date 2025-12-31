#!/bin/bash
# Database Schema Installation Script
# This script installs the complete task and reporting system schema

set -e  # Exit on error

# Configuration
DB_NAME="${DB_NAME:-corpsite}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Task and Reporting System Schema Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if database exists
echo -e "${BLUE}Checking database connection...${NC}"
if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${GREEN}✓ Database '$DB_NAME' found${NC}"
else
    echo -e "${RED}✗ Database '$DB_NAME' not found${NC}"
    read -p "Would you like to create it? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
        echo -e "${GREEN}✓ Database created${NC}"
    else
        echo -e "${RED}Exiting...${NC}"
        exit 1
    fi
fi

echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Schema files in order
SCHEMA_FILES=(
    "01_users_and_roles.sql"
    "02_tasks.sql"
    "03_reports.sql"
    "04_audit_logging.sql"
    "05_views_and_functions.sql"
)

# Install each schema file
for file in "${SCHEMA_FILES[@]}"; do
    echo -e "${BLUE}Installing: $file${NC}"
    if [ -f "$SCRIPT_DIR/$file" ]; then
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SCRIPT_DIR/$file" > /dev/null
        echo -e "${GREEN}✓ $file installed successfully${NC}"
    else
        echo -e "${RED}✗ File not found: $file${NC}"
        exit 1
    fi
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Schema installation completed!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Database: $DB_NAME"
echo "Tables created:"
echo "  - users, roles, user_roles"
echo "  - task_statuses, tasks, task_comments"
echo "  - report_types, reports, report_sections, report_tasks"
echo "  - audit_log"
echo ""
echo "Views created:"
echo "  - v_users_with_managers"
echo "  - v_tasks_full"
echo "  - v_reports_with_status"
echo "  - v_pending_approvals"
echo ""
echo "Functions created:"
echo "  - get_user_tasks(user_id)"
echo "  - get_team_reports(manager_id, management_type)"
echo "  - get_audit_trail(table_name, record_id)"
echo ""
echo "See db/schema/README.md for detailed documentation."
