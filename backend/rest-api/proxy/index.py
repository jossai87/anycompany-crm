"""
Main Lambda handler for CRM API Gateway proxy.

This Lambda function serves as the entry point for all CRM API requests.
It routes requests to appropriate entity handlers, enhances responses with S3 image URLs,
applies CORS headers, and handles exceptions with proper error formatting.

Requirements: 1.1, 1.2, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

# Import handler modules
from router import parse_api_gateway_event, validate_route, get_operation_type
from db_connection import get_database_connection, return_database_connection
from handlers import accounts_handler, opportunities_handler, team_members_handler, industries_handler
from s3_integration import enhance_with_images
from cors_handler import process_cors
from error_handler import (
    handle_validation_error,
    handle_not_found_error,
    handle_conflict_error,
    handle_database_error,
    handle_server_error,
    parse_database_error
)

# CloudWatch client for custom metrics
cloudwatch = boto3.client('cloudwatch')

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler entry point for API Gateway requests.
    
    This function:
    1. Parses the API Gateway event to determine route and operation
    2. Validates the route
    3. Establishes database connection
    4. Invokes the appropriate entity handler
    5. Enhances response with S3 image URLs
    6. Applies CORS headers
    7. Handles exceptions and formats error responses
    
    Args:
        event: API Gateway event dictionary
        context: Lambda context object
        
    Returns:
        API Gateway response dictionary with statusCode, headers, and body
        
    Requirements: 1.1, 1.2, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1, 9.1, 10.1
    """
    request_id = context.aws_request_id if context else "unknown"
    logger.info(f"Processing request {request_id}: {event.get('httpMethod')} {event.get('path')}")
    
    try:
        # Handle CORS preflight requests
        if event.get('httpMethod') == 'OPTIONS':
            return process_cors(event)
        
        # Parse API Gateway event to extract route information
        route_info = parse_api_gateway_event(event)
        
        # Validate route
        validate_route(route_info)

        # Get operation type
        operation = get_operation_type(route_info)
        
        # Get database connection
        connection = get_database_connection()
        
        try:
            # Start timing for search operations
            start_time = time.time()
            
            # Route to appropriate handler and execute operation
            result = execute_operation(connection, route_info, operation)
            
            # Calculate and publish query latency metrics
            elapsed_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Publish QueryLatency metric for ALL database operations
            try:
                cloudwatch.put_metric_data(
                    Namespace='CRM/Database',
                    MetricData=[
                        {
                            'MetricName': 'QueryLatency',
                            'Value': elapsed_time,
                            'Unit': 'Milliseconds',
                            'Dimensions': [
                                {'Name': 'Resource', 'Value': route_info.resource_type},
                                {'Name': 'Operation', 'Value': operation}
                            ]
                        }
                    ]
                )
            except Exception as e:
                logger.warning(f"Failed to publish QueryLatency metric: {str(e)}")
            
            # Publish SearchLatency metric for search operations
            is_search_operation = (
                route_info.resource_type == 'opportunities' and 
                (route_info.query_params.get('search') or 
                 route_info.query_params.get('q') or 
                 route_info.path.endswith('/search'))
            )
            if is_search_operation:
                try:
                    cloudwatch.put_metric_data(
                        Namespace='CRM/Database',
                        MetricData=[
                            {
                                'MetricName': 'SearchLatency',
                                'Value': elapsed_time,
                                'Unit': 'Milliseconds',
                                'Dimensions': [
                                    {'Name': 'QueryType', 'Value': 'FullTextSearch'},
                                    {'Name': 'Resource', 'Value': 'opportunities'}
                                ]
                            }
                        ]
                    )
                    logger.info(f"Published SearchLatency metric: {elapsed_time:.2f}ms")
                except Exception as e:
                    logger.warning(f"Failed to publish SearchLatency metric: {str(e)}")
            
            # Format successful response
            response = format_success_response(result, route_info, operation)
        finally:
            # Return database connection to pool
            return_database_connection(connection)
        
        # Apply CORS headers
        response = process_cors(event, response)
        
        logger.info(f"Request {request_id} completed successfully with status {response['statusCode']}")
        return response
        
    except ValueError as e:
        # Validation errors (400)
        logger.warning(f"Validation error in request {request_id}: {str(e)}")
        response = handle_validation_error(str(e))
        return process_cors(event, response)
        
    except Exception as e:
        # Check if it's a custom error message from handlers
        error_str = str(e)
        
        # Not found errors (404)
        if "not found" in error_str.lower():
            resource_type = route_info.resource_type if 'route_info' in locals() else "Resource"
            resource_id = route_info.resource_id if 'route_info' in locals() else "unknown"
            response = handle_not_found_error(resource_type.capitalize(), resource_id)
            return process_cors(event, response)
        
        # Conflict errors (409)
        if "cannot delete" in error_str.lower() or "already exists" in error_str.lower():
            response = handle_conflict_error(error_str)
            return process_cors(event, response)
        
        # Database errors (500)
        if "database" in error_str.lower() or "failed to" in error_str.lower():
            response = parse_database_error(e)
            return process_cors(event, response)
        
        # Generic server error (500)
        logger.error(f"Unexpected error in request {request_id}: {str(e)}", exc_info=True)
        response = handle_server_error(e, request_id)
        return process_cors(event, response)


