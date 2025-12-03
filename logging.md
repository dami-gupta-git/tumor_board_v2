# TumorBoard LLM Decision Logging

## Overview

TumorBoard includes comprehensive logging of all LLM decisions to help you track, audit, and analyze the variant assessments made by the system. This feature captures detailed information about every LLM request and response, storing both human-readable console output and structured JSON logs for programmatic analysis.

## Features

- **Structured JSON logging** - Each decision is logged as a JSON object for easy parsing and analysis
- **Human-readable summaries** - Console output provides clear decision summaries
- **Request tracking** - Each request gets a unique ID to correlate requests with responses
- **Error logging** - Failures are captured with full context
- **Configurable** - Logging can be enabled/disabled via CLI flags
- **Automatic file organization** - Logs are organized by date

## Log File Location

Logs are automatically saved to:

```
./logs/llm_decisions_YYYYMMDD.jsonl
```

Example: `logs/llm_decisions_20251203.jsonl`

The `.jsonl` extension indicates JSON Lines format - each line is a complete JSON object.

## Usage

### Enable Logging (Default)

Logging is **enabled by default** for all commands:

```bash
# Single variant assessment
tumorboard assess BRAF V600E --tumor melanoma

# Batch processing
tumorboard batch variants.json

# Validation against gold standard
tumorboard validate gold_standard.json
```

### Disable Logging

To disable logging, use the `--no-log` flag:

```bash
tumorboard assess BRAF V600E --tumor melanoma --no-log
tumorboard batch variants.json --no-log
tumorboard validate gold_standard.json --no-log
```

## Log Format

### Console Output

Human-readable log messages are written to the console:

```
2025-12-03 01:15:31 - tumorboard.llm - INFO - LLM decision logging enabled: logs/llm_decisions_20251203.jsonl
2025-12-03 01:15:31 - tumorboard.llm - INFO - LLM Request: EGFR L858R (tumor: lung cancer) using gpt-4o-mini
2025-12-03 01:15:41 - tumorboard.llm - INFO - LLM Decision: EGFR L858R → Tier I (confidence: 95.0%, therapies: 4)
```

Each assessment also includes a detailed decision summary:

```
================================================================================
DECISION SUMMARY
================================================================================
Gene: EGFR
Variant: L858R
Tumor Type: lung cancer
================================================================================
TIER: Tier I
Confidence: 95.0%
================================================================================
KEY EVIDENCE:
  • OncoKB Level A
  • CIViC EID:1
  • FDA approval 2023
================================================================================
RATIONALE:
The EGFR L858R mutation is recognized as a predictive biomarker for sensitivity
to several FDA-approved therapies in NSCLC...
================================================================================
```

### File Output (JSON)

Structured JSON objects are written to the log file, one per line:

#### Request Log Entry

```json
{
  "timestamp": "2025-12-03T01:15:31.329508",
  "event_type": "llm_request",
  "request_id": "EGFR_L858R_20251203_011531_329465",
  "input": {
    "gene": "EGFR",
    "variant": "L858R",
    "tumor_type": "lung cancer",
    "evidence_summary_length": 7074,
    "model": "gpt-4o-mini",
    "temperature": 0.1
  }
}
```

#### Response Log Entry

```json
{
  "timestamp": "2025-12-03T01:15:41.616794",
  "event_type": "llm_response",
  "request_id": "EGFR_L858R_20251203_011531_329465",
  "output": {
    "gene": "EGFR",
    "variant": "L858R",
    "tumor_type": "lung cancer",
    "tier": "Tier I",
    "confidence_score": 0.95,
    "summary": "The EGFR L858R mutation is a well-established actionable variant...",
    "rationale": "The EGFR L858R mutation is recognized as a predictive biomarker...",
    "evidence_strength": "Strong",
    "recommended_therapies": [
      {
        "drug_name": "Erlotinib",
        "evidence_level": "FDA-approved",
        "approval_status": "Approved in indication",
        "clinical_context": "First-line"
      }
    ],
    "references": [
      "OncoKB Level A",
      "CIViC EID:1",
      "FDA approval 2023"
    ]
  },
  "raw_response": "{\"tier\": \"Tier I\", \"confidence_score\": 0.95, ..."
}
```

#### Error Log Entry

```json
{
  "timestamp": "2025-12-03T01:20:15.123456",
  "event_type": "llm_error",
  "request_id": "TP53_R273H_20251203_012015_123400",
  "input": {
    "gene": "TP53",
    "variant": "R273H"
  },
  "error": {
    "type": "JSONDecodeError",
    "message": "Expecting value: line 1 column 1 (char 0)"
  }
}
```

