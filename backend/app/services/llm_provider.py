import os
import json
import logging
import httpx
from typing import Optional
from backend.app.config import settings

logger = logging.getLogger("automotive.llm")
logging.basicConfig(level=logging.INFO)

class LLMProvider:
    def __init__(
        self,
        provider: str = settings.LLM_PROVIDER,
        api_key: Optional[str] = settings.LLM_API_KEY,
        base_url: str = settings.LLM_BASE_URL,
        model: str = settings.LLM_MODEL
    ):
        self.provider = (provider or "demo").lower()
        self.api_key = api_key
        # Default OpenRouter base URL if provider is openrouter
        if self.provider == "openrouter" and (not base_url or "localhost" in base_url):
            self.base_url = "https://openrouter.ai/api/v1"
        else:
            self.base_url = base_url
        self.model = model

    def _mask_key(self, key: Optional[str]) -> str:
        if not key:
            return "None"
        if len(key) <= 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Dispatches prompt to configured provider."""
        masked_key = self._mask_key(self.api_key)
        logger.info(
            f"[LLM] Dispatching prompt | Provider: {self.provider} | Model: {self.model} | "
            f"Endpoint: {self.base_url} | API Key: {masked_key}"
        )

        if self.provider in ["openai", "openrouter"]:
            if not self.api_key:
                raise ValueError(
                    f"LLM Provider is set to '{self.provider}' but LLM_API_KEY is not configured in settings/.env"
                )
            return self._call_openai(prompt, system_prompt)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, system_prompt)
        elif self.provider == "demo":
            logger.info("[LLM] Executing in built-in Demo mode.")
            return self._call_demo_engine(prompt, system_prompt)
        else:
            raise ValueError(f"Unknown LLM Provider configured: '{self.provider}'")

    def _call_openai(self, prompt: str, system_prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://automotive.internal",
            "X-Title": "Automotive Engineering AI Platform"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt or "You are an automotive engineering assistant."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        logger.info(f"[LLM Request] Target: {url} | Model: {self.model} | Prompt length: {len(prompt)} chars")

        try:
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, headers=headers, json=payload)
        except Exception as req_err:
            logger.error(f"[LLM Request Failed] Connection error to {url}: {req_err}")
            raise RuntimeError(f"Failed to connect to LLM provider at {url}: {req_err}") from req_err

        logger.info(f"[LLM Response] HTTP Status: {res.status_code}")

        try:
            data = res.json()
        except Exception as json_err:
            logger.error(f"[LLM Response Parsing Error] Response is not valid JSON (HTTP {res.status_code}): {res.text[:300]}")
            raise RuntimeError(
                f"LLM provider returned non-JSON response (HTTP {res.status_code}): {res.text[:300]}"
            ) from json_err

        # Check for provider-level error envelopes (even if HTTP 200 or non-200)
        if "error" in data:
            err_obj = data["error"]
            err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
            err_code = err_obj.get("code") if isinstance(err_obj, dict) else "N/A"
            logger.error(f"[LLM API Error] Provider error returned | Code: {err_code} | Message: {err_msg}")
            raise RuntimeError(f"LLM Provider API Error [{err_code}]: {err_msg}")

        if res.status_code >= 400:
            logger.error(f"[LLM HTTP Error] HTTP {res.status_code} returned: {res.text[:300]}")
            raise RuntimeError(f"LLM provider HTTP error {res.status_code}: {res.text[:300]}")

        # Check choices array
        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            logger.error(f"[LLM Response Parsing Error] 'choices' key missing or empty in payload: {list(data.keys())}")
            raise RuntimeError(f"LLM provider response missing 'choices': {json.dumps(data)[:300]}")

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")

        # Handle reasoning / thinking models where content may be in reasoning field
        if not content and "reasoning" in message:
            content = message["reasoning"]

        if not content:
            logger.warning("[LLM] Message content is empty or null in response choices.")
            content = "No response content received from LLM."

        logger.info(f"[LLM Success] Successfully parsed response ({len(content)} characters generated).")
        return content

    def _call_ollama(self, prompt: str, system_prompt: str) -> str:
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\nUser: {prompt}\n\nAssistant:",
            "stream": False
        }
        logger.info(f"[LLM Ollama Request] Target: {url} | Model: {self.model}")
        try:
            with httpx.Client(timeout=45.0) as client:
                res = client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data.get("response", "")
                logger.info(f"[LLM Ollama Success] Generated {len(content)} characters.")
                return content
        except Exception as e:
            logger.error(f"[Ollama Error] {e}")
            raise RuntimeError(f"Ollama connection error: {e}") from e

    def _call_demo_engine(self, prompt: str, system_prompt: str) -> str:
        """
        Deterministic, domain-accurate engineering reasoning engine for offline demo mode.
        """
        p_lower = prompt.lower()

        if "interface" in p_lower or "component" in p_lower or "autosar" in p_lower or "hld" in p_lower:
            return (
                "### AUTOSAR Architecture Analysis (Evidence-Based)\n\n"
                "Based on the project High-Level Design (HLD) specifications:\n"
                "- **Camera ECU (SWC_CameraProcessing)** connects to **Perception ECU (SWC_ObjectFusion)** via Ethernet (SOME/IP), carrying the `RawObjectList_t` signal.\n"
                "- **Perception ECU** connects to **Vehicle Control ECU (SWC_TrajectoryPlanner)** via CAN-FD (`CAN_ID_0x120`), carrying `TargetTrajectory_t`.\n"
                "- **Potential Interface Mismatch Detected**: SWC_ObjectFusion specifies port `P_FusedTrack` output rate of 50 ms (20 Hz), "
                "whereas SWC_TrajectoryPlanner expects input port `R_FusedTrack` at 20 ms (50 Hz). Buffer underrun or stale frame condition possible.\n\n"
                "**LIMITATION**: Interface timing compatibility requires explicit verification in the AUTOSAR RTE configuration."
            )
        elif "steering" in p_lower or "hara" in p_lower or "loss of" in p_lower or "hazard" in p_lower:
            return (
                "### Functional Safety Analysis (ISO 26262 Part 3)\n\n"
                "- **Item**: Electric Power Steering & Lane Keep Assist (EPS/LKA)\n"
                "- **Hazardous Event**: Unintended steering torque / loss of steering assistance at highway speed (v > 100 km/h).\n"
                "- **Safety Evaluation Parameter Guidance**:\n"
                "  - Severity: **S3** (Fatal injury or life-threatening harm likely if vehicle leaves roadway at speed).\n"
                "  - Exposure: **E4** (High operational probability; highway driving > 10% operating duration).\n"
                "  - Controllability: **C3** (Uncontrollable for typical driver during sudden torque kick on wet/icy asphalt).\n"
                "- **Recommended Safety Goal (SG-01)**: Prevent unintended lateral torque deviation exceeding +/- 3 Nm for > 50 ms.\n"
                "- **Candidate Functional Safety Requirement (FSR-01)**: EPS shall transition to fail-silent state within 40 ms upon internal dual-core lockstep divergence."
            )
        elif "cybersecurity" in p_lower or "tara" in p_lower or "attack" in p_lower or "asset" in p_lower:
            return (
                "### Cybersecurity Threat Analysis (ISO/SAE 21434)\n\n"
                "- **Primary Asset**: Firmware Update Interface / In-Vehicle CAN Bus\n"
                "- **Attack Surface**: Central Gateway OBD-II Port and Telematics LTE Modem\n"
                "- **Identified Threat Scenario**: Malicious ECU impersonation on vehicle CAN bus sending forged speed signals (ID 0x150).\n"
                "- **Damage Scenario**: Vehicle control ECU disables steering assist due to bogus speed readings.\n"
                "- **Recommended Mitigation (SecOC)**: Implement Secure Onboard Communication (AUTOSAR SecOC) with fresh MAC verification on safety-critical frames."
            )
        elif "uds" in p_lower or "diagnostics" in p_lower or "did" in p_lower:
            return (
                "### UDS Diagnostic Analysis (ISO 14229)\n\n"
                "- **Service Requested**: ReadDataByIdentifier (0x22) or SecurityAccess (0x27)\n"
                "- **Standard Diagnostic Preconditions**: Diagnostic session must be active, bus quiescence verified.\n"
                "- **Positive Response Frame**: 0x62 [DID_MSB] [DID_LSB] [DATA_BYTES...]\n"
                "- **Negative Response Codes (NRC)**: NRC 0x31 (requestOutOfRange) if DID not configured; NRC 0x22 (conditionsNotCorrect) if speed > 0."
            )
        else:
            return (
                "### Automotive Engineering Synthesis\n\n"
                "Analysis of project documents completed. Relevant architectural components and safety specifications have been cross-referenced. "
                "All consequential engineering decisions require human engineer validation."
            )

llm_service = LLMProvider()
