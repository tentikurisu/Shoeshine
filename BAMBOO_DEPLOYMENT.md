# Bamboo Deployment Configuration Guide

This document explains exactly what goes where for deploying to AWS via Bamboo.

## 📁 What IS in the Repository (Committed to Git)

These files are already set up and ready to go:

### ✅ infra/terraform/ (Infrastructure Code)
| File | Purpose |
|------|---------|
| `main.tf` | Defines Lambda, API Gateway, ECR, IAM, CloudWatch |
| `variables.tf` | Defines what can be configured |
| `outputs.tf` | Outputs API Gateway URL after deployment |
| `providers.tf` | AWS provider configuration |
| `backend.tf` | S3 state storage configuration |

### ✅ infra/pipeline/ (Bamboo Pipeline)
| File | Purpose |
|------|---------|
| `pipeline.yaml` | Complete CI/CD pipeline definition |

### ✅ infra/bamboo/ (Bamboo Environment)
| File | Purpose |
|------|---------|
| `Dockerfile` | Build environment for Bamboo agents |

### ❌ infra/terraform/terraform.tfvars (NOT in Git)
This file is **gitignored** and contains real secrets. You create this locally only if running Terraform manually.

---

## 🔐 What YOU Need to Configure

### 1. AWS (Create via AWS Console or CLI)

Run these commands **ONCE** before first deployment:

```bash
# 1. Create S3 bucket for Terraform state
aws s3 mb s3://shoeshine-terraform-state --region eu-west-2

# 2. Enable versioning on S3 bucket
aws s3api put-bucket-versioning \
  --bucket shoeshine-terraform-state \
  --versioning-configuration Status=Enabled

# 3. Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-west-2
```

**That's it!** Terraform will create all other resources (ECR, Lambda, API Gateway, etc.)

---

### 2. Bamboo Cloud (Configure in Web UI)

Go to **Bamboo Cloud → Your Project → Plan Settings → Variables**

#### Plain Variables (Visible):
```
aws_region = eu-west-2
environment = production
ecr_repo_name = shoeshine
lambda_func_name = shoeshine-lambda
api_endpoint = (LEAVE BLANK - will be filled after first deployment)
```

#### Secure Variables (Click "Add secure variable"):
```
aws_access_key = (your IAM user access key)
aws_secret_key = (your IAM user secret key)
api_key = (generate: python -c "import secrets; print(secrets.token_urlsafe(32))")
bedrock_model_id = anthropic.claude-sonnet-4-20250507
```

---

## 📋 Complete Configuration Checklist

### Before First Deployment:

- [ ] Create S3 bucket `shoeshine-terraform-state`
- [ ] Create DynamoDB table `terraform-locks`
- [ ] Create Bamboo Project: Shoeshine
- [ ] Create Bamboo Plan: Shoeshine-Lambda
- [ ] Link repository to Bamboo plan
- [ ] Add plain variables in Bamboo
- [ ] Add secure variables in Bamboo
- [ ] Push code to git
- [ ] Trigger Bamboo plan

### After First Successful Deployment:

- [ ] Copy API Gateway URL from Terraform output
- [ ] Update `api_endpoint` variable in Bamboo
- [ ] Run Bamboo plan again (health check will pass)

---

## 🔄 What Happens During Deployment

```
1. PUSH CODE → Bamboo detects change
2. BUILD → Docker image built & pushed to ECR
3. TEST → Pytest runs
4. INFRASTRUCTURE → Terraform creates:
   - ECR Repository (shoeshine)
   - Lambda Function (shoeshine-production)
   - API Gateway HTTP (shoeshine-production)
   - IAM Roles & Policies
   - CloudWatch Log Group
5. DEPLOY → Lambda updated with new image
6. VALIDATE → Health check on API Gateway
```

---

## 🆘 If Something Goes Wrong

### Check Bamboo Build Logs
1. Go to Bamboo → Your Plan → Build results
2. Click on failed stage
3. View logs for error details

### Common Issues:

**"AWS Access Denied"**
→ Check AWS credentials in Bamboo secure variables

**"S3 Bucket Not Found"**
→ Create S3 bucket before running Terraform

**"State Locked"**
→ Wait a minute, DynamoDB lock will release automatically

**"Health Check Failed"**
→ Update `api_endpoint` with correct URL from output

---

## 🎯 Quick Commands

### Generate API Key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### List S3 Buckets:
```bash
aws s3 ls
```

### List DynamoDB Tables:
```bash
aws dynamodb list-tables --region eu-west-2
```

### Check Lambda Functions:
```bash
aws lambda list-functions --region eu-west-2
```

---

## 📞 Need Help?

Check the deployment guide in the repo:
- README.md - General project documentation
- This file - Bamboo deployment configuration
