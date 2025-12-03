"""Logging configuration for TumorBoard LLM decisions.

Provides structured logging for LLM interactions, decision tracking, and debugging.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class LLMDecisionLogger:
    """Logger for LLM decisions with structured output."""

    def __init__(self, log_dir: Path | None = None, enable_file_logging: bool = True):
        """Initialize the LLM decision logger.

        Args:
            log_dir: Directory for log files. Defaults to ./logs
            enable_file_logging: Whether to write logs to files
        """
        self.logger = logging.getLogger("tumorboard.llm")
        self.logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Console handler for structured output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler for detailed JSON logs
        self.file_handler = None
        if enable_file_logging:
            if log_dir is None:
                log_dir = Path("./logs")
            log_dir.mkdir(exist_ok=True)

            # Create dated log file
            timestamp = datetime.now().strftime("%Y%m%d")
            log_file = log_dir / f"llm_decisions_{timestamp}.jsonl"

            # Use a separate file handler that only logs DEBUG messages
            self.file_handler = logging.FileHandler(log_file)
            self.file_handler.setLevel(logging.DEBUG)
            self.file_handler.setFormatter(logging.Formatter('%(message)s'))
            self.file_handler.addFilter(lambda record: record.levelno == logging.DEBUG)
            self.logger.addHandler(self.file_handler)

            self.log_file = log_file
            self.logger.info(f"LLM decision logging enabled: {log_file}")
        else:
            self.log_file = None

    def log_llm_request(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None,
        evidence_summary: str,
        model: str,
        temperature: float,
    ) -> str:
        """Log an LLM assessment request.

        Returns:
            Request ID for tracking
        """
        request_id = f"{gene}_{variant}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "llm_request",
            "request_id": request_id,
            "input": {
                "gene": gene,
                "variant": variant,
                "tumor_type": tumor_type,
                "evidence_summary_length": len(evidence_summary),
                "model": model,
                "temperature": temperature,
            }
        }

        self.logger.info(f"LLM Request: {gene} {variant} (tumor: {tumor_type or 'unspecified'}) using {model}")

        # Write JSON to file handler only
        if self.file_handler:
            self.file_handler.stream.write(json.dumps(log_entry) + '\n')
            self.file_handler.flush()

        return request_id

    def log_llm_response(
        self,
        request_id: str,
        gene: str,
        variant: str,
        tumor_type: str | None,
        tier: str,
        confidence_score: float,
        summary: str,
        rationale: str,
        evidence_strength: str | None,
        recommended_therapies: list[dict[str, Any]],
        references: list[str],
        raw_response: str | None = None,
    ) -> None:
        """Log an LLM assessment response."""

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "llm_response",
            "request_id": request_id,
            "output": {
                "gene": gene,
                "variant": variant,
                "tumor_type": tumor_type,
                "tier": tier,
                "confidence_score": confidence_score,
                "summary": summary,
                "rationale": rationale,
                "evidence_strength": evidence_strength,
                "recommended_therapies": recommended_therapies,
                "references": references,
            }
        }

        if raw_response:
            log_entry["raw_response"] = raw_response

        self.logger.info(
            f"LLM Decision: {gene} {variant} → {tier} "
            f"(confidence: {confidence_score:.1%}, therapies: {len(recommended_therapies)})"
        )

        # Write JSON to file handler only
        if self.file_handler:
            self.file_handler.stream.write(json.dumps(log_entry) + '\n')
            self.file_handler.flush()

    def log_llm_error(
        self,
        request_id: str,
        gene: str,
        variant: str,
        error: Exception,
    ) -> None:
        """Log an LLM assessment error."""

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "llm_error",
            "request_id": request_id,
            "input": {
                "gene": gene,
                "variant": variant,
            },
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            }
        }

        self.logger.error(f"LLM Error: {gene} {variant} - {error}")

        # Write JSON to file handler only
        if self.file_handler:
            self.file_handler.stream.write(json.dumps(log_entry) + '\n')
            self.file_handler.flush()

    def log_decision_summary(
        self,
        gene: str,
        variant: str,
        tumor_type: str | None,
        tier: str,
        confidence_score: float,
        key_evidence: list[str],
        decision_rationale: str,
    ) -> None:
        """Log a high-level decision summary for easy review."""

        summary = (
            f"\n{'='*80}\n"
            f"DECISION SUMMARY\n"
            f"{'='*80}\n"
            f"Gene: {gene}\n"
            f"Variant: {variant}\n"
            f"Tumor Type: {tumor_type or 'Unspecified'}\n"
            f"{'='*80}\n"
            f"TIER: {tier}\n"
            f"Confidence: {confidence_score:.1%}\n"
            f"{'='*80}\n"
            f"KEY EVIDENCE:\n"
        )

        for evidence in key_evidence:
            summary += f"  • {evidence}\n"

        summary += (
            f"{'='*80}\n"
            f"RATIONALE:\n{decision_rationale}\n"
            f"{'='*80}\n"
        )

        self.logger.info(summary)


# Global logger instance
_global_logger: LLMDecisionLogger | None = None


def get_logger(log_dir: Path | None = None, enable_file_logging: bool = True) -> LLMDecisionLogger:
    """Get or create the global LLM decision logger."""
    global _global_logger

    if _global_logger is None:
        _global_logger = LLMDecisionLogger(log_dir=log_dir, enable_file_logging=enable_file_logging)

    return _global_logger


def reset_logger() -> None:
    """Reset the global logger (mainly for testing)."""
    global _global_logger
    _global_logger = None
