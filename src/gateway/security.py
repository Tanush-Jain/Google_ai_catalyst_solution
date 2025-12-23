"""
Security utilities for prompt injection and PII detection
"""
import re
import logging
from typing import Dict, List, Tuple, Optional
from src.gateway.config import get_settings


logger = logging.getLogger(__name__)


class SecurityChecker:
    """Security checking for LLM prompts and responses"""
    
    def __init__(self):
        self.settings = get_settings()
        self.prompt_injection_patterns = self._load_prompt_injection_patterns()
        self.pii_patterns = self._load_pii_patterns()
    
    def _load_prompt_injection_patterns(self) -> List[str]:
        """Load regex patterns for prompt injection detection"""
        patterns = [
            # Direct instruction overrides
            r"(?i)(ignore\s+(?:all\s+)?(?:previous|above)\s+(?:instructions|prompts))",
            r"(?i)(disregard\s+(?:all\s+)?(?:previous|above)\s+(?:instructions|prompts))",
            r"(?i)(forget\s+(?:all\s+)?(?:previous|above)\s+(?:instructions|prompts))",
            
            # Role-playing and persona manipulation
            r"(?i)(you\s+are\s+(?:not|a|an)\s+.*(?:assistant|AI|model|bot))",
            r"(?i)(act\s+as\s+(?:if\s+)?you\s+(?:are|were)\s+.*(?:different|another|not\s+an?\s+assistant))",
            r"(?i)(pretend\s+(?:to\s+)?be\s+.*(?:different|another|not\s+an?\s+assistant))",
            
            # Jailbreak attempts
            r"(?i)(how\s+to\s+build\s+(?:a\s+)?(?:bomb|weapon|harmful|illegal|malicious)\b)",
            r"(?i)(bypass\s+(?:your|this\s+)?(?:guidelines|restrictions|limitations|system|content\s+filter))",
            r"(?i)(ignore\s+(?:your|this\s+)?(?:guidelines|restrictions|limitations|system|content\s+filter))",
            
            # System prompt extraction
            r"(?i)(what\s+are\s+(?:your|this\s+)?(?:system\s+)?(?:prompts|instructions|guidelines|rules))",
            r"(?i)(repeat\s+(?:back|after\s+me)\s+.*(?:prompts|instructions|guidelines|rules))",
            
            # Code injection attempts
            r"(?i)(execute\s+code|run\s+code|system\(|eval\(|import\s+os|import\s+subprocess)",
            
            # Data extraction attempts
            r"(?i)(extract\s+(?:sensitive|private|confidential)\s+(?:data|information|content))",
            r"(?i)(dump\s+(?:sensitive|private|confidential)\s+(?:data|information|content))",
        ]
        return patterns
    
    def _load_pii_patterns(self) -> Dict[str, str]:
        """Load regex patterns for PII detection"""
        patterns = {
            # Email addresses
            "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            
            # Phone numbers (US format)
            "phone": r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b",
            
            # Social Security Numbers (US)
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            
            # Credit card numbers (basic pattern)
            "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            
            # IP addresses
            "ip_address": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            
            # Dates of birth patterns
            "dob": r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b",
        }
        return patterns
    
    def check_prompt_injection(self, text: str) -> Tuple[bool, List[Dict[str, str]]]:
        """
        Check if text contains prompt injection attempts
        
        Returns:
            Tuple of (is_suspicious, list of detected patterns)
        """
        if not self.settings.ENABLE_SECURITY_CHECKS:
            return False, []
        
        detected_patterns = []
        overall_score = 0.0
        
        for i, pattern in enumerate(self.prompt_injection_patterns):
            matches = re.findall(pattern, text)
            if matches:
                # Weight patterns by severity
                severity_weights = [0.8, 0.7, 0.9, 0.6, 0.8, 0.9, 0.7, 0.8]
                weight = severity_weights[i % len(severity_weights)]
                overall_score += weight * len(matches)
                
                detected_patterns.append({
                    "pattern_id": i,
                    "pattern": pattern,
                    "matches": matches,
                    "severity": weight,
                    "type": "prompt_injection"
                })
        
        # Apply threshold
        is_suspicious = overall_score >= self.settings.PROMPT_INJECTION_THRESHOLD
        
        if detected_patterns:
            logger.warning(f"Prompt injection detected. Score: {overall_score:.2f}, Patterns: {len(detected_patterns)}")
        
        return is_suspicious, detected_patterns
    
    def detect_pii(self, text: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Detect PII in text
        
        Returns:
            Dictionary with PII type as key and list of detections as value
        """
        if not self.settings.PII_DETECTION_ENABLED:
            return {}
        
        detections = {}
        
        for pii_type, pattern in self.pii_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            pii_matches = []
            
            for match in matches:
                pii_matches.append({
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "type": pii_type
                })
            
            if pii_matches:
                detections[pii_type] = pii_matches
        
        if detections:
            total_pii_found = sum(len(matches) for matches in detections.values())
            logger.warning(f"PII detected in text: {total_pii_found} instances across {len(detections)} types")
        
        return detections
    
    def sanitize_prompt(self, text: str) -> Tuple[str, List[str]]:
        """
        Sanitize prompt by removing or masking potentially harmful content
        
        Returns:
            Tuple of (sanitized_text, list_of_actions_taken)
        """
        if not self.settings.ENABLE_SECURITY_CHECKS:
            return text, []
        
        actions = []
        sanitized_text = text
        
        # Check for prompt injection
        is_suspicious, patterns = self.check_prompt_injection(text)
        if is_suspicious:
            # For now, just log - in production you might want to sanitize or block
            actions.append("prompt_injection_detected")
            logger.warning(f"Rejected prompt due to injection detection")
            # TODO: Decide whether to sanitize, mask, or reject the prompt
            # For production, consider returning an error or sanitized version
        
        # Check for PII
        pii_detections = self.detect_pii(text)
        if pii_detections:
            actions.append("pii_detected")
            # TODO: Implement masking or redaction of PII
            # For now, just log the detection
            for pii_type, matches in pii_detections.items():
                logger.info(f"Found {len(matches)} {pii_type} instances")
        
        return sanitized_text, actions
    
    def analyze_response_safety(self, response: str) -> Dict[str, any]:
        """
        Analyze the safety of an LLM response
        
        Returns:
            Dictionary with safety analysis results
        """
        analysis = {
            "is_safe": True,
            "risk_factors": [],
            "confidence_score": 1.0
        }
        
        # Check for potentially harmful content patterns
        harmful_patterns = [
            r"(?i)(violent|harmful|dangerous|illegal|unethical)\s+(?:content|instructions|advice)",
            r"(?i)(how\s+to\s+cause\s+(?:harm|damage|destruction|violence))",
            r"(?i)(create|make|build)\s+(?:harmful|dangerous|malicious|harm)\b",
        ]
        
        for pattern in harmful_patterns:
            matches = re.findall(pattern, response)
            if matches:
                analysis["risk_factors"].append({
                    "type": "harmful_content",
                    "pattern": pattern,
                    "matches": matches,
                    "severity": 0.8
                })
                analysis["is_safe"] = False
                analysis["confidence_score"] -= 0.2
        
        return analysis


# Global security checker instance
security_checker = SecurityChecker()


def check_security(prompt: str, response: Optional[str] = None) -> Dict[str, any]:
    """
    Comprehensive security check for prompt and optionally response
    
    Returns:
        Dictionary with security analysis results
    """
    results = {
        "prompt_analysis": {
            "injection_detected": False,
            "injection_score": 0.0,
            "pii_detected": False,
            "pii_types": [],
            "sanitization_applied": False
        },
        "response_analysis": {
            "safety_score": 1.0,
            "risk_factors": [],
            "is_safe": True
        } if response else None
    }
    
    # Analyze prompt
    is_injection, patterns = security_checker.check_prompt_injection(prompt)
    pii_detections = security_checker.detect_pii(prompt)
    
    results["prompt_analysis"]["injection_detected"] = is_injection
    results["prompt_analysis"]["injection_score"] = len(patterns)
    results["prompt_analysis"]["pii_detected"] = len(pii_detections) > 0
    results["prompt_analysis"]["pii_types"] = list(pii_detections.keys())
    
    # Analyze response if provided
    if response:
        response_analysis = security_checker.analyze_response_safety(response)
        results["response_analysis"] = response_analysis
    
    return results

