"""Generator for creating context files from Dr. Migrate data.

This module converts Dr. Migrate LLM-exposed data (from SQL Server and PostgreSQL views)
into the context file format expected by the Architecture Scoring Engine.

This enables architecture recommendations for ALL applications in Dr. Migrate,
not just those with Java/.NET components that have been scanned by App Cat/App Mod.
"""

import json
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .drmigrate_schema import (
    DrMigrateApplicationData,
    DrMigrateApplicationOverview,
    DrMigrateCloudServerCost,
    DrMigrateInstalledApplication,
    DrMigrateServerOverview,
)


# =============================================================================
# Technology Detection Patterns
# =============================================================================

# Patterns for detecting technology categories from software names
TECHNOLOGY_PATTERNS = {
    # Databases
    "databases": [
        (r"sql\s*server", "SQL Server"),
        (r"mysql", "MySQL"),
        (r"postgresql|postgres", "PostgreSQL"),
        (r"oracle\s*database|oracle\s*db", "Oracle Database"),
        (r"mongodb", "MongoDB"),
        (r"redis", "Redis"),
        (r"mariadb", "MariaDB"),
        (r"db2", "IBM DB2"),
        (r"sqlite", "SQLite"),
        (r"microsoft\s*access", "Microsoft Access"),
        (r"cassandra", "Apache Cassandra"),
        (r"couchdb", "CouchDB"),
        (r"elasticsearch", "Elasticsearch"),
    ],
    # Web servers
    "web_servers": [
        (r"iis|internet\s*information\s*services", "Microsoft IIS"),
        (r"apache\s*http|apache2|httpd", "Apache HTTP Server"),
        (r"nginx", "NGINX"),
        (r"tomcat", "Apache Tomcat"),
        (r"jetty", "Eclipse Jetty"),
        (r"lighttpd", "Lighttpd"),
        (r"caddy", "Caddy"),
    ],
    # Runtimes
    "runtimes": [
        (r"\.net\s*framework\s*(\d+\.?\d*)", ".NET Framework {0}"),
        (r"\.net\s*core\s*(\d+\.?\d*)", ".NET Core {0}"),
        (r"\.net\s*(\d+)", ".NET {0}"),
        (r"java\s*(\d+)", "Java {0}"),
        (r"jdk\s*(\d+)", "Java {0}"),
        (r"jre\s*(\d+)", "Java {0}"),
        (r"openjdk\s*(\d+)", "Java {0}"),
        (r"python\s*(\d+\.?\d*)", "Python {0}"),
        (r"node\.?js\s*(\d+\.?\d*)", "Node.js {0}"),
        (r"php\s*(\d+\.?\d*)", "PHP {0}"),
        (r"ruby\s*(\d+\.?\d*)", "Ruby {0}"),
        (r"go\s*(\d+\.?\d*)|golang", "Go {0}"),
        (r"rust\s*(\d+\.?\d*)", "Rust {0}"),
        (r"perl\s*(\d+\.?\d*)", "Perl {0}"),
    ],
    # Frameworks
    "frameworks": [
        (r"spring\s*boot", "Spring Boot"),
        (r"spring\s*framework", "Spring Framework"),
        (r"asp\.?net\s*mvc", "ASP.NET MVC"),
        (r"asp\.?net\s*core", "ASP.NET Core"),
        (r"asp\.?net", "ASP.NET"),
        (r"django", "Django"),
        (r"flask", "Flask"),
        (r"fastapi", "FastAPI"),
        (r"express", "Express.js"),
        (r"nextjs|next\.js", "Next.js"),
        (r"react", "React"),
        (r"angular", "Angular"),
        (r"vue\.?js|vuejs", "Vue.js"),
        (r"rails|ruby\s*on\s*rails", "Ruby on Rails"),
        (r"laravel", "Laravel"),
        (r"symfony", "Symfony"),
        (r"wordpress", "WordPress"),
        (r"drupal", "Drupal"),
        (r"magento", "Magento"),
    ],
    # Messaging
    "messaging": [
        (r"rabbitmq", "RabbitMQ"),
        (r"kafka", "Apache Kafka"),
        (r"activemq", "Apache ActiveMQ"),
        (r"msmq", "Microsoft MSMQ"),
        (r"ibm\s*mq|websphere\s*mq", "IBM MQ"),
        (r"zeromq", "ZeroMQ"),
        (r"nats", "NATS"),
    ],
    # Middleware
    "middleware": [
        (r"websphere", "IBM WebSphere"),
        (r"weblogic", "Oracle WebLogic"),
        (r"jboss|wildfly", "JBoss/WildFly"),
        (r"biztalk", "Microsoft BizTalk"),
        (r"mulesoft", "MuleSoft"),
        (r"tibco", "TIBCO"),
    ],
}

