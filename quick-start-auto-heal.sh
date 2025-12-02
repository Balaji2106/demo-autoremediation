#!/bin/bash

# =============================================================================
# Quick Start Script for Auto-Heal System
# =============================================================================
# This script helps you quickly set up and test the auto-remediation system
# with the built-in playbook server (no Azure Logic Apps required).
# =============================================================================

set -e  # Exit on error

echo "🤖 Auto-Heal Quick Start"
echo "========================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo "✅ .env created"
else
    echo "✅ .env already exists"
fi

echo ""
echo "🔧 Configuration Checklist:"
echo ""

# Check required configs
MISSING_CONFIG=0

# Check AI Provider
AI_PROVIDER=$(grep "^AI_PROVIDER=" .env | cut -d '=' -f2 || echo "")
if [ -z "$AI_PROVIDER" ] || [ "$AI_PROVIDER" = "gemini" ]; then
    GEMINI_KEY=$(grep "^GEMINI_API_KEY=" .env | cut -d '=' -f2 || echo "")
    if [ "$GEMINI_KEY" = "your-google-gemini-api-key" ] || [ -z "$GEMINI_KEY" ]; then
        echo "❌ GEMINI_API_KEY not configured in .env"
        MISSING_CONFIG=1
    else
        echo "✅ Gemini API Key configured"
    fi
elif [ "$AI_PROVIDER" = "azure_openai" ]; then
    AZURE_OPENAI_KEY=$(grep "^AZURE_OPENAI_API_KEY=" .env | cut -d '=' -f2 || echo "")
    if [ "$AZURE_OPENAI_KEY" = "your-azure-openai-api-key" ] || [ -z "$AZURE_OPENAI_KEY" ]; then
        echo "❌ AZURE_OPENAI_API_KEY not configured in .env"
        MISSING_CONFIG=1
    else
        echo "✅ Azure OpenAI configured"
    fi
elif [ "$AI_PROVIDER" = "ollama" ]; then
    OLLAMA_HOST=$(grep "^OLLAMA_HOST=" .env | cut -d '=' -f2 || echo "")
    if [ -z "$OLLAMA_HOST" ]; then
        echo "❌ OLLAMA_HOST not configured in .env"
        MISSING_CONFIG=1
    else
        echo "✅ Ollama configured at $OLLAMA_HOST"
    fi
fi

# Check Databricks credentials
DATABRICKS_HOST=$(grep "^DATABRICKS_HOST=" .env | cut -d '=' -f2 || echo "")
DATABRICKS_TOKEN=$(grep "^DATABRICKS_TOKEN=" .env | cut -d '=' -f2 || echo "")

if [ "$DATABRICKS_HOST" = "https://your-databricks-workspace-url.azuredatabricks.net" ] || [ -z "$DATABRICKS_HOST" ]; then
    echo "⚠️  DATABRICKS_HOST not configured (optional for Databricks playbooks)"
else
    echo "✅ Databricks Host configured"
fi

if [ "$DATABRICKS_TOKEN" = "dapi1234567890abcdef..." ] || [ -z "$DATABRICKS_TOKEN" ]; then
    echo "⚠️  DATABRICKS_TOKEN not configured (optional for Databricks playbooks)"
else
    echo "✅ Databricks Token configured"
fi

echo ""

if [ $MISSING_CONFIG -eq 1 ]; then
    echo "⚠️  Some configurations are missing. Please update .env file."
    echo ""
    read -p "Do you want to continue anyway for testing? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup cancelled. Please configure .env and run this script again."
        exit 1
    fi
fi

