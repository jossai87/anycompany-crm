# AnyCompany CRM — Application Source Code

This directory contains the clean CRM application source code — the backend API handlers, database schema, and Lambda functions that power the AnyCompany CRM.

This is the code that gets pushed to the GitHub repository connected to the AWS DevOps Agent service. It contains **only** the production CRM application code — no failure simulator, no admin handler, no infrastructure manipulation logic.

## Structure

```
backend/
  rest-api/proxy/         # API Gateway Lambda proxy — CRM CRUD endpoints
    handlers/             # Entity handlers (accounts, opportunities, team-members, industries)
    index.py              # Lambda entry point
    router.py             # Request routing
    db_connection.py      # RDS connection pooling
    cors_handler.py       # CORS handling
    error_handler.py      # Error formatting
    s3_integration.py     # S3 image URL enhancement
    validation.py         # Input validation
  database/seed-function/ # Database schema initialization and seed data
  queue-consumer/         # SQS queue consumer Lambda
  target-lambda/          # CRM event processor Lambda
```

## Why This Exists

When the AWS DevOps Agent investigates an incident, it has access to the connected GitHub repository for code context. By keeping only the CRM application code in this repository, the agent performs a clean, realistic investigation — analyzing logs, metrics, IAM policies, and code.