## Viewing and Analyzing Logs

### View All Logs

```bash
cat logs/llm_decisions_20251203.jsonl
```

### View Formatted JSON (one entry at a time)

```bash
# First entry
head -1 logs/llm_decisions_20251203.jsonl | python3 -m json.tool

# Last entry
tail -1 logs/llm_decisions_20251203.jsonl | python3 -m json.tool

# Specific line
sed -n '5p' logs/llm_decisions_20251203.jsonl | python3 -m json.tool
```

### Filter by Event Type

```bash
# All requests
grep '"event_type": "llm_request"' logs/llm_decisions_20251203.jsonl

# All responses
grep '"event_type": "llm_response"' logs/llm_decisions_20251203.jsonl

# All errors
grep '"event_type": "llm_error"' logs/llm_decisions_20251203.jsonl
```

### Analyze with Python

```python
import json

# Read all log entries
with open('logs/llm_decisions_20251203.jsonl', 'r') as f:
    logs = [json.loads(line) for line in f]

# Filter responses
responses = [log for log in logs if log['event_type'] == 'llm_response']

# Analyze tier distribution
tier_counts = {}
for response in responses:
    tier = response['output']['tier']
    tier_counts[tier] = tier_counts.get(tier, 0) + 1

print("Tier Distribution:")
for tier, count in sorted(tier_counts.items()):
    print(f"  {tier}: {count}")

# Calculate average confidence scores
confidences = [r['output']['confidence_score'] for r in responses]
avg_confidence = sum(confidences) / len(confidences)
print(f"\nAverage Confidence: {avg_confidence:.1%}")

# Find high-confidence Tier I variants
tier_i_high_conf = [
    r for r in responses
    if r['output']['tier'] == 'Tier I'
    and r['output']['confidence_score'] >= 0.9
]
print(f"\nTier I variants with ≥90% confidence: {len(tier_i_high_conf)}")
```

### Analyze with jq

```bash
# Count events by type
cat logs/llm_decisions_20251203.jsonl | jq -r '.event_type' | sort | uniq -c

# Extract all tier decisions
cat logs/llm_decisions_20251203.jsonl | jq -r 'select(.event_type == "llm_response") | .output.tier'

# Get variants with Tier I decisions
cat logs/llm_decisions_20251203.jsonl | \
  jq -r 'select(.event_type == "llm_response" and .output.tier == "Tier I") | "\(.output.gene) \(.output.variant)"'

# Calculate average confidence score
cat logs/llm_decisions_20251203.jsonl | \
  jq -r 'select(.event_type == "llm_response") | .output.confidence_score' | \
  awk '{sum+=$1; count+=1} END {print sum/count}'
```

## Information Captured

### Request Information
- Gene symbol
- Variant notation
- Tumor type (if specified)
- LLM model used
- Temperature setting
- Evidence summary length
- Timestamp
- Unique request ID

### Response Information
- All request information (via request_id)
- Tier classification (I, II, III, IV, Unknown)
- Confidence score (0.0 - 1.0)
- Clinical summary
- Detailed rationale
- Evidence strength (Strong/Moderate/Weak)
- Recommended therapies with:
  - Drug name
  - Evidence level
  - Approval status
  - Clinical context
- Supporting references
- First 500 characters of raw LLM response
- Timestamp

### Error Information
- Request ID
- Gene and variant
- Error type
- Error message
- Timestamp

## Implementation Details

### Architecture

The logging system consists of three main components:

1. **LLMDecisionLogger** ([src/tumorboard/utils/logging_config.py](src/tumorboard/utils/logging_config.py))
   - Core logging functionality
   - Manages console and file handlers
   - Formats structured JSON output

2. **LLMService** ([src/tumorboard/llm/service.py](src/tumorboard/llm/service.py))
   - Calls logger before and after LLM requests
   - Captures errors and logs them
   - Generates decision summaries

3. **CLI Integration** ([src/tumorboard/cli.py](src/tumorboard/cli.py))
   - Exposes `--log/--no-log` flags
   - Passes logging configuration to engine

### Log File Management

- Logs are organized by date (one file per day)
- Log directory (`./logs/`) is created automatically
- Files use `.jsonl` extension (JSON Lines format)
- Each JSON entry is on a single line for easy streaming

### Thread Safety

The logger writes directly to file streams and flushes after each write, ensuring:
- Log entries are written immediately
- No data loss on crashes
- Safe for concurrent access (though TumorBoard runs sequentially per variant)

## Use Cases

### Auditing and Compliance

