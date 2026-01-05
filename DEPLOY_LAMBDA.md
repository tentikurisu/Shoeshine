# Quick Start: Lambda Deployment

This guide provides step-by-step instructions for deploying Shoeshine to AWS Lambda.

---

## Prerequisites

- AWS CLI installed and configured
- Docker installed locally
- Terraform installed
- AWS account with appropriate permissions

---

## Step 1: Build and Push Image to ECR

### 1.1 Get Your AWS Account ID

```bash
aws sts get-caller-identity --query Account --output text
```

### 1.2 Login to ECR

```bash
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin \
  <account-id>.dkr.ecr.eu-west-1.amazonaws.com
```

### 1.3 Create ECR Repository (if it doesn't exist)

```bash
aws ecr create-repository --repository-name shoeshine --region eu-west-1
```

### 1.4 Build Lambda Image

```bash
docker build -f Dockerfile.lambda \
  -t <account-id>.dkr.ecr.eu-west-1.amazonaws.com/shoeshine:latest .
```

**Note:** This will take several minutes (10-15 min) as it downloads EasyOCR models (~300MB).

### 1.5 Push to ECR

```bash
docker push <account-id>.dkr.ecr.eu-west-1.amazonaws.com/shoeshine:latest
```

---

## Step 2: Deploy Infrastructure with Terraform

### 2.1 Navigate to Terraform Directory

```bash
cd terraform
```

### 2.2 Copy Example Configuration

```bash
cp terraform.tfvars.example terraform.tfvars
```

### 2.3 Edit terraform.tfvars

```bash
# Open terraform.tfvars and update these values:
# - api_key (generate with: openssl rand -base64 32)
# - aws_region (if not using eu-west-1)
# - s3_bucket (optional - leave empty to skip)
```

Example `terraform.tfvars`:

```hcl
aws_region   = "eu-west-1"
environment  = "production"
api_key      = "your-generated-api-key-here"
lambda_memory             = 2048
lambda_timeout            = 300
lambda_reserved_concurrency = 0
enable_bedrock = true
bedrock_model_id = "anthropic.claude-sonnet-4-20250507"
s3_bucket = ""
ecr_image_tag = "latest"
```

### 2.4 Initialize Terraform

```bash
terraform init
```

### 2.5 Review the Plan

```bash
terraform plan -out=tfplan
```

### 2.6 Apply the Deployment

```bash
terraform apply tfplan
```

Type `yes` when prompted to confirm.

### 2.7 Get the API Endpoint

```bash
terraform output api_endpoint
```

You should see output like:
```
https://xyz123abc.execute-api.eu-west-1.amazonaws.com
```

---

## Step 3: Test the Deployment

### 3.1 Health Check

```bash
API_ENDPOINT=$(terraform output -raw api_endpoint)
curl $API_ENDPOINT/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0",
  "environment": "production",
  "services": {
    "ocr": true,
    "bedrock": true,
    "storage": true
  }
}
```

### 3.2 Test Text Extraction

```bash
# Create a test image (1x1 pixel PNG)
echo "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==" | base64 -d > test.png

# Extract text
curl -X POST $API_ENDPOINT/extract/text \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d "{\"document\": \"$(base64 -w 0 test.png)\"}"
```

### 3.3 Test Harvest Endpoint (if Bedrock enabled)

```bash
# Test structured extraction
curl -X POST $API_ENDPOINT/harvest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "document": "<base64-encoded-image>",
    "fields": ["total", "date", "vendor"]
  }'
```

---

## Step 4: Monitor and Debug

### 4.1 View CloudWatch Logs

```bash
# Get log group name
LOG_GROUP=$(terraform output -raw cloudwatch_log_group)

# View recent logs
aws logs tail $LOG_GROUP --follow
```

### 4.2 Check Lambda Metrics

```bash
# Get Lambda function name
FUNCTION_NAME=$(terraform output -raw lambda_function_name)

# View metrics in AWS Console
aws lambda get-function-configuration \
  --function-name $FUNCTION_NAME \
  --region eu-west-1
```

### 4.3 View API Gateway Logs

```bash
# API Gateway logs are in CloudWatch under:
# /aws/apigateway/your-api-id
aws logs describe-log-groups --log-group-name-prefix /aws/apigateway
```

---

## Common Issues

### Issue: First request takes 15-30 seconds

**Cause:** Lambda cold start - EasyOCR models need to load.

**Solution:** This is normal. Subsequent requests will be faster (2-5 seconds).

### Issue: Lambda timeout error

**Cause:** Document is too large or OCR is slow.

**Solutions:**
1. Increase timeout in `terraform.tfvars`:
   ```hcl
   lambda_timeout = 600
   ```
2. Increase memory (faster processing):
   ```hcl
   lambda_memory = 3072
   ```
3. Apply changes:
   ```bash
   terraform apply -var 'lambda_timeout=600' -var 'lambda_memory=3072'
   ```

### Issue: API returns 403 Forbidden

**Cause:** API key missing or incorrect.

**Solution:** Ensure you include the `X-API-Key` header with your configured API key.

### Issue: Bedrock returns "Access Denied"

**Cause:** IAM role doesn't have Bedrock permissions or model not available in region.

**Solutions:**
1. Check if model is available:
   ```bash
   aws bedrock list-foundation-models --region eu-west-1
   ```
2. Ensure IAM role has correct permissions (Terraform handles this)

### Issue: Image upload fails

**Cause:** API Gateway has a 10MB payload limit.

**Solutions:**
1. Compress images before upload
2. Use S3 upload workflow:
   - Upload file to S3
   - Send S3 object key to Lambda
   - Lambda reads from S3

---

## Cleanup

### Remove All Resources

```bash
cd terraform
terraform destroy
```

### Delete ECR Repository (if not destroyed by Terraform)

```bash
aws ecr delete-repository --repository-name shoeshine --force --region eu-west-1
```

### Delete Docker Images Locally

```bash
docker images | grep shoeshine
docker rmi <image-id>
```

---

## Next Steps

1. **Set up custom domain** - Configure API Gateway with your own domain
2. **Enable monitoring** - Set up CloudWatch alarms for errors and latency
3. **Configure staging** - Use separate Terraform workspace for staging environment
4. **Set up CI/CD** - Configure GitHub Actions for automated deployments (see `.github/workflows/docker-deploy.yml`)

---

## Cost Optimization

### Reduce Lambda Costs

- **Lower memory** for smaller documents:
  ```hcl
  lambda_memory = 1024
  ```
- **Reduce timeout** for faster processing:
  ```hcl
  lambda_timeout = 60
  ```

### Reduce Cold Starts

- **Increase memory** (more CPU = faster loading):
  ```hcl
  lambda_memory = 3072
  ```
- Keep models pre-downloaded (already done in Dockerfile)

### Estimated Costs

| Request Volume | Lambda | API Gateway | Bedrock | Total/month |
|---------------|--------|-------------|---------|-------------|
| 100K | $10 | $0.35 | $5 | $15.35 |
| 1M | $100 | $3.50 | $50 | $153.50 |
| 10M | $1,000 | $35.00 | $500 | $1,535.00 |

**Note:** These are estimates. Actual costs depend on document size, complexity, and processing time.

---

## Additional Resources

- [Full Deployment Guide](DEPLOYMENT.md) - Comprehensive documentation
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

---

## Support

- GitHub Issues: https://github.com/yourusername/shoeshine/issues
- AWS Support: https://aws.amazon.com/support/
