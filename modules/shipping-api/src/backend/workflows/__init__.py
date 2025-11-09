"""
Temporal workflows registry.

All workflows are automatically registered here.
"""

# Import workflows here
# They will be auto-added by the add-temporal-workflow tool

# Registry of all workflows

from .shipment import ShipmentWorkflow

WORKFLOWS = [
    ShipmentWorkflow,
]
