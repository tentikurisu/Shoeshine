# Shoeshine Privacy & Security Guarantees

## Philosophy: This is NOT AI

Shoeshine is a **document-to-text translator**, not an AI system. It uses OCR (Optical Character Recognition) techniques to extract text from images and PDFs.

---

## Explicit Privacy Guarantees

### 1. No Data Retention
- Documents are **never stored** on disk
- All temporary buffers are cleared immediately after processing
- No temporary files are written to disk

### 2. No Training Data
- Your documents **never train** any model
- No embeddings are stored
- No data is sent to external AI services (unless explicitly configured)

### 3. Zero External Calls (by default)
- OCR runs **locally** using PaddleOCR
- No data leaves your infrastructure
- Optional: Only if you configure Ollama/Bedrock integration

### 4. Memory Cleanup
- All process memory is cleared after each request
- No caching of extracted text

### 5. Audit Logging (minimal)
- Only metadata is logged:
  - Request timestamps
  - File sizes (not contents)
  - Processing times
  - Success/failure status

---

## What Shoeshine Collects (Nothing)

| Data Type | Collected? | Notes |
|-----------|------------|-------|
| Document contents | ❌ No | Extracted text only, never stored |
| Images/PDFs | ❌ No | Processed in memory only |
| Text extracted | ❌ No | Returned to caller, not stored |
| User identifiers | ❌ No | Unless API key is used |
| IP addresses | ❌ No | Not logged |
| Model responses | ❌ No | Direct from Ollama to caller |

---

## Security Measures

### Input Validation
- File type verification (magic bytes, not just extensions)
- Size limits (configurable, default 10MB)
- Malformed file detection

### Authentication (Optional)
- API key authentication (simple mode)
- AWS Cognito integration (enterprise mode)

### Network Security
- CORS configuration for controlled access
- HTTPS recommended for production

---

## Data Flow

```
Your Document → Shoeshine (Memory Only) → Extracted Text → Your App/Model
                  ↓
           All buffers cleared
           No storage
```

---

## For AWS Deployment

When deploying to AWS:

1. **ECS Fargate**: No persistent storage needed
2. **EC2**: Use ephemeral storage, don't mount volumes
3. **VPC**: Deploy in private subnet
4. **WAF**: Add rate limiting if exposed to internet

---

## Compliance Notes

- **GDPR**: No personal data is stored or processed beyond the request
- **HIPAA**: Suitable for PHI when deployed in secure environment
- **SOC 2**: Audit logging available, no data retention

---

## Questions?

If you have questions about privacy or security, please open an issue on GitHub.
