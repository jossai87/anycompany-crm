"""
Request routing and parsing module for API Gateway events.
Handles route parsing, parameter extraction, and request routing to appropriate entity handlers.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, Tuple

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class RouteInfo:
    """
    Container for parsed route information from API Gateway event.
    """
    def __init__(
        self,
        resource_type: str,
        http_method: str,
        resource_id: Optional[str] = None,
        query_params: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None
    ):
        self.resource_type = resource_type
        self.http_method = http_method
        self.resource_id = resource_id
        self.query_params = query_params or {}
        self.body = body or {}
        self.path = path or ""
    
    def __repr__(self):
        return (f"RouteInfo(resource_type={self.resource_type}, "
                f"http_method={self.http_method}, "
                f"resource_id={self.resource_id}, "
                f"query_params={self.query_params})")


def parse_api_gateway_event(event: Dict[str, Any]) -> RouteInfo:
    """
    Parse API Gateway event to extract routing information.
    """
    try:
        http_method = event.get('httpMethod', '').upper()
        if not http_method:
            raise ValueError("HTTP method not found in event")

        path = event.get('path', '')
        if not path:
            raise ValueError("Path not found in event")
        
        logger.info(f"Parsing route: {http_method} {path}")
        
        resource_type, resource_id = _parse_path(path)
        query_params = _extract_query_parameters(event)
        body = _parse_request_body(event)
        
        route_info = RouteInfo(
            resource_type=resource_type,
            http_method=http_method,
            resource_id=resource_id,
            query_params=query_params,
            body=body,
            path=path
        )
        
        logger.info(f"Parsed route: {route_info}")
        return route_info
        
    except Exception as e:
        logger.error(f"Failed to parse API Gateway event: {str(e)}")
        raise ValueError(f"Failed to parse API Gateway event: {str(e)}")


def _parse_path(path: str) -> Tuple[str, Optional[str]]:
    """
    Parse the path to extract resource type and optional resource ID.
    """
    path = path.strip('/')
    parts = path.split('/')
    
    if len(parts) == 0 or not parts[0]:
        raise ValueError("Invalid path: empty or root path")
    
    resource_type = parts[0]
    
    valid_resources = ['accounts', 'opportunities', 'team-members', 'industries']
    if resource_type not in valid_resources:
        raise ValueError(f"Invalid resource type: {resource_type}. "
                        f"Must be one of: {', '.join(valid_resources)}")
    
    resource_id = None
    if len(parts) > 1:
        second_part = parts[1]
        if not second_part:
            raise ValueError("Invalid path: resource ID is empty")
        
        if second_part == 'search':
            resource_id = None
        else:
            resource_id = second_part
    
    if len(parts) > 2:
        raise ValueError(f"Invalid path: too many segments. Expected format: /{resource_type} or /{resource_type}/{{id}} or /{resource_type}/search")
    
    return resource_type, resource_id


def _extract_query_parameters(event: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract query string parameters from API Gateway event.
    """
    query_params = event.get('queryStringParameters') or {}
    
    if query_params is None:
        query_params = {}
    
    logger.info(f"Extracted query parameters: {query_params}")
    return query_params


def _parse_request_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate JSON request body from API Gateway event.
    """
    body_str = event.get('body')
    
    if not body_str:
        return {}
    
    is_base64 = event.get('isBase64Encoded', False)
    if is_base64:
        import base64
        body_str = base64.b64decode(body_str).decode('utf-8')
    
    try:
        body = json.loads(body_str)
        logger.info(f"Parsed request body with {len(body)} fields")
        return body
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON body: {str(e)}")
        raise ValueError(f"Invalid JSON in request body: {str(e)}")


def route_request(route_info: RouteInfo) -> str:
    """
    Determine which entity handler should process the request.
    """
    resource_type = route_info.resource_type
    
    handler_map = {
        'accounts': 'accounts',
        'opportunities': 'opportunities',
        'team-members': 'team-members',
        'industries': 'industries',
    }
    
    handler = handler_map.get(resource_type)
    if not handler:
        raise ValueError(f"No handler found for resource type: {resource_type}")
    
    logger.info(f"Routing to handler: {handler}")
    return handler


def validate_route(route_info: RouteInfo) -> None:
    """
    Validate that the route is valid for the given HTTP method and resource type.
    """
    method = route_info.http_method
    resource_type = route_info.resource_type
    resource_id = route_info.resource_id
    
    # Industries are read-only
    if resource_type == 'industries' and method not in ['GET', 'OPTIONS']:
        raise ValueError(f"Industries resource only supports GET operations, got {method}")
    
    # POST should not have resource ID (creating new resource)
    if method == 'POST' and resource_id is not None:
        raise ValueError(f"POST requests should not include resource ID in path")
    
    # PUT and DELETE must have resource ID
    if method in ['PUT', 'DELETE'] and resource_id is None:
        raise ValueError(f"{method} requests must include resource ID in path")
    
    logger.info(f"Route validation passed for {method} {resource_type}")


def get_operation_type(route_info: RouteInfo) -> str:
    """
    Determine the CRUD operation type based on HTTP method and resource ID.
    """
    method = route_info.http_method
    has_id = route_info.resource_id is not None
    
    operation_map = {
        ('GET', False): 'list',
        ('GET', True): 'get',
        ('POST', False): 'create',
        ('PUT', True): 'update',
        ('DELETE', True): 'delete',
    }
    
    operation = operation_map.get((method, has_id))
    if not operation:
        raise ValueError(f"Invalid combination: {method} with {'ID' if has_id else 'no ID'}")
    
    logger.info(f"Operation type: {operation}")
    return operation