# Azure service mapping for common on-prem technologies
AZURE_SERVICE_MAPPINGS = {
    # Databases
    "SQL Server": "Azure SQL Database",
    "MySQL": "Azure Database for MySQL",
    "PostgreSQL": "Azure Database for PostgreSQL",
    "Oracle Database": "Oracle Database@Azure",
    "MongoDB": "Azure Cosmos DB",
    "Redis": "Azure Cache for Redis",
    "MariaDB": "Azure Database for MariaDB",
    "Apache Cassandra": "Azure Cosmos DB for Apache Cassandra",
    "CouchDB": "Azure Cosmos DB",
    "Elasticsearch": "Azure Cognitive Search",
    # Web servers
    "Microsoft IIS": "Azure App Service",
    "Apache HTTP Server": "Azure App Service",
    "NGINX": "Azure App Service",
    "Apache Tomcat": "Azure App Service",
    "Eclipse Jetty": "Azure App Service",
    "Lighttpd": "Azure App Service",
    "Caddy": "Azure Container Apps",
    # Runtimes
    ".NET Framework": "Azure Virtual Machines",
    ".NET Core": "Azure App Service",
    ".NET": "Azure App Service",
    "Java": "Azure App Service",
    "Python": "Azure App Service",
    "Node.js": "Azure App Service",
    "PHP": "Azure App Service",
    "Ruby": "Azure App Service",
    "Go": "Azure Container Apps",
    "Rust": "Azure Container Apps",
    "Perl": "Azure Virtual Machines",
    # Frameworks
    "Spring Boot": "Azure App Service",
    "Django": "Azure App Service",
    "Flask": "Azure App Service",
    "FastAPI": "Azure Container Apps",
    "Express.js": "Azure App Service",
    "Next.js": "Azure Static Web Apps",
    "Ruby on Rails": "Azure App Service",
    "Laravel": "Azure App Service",
    "Symfony": "Azure App Service",
    "WordPress": "Azure App Service",
    "Drupal": "Azure App Service",
    "Magento": "Azure Kubernetes Service",
    # Messaging
    "RabbitMQ": "Azure Service Bus",
    "Apache Kafka": "Azure Event Hubs",
    "Apache ActiveMQ": "Azure Service Bus",
    "Microsoft MSMQ": "Azure Service Bus",
    "IBM MQ": "Azure Service Bus",
    "ZeroMQ": "Azure Service Bus",
    "NATS": "Azure Service Bus",
    # Middleware
    "IBM WebSphere": "Azure Kubernetes Service",
    "Oracle WebLogic": "Azure Kubernetes Service",
    "JBoss/WildFly": "Azure App Service",
    "MuleSoft": "Azure API Management",
    "TIBCO": "Azure Logic Apps",
}

# =============================================================================
# Inferred Platform Compatibility Mappings
# =============================================================================
# These mappings define Azure modernization pathways for each technology.
# They represent the recommended Azure targets for different migration strategies.
#
# Structure for each technology:
#   - rehost: Azure target for lift-and-shift (minimal changes)
#   - replatform: Azure PaaS target (some configuration changes)
#   - refactor: Cloud-native target (containerization/serverless)
#   - azure_equivalent: Direct Azure managed service equivalent
#   - modernization_path: Recommended journey from rehost to cloud-native
#
# NOTE: These are INFERRED pathways based on technology type, NOT code analysis.

