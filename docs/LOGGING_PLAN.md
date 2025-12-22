# LLM Logging Strategy for TumorBoard

## Overview

Comprehensive LLM logging is critical for TumorBoard as a medical AI system to ensure:
- **Audit trails** for clinical decision support
- **Debugging** assessment discrepancies
- **Cost tracking** for LiteLLM API usage
- **Performance monitoring** (latency, token usage)
- **Quality assurance** and validation

## Multi-tier Approach

### 1. Structured Logging (Python `logging` module)

Add to [service.py:18-87](src/tumorboard/llm/service.py#L18-L87)

**Features:**
- Log at key decision points with structured fields
- Levels: INFO for normal flow, WARNING for edge cases, ERROR for failures
- JSON formatting for machine-readable logs
- Log rotation to prevent disk space issues

**What to log:**
- Assessment start/completion
- Model selection and parameters
- Evidence summary statistics
- Response parsing success/failure
- Error conditions and stack traces

### 2. LiteLLM Built-in Callbacks

LiteLLM supports success/failure callbacks and integrations:
- Langfuse
- Weights & Biases
- Helicone
- Custom callbacks

**Features:**
- Automatically captures tokens, cost, latency
- Minimal code changes
- Native integration with observability platforms

**Implementation:**
```python
import litellm
from litellm import acompletion

# Enable success/failure callbacks
litellm.success_callback = ["langfuse"]
litellm.failure_callback = ["langfuse"]

# Or custom callback
def custom_log_callback(kwargs, response_obj, start_time, end_time):
    # Custom logging logic
    pass
```

### 3. Persistent Audit Log (JSON/Database)

For compliance and debugging, store each LLM call with complete context.

**Storage location:**
- Filesystem: `logs/llm_audit/YYYY-MM-DD/`
- Database: SQLite or PostgreSQL table

**Schema:**
```json
{
  "request_id": "uuid-v4",
  "timestamp": "2025-12-03T10:30:45.123Z",
  "input": {
    "gene": "BRAF",
    "variant": "V600E",
    "tumor_type": "melanoma",
    "evidence_summary": "...",
    "evidence_summary_length": 2500
  },
  "llm_request": {
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "messages": [...],
    "prompt_tokens": 1500,
    "completion_tokens": 350
  },
  "llm_response": {
    "raw_content": "...",
    "parsed_assessment": {...},
    "parse_success": true,
    "response_time_ms": 2500
  },
  "metadata": {
    "cost_usd": 0.002,
    "normalized_variant": "V600E",
    "variant_type": "missense",
    "session_id": "optional-session-id"
  },
  "error": null
}
```

### 4. Performance Metrics

Track and aggregate statistics for monitoring:

**Metrics to track:**
- Token usage per assessment (prompt + completion)
- API latency (p50, p95, p99)
- Cost per assessment
- Success/failure rates
- Timeout rates
- Model-specific performance

**Aggregation:**
- Daily/weekly/monthly summaries
- Per-model breakdowns
- Per-tumor-type patterns

## Implementation Levels

### Level 1: Basic (Minimal overhead)

**Effort:** 1-2 hours
**Storage:** In-memory + console output

**Features:**
- Add Python logging to [service.py](src/tumorboard/llm/service.py)
- Log INFO/ERROR messages
- Use LiteLLM's built-in callbacks for token/cost tracking

**Code changes:**
- Add `import logging` to service.py
- Initialize logger in `LLMService.__init__`
- Add log statements at key points

**Pros:**
- Quick to implement
- Minimal performance overhead
- Standard Python logging

**Cons:**
- No persistent storage
- Limited structured data
- Manual cost calculation

### Level 2: Production (Recommended)

**Effort:** 4-6 hours
**Storage:** JSON files with rotation

**Features:**
- Structured JSON logging with rotation
- Persistent audit trail to filesystem (`logs/llm_audit/`)
- Token and cost tracking
- Error tracking with full context
- Daily log rotation

**Code changes:**
- Add logging utility module
- Implement JSON formatter
- Add pre/post hooks in `assess_variant`
- Configure log rotation (Python `logging.handlers.RotatingFileHandler`)

**Pros:**
- Production-ready audit trail
- Easy to parse and analyze
- Compliant with medical AI requirements
- Good balance of features vs complexity

**Cons:**
- Requires disk space management
- No real-time monitoring dashboard

### Level 3: Enterprise

**Effort:** 1-2 days
**Storage:** Database + observability platform

**Features:**
- Database storage (PostgreSQL/SQLite)
- Real-time dashboards (Grafana, custom UI)
- Integration with observability platforms (Langfuse, Weights & Biases)
- Automated alerting
- Advanced analytics and reporting

**Code changes:**
- Add database models and migrations
- Implement async database logging
- Set up observability platform integration
- Create monitoring dashboards

**Pros:**
- Complete observability
- Real-time monitoring and alerting
- Advanced analytics capabilities
- Scalable for high volume

**Cons:**
- Significant implementation effort
- Additional infrastructure dependencies
- Higher complexity

## Key Data to Log

### Input Context

- `gene` (e.g., "BRAF")
- `variant` (e.g., "V600E")
- `tumor_type` (e.g., "melanoma" or null)
- `evidence_summary` (truncated or full based on level)
- Evidence summary length (character count)
- Evidence source counts (OncoKB, CIViC, etc.)
- Normalized variant notation (if different from input)
- Variant type (missense, nonsense, etc.)

### LLM Request

- Model name (e.g., "gpt-4o-mini")
- Temperature setting
- Token counts:
  - Prompt tokens
  - Completion tokens
  - Total tokens
- Full messages payload (system + user prompts)
- Request timestamp
- Response format settings (JSON mode, etc.)

### LLM Response

- Raw response content
- Parsed assessment data:
  - Tier
  - Confidence score
  - Summary
  - Rationale
  - Recommended therapies
  - References
- Parsing success/failure status
- Response time (milliseconds)
- Any markdown/code block stripping performed

### Metadata

- Request ID (UUID)
- Timestamp (ISO 8601 format)
- User/session context (if applicable)
- Cost estimate (USD)
- CLI command or API endpoint used
- Application version
- Environment (dev/staging/production)

### Error Details (if applicable)

- Exception type and message
- Stack trace
- HTTP status code (for API errors)
- LiteLLM error details
- JSON parsing errors
- Retry attempts

## Recommended Implementation Path

### Phase 1: Foundation (Week 1)

1. Add Python logging module to [service.py](src/tumorboard/llm/service.py)
2. Configure structured logging with JSON formatter
3. Log basic INFO/ERROR messages
4. Set up log rotation

### Phase 2: Audit Trail (Week 2)

1. Implement persistent JSON audit log
2. Create log utility functions
3. Add pre/post assessment hooks
4. Test log parsing and analysis scripts

### Phase 3: Metrics (Week 3)

1. Track token usage and costs
2. Implement performance metrics collection
3. Create daily summary reports
4. Add cost analysis tools

### Phase 4: Integration (Week 4)

1. Integrate with LiteLLM callbacks
2. Optional: Set up Langfuse or W&B integration
3. Create monitoring dashboards
4. Document logging architecture

## File Structure

```
tumor_board_v2/
├── src/tumorboard/
│   ├── llm/
│   │   ├── service.py          # Add logging hooks here
│   │   └── prompts.py
│   └── utils/
│       └── logging_utils.py    # New: Logging utilities
├── logs/
│   ├── llm_audit/              # Audit logs by date
│   │   ├── 2025-12-03/
│   │   │   ├── assessments.jsonl
│   │   │   └── errors.jsonl
│   │   └── 2025-12-04/
│   ├── application.log         # Standard app logs
│   └── performance.log         # Performance metrics
└── scripts/
    └── analyze_logs.py         # Log analysis utilities
```

## Security and Privacy Considerations

### PHI/PII Protection

- **Do NOT log patient identifiers** (patient ID, name, MRN, etc.)
- **Genetic variants are not PHI** under HIPAA when de-identified
- If tumor type is specific (e.g., "right breast cancer stage IIB"), generalize it
- Implement log access controls and encryption at rest

### Access Control

- Restrict log file permissions (chmod 600 or 640)
- Use separate log files for sensitive data
- Implement log retention policies (e.g., 90 days for audit logs)
- Document who has access to logs

### Compliance

- HIPAA compliance for clinical usage
- Data retention requirements
- Audit trail requirements for FDA-regulated software
- Export capabilities for regulatory review

## Cost Estimation

Based on GPT-4o-mini pricing:

**Per Assessment:**
- Average prompt: ~1500 tokens
- Average completion: ~350 tokens
- Cost: ~$0.002 per assessment

**Logging overhead:**
- Level 1: Negligible (<1% CPU)
- Level 2: ~5MB per 1000 assessments
- Level 3: ~10-20MB per 1000 assessments (with database)

## Next Steps

1. **Decide on implementation level** (recommend Level 2 for production)
2. **Create logging utility module** (`src/tumorboard/utils/logging_utils.py`)
3. **Integrate logging into LLMService** ([service.py](src/tumorboard/llm/service.py))
4. **Test with validation dataset** to ensure logging doesn't impact performance
5. **Create log analysis scripts** for cost tracking and debugging
6. **Document logging configuration** for operations team

## Example Log Entry (Level 2)

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-12-03T10:30:45.123Z",
  "input": {
    "gene": "BRAF",
    "variant": "V600E",
    "tumor_type": "melanoma",
    "evidence_summary_length": 2500,
    "normalized_variant": "V600E",
    "variant_type": "missense"
  },
  "llm_request": {
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "prompt_tokens": 1500,
    "completion_tokens": 350,
    "total_tokens": 1850
  },
  "llm_response": {
    "tier": "Tier I",
    "confidence_score": 0.95,
    "parse_success": true,
    "response_time_ms": 2500
  },
  "metadata": {
    "cost_usd": 0.002,
    "cli_command": "assess",
    "version": "0.1.0"
  },
  "error": null
}
```