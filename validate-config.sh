#!/bin/bash

# =============================================================================
# Configuration Validator for Auto-Heal System
# =============================================================================
# This script validates that all required configurations are properly set
# =============================================================================

echo "🔍 Validating Auto-Heal System Configuration"
echo "=============================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
ERRORS=0
WARNINGS=0
SUCCESS=0

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ ERROR: .env file not found!${NC}"
    echo "   Run: cp .env.example .env"
    exit 1
fi

echo -e "${GREEN}✅ .env file found${NC}"
echo ""

# Load .env
export $(grep -v '^#' .env | xargs)

# Function to check required variable
check_required() {
    local var_name=$1
    local var_value="${!var_name}"

    if [ -z "$var_value" ] || [ "$var_value" == "your-"* ] || [ "$var_value" == "xoxb-your"* ]; then
        echo -e "${RED}❌ $var_name: NOT SET or still has placeholder${NC}"
        ((ERRORS++))
        return 1
    else
        echo -e "${GREEN}✅ $var_name: SET${NC}"
        ((SUCCESS++))
        return 0
    fi
}

# Function to check optional variable
check_optional() {
    local var_name=$1
    local var_value="${!var_name}"

    if [ -z "$var_value" ] || [ "$var_value" == "your-"* ]; then
        echo -e "${YELLOW}⚠️  $var_name: NOT SET (optional)${NC}"
        ((WARNINGS++))
        return 1
    else
        echo -e "${GREEN}✅ $var_name: SET${NC}"
        ((SUCCESS++))
        return 0
    fi
}

# Section: Core Settings
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📋 Core Settings${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_required "PUBLIC_BASE_URL"
check_required "RCA_API_KEY"
echo ""

# Section: Database
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🗄️  Database Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_required "DB_TYPE"
if [ "$DB_TYPE" == "sqlite" ]; then
    check_required "DB_PATH"
    # Check if database file exists or can be created
    DB_DIR=$(dirname "$DB_PATH")
    if [ ! -d "$DB_DIR" ]; then
        mkdir -p "$DB_DIR" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Database directory created: $DB_DIR${NC}"
        else
            echo -e "${RED}❌ Cannot create database directory: $DB_DIR${NC}"
            ((ERRORS++))
        fi
    else
        echo -e "${GREEN}✅ Database directory exists: $DB_DIR${NC}"
    fi
fi
echo ""

# Section: AI Provider
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🤖 AI Provider Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_required "AI_PROVIDER"
echo "   Selected: $AI_PROVIDER"

if [ "$AI_PROVIDER" == "gemini" ]; then
    check_required "GEMINI_API_KEY"
    check_required "MODEL_ID"
elif [ "$AI_PROVIDER" == "azure_openai" ]; then
    check_required "AZURE_OPENAI_API_KEY"
    check_required "AZURE_OPENAI_ENDPOINT"
    check_required "AZURE_OPENAI_DEPLOYMENT"
elif [ "$AI_PROVIDER" == "ollama" ]; then
    check_required "OLLAMA_HOST"
    check_required "OLLAMA_MODEL"
    # Test Ollama connectivity
    if curl -s "$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama server is reachable${NC}"
    else
        echo -e "${RED}❌ Cannot connect to Ollama server${NC}"
        ((ERRORS++))
    fi
else
    echo -e "${RED}❌ Invalid AI_PROVIDER: $AI_PROVIDER${NC}"
    echo "   Valid options: gemini, azure_openai, ollama"
    ((ERRORS++))
fi
echo ""

# Section: Databricks
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}⚡ Databricks Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_required "DATABRICKS_HOST"
check_required "DATABRICKS_TOKEN"

# Test Databricks connectivity
if [ -n "$DATABRICKS_HOST" ] && [ -n "$DATABRICKS_TOKEN" ]; then
    echo -n "   Testing Databricks API connectivity... "
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: Bearer $DATABRICKS_TOKEN" \
        "$DATABRICKS_HOST/api/2.0/clusters/list" 2>/dev/null)

    if [ "$RESPONSE" == "200" ]; then
        echo -e "${GREEN}✅ Connected${NC}"
    else
        echo -e "${RED}❌ Failed (HTTP $RESPONSE)${NC}"
        echo "   Check DATABRICKS_HOST and DATABRICKS_TOKEN"
        ((ERRORS++))
    fi
fi
echo ""