def execute_operation(connection, route_info, operation: str) -> Any:
    """
    Execute the appropriate CRUD operation based on route information.
    
    Args:
        connection: Database connection object
        route_info: Parsed route information
        operation: Operation type ('list', 'get', 'create', 'update', 'delete')
        
    Returns:
        Operation result (record, list of records, or boolean)
        
    Raises:
        ValueError: If resource type or operation is not supported
    """
    resource_type = route_info.resource_type
    resource_id = route_info.resource_id
    query_params = route_info.query_params
    body = route_info.body
    
    logger.info(f"Executing {operation} operation on {resource_type}")
    
    # Route to accounts handler
    if resource_type == 'accounts':
        if operation == 'list':
            return accounts_handler.list_accounts(connection)
        elif operation == 'get':
            result = accounts_handler.get_account(connection, resource_id)
            if result is None:
                raise ValueError(f"Account with id {resource_id} not found")
            return result
        elif operation == 'create':
            return accounts_handler.create_account(connection, body)
        elif operation == 'update':
            result = accounts_handler.update_account(connection, resource_id, body)
            if result is None:
                raise ValueError(f"Account with id {resource_id} not found")
            return result
        elif operation == 'delete':
            success = accounts_handler.delete_account(connection, resource_id)
            if not success:
                raise ValueError(f"Account with id {resource_id} not found")
            return None
    
    # Route to opportunities handler
    elif resource_type == 'opportunities':
        account_id = query_params.get('accountId')
        search_query = query_params.get('search') or query_params.get('q')  # Support both 'search' and 'q' parameters
        
        # Check if this is a search endpoint (/opportunities/search)
        is_search_endpoint = route_info.path.endswith('/search')
        
        if operation == 'list' or is_search_endpoint:
            # If search query is provided, perform search instead of list
            if search_query:
                return opportunities_handler.search_opportunities(connection, search_query, account_id)
            else:
                return opportunities_handler.list_opportunities(connection, account_id)
        elif operation == 'get':
            result = opportunities_handler.get_opportunity(connection, resource_id)
            if result is None:
                raise ValueError(f"Opportunity with id {resource_id} not found")
            return result
        elif operation == 'create':
            return opportunities_handler.create_opportunity(connection, body)
        elif operation == 'update':
            result = opportunities_handler.update_opportunity(connection, resource_id, body)
            if result is None:
                raise ValueError(f"Opportunity with id {resource_id} not found")
            return result
        elif operation == 'delete':
            success = opportunities_handler.delete_opportunity(connection, resource_id)
            if not success:
                raise ValueError(f"Opportunity with id {resource_id} not found")
            return None
    
    # Route to team members handler
    elif resource_type == 'team-members':
        if operation == 'list':
            return team_members_handler.list_team_members(connection)
        elif operation == 'get':
            result = team_members_handler.get_team_member(connection, resource_id)
            if result is None:
                raise ValueError(f"Team member with id {resource_id} not found")
            return result
        elif operation == 'create':
            return team_members_handler.create_team_member(connection, body)
        elif operation == 'update':
            result = team_members_handler.update_team_member(connection, resource_id, body)
            if result is None:
                raise ValueError(f"Team member with id {resource_id} not found")
            return result
        elif operation == 'delete':
            success = team_members_handler.delete_team_member(connection, resource_id)
            if not success:
                raise ValueError(f"Team member with id {resource_id} not found")
            return None
    
    # Route to industries handler
    elif resource_type == 'industries':
        if operation == 'list':
            return industries_handler.list_industries(connection)
        elif operation == 'get':
            result = industries_handler.get_industry(connection, resource_id)
            if result is None:
                raise ValueError(f"Industry with id {resource_id} not found")
            return result
        else:
            raise ValueError(f"Industries resource only supports GET operations")
    
    else:
        raise ValueError(f"Unsupported resource type: {resource_type}")


def format_success_response(result: Any, route_info, operation: str) -> Dict[str, Any]:
    """
    Format successful operation result into API Gateway response.
    
    Args:
        result: Operation result (record, list of records, or None for delete)
        route_info: Parsed route information
        operation: Operation type
        
    Returns:
        API Gateway response dictionary
    """
    resource_type = route_info.resource_type
    
    # Determine status code based on operation
    if operation == 'create':
        status_code = 201
    elif operation == 'delete':
        status_code = 204
    else:
        status_code = 200
    
    # For delete operations, return empty response
    if operation == 'delete':
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': ''
        }
    
    # Enhance result with S3 image URLs
    entity_type_map = {
        'accounts': 'account',
        'opportunities': 'opportunity',
        'team-members': 'team_member',
        'industries': 'industry'
    }
    entity_type = entity_type_map.get(resource_type, resource_type)
    
    enhanced_result = enhance_with_images(result, entity_type)
    
    # Format response body
    response = {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(enhanced_result)
    }
    
    return response