echo ""
echo "🎯 What do you want to do?"
echo ""
echo "1) Start Playbook Server ONLY (for testing playbooks)"
echo "2) Start Main Application ONLY (requires playbook URLs already configured)"
echo "3) Start BOTH (Playbook Server + Main Application)"
echo "4) Configure .env for local playbook server"
echo "5) Test a playbook manually"
echo "6) Exit"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo ""
        echo "🚀 Starting Playbook Server..."
        echo "   Server will run at: http://localhost:8001"
        echo "   API docs at: http://localhost:8001/docs"
        echo ""
        echo "Press Ctrl+C to stop"
        echo ""
        cd genai_rca_assistant
        python3 playbook_server.py
        ;;

    2)
        echo ""
        echo "🚀 Starting Main Application..."
        echo "   Server will run at: http://localhost:8000"
        echo ""
        echo "Make sure your .env has valid PLAYBOOK_* URLs configured!"
        echo ""
        read -p "Press Enter to continue or Ctrl+C to cancel..."
        cd genai_rca_assistant
        python3 main.py
        ;;

    3)
        echo ""
        echo "🚀 Starting BOTH servers..."
        echo ""

        # Update .env to use local playbook server
        sed -i 's|^PLAYBOOK_RETRY_PIPELINE=.*|PLAYBOOK_RETRY_PIPELINE=http://localhost:8001/playbooks/retry-pipeline|' .env
        sed -i 's|^PLAYBOOK_RESTART_CLUSTER=.*|PLAYBOOK_RESTART_CLUSTER=http://localhost:8001/playbooks/restart-cluster|' .env
        sed -i 's|^PLAYBOOK_RETRY_JOB=.*|PLAYBOOK_RETRY_JOB=http://localhost:8001/playbooks/retry-job|' .env
        sed -i 's|^PLAYBOOK_SCALE_CLUSTER=.*|PLAYBOOK_SCALE_CLUSTER=http://localhost:8001/playbooks/scale-cluster|' .env
        sed -i 's|^PLAYBOOK_REINSTALL_LIBRARIES=.*|PLAYBOOK_REINSTALL_LIBRARIES=http://localhost:8001/playbooks/reinstall-libraries|' .env
        sed -i 's|^AUTO_REMEDIATION_ENABLED=.*|AUTO_REMEDIATION_ENABLED=true|' .env

        echo "✅ Updated .env with local playbook URLs"
        echo "✅ Enabled auto-remediation"
        echo ""

        # Start playbook server in background
        cd genai_rca_assistant
        echo "📡 Starting Playbook Server on port 8001..."
        python3 playbook_server.py > /tmp/playbook_server.log 2>&1 &
        PLAYBOOK_PID=$!
        echo "   PID: $PLAYBOOK_PID"

        # Wait for playbook server to start
        sleep 3

        # Check if playbook server is running
        if curl -s http://localhost:8001/playbooks/health > /dev/null; then
            echo "✅ Playbook Server is healthy"
        else
            echo "❌ Playbook Server failed to start. Check /tmp/playbook_server.log"
            kill $PLAYBOOK_PID 2>/dev/null || true
            exit 1
        fi

        echo ""
        echo "📡 Starting Main Application on port 8000..."
        echo ""
        echo "🎉 Both servers are running!"
        echo ""
        echo "📊 URLs:"
        echo "   Main App:        http://localhost:8000"
        echo "   Dashboard:       http://localhost:8000/dashboard"
        echo "   Playbook Server: http://localhost:8001"
        echo "   Playbook Docs:   http://localhost:8001/docs"
        echo ""
        echo "Press Ctrl+C to stop both servers"
        echo ""

        # Trap Ctrl+C to kill both processes
        trap "echo ''; echo '🛑 Stopping servers...'; kill $PLAYBOOK_PID 2>/dev/null || true; exit" INT TERM

        # Start main application
        python3 main.py
        ;;

    4)
        echo ""
        echo "📝 Configuring .env for local playbook server..."

        # Backup original
        cp .env .env.backup

        # Update playbook URLs
        cat >> .env << 'EOF'

# ============================================================================
# Auto-Remediation - Local Playbook Server Configuration
# ============================================================================
AUTO_REMEDIATION_ENABLED=true

# Local Playbook Server URLs (running on port 8001)
PLAYBOOK_RETRY_PIPELINE=http://localhost:8001/playbooks/retry-pipeline
PLAYBOOK_RESTART_CLUSTER=http://localhost:8001/playbooks/restart-cluster
PLAYBOOK_RETRY_JOB=http://localhost:8001/playbooks/retry-job
PLAYBOOK_SCALE_CLUSTER=http://localhost:8001/playbooks/scale-cluster
PLAYBOOK_REINSTALL_LIBRARIES=http://localhost:8001/playbooks/reinstall-libraries
EOF

        echo "✅ Configuration added to .env"
        echo "✅ Backup saved to .env.backup"
        echo ""
        echo "Next steps:"
        echo "1. Start playbook server: python3 genai_rca_assistant/playbook_server.py"
        echo "2. Start main application: python3 genai_rca_assistant/main.py"
        ;;

    5)
        echo ""
        echo "🧪 Manual Playbook Test"
        echo ""
        echo "Which playbook do you want to test?"
        echo "1) Retry ADF Pipeline"
        echo "2) Restart Databricks Cluster"
        echo "3) Retry Databricks Job"
        echo "4) Health Check"
        echo ""
        read -p "Enter choice [1-4]: " test_choice

        case $test_choice in
            1)
                echo ""
                echo "Testing: Retry ADF Pipeline"
                echo ""
                curl -X POST "http://localhost:8001/playbooks/retry-pipeline" \
                  -H "Content-Type: application/json" \
                  -d '{
                    "ticket_id": "TEST-001",
                    "error_type": "GatewayTimeout",
                    "metadata": {
                      "run_id": "test-run-001",
                      "pipeline": "Test_Pipeline",
                      "source": "adf"
                    },
                    "retry_attempt": 1,
                    "max_retries": 3
                  }' | python3 -m json.tool
                ;;

            2)
                echo ""
                echo "Testing: Restart Databricks Cluster"
                echo ""
                curl -X POST "http://localhost:8001/playbooks/restart-cluster" \
                  -H "Content-Type: application/json" \
                  -d '{
                    "ticket_id": "TEST-002",
                    "error_type": "DatabricksClusterStartFailure",
                    "metadata": {
                      "cluster_id": "1234-567890-abc123",
                      "source": "databricks"
                    }
                  }' | python3 -m json.tool
                ;;

            3)
                echo ""
                echo "Testing: Retry Databricks Job"
                echo ""
                curl -X POST "http://localhost:8001/playbooks/retry-job" \
                  -H "Content-Type: application/json" \
                  -d '{
                    "ticket_id": "TEST-003",
                    "error_type": "DatabricksTimeoutError",
                    "metadata": {
                      "job_id": "12345"
                    }
                  }' | python3 -m json.tool
                ;;

            4)
                echo ""
                echo "Testing: Health Check"
                echo ""
                curl -s "http://localhost:8001/playbooks/health" | python3 -m json.tool
                ;;

            *)
                echo "Invalid choice"
                ;;
        esac
        echo ""
        ;;

    6)
        echo "👋 Goodbye!"
        exit 0
        ;;

    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
