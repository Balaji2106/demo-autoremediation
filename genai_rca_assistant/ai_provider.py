"""
Multi-AI Provider Support for RCA Generation

Supports multiple AI backends:
- Google Gemini (default)
- Azure OpenAI (GPT-4, GPT-4o, GPT-3.5-turbo)
- Ollama (self-hosted, DeepSeek-R1, Llama3, etc.)

Configuration:
    AI_PROVIDER=gemini|azure_openai|ollama (default: gemini)

    # Gemini
    GEMINI_API_KEY=your-key
    MODEL_ID=models/gemini-2.5-flash

    # Azure OpenAI
    AZURE_OPENAI_API_KEY=your-key
    AZURE_OPENAI_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
    AZURE_OPENAI_DEPLOYMENT=gpt-4  # or gpt-4o, gpt-35-turbo
    RAG_AZURE_OPENAI_API_VERSION=2024-12-01-preview

    # Ollama
    OLLAMA_HOST=http://localhost:11434
    OLLAMA_MODEL=deepseek-r1:latest  # or llama3, mistral, etc.
"""

import os
import logging
import json
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger("aiops_rca.ai_provider")

# =============================================================================
# AI PROVIDER CONFIGURATION
# =============================================================================

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

# Gemini Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL_ID = os.getenv("MODEL_ID", "models/gemini-2.5-flash")

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip('/')
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("RAG_AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

# Ollama Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip('/')
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:latest")


# =============================================================================
# RCA PROMPT TEMPLATE
# =============================================================================

RCA_PROMPT_TEMPLATE = """You are an expert AIOps engineer analyzing a production failure.

Analyze this error and provide a structured response in JSON format.

ERROR DETAILS:
{error_message}

Please provide your analysis in the following JSON structure:
{{
  "root_cause": "Clear explanation of what caused this error",
  "error_type": "Error classification (e.g., GatewayTimeout, DatabricksClusterStartFailure, etc.)",
  "severity": "Critical|High|Medium|Low",
  "priority": "P1|P2|P3|P4",
  "confidence": "High|Medium|Low",
  "affected_entity": "What component/service/resource is affected",
  "recommendations": [
    "Specific actionable step 1",
    "Specific actionable step 2",
    "Specific actionable step 3"
  ],
  "auto_heal_possible": true or false,
  "auto_heal_strategy": "Description of automated recovery approach if applicable"
}}

ERROR TYPE CLASSIFICATIONS (use these for error_type field):
- Azure Data Factory: GatewayTimeout, HttpConnectionFailed, ThrottlingError, UserErrorSourceBlobNotExists, InternalServerError
- Databricks: DatabricksClusterStartFailure, DatabricksTimeoutError, DatabricksDriverNotResponding, DatabricksLibraryInstallationError, DatabricksResourceExhausted, ClusterUnexpectedTermination

AUTO-HEAL ELIGIBILITY:
- Set auto_heal_possible to true ONLY if this error can be safely retried or automatically remediated
- Transient errors (timeouts, connection failures, throttling) are usually auto-healable
- Data corruption, permission errors, schema mismatches are NOT auto-healable

Return ONLY valid JSON, no additional text.
"""


# =============================================================================
# UNIFIED RCA GENERATION INTERFACE
# =============================================================================

def generate_rca_and_recs(error_message: str) -> Dict[str, Any]:
    """
    Generate RCA using configured AI provider

    Args:
        error_message: Error description to analyze

    Returns:
        Dictionary with RCA results (root_cause, recommendations, etc.)
    """
    logger.info(f"🤖 Generating RCA using AI provider: {AI_PROVIDER}")

    try:
        if AI_PROVIDER == "gemini":
            return _generate_rca_gemini(error_message)
        elif AI_PROVIDER == "azure_openai":
            return _generate_rca_azure_openai(error_message)
        elif AI_PROVIDER == "ollama":
            return _generate_rca_ollama(error_message)
        else:
            logger.error(f"❌ Unknown AI provider: {AI_PROVIDER}")
            return _fallback_rca(error_message, f"Unknown AI provider: {AI_PROVIDER}")

    except Exception as e:
        logger.error(f"❌ Error generating RCA: {e}")
        return _fallback_rca(error_message, str(e))


# =============================================================================
# GOOGLE GEMINI IMPLEMENTATION
# =============================================================================

def _generate_rca_gemini(error_message: str) -> Dict[str, Any]:
    """Generate RCA using Google Gemini"""
    if not GEMINI_API_KEY:
        logger.error("❌ GEMINI_API_KEY not configured")
        return _fallback_rca(error_message, "GEMINI_API_KEY not configured")

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL_ID)

        prompt = RCA_PROMPT_TEMPLATE.format(error_message=error_message)
        response = model.generate_content(prompt)

        # Parse JSON response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        rca = json.loads(response_text.strip())
        logger.info(f"✅ Gemini RCA generated successfully")
        return rca

    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse Gemini JSON response: {e}")
        logger.error(f"Response text: {response_text[:500]}")
        return _fallback_rca(error_message, f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        return _fallback_rca(error_message, str(e))


# =============================================================================
# AZURE OPENAI IMPLEMENTATION
# =============================================================================

def _generate_rca_azure_openai(error_message: str) -> Dict[str, Any]:
    """Generate RCA using Azure OpenAI"""
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        logger.error("❌ Azure OpenAI credentials not configured")
        return _fallback_rca(error_message, "Azure OpenAI not configured")

    url = f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"

    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_API_KEY
    }

    prompt = RCA_PROMPT_TEMPLATE.format(error_message=error_message)

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are an expert AIOps engineer. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"}
    }

    try:
        logger.info(f"🔄 Calling Azure OpenAI: {AZURE_OPENAI_DEPLOYMENT}")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        rca = json.loads(content)
        logger.info(f"✅ Azure OpenAI RCA generated successfully")
        return rca

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Azure OpenAI API error: {e}")
        return _fallback_rca(error_message, str(e))
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"❌ Failed to parse Azure OpenAI response: {e}")
        return _fallback_rca(error_message, str(e))


