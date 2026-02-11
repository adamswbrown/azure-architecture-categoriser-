"""
Type definitions for authentication credentials and responses.

This module provides strongly-typed structures for authentication credentials
across different cloud providers, improving type safety and IDE support.
"""

from datetime import datetime
from typing import TypedDict, Optional, Dict, Any


# ============================================================================
# Azure Managed Identity Credentials
# ============================================================================

class AzureCredentials(TypedDict):
    """Azure managed identity access token response."""
    access_token: str
    token_type: str  # Always "Bearer"
    expires_on: datetime
    resource: str


class AzureTokenResponse(TypedDict):
    """Raw IMDS token response from Azure."""
    access_token: str
    client_id: str
    expires_in: str
    expires_on: str
    ext_expires_in: str
    not_before: str
    resource: str
    token_type: str


# ============================================================================
# AWS Web Identity Federation Credentials
# ============================================================================

class AWSCredentials(TypedDict):
    """AWS temporary credentials from STS AssumeRoleWithWebIdentity."""
    AccessKeyId: str
    SecretAccessKey: str
    SessionToken: str
    Expiration: datetime


class AWSSTSResponse(TypedDict):
    """Complete AWS STS response including assumed role info."""
    Credentials: Dict[str, str]  # Contains AccessKeyId, SecretAccessKey, SessionToken, Expiration
    AssumedRoleUser: Dict[str, str]  # Contains Arn, AssumedRoleId
    SubjectFromWebIdentityToken: str
    PackedPolicySize: Optional[int]


# ============================================================================
# GCP Workload Identity Federation Credentials
# ============================================================================

class GCPCredentials(TypedDict):
    """GCP credentials from workload identity federation."""
    access_token: str
    token_type: str  # Always "Bearer"
    expires_in: int  # seconds
    issued_token_type: str
    expiry: datetime


class GCPTokenExchangeResponse(TypedDict):
    """GCP STS token exchange response."""
    access_token: str
    issued_token_type: str
    token_type: str
    expires_in: int


# ============================================================================
# Generic Credential Interface
# ============================================================================

class Credentials(TypedDict):
    """
    Generic credential structure.

    This is used for framework-agnostic credential passing.
    Different cloud providers will have different fields.
    """
    credentials: Dict[str, Any]
    expiration: Optional[datetime]
    credential_type: str  # 'azure', 'aws', 'gcp'


# ============================================================================
# IMDS Responses
# ============================================================================

class IMDSInstanceMetadata(TypedDict, total=False):
    """Azure IMDS instance metadata response."""
    compute: Dict[str, Any]
    network: Dict[str, Any]


class VMMetadata(TypedDict):
    """Parsed VM metadata from IMDS."""
    name: str
    location: str
    vmId: str
    resourceGroupName: str
    subscriptionId: str
    tags: Optional[Dict[str, str]]


# ============================================================================
# Identity Information
# ============================================================================

class IdentityInfo(TypedDict):
    """Managed identity information."""
    client_id: str
    principal_id: str
    resource_id: str
    identity_type: str  # 'system' or 'user'
    name: str


# ============================================================================
# Configuration Types
# ============================================================================

class EndpointInfo(TypedDict):
    """Endpoint configuration information."""
    tier: str
    model: str
    region: str
    endpoint_url: Optional[str]


class AuthConfig(TypedDict, total=False):
    """Authentication configuration for a cloud provider."""
    # AWS
    role_arn: Optional[str]
    region: Optional[str]

    # GCP
    project_id: Optional[str]
    pool_id: Optional[str]
    provider_id: Optional[str]
    service_account: Optional[str]
    location: Optional[str]

    # Azure
    scope: Optional[str]


# ============================================================================
# Health Check Types
# ============================================================================

class HealthStatus(TypedDict):
    """Health check status."""
    healthy: bool
    component: str
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]]
