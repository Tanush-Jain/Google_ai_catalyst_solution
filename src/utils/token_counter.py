"""
Token counting utilities for LLM text processing
"""
import math
import logging


logger = logging.getLogger(__name__)


def estimate_token_count(text: str) -> int:
    """
    Estimate the number of tokens in text using multiple approximation methods
    
    This is a simplified token estimation that works reasonably well for English text.
    For production use, consider using the tiktoken library or model-specific tokenizers.
    
    Args:
        text: Input text to count tokens for
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Method 1: Character-based approximation
    # Average English word is ~4.5 characters, and average token is ~4 characters
    # So we estimate: tokens ≈ characters / 4
    
    # Method 2: Word-based approximation (more accurate)
    # Count words and apply a token-to-word ratio
    
    # Method 3: For code or special content, use different heuristics
    
    try:
        # Clean and prepare text
        text = text.strip()
        if not text:
            return 0
        
        # Method 2: Word-based estimation (more reliable)
        words = text.split()
        word_count = len(words)
        
        # Average token-to-word ratio varies by content type
        # - Plain English: ~1.2 tokens per word
        # - Code: ~1.5 tokens per word  
        # - Mixed content: ~1.3 tokens per word
        
        # Detect content type
        if _is_code_like(text):
            ratio = 1.5
        elif _is_english_heavy(text):
            ratio = 1.2
        else:
            ratio = 1.3
        
        token_estimate = int(word_count * ratio)
        
        # Method 1: Character-based as validation
        char_based_estimate = max(1, len(text) // 4)
        
        # Use the more conservative estimate (higher token count)
        final_estimate = max(token_estimate, char_based_estimate)
        
        logger.debug(f"Token estimate: {final_estimate} (words: {word_count}, chars: {len(text)})")
        
        return final_estimate
        
    except Exception as e:
        logger.error(f"Error estimating tokens: {e}")
        # Fallback to simple character-based estimation
        return max(1, len(text) // 4)


def _is_code_like(text: str) -> bool:
    """Detect if text looks like code"""
    code_indicators = [
        # Programming keywords
        r'\b(function|def|class|import|from|return|if|else|for|while|try|catch)\b',
        # Code syntax
        r'[{}()\[\];,]',
        r'=\s*\w+',
        r'\b(var|let|const)\b',
        # Comments
        r'//|#|/\*|\*/',
    ]
    
    import re
    code_pattern_count = sum(1 for pattern in code_indicators if re.search(pattern, text, re.IGNORECASE))
    return code_pattern_count >= 2


def _is_english_heavy(text: str) -> bool:
    """Detect if text is predominantly English prose"""
    import re
    
    # Simple heuristic: count common English words
    english_words = r'\b(the|and|or|but|is|are|was|were|have|has|had|will|would|could|should|may|might|can|this|that|these|those|with|from|they|them|their|there|here|when|where|who|what|how|why)\b'
    
    words = text.split()
    english_word_count = len(re.findall(english_words, text, re.IGNORECASE))
    english_ratio = english_word_count / len(words) if words else 0
    
    return english_ratio > 0.1


def calculate_input_output_tokens(prompt: str, response: str) -> tuple[int, int]:
    """
    Calculate input and output token counts for a prompt-response pair
    
    Args:
        prompt: Input prompt text
        response: Generated response text
        
    Returns:
        Tuple of (input_tokens, output_tokens)
    """
    input_tokens = estimate_token_count(prompt)
    output_tokens = estimate_token_count(response)
    
    return input_tokens, output_tokens


def estimate_cost_from_tokens(input_tokens: int, output_tokens: int, model: str = "gemini-1.5-pro") -> float:
    """
    Estimate cost based on token usage and model pricing
    
    TODO: Update with current Google Vertex AI pricing
    This is a placeholder with approximate pricing
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens  
        model: Model name for pricing lookup
        
    Returns:
        Estimated cost in USD
    """
    # TODO: Load actual pricing from configuration or external source
    # These are placeholder prices - update with current Gemini pricing
    pricing = {
        "gemini-1.5-pro": {
            "input_per_1k": 0.00125,  # $0.00125 per 1K input tokens
            "output_per_1k": 0.0025   # $0.0025 per 1K output tokens
        },
        "gemini-1.5-flash": {
            "input_per_1k": 0.000075,  # $0.000075 per 1K input tokens
            "output_per_1k": 0.0003    # $0.0003 per 1K output tokens
        }
    }
    
    model_pricing = pricing.get(model, pricing["gemini-1.5-pro"])
    
    input_cost = (input_tokens / 1000) * model_pricing["input_per_1k"]
    output_cost = (output_tokens / 1000) * model_pricing["output_per_1k"]
    
    total_cost = input_cost + output_cost
    
    logger.debug(f"Cost estimate: ${total_cost:.6f} ({input_tokens} input + {output_tokens} output tokens)")
    
    return round(total_cost, 6)


def format_token_count(tokens: int) -> str:
    """
    Format token count for human-readable display
    
    Args:
        tokens: Token count to format
        
    Returns:
        Formatted string (e.g., "1.2K", "1.5M")
    """
    if tokens >= 1_000_000:
        return f"{tokens/1_000_000:.1f}M"
    elif tokens >= 1_000:
        return f"{tokens/1_000:.1f}K"
    else:
        return str(tokens)


def validate_token_limits(prompt: str, max_tokens: int, model: str = "gemini-1.5-pro") -> Dict[str, any]:
    """
    Validate that prompt tokens are within model limits
    
    Args:
        prompt: Input prompt text
        max_tokens: Maximum allowed tokens
        model: Model name for limit lookup
        
    Returns:
        Dictionary with validation results
    """
    # TODO: Get actual model limits from configuration
    model_limits = {
        "gemini-1.5-pro": 1_000_000,      # 1M tokens context window
        "gemini-1.5-flash": 1_000_000,    # 1M tokens context window
        "gemini-1.0-pro": 30_000          # 30K tokens context window
    }
    
    model_limit = model_limits.get(model, model_limits["gemini-1.5-pro"])
    prompt_tokens = estimate_token_count(prompt)
    
    result = {
        "within_limits": prompt_tokens <= max_tokens,
        "prompt_tokens": prompt_tokens,
        "max_tokens": max_tokens,
        "model_limit": model_limit,
        "model": model,
        "usage_percentage": round((prompt_tokens / model_limit) * 100, 2)
    }
    
    if not result["within_limits"]:
        logger.warning(f"Prompt exceeds token limit: {prompt_tokens} > {max_tokens}")
    
    return result

