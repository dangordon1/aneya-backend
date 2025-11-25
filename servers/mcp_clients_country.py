#!/usr/bin/env python
"""
Country-Specific MCP Clients

This module provides specialized MCP client classes for different countries,
each connecting to the appropriate set of clinical guideline servers.

Each client inherits from the base MCPClient class and configures connections
to country-specific guideline sources plus common servers (patient_info).

Supported Countries:
- UK: NICE Guidelines, BNF (British National Formulary)
- India: FOGSI, ICMR, STG, RSSDI, CSI, NCG, IAP
- US: USPSTF, CDC, IDSA, ADA, AHA/ACC, AAP
- Australia: NHMRC
- International: PubMed (fallback for unsupported countries)
"""

from pathlib import Path
from typing import Dict, Any
from mcp_client_base import MCPClient


class UKMCPClient(MCPClient):
    """
    MCP client for UK clinical guidelines.

    Connects to:
    - NICE Guidelines: National Institute for Health and Care Excellence
    - BNF: British National Formulary (drug information)
    - Patient Info: Patient data management

    The UK healthcare system relies heavily on NICE guidance and the BNF
    for evidence-based prescribing decisions.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize UK MCP client.

        Args:
            verbose: Whether to print connection progress
        """
        servers_dir = Path(__file__).parent.parent

        servers = {
            "nice": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "guidelines" / "uk" / "nice_guidelines_server.py")]
            },
            "bnf": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "guidelines" / "uk" / "bnf_server.py")]
            },
            "patient_info": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "patient_info_server.py")]
            }
        }

        super().__init__(servers=servers, verbose=verbose)


class IndiaMCPClient(MCPClient):
    """
    MCP client for Indian clinical guidelines.

    Connects to all major Indian medical guideline organizations:
    - FOGSI: Federation of Obstetric & Gynaecological Societies of India
    - ICMR: Indian Council of Medical Research
    - STG: Standard Treatment Guidelines
    - RSSDI: Research Society for the Study of Diabetes in India
    - CSI: Cardiological Society of India
    - NCG: National Clinical Guidelines
    - IAP: Indian Academy of Pediatrics
    - Patient Info: Patient data management

    India has a diverse set of specialty-specific guideline bodies that
    provide evidence-based recommendations for the Indian healthcare context.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize India MCP client.

        Args:
            verbose: Whether to print connection progress
        """
        servers_dir = Path(__file__).parent.parent
        india_guidelines = servers_dir / "servers" / "guidelines" / "india"

        servers = {
            "fogsi": {
                "command": "python",
                "args": [str(india_guidelines / "fogsi_server.py")]
            },
            "icmr": {
                "command": "python",
                "args": [str(india_guidelines / "icmr_server.py")]
            },
            "stg": {
                "command": "python",
                "args": [str(india_guidelines / "stg_server.py")]
            },
            "rssdi": {
                "command": "python",
                "args": [str(india_guidelines / "rssdi_server.py")]
            },
            "csi": {
                "command": "python",
                "args": [str(india_guidelines / "csi_server.py")]
            },
            "ncg": {
                "command": "python",
                "args": [str(india_guidelines / "ncg_server.py")]
            },
            "iap": {
                "command": "python",
                "args": [str(india_guidelines / "iap_guidelines_server.py")]
            },
            "patient_info": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "patient_info_server.py")]
            }
        }

        super().__init__(servers=servers, verbose=verbose)


class USMCPClient(MCPClient):
    """
    MCP client for US clinical guidelines.

    Connects to major US medical guideline organizations:
    - USPSTF: US Preventive Services Task Force
    - CDC: Centers for Disease Control and Prevention
    - IDSA: Infectious Diseases Society of America
    - ADA: American Diabetes Association
    - AHA/ACC: American Heart Association / American College of Cardiology
    - AAP: American Academy of Pediatrics
    - Patient Info: Patient data management

    The US healthcare system has multiple specialty-specific organizations
    that publish evidence-based clinical practice guidelines.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize US MCP client.

        Args:
            verbose: Whether to print connection progress
        """
        servers_dir = Path(__file__).parent.parent
        us_guidelines = servers_dir / "servers" / "guidelines" / "us"

        servers = {
            "uspstf": {
                "command": "python",
                "args": [str(us_guidelines / "uspstf_server.py")]
            },
            "cdc": {
                "command": "python",
                "args": [str(us_guidelines / "cdc_guidelines_server.py")]
            },
            "idsa": {
                "command": "python",
                "args": [str(us_guidelines / "idsa_server.py")]
            },
            "ada": {
                "command": "python",
                "args": [str(us_guidelines / "ada_standards_server.py")]
            },
            "aha_acc": {
                "command": "python",
                "args": [str(us_guidelines / "aha_acc_server.py")]
            },
            "aap": {
                "command": "python",
                "args": [str(us_guidelines / "aap_guidelines_server.py")]
            },
            "patient_info": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "patient_info_server.py")]
            }
        }

        super().__init__(servers=servers, verbose=verbose)


class AustraliaMCPClient(MCPClient):
    """
    MCP client for Australian clinical guidelines.

    Connects to:
    - NHMRC: National Health and Medical Research Council
    - Patient Info: Patient data management

    NHMRC is Australia's primary source for evidence-based clinical guidelines
    and health research recommendations.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize Australia MCP client.

        Args:
            verbose: Whether to print connection progress
        """
        servers_dir = Path(__file__).parent.parent

        servers = {
            "nhmrc": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "guidelines" / "australia" / "nhmrc_guidelines_server.py")]
            },
            "patient_info": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "patient_info_server.py")]
            }
        }

        super().__init__(servers=servers, verbose=verbose)


class InternationalMCPClient(MCPClient):
    """
    MCP client for international/unsupported countries.

    Connects to:
    - PubMed: 35M+ medical research articles (global coverage)
    - Patient Info: Patient data management

    This client serves as a fallback for countries without dedicated
    guideline servers, providing access to peer-reviewed medical literature
    through PubMed.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize International MCP client.

        Args:
            verbose: Whether to print connection progress
        """
        servers_dir = Path(__file__).parent.parent

        servers = {
            "pubmed": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "pubmed_server.py")]
            },
            "patient_info": {
                "command": "python",
                "args": [str(servers_dir / "servers" / "patient_info_server.py")]
            }
        }

        super().__init__(servers=servers, verbose=verbose)
