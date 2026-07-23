"""
S3 integration module for enhancing CRM records with image URLs.
Handles mapping of database image references to S3 bucket URLs.
"""

import logging
import os
from typing import Dict, Any, List, Union

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get S3 bucket name from environment variable
CRM_IMAGES_BUCKET = os.environ.get('CRM_IMAGES_BUCKET', '')


def _get_s3_url(bucket_name: str, key: str) -> str:
    """
    Generate S3 URL for a given bucket and key.
    """
    return f"https://{bucket_name}.s3.amazonaws.com/{key}"


def _enhance_account_with_image(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance account record with S3 logo URL.
    """
    logo_url = record.get('logoUrl')
    
    if logo_url and CRM_IMAGES_BUCKET:
        s3_key = f"logos/{logo_url}"
        record['logoUrl'] = _get_s3_url(CRM_IMAGES_BUCKET, s3_key)
        logger.debug(f"Enhanced account logo URL: {record['logoUrl']}")
    else:
        record['logoUrl'] = None
    
    return record


def _enhance_team_member_with_image(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance team member record with S3 avatar URL.
    """
    avatar_url = record.get('avatarUrl')
    
    if avatar_url and CRM_IMAGES_BUCKET:
        s3_key = f"avatars/{avatar_url}"
        record['avatarUrl'] = _get_s3_url(CRM_IMAGES_BUCKET, s3_key)
        logger.debug(f"Enhanced team member avatar URL: {record['avatarUrl']}")
    else:
        record['avatarUrl'] = None
    
    return record


def _enhance_industry_with_image(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance industry record with S3 icon URL.
    """
    industry_id = record.get('id')
    
    if industry_id and CRM_IMAGES_BUCKET:
        icon_filename = f"{industry_id.lower()}.png"
        s3_key = f"icons/{icon_filename}"
        record['iconUrl'] = _get_s3_url(CRM_IMAGES_BUCKET, s3_key)
        logger.debug(f"Enhanced industry icon URL: {record['iconUrl']}")
    else:
        record['iconUrl'] = None
    
    return record


def enhance_with_images(
    records: Union[Dict[str, Any], List[Dict[str, Any]]], 
    entity_type: str
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Add S3 image URLs to CRM records based on entity type.
    
    This function enhances records with S3 URLs for images stored in the CRM images bucket.
    It handles different entity types and their corresponding image fields:
    - Accounts: logoUrl (maps to S3 logos folder)
    - Team Members: avatarUrl (maps to S3 avatars folder)
    - Industries: iconUrl (maps to S3 icons folder)
    
    Args:
        records: Single record dict or list of record dicts
        entity_type: Type of entity ('account', 'team_member', 'industry', 'opportunity')
    
    Returns:
        Enhanced record(s) with S3 URLs or null for missing images
    
    Raises:
        ValueError: If entity_type is not recognized
    """
    if not CRM_IMAGES_BUCKET:
        logger.warning("CRM_IMAGES_BUCKET environment variable not set, skipping image enhancement")
        return records
    
    # Normalize entity type to lowercase
    entity_type = entity_type.lower()
    
    # Determine if we're processing a single record or a list
    is_single_record = isinstance(records, dict)
    records_list = [records] if is_single_record else records
    
    # Enhance each record based on entity type
    enhanced_records = []
    for record in records_list:
        if entity_type == 'account':
            enhanced_record = _enhance_account_with_image(record)
        elif entity_type == 'team_member':
            enhanced_record = _enhance_team_member_with_image(record)
        elif entity_type == 'industry':
            enhanced_record = _enhance_industry_with_image(record)
        elif entity_type == 'opportunity':
            # Opportunities don't have image fields, return as-is
            enhanced_record = record
        else:
            logger.warning(f"Unknown entity type: {entity_type}, returning record unchanged")
            enhanced_record = record
        
        enhanced_records.append(enhanced_record)
    
    # Return single record or list based on input type
    return enhanced_records[0] if is_single_record else enhanced_records