DEFAULT_COMPATIBILITY_MAPPINGS = {
    # ==========================================================================
    # Java Ecosystem
    # ==========================================================================
    "Java": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Kubernetes Service",
        "azure_equivalent": "Azure App Service (Java)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps", "Azure Kubernetes Service"],
        "notes": "Java apps can run on App Service with Tomcat/Java SE. Spring Boot apps should consider Azure Spring Apps.",
    },
    "Spring Boot": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Spring Apps",
        "refactor": "Azure Kubernetes Service",
        "azure_equivalent": "Azure Spring Apps",
        "modernization_path": ["Azure Virtual Machines", "Azure Spring Apps", "Azure Container Apps", "Azure Kubernetes Service"],
        "notes": "Azure Spring Apps is the native Azure service for Spring Boot applications.",
    },
    "Apache Tomcat": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (Tomcat)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "App Service supports Tomcat natively. Consider containerizing for more control.",
    },
    "JBoss/WildFly": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Red Hat OpenShift",
        "refactor": "Azure Kubernetes Service",
        "azure_equivalent": "Azure Red Hat OpenShift",
        "modernization_path": ["Azure Virtual Machines", "Azure Red Hat OpenShift", "Azure Kubernetes Service"],
        "notes": "JBoss EAP available on Azure Red Hat OpenShift. Complex apps may need AKS.",
    },
    # ==========================================================================
    # .NET Ecosystem
    # ==========================================================================
    ".NET Core": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps", "Azure Functions"],
        "notes": ".NET Core/5+ is fully supported across all Azure compute. Consider Functions for event-driven workloads.",
    },
    ".NET Framework": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service (Windows)",
        "refactor": "Migrate to .NET 6+ then Azure Container Apps",
        "azure_equivalent": "Azure Virtual Machines",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service (Windows)"],
        "notes": ".NET Framework requires Windows. Full modernization requires migration to .NET 6+.",
        "blockers": ["Linux containers not supported", "Requires Windows App Service plan"],
    },
    ".NET": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Modern .NET (5+) supports cross-platform deployment.",
    },
    "ASP.NET Core": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps", "Azure Kubernetes Service"],
        "notes": "ASP.NET Core is fully cloud-native ready. Consider Azure Front Door for global distribution.",
    },
    "ASP.NET": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service (Windows)",
        "refactor": "Migrate to ASP.NET Core then containerize",
        "azure_equivalent": "Azure App Service (Windows)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service (Windows)"],
        "notes": "Classic ASP.NET requires Windows and IIS. Consider migrating to ASP.NET Core for full modernization.",
        "blockers": ["Requires Windows", "IIS dependencies"],
    },
    # ==========================================================================
    # Python Ecosystem
    # ==========================================================================
    "Python": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Functions",
        "azure_equivalent": "Azure App Service (Python)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps", "Azure Functions"],
        "notes": "Python supported on App Service (Linux). Consider Functions for lightweight APIs.",
    },
    "Django": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (Python)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Django runs well on App Service Linux. Use Azure Database for PostgreSQL for data layer.",
    },
    "Flask": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Functions",
        "azure_equivalent": "Azure App Service (Python)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Functions"],
        "notes": "Flask apps can often be converted to Azure Functions for serverless operation.",
    },
    "FastAPI": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Container Apps",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure Container Apps",
        "modernization_path": ["Azure Virtual Machines", "Azure Container Apps"],
        "notes": "FastAPI is async-native and works excellently in containers. Container Apps recommended.",
    },
    # ==========================================================================
    # Node.js Ecosystem
    # ==========================================================================
    "Node.js": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Functions",
        "azure_equivalent": "Azure App Service (Node)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Functions", "Azure Container Apps"],
        "notes": "Node.js has first-class support on App Service and Functions.",
    },
    "Express.js": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (Node)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Express apps run directly on App Service. Consider Container Apps for microservices.",
    },
    "Next.js": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Static Web Apps",
        "refactor": "Azure Static Web Apps",
        "azure_equivalent": "Azure Static Web Apps",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Static Web Apps"],
        "notes": "Azure Static Web Apps has native Next.js support with hybrid rendering.",
    },
    # ==========================================================================
    # PHP Ecosystem
    # ==========================================================================
    "PHP": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (PHP)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "PHP supported on App Service Linux. Use Azure Database for MySQL/PostgreSQL.",
    },
    "Laravel": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (PHP)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Laravel runs on App Service with Composer. Queue workers may need Container Apps.",
    },
    "Symfony": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (PHP)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Symfony supported on App Service. Consider containerization for complex deployments.",
    },
    "WordPress": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure App Service with Azure CDN",
        "azure_equivalent": "Azure App Service (WordPress)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service"],
        "notes": "Azure has WordPress-specific App Service plans. Consider headless WordPress with Static Web Apps.",
    },
    "Drupal": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (PHP)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Drupal runs on App Service. Complex multisite setups may benefit from containers.",
    },
    "Magento": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Kubernetes Service",
        "refactor": "Azure Kubernetes Service",
        "azure_equivalent": "Azure Kubernetes Service",
        "modernization_path": ["Azure Virtual Machines", "Azure Kubernetes Service"],
        "notes": "Magento 2 is resource-intensive. AKS recommended for production workloads.",
        "blockers": ["High resource requirements", "Complex caching needs"],
    },
    # ==========================================================================
    # Ruby Ecosystem
    # ==========================================================================
    "Ruby": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (Ruby)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Ruby supported on App Service Linux.",
    },
    "Ruby on Rails": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure App Service (Ruby)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service", "Azure Container Apps"],
        "notes": "Rails apps run on App Service. Background jobs may need separate workers on Container Apps.",
    },
    # ==========================================================================
    # Go & Rust (Cloud-Native)
    # ==========================================================================
    "Go": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Container Apps",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure Container Apps",
        "modernization_path": ["Azure Virtual Machines", "Azure Container Apps", "Azure Kubernetes Service"],
        "notes": "Go compiles to single binary - ideal for containers. Container Apps or AKS recommended.",
    },
    "Rust": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Container Apps",
        "refactor": "Azure Container Apps",
        "azure_equivalent": "Azure Container Apps",
        "modernization_path": ["Azure Virtual Machines", "Azure Container Apps", "Azure Kubernetes Service"],
        "notes": "Rust compiles to native binary. Excellent for containers and serverless.",
    },
    # ==========================================================================
    # Web Servers
    # ==========================================================================
    "NGINX": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Application Gateway",
        "refactor": "Azure Front Door",
        "azure_equivalent": "Azure Application Gateway / Azure Front Door",
        "modernization_path": ["Azure Virtual Machines", "Azure Application Gateway", "Azure Front Door"],
        "notes": "NGINX as reverse proxy replaced by Application Gateway/Front Door. As web server, consider App Service.",
    },
    "Apache HTTP Server": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service",
        "refactor": "Azure Front Door + App Service",
        "azure_equivalent": "Azure App Service",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service"],
        "notes": "Apache functionality replaced by App Service. Reverse proxy needs replaced by Azure Front Door.",
    },
    "Microsoft IIS": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure App Service (Windows)",
        "refactor": "Azure App Service",
        "azure_equivalent": "Azure App Service (Windows)",
        "modernization_path": ["Azure Virtual Machines", "Azure App Service (Windows)"],
        "notes": "IIS apps migrate directly to Windows App Service. Consider ASP.NET Core migration for Linux.",
    },
    # ==========================================================================
    # Middleware
    # ==========================================================================
    "IBM WebSphere": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Red Hat OpenShift",
        "refactor": "Azure Kubernetes Service",
        "azure_equivalent": "Azure Red Hat OpenShift",
        "modernization_path": ["Azure Virtual Machines", "Azure Red Hat OpenShift", "Azure Kubernetes Service"],
        "notes": "WebSphere Liberty available on OpenShift. Traditional WAS requires VMs or containerization.",
        "blockers": ["Proprietary APIs", "Complex clustering"],
    },
    "Oracle WebLogic": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Oracle WebLogic on AKS",
        "refactor": "Azure Kubernetes Service",
        "azure_equivalent": "Oracle WebLogic Server on Azure Kubernetes Service",
        "modernization_path": ["Azure Virtual Machines", "WebLogic on AKS", "Azure Kubernetes Service"],
        "notes": "Oracle and Microsoft offer WebLogic on AKS. Consider migrating to lighter frameworks.",
        "blockers": ["Oracle licensing", "Proprietary features"],
    },
    "Microsoft BizTalk": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Logic Apps",
        "refactor": "Azure Logic Apps + Azure Functions",
        "azure_equivalent": "Azure Logic Apps",
        "modernization_path": ["Azure Virtual Machines", "Azure Logic Apps"],
        "notes": "Azure Logic Apps is the cloud-native replacement for BizTalk integration scenarios.",
    },
    "MuleSoft": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure API Management",
        "refactor": "Azure API Management + Azure Functions",
        "azure_equivalent": "Azure API Management",
        "modernization_path": ["Azure Virtual Machines", "Azure API Management"],
        "notes": "MuleSoft can run on VMs. Consider Azure API Management for API gateway scenarios.",
    },
    # ==========================================================================
    # Databases (for reference in modernization paths)
    # ==========================================================================
    "SQL Server": {
        "rehost": "SQL Server on Azure Virtual Machines",
        "replatform": "Azure SQL Managed Instance",
        "refactor": "Azure SQL Database",
        "azure_equivalent": "Azure SQL Database",
        "modernization_path": ["SQL Server on Azure VMs", "Azure SQL Managed Instance", "Azure SQL Database"],
        "notes": "Managed Instance for near-100% compatibility. Azure SQL Database for full PaaS.",
    },
    "MySQL": {
        "rehost": "MySQL on Azure Virtual Machines",
        "replatform": "Azure Database for MySQL Flexible Server",
        "refactor": "Azure Database for MySQL Flexible Server",
        "azure_equivalent": "Azure Database for MySQL",
        "modernization_path": ["MySQL on Azure VMs", "Azure Database for MySQL"],
        "notes": "Flexible Server is the recommended deployment option.",
    },
    "PostgreSQL": {
        "rehost": "PostgreSQL on Azure Virtual Machines",
        "replatform": "Azure Database for PostgreSQL Flexible Server",
        "refactor": "Azure Database for PostgreSQL Flexible Server",
        "azure_equivalent": "Azure Database for PostgreSQL",
        "modernization_path": ["PostgreSQL on Azure VMs", "Azure Database for PostgreSQL"],
        "notes": "Flexible Server recommended. Consider Cosmos DB for PostgreSQL for hyperscale.",
    },
    "MongoDB": {
        "rehost": "MongoDB on Azure Virtual Machines",
        "replatform": "Azure Cosmos DB for MongoDB",
        "refactor": "Azure Cosmos DB for MongoDB",
        "azure_equivalent": "Azure Cosmos DB for MongoDB",
        "modernization_path": ["MongoDB on Azure VMs", "Azure Cosmos DB for MongoDB"],
        "notes": "Cosmos DB MongoDB API provides compatibility with global distribution.",
    },
    "Oracle Database": {
        "rehost": "Oracle on Azure Virtual Machines",
        "replatform": "Oracle Database@Azure",
        "refactor": "Oracle Database@Azure or migrate to Azure SQL/PostgreSQL",
        "azure_equivalent": "Oracle Database@Azure",
        "modernization_path": ["Oracle on Azure VMs", "Oracle Database@Azure"],
        "notes": "Oracle Database@Azure is Oracle-managed. Consider migration to Azure SQL for cost savings.",
        "blockers": ["Oracle licensing complexity", "PL/SQL migration effort"],
    },
    "Redis": {
        "rehost": "Redis on Azure Virtual Machines",
        "replatform": "Azure Cache for Redis",
        "refactor": "Azure Cache for Redis",
        "azure_equivalent": "Azure Cache for Redis",
        "modernization_path": ["Redis on Azure VMs", "Azure Cache for Redis"],
        "notes": "Azure Cache for Redis is fully managed with Enterprise tier for Redis Enterprise features.",
    },
    # ==========================================================================
    # Messaging
    # ==========================================================================
    "RabbitMQ": {
        "rehost": "RabbitMQ on Azure Virtual Machines",
        "replatform": "Azure Service Bus",
        "refactor": "Azure Service Bus",
        "azure_equivalent": "Azure Service Bus",
        "modernization_path": ["RabbitMQ on Azure VMs", "Azure Service Bus"],
        "notes": "Service Bus provides similar patterns. AMQP protocol supported for easier migration.",
    },
    "Apache Kafka": {
        "rehost": "Kafka on Azure Virtual Machines",
        "replatform": "Azure Event Hubs (Kafka API)",
        "refactor": "Azure Event Hubs",
        "azure_equivalent": "Azure Event Hubs for Apache Kafka",
        "modernization_path": ["Kafka on Azure VMs", "Azure Event Hubs"],
        "notes": "Event Hubs provides Kafka-compatible endpoint. No Kafka cluster management needed.",
    },
    # ==========================================================================
    # Default fallback
    # ==========================================================================
    "_default": {
        "rehost": "Azure Virtual Machines",
        "replatform": "Azure Virtual Machines",
        "refactor": "Assess for containerization",
        "azure_equivalent": "Azure Virtual Machines",
        "modernization_path": ["Azure Virtual Machines"],
        "notes": "Unknown technology - recommend assessment for modernization options.",
    },
}


