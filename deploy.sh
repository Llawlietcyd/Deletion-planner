#!/bin/bash

# AI Academy Deployment Script
set -e

echo "🚀 Starting AI Academy Deployment..."

# Check if required tools are installed
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed. Aborting." >&2; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "❌ AWS CLI is required but not installed. Aborting." >&2; exit 1; }

# Configuration
BUCKET_NAME="${S3_BUCKET:-ai-academy-frontend}"
BACKEND_REPO="${ECR_REPO:-ai-academy-backend}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ACCOUNT_ID="${AWS_ACCOUNT_ID}"

if [ -z "$ACCOUNT_ID" ]; then
    echo "❌ AWS_ACCOUNT_ID environment variable is required"
    exit 1
fi

echo "📦 Building Frontend..."
cd frontend
REACT_APP_API_ENDPOINT=https://api.aiacademy.com npm run build

echo "☁️ Deploying Frontend to S3..."
aws s3 sync build/ s3://$BUCKET_NAME --acl public-read --delete

echo "🐳 Building Backend Docker Image..."
cd ../server
docker build -t $BACKEND_REPO . --platform linux/amd64

echo "🏷️ Tagging Docker Image..."
docker tag $BACKEND_REPO:latest $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$BACKEND_REPO:latest

echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "📤 Pushing Docker Image..."
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$BACKEND_REPO:latest

echo "🌐 Deploying to Elastic Beanstalk..."
cd aws_deploy
eb deploy

echo "✅ Deployment Complete!"
echo "🌍 Frontend: https://$BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com"
echo "📚 Docs: https://$BUCKET_NAME.s3-website-$AWS_REGION.amazonaws.com/docs"
echo "🔗 Backend: Check Elastic Beanstalk console for URL"