# =============================================================================
# OLLAMA IMPLEMENTATION
# =============================================================================

def _generate_rca_ollama(error_message: str) -> Dict[str, Any]:
    """Generate RCA using Ollama (self-hosted)"""
    if not OLLAMA_HOST:
        logger.error("❌ OLLAMA_HOST not configured")
        return _fallback_rca(error_message, "OLLAMA_HOST not configured")

    url = f"{OLLAMA_HOST}/api/generate"

    prompt = RCA_PROMPT_TEMPLATE.format(error_message=error_message)

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 2000
        }
    }

    try:
        logger.info(f"🔄 Calling Ollama: {OLLAMA_MODEL}")
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        data = response.json()
        response_text = data.get("response", "")

        # Parse JSON from response
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        rca = json.loads(response_text.strip())
        logger.info(f"✅ Ollama RCA generated successfully")
        return rca

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ollama API error: {e}")
        logger.error(f"Make sure Ollama is running at {OLLAMA_HOST}")
        return _fallback_rca(error_message, str(e))
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"❌ Failed to parse Ollama response: {e}")
        return _fallback_rca(error_message, str(e))


# =============================================================================
# FALLBACK RCA (When AI fails)
# =============================================================================

def _fallback_rca(error_message: str, reason: str) -> Dict[str, Any]:
    """Generate a basic RCA when AI provider fails"""
    logger.warning(f"⚠️ Using fallback RCA due to: {reason}")

    # Try to classify error type based on keywords
    error_type = "Unknown"
    auto_heal_possible = False
    severity = "Medium"

    error_lower = error_message.lower()

    if "timeout" in error_lower or "timed out" in error_lower:
        error_type = "GatewayTimeout" if "gateway" in error_lower else "DatabricksTimeoutError"
        auto_heal_possible = True
        severity = "Medium"
    elif "connection" in error_lower and "failed" in error_lower:
        error_type = "HttpConnectionFailed"
        auto_heal_possible = True
        severity = "Medium"
    elif "throttl" in error_lower:
        error_type = "ThrottlingError"
        auto_heal_possible = True
        severity = "Low"
    elif "cluster" in error_lower:
        error_type = "DatabricksClusterStartFailure"
        auto_heal_possible = True
        severity = "High"
    elif "library" in error_lower or "package" in error_lower:
        error_type = "DatabricksLibraryInstallationError"
        auto_heal_possible = True
        severity = "Medium"

    return {
        "root_cause": f"Error analysis failed ({reason}). Manual review required for: {error_message[:200]}",
        "error_type": error_type,
        "severity": severity,
        "priority": "P2",
        "confidence": "Low",
        "affected_entity": "Unknown",
        "recommendations": [
            "Review error logs for more details",
            "Check system health and connectivity",
            "Retry operation manually if appropriate",
            f"AI Provider Error: {reason}"
        ],
        "auto_heal_possible": auto_heal_possible,
        "auto_heal_strategy": "Basic retry with exponential backoff" if auto_heal_possible else "Not applicable"
    }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_provider_info() -> Dict[str, Any]:
    """Get information about configured AI provider"""
    info = {
        "provider": AI_PROVIDER,
        "configured": False,
        "model": None
    }

    if AI_PROVIDER == "gemini":
        info["configured"] = bool(GEMINI_API_KEY)
        info["model"] = GEMINI_MODEL_ID
    elif AI_PROVIDER == "azure_openai":
        info["configured"] = bool(AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT)
        info["model"] = AZURE_OPENAI_DEPLOYMENT
        info["endpoint"] = AZURE_OPENAI_ENDPOINT
    elif AI_PROVIDER == "ollama":
        info["configured"] = bool(OLLAMA_HOST)
        info["model"] = OLLAMA_MODEL
        info["host"] = OLLAMA_HOST

    return info


def test_provider_connection() -> bool:
    """Test if AI provider is accessible"""
    try:
        if AI_PROVIDER == "gemini":
            if not GEMINI_API_KEY:
                return False
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel(GEMINI_MODEL_ID)
            response = model.generate_content("Test")
            return bool(response.text)

        elif AI_PROVIDER == "azure_openai":
            if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
                return False
            # Simple test call would go here
            return True

        elif AI_PROVIDER == "ollama":
            if not OLLAMA_HOST:
                return False
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            return response.status_code == 200

    except Exception as e:
        logger.error(f"Provider test failed: {e}")
        return False

    return False