# =============================================================================
# Generator Class
# =============================================================================


class DrMigrateContextGenerator:
    """Generates context files from Dr. Migrate data sources.

    This class transforms Dr. Migrate data into the format expected by the
    Architecture Scoring Engine, enabling architecture recommendations for
    applications that don't have App Cat/App Mod scan results.

    IMPORTANT: Compatibility assessments generated by this class are INFERRED
    from technology detection patterns, NOT from actual code analysis like
    App Cat provides. Results should be treated as estimates and may require
    manual validation for production migration decisions.
    """

    def __init__(
        self,
        include_cost_data: bool = False,
        include_network_data: bool = False,
        azure_service_mappings: Optional[dict[str, str]] = None,
        compatibility_mappings: Optional[dict[str, dict[str, str]]] = None,
    ):
        """Initialize the generator.

        Args:
            include_cost_data: Include cost information in extended fields
            include_network_data: Include network dependency information
            azure_service_mappings: Custom Azure service mappings (overrides defaults)
            compatibility_mappings: Custom platform compatibility mappings (overrides defaults).
                Format: {"Technology": {"azure_service": "CompatibilityLevel"}}
                Compatibility levels: FullySupported, Supported, SupportedWithChanges, NotSupported
        """
        self.include_cost_data = include_cost_data
        self.include_network_data = include_network_data
        self.azure_service_mappings = azure_service_mappings or AZURE_SERVICE_MAPPINGS
        self.compatibility_mappings = compatibility_mappings or DEFAULT_COMPATIBILITY_MAPPINGS

    def generate_context(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate a context file from Dr. Migrate application data.

        Args:
            app_data: Complete Dr. Migrate data for an application

        Returns:
            Context file structure as a list with one dictionary (matching expected format)
        """
        context = {
            "app_overview": self._generate_app_overview(app_data),
            "detected_technology_running": self._detect_technologies(app_data),
            "app_approved_azure_services": self._generate_azure_services(app_data),
            "server_details": self._generate_server_details(app_data),
            "App Mod results": self._generate_app_mod_results(app_data),
        }

        # Add extended data if requested
        if self.include_cost_data and app_data.cost_comparison:
            context["_cost_comparison"] = {
                "current_total_cost_annual": app_data.cost_comparison.current_total_cost_annual,
                "cloud_total_cost_annual": app_data.cost_comparison.cloud_total_cost_annual,
                "currency": app_data.cost_comparison.Currency,
            }

        if self.include_network_data and app_data.network_dependencies:
            context["_network_dependencies"] = [
                {
                    "source": dep.source_application,
                    "destination": dep.destination_application,
                    "port": dep.port,
                }
                for dep in app_data.network_dependencies
            ]

        # Add metadata about generation
        context["_generated_from"] = "dr_migrate"
        context["_generated_at"] = datetime.utcnow().isoformat()

        return [context]

    def _generate_app_overview(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate app_overview section from Application_Overview data."""
        overview = app_data.application_overview

        return [{
            "application": overview.application,
            "app_type": self._determine_app_type(overview),
            "business_crtiticality": self._determine_criticality(overview),
            "treatment": self._map_migration_strategy(overview.assigned_migration_strategy),
            "description": self._generate_description(overview),
            "owner": overview.app_owner,
        }]

    def _determine_app_type(self, overview: DrMigrateApplicationOverview) -> str:
        """Determine application type from Dr. Migrate data."""
        if overview.app_type:
            return overview.app_type

        if overview.app_function:
            if "tool" in overview.app_function.lower():
                return "IT Tool"
            elif "business" in overview.app_function.lower():
                return "Business Application"

        return "Application"

    def _determine_criticality(self, overview: DrMigrateApplicationOverview) -> str:
        """Determine business criticality from available indicators."""
        # Check explicit business_critical field first
        if overview.business_critical:
            bc_lower = overview.business_critical.lower()
            if bc_lower in ("yes", "true", "high", "critical"):
                return "High"
            elif bc_lower in ("no", "false", "low"):
                return "Low"

        # Check inherent_risk as secondary indicator
        if overview.inherent_risk:
            risk_lower = overview.inherent_risk.lower()
            if "high" in risk_lower or "critical" in risk_lower:
                return "High"
            elif "medium" in risk_lower:
                return "Medium"
            elif "low" in risk_lower:
                return "Low"

        # Check materiality
        if overview.materiality:
            mat_lower = overview.materiality.lower()
            if mat_lower in ("yes", "true", "material"):
                return "High"

        # Check high_availability and disaster_recovery as indicators
        if overview.high_availability and overview.high_availability.lower() in ("yes", "true"):
            return "High"
        if overview.disaster_recovery and overview.disaster_recovery.lower() in ("yes", "true"):
            return "High"

        return "Medium"  # Default

    def _map_migration_strategy(self, strategy: Optional[str]) -> Optional[str]:
        """Map Dr. Migrate strategy to context file treatment."""
        if not strategy:
            return None

        strategy_lower = strategy.lower()
        mapping = {
            "rehost": "Rehost",
            "lift and shift": "Rehost",
            "replatform": "Replatform",
            "refactor": "Refactor",
            "rearchitect": "Refactor",
            "rebuild": "Rebuild",
            "replace": "Replace",
            "repurchase": "Replace",
            "retire": "Retire",
            "retain": "Retain",
            "tolerate": "Tolerate",
        }

        for key, value in mapping.items():
            if key in strategy_lower:
                return value

        return strategy  # Return original if no mapping found

    def _generate_description(self, overview: DrMigrateApplicationOverview) -> str:
        """Generate a description from available metadata."""
        parts = []

        if overview.app_function:
            parts.append(overview.app_function)

        if overview.complexity_rating:
            parts.append(f"Complexity: {overview.complexity_rating}")

        if overview.number_of_machines:
            parts.append(f"{overview.number_of_machines} servers")

        if overview.number_of_environments:
            parts.append(f"{overview.number_of_environments} environments")

        return ". ".join(parts) if parts else ""

    def _detect_technologies(self, app_data: DrMigrateApplicationData) -> list[str]:
        """Detect and normalize technologies from all available sources."""
        technologies = set()

        # From Application_Overview tech stack
        if app_data.application_overview.other_tech_stack_components:
            techs = app_data.application_overview.other_tech_stack_components.split(",")
            for tech in techs:
                normalized = self._normalize_technology(tech.strip())
                if normalized:
                    technologies.add(normalized)

        # From Application_Overview detected components
        if app_data.application_overview.detected_app_components:
            components = app_data.application_overview.detected_app_components.split(",")
            for comp in components:
                normalized = self._normalize_technology(comp.strip())
                if normalized:
                    technologies.add(normalized)

        # From unique operating systems
        if app_data.application_overview.unique_operating_systems:
            oses = app_data.application_overview.unique_operating_systems.split(",")
            for os in oses:
                technologies.add(os.strip())

        # From installed applications
        for app in app_data.installed_applications:
            if app.key_software:
                normalized = self._normalize_technology(app.key_software)
                if normalized:
                    technologies.add(normalized)
            if app.specific_software_detected:
                normalized = self._normalize_technology(app.specific_software_detected)
                if normalized:
                    technologies.add(normalized)

        # From key software
        for sw in app_data.key_software:
            if sw.key_software:
                normalized = self._normalize_technology(sw.key_software)
                if normalized:
                    technologies.add(normalized)

        # From app mod candidates (modernization technologies)
        for candidate in app_data.app_mod_candidates:
            if candidate.app_mod_candidate_technology:
                technologies.add(candidate.app_mod_candidate_technology)

        # From server details (OS)
        for server in app_data.server_overviews:
            if server.OperatingSystem:
                technologies.add(server.OperatingSystem)

        return sorted(list(technologies))

    def _normalize_technology(self, tech: str) -> Optional[str]:
        """Normalize a technology name using pattern matching."""
        if not tech:
            return None

        tech_lower = tech.lower()

        # Check all pattern categories
        for category, patterns in TECHNOLOGY_PATTERNS.items():
            for pattern, name_template in patterns:
                match = re.search(pattern, tech_lower, re.IGNORECASE)
                if match:
                    if "{0}" in name_template and match.groups():
                        return name_template.format(match.group(1))
                    return name_template

        # Return original if no pattern matched (might be a valid tech name)
        return tech if len(tech) > 1 else None

    def _generate_azure_services(self, app_data: DrMigrateApplicationData) -> list[dict[str, str]]:
        """Generate Azure service mappings for detected technologies."""
        mappings = {}

        # Get all detected technologies
        technologies = self._detect_technologies(app_data)

        for tech in technologies:
            # Check direct mapping
            if tech in self.azure_service_mappings:
                mappings[tech] = self.azure_service_mappings[tech]
                continue

            # Check pattern-based mapping
            tech_lower = tech.lower()
            for source, target in self.azure_service_mappings.items():
                if source.lower() in tech_lower:
                    mappings[tech] = target
                    break

        # Also check cloud server costs for assigned targets
        for cost in app_data.cloud_server_costs:
            if cost.assigned_target:
                # Try to map the treatment to a technology
                if cost.assigned_treatment:
                    mappings[cost.assigned_treatment] = cost.assigned_target

        return [mappings] if mappings else [{}]

    def _generate_server_details(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate server_details section from Server_Overview_Current data."""
        servers = []

        # Create lookup maps for additional data
        cloud_costs_by_machine = {
            cost.machine: cost for cost in app_data.cloud_server_costs
        }
        installed_apps_by_machine: dict[str, list[str]] = {}
        for app in app_data.installed_applications:
            if app.machine not in installed_apps_by_machine:
                installed_apps_by_machine[app.machine] = []
            if app.key_software:
                installed_apps_by_machine[app.machine].append(app.key_software)

        for server in app_data.server_overviews:
            server_detail = {
                "machine": server.machine,
                "environment": server.environment or "Production",
                "OperatingSystem": server.OperatingSystem,
                "ip_address": self._parse_ip_addresses(server.ip_address),
                "StorageGB": server.StorageGB,
                "MemoryGB": server.AllocatedMemoryInGB,
                "Cores": server.Cores,
                "CPUUsage": server.CPUUsageInPct,
                "MemoryUsage": server.MemoryUsageInPct,
                "DiskReadOpsPersec": server.DiskReadOpsPerSec,
                "DiskWriteOpsPerSec": server.DiskWriteOpsPerSec,
                "NetworkInMBPS": self._parse_network_value(server.NetworkInMBPS),
                "NetworkOutMBPS": self._parse_network_value(server.NetworkOutMBPS),
                "StandardSSDDisks": 0,  # Not available in Dr. Migrate
                "StandardHDDDisks": 0,
                "PremiumDisks": 0,
                "AzureVMReadiness": self._map_vm_readiness(server.CloudVMReadiness),
                "AzureReadinessIssues": self._get_readiness_issues(server),
                "migration_strategy": self._map_migration_strategy(
                    app_data.application_overview.assigned_migration_strategy
                ),
                "detected_COTS": installed_apps_by_machine.get(server.machine, []),
            }

            # Add treatment option from cloud costs if available
            cloud_cost = cloud_costs_by_machine.get(server.machine)
            if cloud_cost:
                server_detail["treatment_option"] = cloud_cost.assigned_target
                server_detail["assigned_treatment"] = cloud_cost.assigned_treatment

            servers.append(server_detail)

        return servers

    def _parse_ip_addresses(self, ip_string: Optional[str]) -> list[str]:
        """Parse IP addresses from a string."""
        if not ip_string:
            return []

        # Handle comma-separated or space-separated IPs
        ips = re.split(r"[,;\s]+", ip_string)
        return [ip.strip() for ip in ips if ip.strip()]

    def _parse_network_value(self, value: Optional[str]) -> Optional[float]:
        """Parse network value to float."""
        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            # Try to extract numeric part
            match = re.search(r"[\d.]+", str(value))
            if match:
                return float(match.group())
            return None

    def _map_vm_readiness(self, readiness: Optional[str]) -> str:
        """Map Dr. Migrate CloudVMReadiness to context file format."""
        if not readiness:
            return "Unknown"

        readiness_lower = readiness.lower()
        if "ready" in readiness_lower and "not" not in readiness_lower:
            if "condition" in readiness_lower:
                return "ReadyWithConditions"
            return "Ready"
        elif "not" in readiness_lower or "no" in readiness_lower:
            return "NotReady"

        return "Unknown"

    def _get_readiness_issues(self, server: DrMigrateServerOverview) -> Optional[str]:
        """Determine readiness issues from server data."""
        issues = []

        # Check OS support status
        if server.os_support_status:
            if "unsupported" in server.os_support_status.lower():
                issues.append("Unsupported OS")
            elif "end" in server.os_support_status.lower():
                issues.append("End of support OS")

        # Check power status
        if server.PowerStatus and server.PowerStatus.lower() == "off":
            issues.append("Server powered off")

        return "; ".join(issues) if issues else None

    def _generate_app_mod_results(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate App Mod results section.

        For applications without Java/.NET App Cat scans, this generates
        a minimal/inferred result based on available data.
        """
        # Check if we have app mod candidates
        app_mod_techs = set()
        for candidate in app_data.app_mod_candidates:
            if candidate.app_mod_candidate_technology:
                app_mod_techs.add(candidate.app_mod_candidate_technology)

        # Check for modernization options in application overview
        mod_options = app_data.application_overview.app_component_modernization_options

        # If no modernization data available, return minimal structure
        if not app_mod_techs and not mod_options:
            return self._generate_inferred_app_mod_results(app_data)

        results = []
        for tech in app_mod_techs:
            # Get Azure modernization pathways for this technology
            pathways = self._infer_compatibility(tech)

            # Build backwards-compatible compatibility dict (string values only)
            compatibility = {
                "rehost_target": pathways.get("rehost", "Azure Virtual Machines"),
                "replatform_target": pathways.get("replatform", "Azure Virtual Machines"),
                "refactor_target": pathways.get("refactor", "Assess for containerization"),
                "azure_equivalent": pathways.get("azure_equivalent", "Azure Virtual Machines"),
            }

            result = {
                "technology": tech,
                "summary": {
                    "modernization_feasible": True,
                    "inferred_from_dr_migrate": True,
                },
                "findings": [],
                # Backwards-compatible format (dict[str, str])
                "compatibility": compatibility,
                # Extended pathway information (new format)
                "azure_modernization_pathways": {
                    "rehost": pathways.get("rehost", "Azure Virtual Machines"),
                    "replatform": pathways.get("replatform", "Azure Virtual Machines"),
                    "refactor": pathways.get("refactor", "Assess for containerization"),
                    "azure_equivalent": pathways.get("azure_equivalent", "Azure Virtual Machines"),
                    "modernization_path": pathways.get("modernization_path", ["Azure Virtual Machines"]),
                },
                "recommended_targets": self._get_recommended_targets(tech),
                "blockers": pathways.get("blockers", []),
            }
            results.append(result)

        return results if results else self._generate_inferred_app_mod_results(app_data)

    def _generate_inferred_app_mod_results(
        self, app_data: DrMigrateApplicationData
    ) -> list[dict[str, Any]]:
        """Generate inferred App Mod results when no explicit data available.

        WARNING: These results are INFERRED from technology detection patterns,
        NOT from actual code analysis. They should be treated as estimates only.
        """
        # Detect primary technology from available data
        technologies = self._detect_technologies(app_data)
        primary_tech = self._detect_primary_technology(technologies)

        if not primary_tech:
            # Return empty if we can't determine technology
            return []

        # Get Azure modernization pathways for this technology
        pathways = self._infer_compatibility(primary_tech)

        # Determine if modernization is feasible based on treatment
        strategy = app_data.application_overview.assigned_migration_strategy
        mod_feasible = strategy and strategy.lower() in (
            "refactor", "rearchitect", "replatform", "rebuild"
        )

        # Build findings with pathway-specific guidance
        findings = [
            {
                "type": "InferredFromDrMigrate",
                "severity": "Warning",
                "description": (
                    "Azure modernization pathways are INFERRED from detected technology patterns. "
                    "Unlike App Cat scans which analyze actual code, these recommendations are "
                    "based on general technology characteristics. Manual validation is "
                    "recommended before making migration decisions."
                ),
            },
            {
                "type": "NoCodeAnalysis",
                "severity": "Info",
                "description": (
                    f"No App Cat scan available. Azure pathways for '{primary_tech}' are based on "
                    "predefined mappings that may not account for custom code, dependencies, "
                    "or configuration-specific issues."
                ),
            },
        ]

        # Add pathway-specific notes if available
        if pathways.get("notes"):
            findings.append({
                "type": "ModernizationGuidance",
                "severity": "Info",
                "description": pathways["notes"],
            })

        # Add blockers if any
        blockers = pathways.get("blockers", [])
        if blockers:
            findings.append({
                "type": "PotentialBlockers",
                "severity": "Warning",
                "description": f"Known considerations: {', '.join(blockers)}",
            })

        # Build backwards-compatible compatibility dict (string values only)
        # This maintains compatibility with RawAppModResult schema
        compatibility = {
            "rehost_target": pathways.get("rehost", "Azure Virtual Machines"),
            "replatform_target": pathways.get("replatform", "Azure Virtual Machines"),
            "refactor_target": pathways.get("refactor", "Assess for containerization"),
            "azure_equivalent": pathways.get("azure_equivalent", "Azure Virtual Machines"),
        }

        return [{
            "technology": primary_tech,
            "summary": {
                "modernization_feasible": mod_feasible,
                "inferred_from_dr_migrate": True,
                "no_appcat_scan": True,
                "confidence": "Low",
                "warning": "Pathways inferred from technology type, not code analysis",
            },
            # Backwards-compatible format (dict[str, str])
            "compatibility": compatibility,
            # Extended pathway information (new format)
            "azure_modernization_pathways": {
                "rehost": pathways.get("rehost", "Azure Virtual Machines"),
                "replatform": pathways.get("replatform", "Azure Virtual Machines"),
                "refactor": pathways.get("refactor", "Assess for containerization"),
                "azure_equivalent": pathways.get("azure_equivalent", "Azure Virtual Machines"),
                "modernization_path": pathways.get("modernization_path", ["Azure Virtual Machines"]),
            },
            "findings": findings,
            "recommended_targets": self._get_recommended_targets(primary_tech),
            "blockers": blockers,
        }]

    def _detect_primary_technology(self, technologies: list[str]) -> str:
        """Detect the primary technology from a list of technologies."""
        # Priority order for primary technology detection
        # Order matters: more specific patterns first
        priority_patterns = [
            # Frameworks (most specific)
            (r"spring\s*boot", "Spring Boot"),
            (r"asp\.?net\s*core", "ASP.NET Core"),
            (r"asp\.?net", "ASP.NET"),
            (r"django", "Django"),
            (r"flask", "Flask"),
            (r"fastapi", "FastAPI"),
            (r"laravel", "Laravel"),
            (r"symfony", "Symfony"),
            (r"rails|ruby\s*on\s*rails", "Ruby on Rails"),
            (r"express", "Express.js"),
            (r"next\.?js", "Next.js"),
            # Runtimes
            (r"\.net\s*core", ".NET Core"),
            (r"\.net\s*framework", ".NET Framework"),
            (r"java", "Java"),
            (r"\.net|dotnet", ".NET"),
            (r"python", "Python"),
            (r"node\.?js", "Node.js"),
            (r"php", "PHP"),
            (r"ruby", "Ruby"),
            (r"go|golang", "Go"),
            (r"rust", "Rust"),
            # Web servers
            (r"nginx", "NGINX"),
            (r"tomcat", "Apache Tomcat"),
            (r"iis", "Microsoft IIS"),
        ]

        for tech in technologies:
            tech_lower = tech.lower()
            for pattern, name in priority_patterns:
                if re.search(pattern, tech_lower):
                    return name

        # Default based on OS
        for tech in technologies:
            if "windows" in tech.lower():
                return "Windows Application"
            elif "linux" in tech.lower() or "ubuntu" in tech.lower() or "centos" in tech.lower():
                return "Linux Application"

        return "Unknown"

    def _infer_compatibility(self, technology: str) -> dict[str, Any]:
        """Infer Azure modernization pathways based on technology.

        Returns a dictionary containing Azure migration pathways and recommendations.
        Uses the configurable compatibility_mappings dictionary.

        NOTE: These are INFERRED pathways based on technology type, NOT code analysis.

        Returns:
            Dictionary with keys:
                - rehost: Azure target for lift-and-shift
                - replatform: Azure PaaS target
                - refactor: Cloud-native target
                - azure_equivalent: Direct Azure managed service
                - modernization_path: List of recommended migration stages
                - notes: Additional guidance
                - blockers: Known blockers (if any)
        """
        default_mapping = {
            "rehost": "Azure Virtual Machines",
            "replatform": "Azure Virtual Machines",
            "refactor": "Assess for containerization",
            "azure_equivalent": "Azure Virtual Machines",
            "modernization_path": ["Azure Virtual Machines"],
            "notes": "Unknown technology - recommend assessment for modernization options.",
        }

        # First, check for exact match in mappings
        if technology in self.compatibility_mappings:
            return self.compatibility_mappings[technology].copy()

        # Check for partial matches (case-insensitive)
        tech_lower = technology.lower()
        for mapped_tech, compat in self.compatibility_mappings.items():
            if mapped_tech == "_default":
                continue
            if mapped_tech.lower() in tech_lower or tech_lower in mapped_tech.lower():
                return compat.copy()

        # Pattern-based fallback for common technology families
        pattern_matches = [
            ("spring boot", "Spring Boot"),
            ("java", "Java"),
            (".net core", ".NET Core"),
            ("dotnet core", ".NET Core"),
            ("asp.net core", "ASP.NET Core"),
            (".net framework", ".NET Framework"),
            ("dotnet framework", ".NET Framework"),
            ("asp.net", "ASP.NET"),
            (".net", ".NET"),
            ("dotnet", ".NET"),
            ("django", "Django"),
            ("flask", "Flask"),
            ("fastapi", "FastAPI"),
            ("python", "Python"),
            ("next.js", "Next.js"),
            ("nextjs", "Next.js"),
            ("express", "Express.js"),
            ("node", "Node.js"),
            ("laravel", "Laravel"),
            ("symfony", "Symfony"),
            ("wordpress", "WordPress"),
            ("drupal", "Drupal"),
            ("magento", "Magento"),
            ("php", "PHP"),
            ("rails", "Ruby on Rails"),
            ("ruby", "Ruby"),
            ("golang", "Go"),
            ("go", "Go"),
            ("rust", "Rust"),
            ("nginx", "NGINX"),
            ("tomcat", "Apache Tomcat"),
            ("iis", "Microsoft IIS"),
            ("websphere", "IBM WebSphere"),
            ("weblogic", "Oracle WebLogic"),
            ("jboss", "JBoss/WildFly"),
            ("wildfly", "JBoss/WildFly"),
            ("sql server", "SQL Server"),
            ("mysql", "MySQL"),
            ("postgresql", "PostgreSQL"),
            ("postgres", "PostgreSQL"),
            ("mongodb", "MongoDB"),
            ("redis", "Redis"),
            ("kafka", "Apache Kafka"),
            ("rabbitmq", "RabbitMQ"),
        ]

        for pattern, tech_name in pattern_matches:
            if pattern in tech_lower:
                if tech_name in self.compatibility_mappings:
                    return self.compatibility_mappings[tech_name].copy()

        # Return default for unknown technologies
        return self.compatibility_mappings.get("_default", {
            "azure_virtual_machines": "Supported",
        }).copy()

    def _get_recommended_targets(self, technology: str) -> list[str]:
        """Get recommended Azure targets based on technology.

        Returns the modernization path from the compatibility mappings,
        which represents a prioritized list of Azure services suitable for the technology.
        """
        # Get the compatibility/pathway mapping for this technology
        pathways = self._infer_compatibility(technology)

        # Return the modernization path if available
        if "modernization_path" in pathways:
            return pathways["modernization_path"]

        # Fallback: build from rehost/replatform/refactor if modernization_path not present
        targets = []
        if pathways.get("refactor"):
            targets.append(pathways["refactor"])
        if pathways.get("replatform") and pathways["replatform"] not in targets:
            targets.append(pathways["replatform"])
        if pathways.get("rehost") and pathways["rehost"] not in targets:
            targets.append(pathways["rehost"])

        return targets if targets else ["Azure Virtual Machines"]

    def generate_context_json(self, app_data: DrMigrateApplicationData, indent: int = 2) -> str:
        """Generate context file as JSON string.

        Args:
            app_data: Complete Dr. Migrate data for an application
            indent: JSON indentation level

        Returns:
            JSON string of the context file
        """
        context = self.generate_context(app_data)
        return json.dumps(context, indent=indent, default=str)

    def generate_batch_contexts(
        self,
        applications: list[DrMigrateApplicationData],
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate context files for multiple applications.

        Args:
            applications: List of Dr. Migrate application data

        Returns:
            Dictionary mapping application names to their context files
        """
        return {
            app.application_overview.application: self.generate_context(app)
            for app in applications
        }
