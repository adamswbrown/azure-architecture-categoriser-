"""Centralized configuration management for the catalog builder."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class DetectionConfig(BaseModel):
    """Detection heuristics configuration."""

    include_folders: list[str] = Field(default_factory=lambda: [
        'docs/example-scenario',
        'docs/web-apps',
        'docs/data',
        'docs/integration',
        'docs/ai-ml',
        'docs/databases',
        'docs/iot',
        'docs/microservices',
        'docs/mobile',
        'docs/networking',
        'docs/security',
        'docs/solution-ideas',
        'docs/reference-architectures',
        'docs/hybrid',
        'docs/aws-professional',
        'docs/gcp-professional',
        'docs/oracle-azure',
        'docs/sap',
        'docs/high-availability',
        'docs/serverless',
    ])

    exclude_folders: list[str] = Field(default_factory=lambda: [
        'docs/guide',
        'docs/best-practices',
        'docs/patterns',
        'docs/antipatterns',
        'docs/framework',
        'docs/icons',
        'docs/includes',
        'docs/resources',
        'docs/browse',
        '_themes',
        '_shared',
    ])

    exclude_files: list[str] = Field(default_factory=lambda: [
        'index.md',
        'toc.yml',
        'toc.md',
        'readme.md',
        'changelog.md',
    ])

    architecture_sections: list[str] = Field(default_factory=lambda: [
        'architecture',
        'components',
        'diagram',
        'solution architecture',
        'reference architecture',
        'architectural approach',
        'design',
        'workflow',
        'data flow',
        'dataflow',
    ])

    architecture_keywords: list[str] = Field(default_factory=lambda: [
        r'reference\s+architecture',
        r'baseline\s+architecture',
        r'solution\s+idea',
        r'architecture\s+pattern',
        r'architectural\s+design',
        r'this\s+architecture',
        r'the\s+architecture',
        r'architecture\s+diagram',
        r'components\s+of\s+this',
        r'azure\s+architecture',
    ])

    diagram_patterns: list[str] = Field(default_factory=lambda: [
        r'.*architecture.*\.(svg|png)$',
        r'.*diagram.*\.(svg|png)$',
        r'.*flow.*\.(svg|png)$',
        r'.*-arch\.(svg|png)$',
        r'.*\.svg$',
    ])

    # Scoring weights
    folder_score: float = 0.3
    diagram_score: float = 0.3
    section_score: float = 0.2
    keyword_score: float = 0.2
    frontmatter_score: float = 0.1

    # Thresholds
    min_confidence: float = 0.4
    min_signals: int = 2


class ClassificationConfig(BaseModel):
    """Classification keywords configuration."""

    domain_keywords: dict[str, list[str]] = Field(default_factory=lambda: {
        'web': [
            'web app', 'website', 'frontend', 'spa', 'single page',
            'web application', 'web service', 'web api', 'blazor',
            'asp.net', 'react', 'angular', 'vue', 'node.js',
        ],
        'data': [
            'data warehouse', 'data lake', 'analytics', 'big data',
            'etl', 'data pipeline', 'olap', 'reporting', 'bi ',
            'business intelligence', 'data platform', 'synapse',
            'databricks', 'data factory', 'hdinsight',
        ],
        'integration': [
            'integration', 'api gateway', 'message', 'queue', 'event',
            'service bus', 'event hub', 'event grid', 'logic app',
            'b2b', 'edi', 'middleware', 'esb', 'ipaa',
        ],
        'security': [
            'security', 'identity', 'authentication', 'authorization',
            'zero trust', 'firewall', 'waf', 'ddos', 'encryption',
            'key vault', 'secret', 'certificate', 'compliance',
        ],
        'ai': [
            'machine learning', 'ml ', 'ai ', 'artificial intelligence',
            'cognitive', 'nlp', 'computer vision', 'deep learning',
            'neural', 'openai', 'gpt', 'llm', 'chatbot', 'bot ',
        ],
        'infrastructure': [
            'infrastructure', 'network', 'hybrid', 'vpn', 'expressroute',
            'virtual network', 'vnet', 'dns', 'load balancer', 'firewall',
            'hub and spoke', 'landing zone', 'governance',
        ],
    })

    family_keywords: dict[str, list[str]] = Field(default_factory=lambda: {
        'foundation': [
            'landing zone', 'foundation', 'baseline', 'governance',
            'enterprise scale', 'caf ', 'cloud adoption',
        ],
        'iaas': [
            'virtual machine', 'vm ', 'iaas', 'lift and shift',
            'vm scale set', 'vmss', 'availability set',
        ],
        'paas': [
            'app service', 'paas', 'platform as a service',
            'azure sql', 'cosmos db', 'managed service',
        ],
        'cloud_native': [
            'kubernetes', 'aks', 'container', 'microservice',
            'cloud native', 'serverless', 'function', 'cloud-native',
        ],
        'data': [
            'data platform', 'data warehouse', 'data lake',
            'analytics', 'synapse', 'databricks', 'data mesh',
        ],
        'integration': [
            'integration', 'api management', 'logic app',
            'service bus', 'event-driven', 'messaging',
        ],
        'specialized': [
            'sap', 'oracle', 'mainframe', 'hpc', 'high performance',
            'gaming', 'media', 'iot', 'digital twin',
        ],
    })

    runtime_keywords: dict[str, list[str]] = Field(default_factory=lambda: {
        'microservices': [
            'microservice', 'micro-service', 'distributed service',
            'service mesh', 'sidecar', 'dapr',
        ],
        'event_driven': [
            'event-driven', 'event driven', 'event sourcing', 'cqrs',
            'pub/sub', 'publish subscribe', 'reactive',
        ],
        'api': [
            'rest api', 'graphql', 'api-first', 'api gateway',
            'web api', 'api management',
        ],
        'n_tier': [
            'n-tier', 'three-tier', '3-tier', 'multi-tier',
            'presentation layer', 'business layer', 'data layer',
        ],
        'batch': [
            'batch processing', 'batch job', 'scheduled job',
            'etl', 'data pipeline', 'nightly job',
        ],
        'monolith': [
            'monolith', 'single application', 'traditional app',
        ],
    })

    availability_keywords: dict[str, list[str]] = Field(default_factory=lambda: {
        'multi_region_active_active': [
            'active-active', 'multi-region active', 'global distribution',
            'geo-replication', 'global load balancing',
        ],
        'multi_region_active_passive': [
            'active-passive', 'disaster recovery', 'dr region',
            'failover region', 'backup region', 'geo-redundant',
        ],
        'zone_redundant': [
            'zone redundant', 'availability zone', 'zone-redundant',
            'across zones', 'zonal',
        ],
    })


class ServiceConfig(BaseModel):
    """Azure service extraction configuration."""

    # Patterns to find Azure services in text
    detection_patterns: list[str] = Field(default_factory=lambda: [
        r'Azure\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
        r'(App\s+Service|Functions?|Cosmos\s+DB|SQL\s+Database)',
        r'(Blob\s+Storage|Queue\s+Storage|Table\s+Storage)',
        r'(Event\s+Hub|Service\s+Bus|Event\s+Grid)',
        r'(Virtual\s+Machine|VM\s+Scale\s+Set)',
        r'(Kubernetes\s+Service|AKS|Container\s+Instances|Container\s+Apps)',
        r'(API\s+Management|Front\s+Door|Application\s+Gateway|Load\s+Balancer)',
        r'(Key\s+Vault|Active\s+Directory|Entra\s+ID)',
        r'(Monitor|Log\s+Analytics|Application\s+Insights)',
        r'(Data\s+Factory|Synapse|Databricks|Data\s+Lake)',
        r'(Cognitive\s+Services|OpenAI|Machine\s+Learning)',
        r'(Redis\s+Cache|Cache\s+for\s+Redis)',
        r'(SignalR|Notification\s+Hubs)',
        r'(Logic\s+Apps|Power\s+Automate)',
    ])

    # Normalize service names to canonical form
    normalizations: dict[str, str] = Field(default_factory=lambda: {
        'aks': 'Azure Kubernetes Service',
        'vm': 'Azure Virtual Machines',
        'vms': 'Azure Virtual Machines',
        'sql database': 'Azure SQL Database',
        'cosmos db': 'Azure Cosmos DB',
        'app service': 'Azure App Service',
        'functions': 'Azure Functions',
        'blob storage': 'Azure Blob Storage',
        'key vault': 'Azure Key Vault',
        'api management': 'Azure API Management',
        'front door': 'Azure Front Door',
        'application gateway': 'Azure Application Gateway',
        'load balancer': 'Azure Load Balancer',
        'event hub': 'Azure Event Hubs',
        'event hubs': 'Azure Event Hubs',
        'service bus': 'Azure Service Bus',
        'event grid': 'Azure Event Grid',
        'container apps': 'Azure Container Apps',
        'container instances': 'Azure Container Instances',
        'redis cache': 'Azure Cache for Redis',
        'cache for redis': 'Azure Cache for Redis',
        'active directory': 'Microsoft Entra ID',
        'entra id': 'Microsoft Entra ID',
        'monitor': 'Azure Monitor',
        'application insights': 'Application Insights',
        'log analytics': 'Azure Log Analytics',
        'data factory': 'Azure Data Factory',
        'synapse': 'Azure Synapse Analytics',
        'databricks': 'Azure Databricks',
        'machine learning': 'Azure Machine Learning',
        'openai': 'Azure OpenAI Service',
        'cognitive services': 'Azure Cognitive Services',
        'logic apps': 'Azure Logic Apps',
        'signalr': 'Azure SignalR Service',
    })


class UrlConfig(BaseModel):
    """URL generation configuration."""

    learn_base_url: str = "https://learn.microsoft.com/en-us/azure/architecture"


class CatalogConfig(BaseModel):
    """Complete catalog builder configuration."""

    detection: DetectionConfig = Field(default_factory=DetectionConfig)
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
    services: ServiceConfig = Field(default_factory=ServiceConfig)
    urls: UrlConfig = Field(default_factory=UrlConfig)


# Global config instance
_config: Optional[CatalogConfig] = None


def get_config() -> CatalogConfig:
    """Get the current configuration (loads default if not set)."""
    global _config
    if _config is None:
        _config = CatalogConfig()
    return _config


def load_config(config_path: Path) -> CatalogConfig:
    """Load configuration from a YAML file."""
    global _config

    with open(config_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    _config = CatalogConfig.model_validate(data)
    return _config


def reset_config() -> None:
    """Reset to default configuration."""
    global _config
    _config = None


def save_default_config(output_path: Path) -> None:
    """Save the default configuration to a YAML file."""
    config = CatalogConfig()

    # Convert to dict, handling nested models
    data = config.model_dump()

    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def find_config_file() -> Optional[Path]:
    """Find a config file in standard locations."""
    search_paths = [
        Path.cwd() / 'catalog-config.yaml',
        Path.cwd() / 'catalog-config.yml',
        Path.cwd() / '.catalog-config.yaml',
        Path.home() / '.config' / 'catalog-builder' / 'config.yaml',
    ]

    # Also check environment variable
    env_config = os.environ.get('CATALOG_CONFIG')
    if env_config:
        search_paths.insert(0, Path(env_config))

    for path in search_paths:
        if path.exists():
            return path

    return None