Track all variant assessments for regulatory compliance:

```bash
# Generate audit report for date range
for date in 20251201 20251202 20251203; do
  echo "Date: $date"
  cat logs/llm_decisions_${date}.jsonl | \
    jq -r 'select(.event_type == "llm_response") | "\(.output.gene) \(.output.variant) -> \(.output.tier)"'
done
```

### Quality Assurance

Monitor confidence scores and identify low-confidence decisions:

```bash
# Find low-confidence assessments
cat logs/llm_decisions_20251203.jsonl | \
  jq 'select(.event_type == "llm_response" and .output.confidence_score < 0.7) |
      {gene: .output.gene, variant: .output.variant, confidence: .output.confidence_score}'
```

### Performance Monitoring

Track LLM response times:

```python
import json
from datetime import datetime

with open('logs/llm_decisions_20251203.jsonl', 'r') as f:
    logs = [json.loads(line) for line in f]

# Group by request_id
requests = {log['request_id']: log for log in logs if log['event_type'] == 'llm_request'}
responses = {log['request_id']: log for log in logs if log['event_type'] == 'llm_response'}

# Calculate response times
response_times = []
for req_id in requests:
    if req_id in responses:
        req_time = datetime.fromisoformat(requests[req_id]['timestamp'])
        resp_time = datetime.fromisoformat(responses[req_id]['timestamp'])
        duration = (resp_time - req_time).total_seconds()
        response_times.append(duration)

print(f"Average response time: {sum(response_times)/len(response_times):.2f}s")
print(f"Min: {min(response_times):.2f}s, Max: {max(response_times):.2f}s")
```

### Research and Validation

Compare LLM decisions against gold standards:

```python
import json

# Load gold standard
with open('benchmarks/gold_standard.json', 'r') as f:
    gold_standard = {f"{entry['gene']}_{entry['variant']}": entry for entry in json.load(f)}

# Load LLM decisions
with open('logs/llm_decisions_20251203.jsonl', 'r') as f:
    logs = [json.loads(line) for line in f]

responses = [log for log in logs if log['event_type'] == 'llm_response']

# Compare
matches = 0
total = 0
for response in responses:
    key = f"{response['output']['gene']}_{response['output']['variant']}"
    if key in gold_standard:
        total += 1
        if response['output']['tier'] == gold_standard[key]['expected_tier']:
            matches += 1

print(f"Accuracy: {matches}/{total} ({matches/total*100:.1f}%)")
```

## Best Practices

1. **Keep logs for audit trails** - Retain logs for compliance and historical analysis
2. **Monitor log file sizes** - Rotate or archive old logs periodically
3. **Use structured analysis** - Leverage jq, Python, or other tools for JSON parsing
4. **Correlate with outputs** - Use request IDs to match logs with result files
5. **Review errors** - Regularly check for `llm_error` events and investigate causes
6. **Validate against gold standards** - Use logs to track model performance over time

## Troubleshooting

### Logs not being created

Check that:
- You're using `--log` or not using `--no-log`
- The `./logs/` directory is writable
- The application has permission to create files

### Log file empty

Ensure the assessment completes successfully. Logs are flushed immediately, so partial runs should still produce entries.

### Cannot parse JSON

Each line in the `.jsonl` file is a separate JSON object. Parse line by line:

```python
with open('logs/llm_decisions_20251203.jsonl', 'r') as f:
    for line in f:
        entry = json.loads(line)
        # Process entry
```

### Logs contain sensitive information

The logs capture clinical data (gene, variant, tumor type). Store logs securely and:
- Set appropriate file permissions
- Encrypt log files if required
- Follow institutional data retention policies

## Privacy and Security

**Important:** Log files may contain:
- Patient tumor types
- Genetic variant information
- Clinical recommendations

Treat log files as **Protected Health Information (PHI)** if they can be linked to patient records. Implement appropriate:
- Access controls
- Encryption (at rest and in transit)
- Retention and deletion policies
- Audit logging for log access

## Related Files

- [src/tumorboard/utils/logging_config.py](src/tumorboard/utils/logging_config.py) - Logger implementation
- [src/tumorboard/llm/service.py](src/tumorboard/llm/service.py) - LLM service with logging
- [src/tumorboard/engine.py](src/tumorboard/engine.py) - Assessment engine
- [src/tumorboard/cli.py](src/tumorboard/cli.py) - CLI with logging options

## Support

For issues or questions about logging:
1. Check this documentation
2. Review the source code in `src/tumorboard/utils/logging_config.py`
3. Open an issue at https://github.com/anthropics/tumorboard/issues (if applicable)