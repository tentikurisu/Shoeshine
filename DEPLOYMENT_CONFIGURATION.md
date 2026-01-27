# Shoeshine Deployment Configuration Guide

This document explains exactly what needs to be configured where for Bamboo deployment.

## 📁 Repository Configuration (INCLUDED in git)

These files are committed to git and contain only non-sensitive defaults:

### infra/terraform/terraform.tfvars.example
- Default values only (eu-west-2, production, etc.)
- No real API keys or passwords
- Example values shown

### infra/terraform/variables.tf
- Variable definitions
- No sensitive data

### infra/terraform/main.tf
- Infrastructure code
- No sensitive data

### infra/terraform/outputs.tf
- Output definitions
- No sensitive data

### infra/terraform/providers.tf
- Provider configuration
- No sensitive data

### infra/terraform/backend.tf
- Backend configuration
- No sensitive data

---

## 🚫 Repository Configuration (EXCLUDED from git)

This file is automatically excluded by .gitignore and should NEVER be committed:

### infra/terraform/terraform.tfvars
Contains REAL sensitive values:
- api_key (your actual production API key)
- bedrock_model_id (your actual Bedrock model)
- Other environment-specific values

**DO NOT COMMIT THIS FILE!**

---

## 🔐 Bamboo Configuration (Configure in Bamboo Cloud)

These are configured in Bamboo Plan Settings → Variables:

### Plain Variables (Visible in Bamboo)
These are NOT secrets and can be seen:
```
aws_region = eu-west-2
environment = production
ecr_repo_name = shoeshine
lambda_func_name = shoeshine-lambda
api_endpoint = https://xxxxx.execute-api.eu-west-1.amazonaws.com/prod  (LEAVE BLANK initially)
```

### Secure Variables (Masked in Bamboo)
These are HIDDEN and MASKED:
```
aws_access_key = (your IAM user access key)
aws_secret_key = (your IAM user secret key)
api_key = (your production API key)
bedrock_model_id = anthropic.claude-sonnet-4-20250507
```

---

## ⚡ What Bamboo Automatically Configures

During the pipeline run, Bamboo automatically:

1. **Build Stage**:
   - Builds Docker image from Dockerfile.lambda
   - Tags image with :latest and :bamboo-{revision}
   - Pushes to ECR

2. **Test Stage**:
   - Runs pytest on tests/
   - Reports test results

3. **Infrastructure Stage**:
   - Runs `terraform init` (uses backend.tf config)
   - Runs `terraform plan` (uses variables from Bamboo)
   - Runs `terraform apply` (creates AWS resources)
   - Creates: ECR, Lambda, API Gateway, IAM, CloudWatch

4. **Deploy Stage**:
   - Updates Lambda with new ECR image
   - Waits for deployment completion

5. **Validate Stage**:
   - Calls /health endpoint
   - Reports success/failure

---

## 📋 Complete Configuration Checklist

### Before First Deployment

#### 1. AWS CLI (Do Once)
```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://shoeshine-terraform-state --region eu-west-2

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket shoeshine-terraform-state \
  --versioning-configuration Status=Enabled

# Create DynamoDB table
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-2
```

#### 2. Create API Key (Do Once)
```bash
# Generate a secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 3. Configure Bamboo (Do Once)
Go to Bamboo Cloud → Plan Settings → Variables:

**Plain Variables:**
```
aws_region = eu-west-2
environment = production
ecr_repo_name = shoeshine
lambda_func_name = shoeshine-lambda
api_endpoint = (leave blank for now)
```

**Secure Variables:**
```
aws_access_key = (your IAM access key)
aws_secret_key = (your IAM secret key)
api_key = (your generated API key)
bedrock_model_id = anthropic.claude-sonnet-4-20250507
```

#### 4. Local Development (Optional)
If you want to run Terraform locally:
```bash
# Copy example to actual file
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars

# Edit with your values
# (This file is gitignored, so safe to edit)
```

---

## 🎯 Deployment Flow

### First Deployment
1. Push code to branch
2. Bamboo runs pipeline
3. Infrastructure stage creates all AWS resources
4. API Gateway URL is output in logs
5. Copy URL and update `api_endpoint` variable in Bamboo
6. Run pipeline again

### Subsequent Deployments
1. Push code changes
2. Bamboo automatically runs pipeline
3. Terraform updates infrastructure (if changed)
4. Lambda updates with new image
5. Health check validates deployment

---

## 🔍 What Happens If...

### ...I forget to create S3 bucket?
❌ Terraform init will fail in Bamboo

### ...I don't configure secure variables?
❌ AWS authentication will fail in Bamboo

### ...I don't update api_endpoint after first run?
❌ Health check will fail (wrong URL)

### ...I commit terraform.tfvars?
✅ Won't happen - it's in .gitignore!

---

## 📞 Support

If deployment fails:
1. Check Bamboo build logs
2. Verify AWS credentials have correct permissions
3. Ensure S3 bucket and DynamoDB table exist
4. Check Terraform output for error messages