# Section: Auto-Remediation
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🤖 Auto-Remediation System${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_required "AUTO_REMEDIATION_ENABLED"
if [ "$AUTO_REMEDIATION_ENABLED" == "true" ]; then
    echo -e "${GREEN}   Auto-remediation is ENABLED${NC}"

    # Check playbook URLs
    echo ""
    echo "   Checking playbook URLs..."
    check_optional "PLAYBOOK_RETRY_PIPELINE"
    check_optional "PLAYBOOK_RESTART_CLUSTER"
    check_optional "PLAYBOOK_RETRY_JOB"
    check_optional "PLAYBOOK_SCALE_CLUSTER"
    check_optional "PLAYBOOK_REINSTALL_LIBRARIES"

    if [ $WARNINGS -gt 0 ]; then
        echo ""
        echo -e "${YELLOW}   ⚠️  Some playbook URLs not configured${NC}"
        echo "   Options:"
        echo "   1. Use local playbook server (recommended for testing)"
        echo "   2. Set up Azure Logic Apps (recommended for production)"
    fi
else
    echo -e "${YELLOW}   ⚠️  Auto-remediation is DISABLED${NC}"
    echo "   To enable: Set AUTO_REMEDIATION_ENABLED=true"
fi
echo ""

# Section: ITSM (Jira)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🎫 ITSM Integration (Jira)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$ITSM_TOOL" == "jira" ]; then
    check_required "JIRA_DOMAIN"
    check_required "JIRA_USER_EMAIL"
    check_required "JIRA_API_TOKEN"
    check_required "JIRA_PROJECT_KEY"

    # Test Jira connectivity
    if [ -n "$JIRA_DOMAIN" ] && [ -n "$JIRA_API_TOKEN" ]; then
        echo -n "   Testing Jira API connectivity... "
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
            -u "$JIRA_USER_EMAIL:$JIRA_API_TOKEN" \
            "$JIRA_DOMAIN/rest/api/3/myself" 2>/dev/null)

        if [ "$RESPONSE" == "200" ]; then
            echo -e "${GREEN}✅ Connected${NC}"
        else
            echo -e "${RED}❌ Failed (HTTP $RESPONSE)${NC}"
            echo "   Check JIRA_API_TOKEN and JIRA_USER_EMAIL"
            ((ERRORS++))
        fi
    fi
else
    echo -e "${YELLOW}   ℹ️  Jira integration disabled (ITSM_TOOL=$ITSM_TOOL)${NC}"
fi
echo ""

# Section: Azure Blob Storage
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}☁️  Azure Blob Storage${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ "$AZURE_BLOB_ENABLED" == "true" ]; then
    check_required "AZURE_STORAGE_CONN"
    check_required "AZURE_BLOB_CONTAINER_NAME"
    echo -e "${GREEN}   Azure Blob logging is ENABLED${NC}"
else
    echo -e "${YELLOW}   ℹ️  Azure Blob logging is DISABLED${NC}"
fi
echo ""

# Section: Slack (Optional)
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}💬 Slack Integration (Optional)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_optional "SLACK_BOT_TOKEN"
check_optional "SLACK_ALERT_CHANNEL"
echo ""

# Section: Webhook URLs
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔗 Webhook Configuration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
check_required "AUTO_HEAL_WEBHOOK_URL"

# Test if webhook endpoint is accessible
if [ -n "$PUBLIC_BASE_URL" ]; then
    echo -n "   Testing webhook endpoint accessibility... "
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        "$PUBLIC_BASE_URL/databricks-monitor" 2>/dev/null)

    # 405 is expected (GET not allowed, needs POST)
    if [ "$RESPONSE" == "405" ] || [ "$RESPONSE" == "200" ]; then
        echo -e "${GREEN}✅ Reachable (HTTP $RESPONSE)${NC}"
    else
        echo -e "${YELLOW}⚠️  Not reachable (HTTP $RESPONSE)${NC}"
        echo "   This is OK if not yet deployed"
        ((WARNINGS++))
    fi
fi
echo ""

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}📊 Validation Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "   ${GREEN}✅ Success: $SUCCESS${NC}"
echo -e "   ${YELLOW}⚠️  Warnings: $WARNINGS${NC}"
echo -e "   ${RED}❌ Errors: $ERRORS${NC}"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}❌ Configuration validation FAILED${NC}"
    echo ""
    echo "Please fix the errors above before starting the system."
    echo ""
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Configuration has warnings${NC}"
    echo ""
    echo "Optional features may not work, but core system will function."
    echo ""
    echo "🚀 You can start the system with:"
    echo "   ./quick-start-auto-heal.sh"
    echo ""
    exit 0
else
    echo -e "${GREEN}✅ Configuration validation PASSED!${NC}"
    echo ""
    echo "🎉 All required configurations are properly set!"
    echo ""
    echo "🚀 Next steps:"
    echo "   1. Start the system:"
    echo "      ./quick-start-auto-heal.sh"
    echo ""
    echo "   2. Configure Databricks webhooks:"
    echo "      python3 setup-databricks-webhooks.py"
    echo ""
    echo "   3. Test auto-heal:"
    echo "      Trigger a test job failure in Databricks"
    echo ""
    exit 0
fi
