"""
app/services/actions/base.py

Base module for action parameter models.

Provides Pydantic models for generic action parameter validation.
Domain-specific parameter models should be in app.{domain}/actions/base.py.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator


# ============== Smart Update Parameters (Generic) ==============

class SmartUpdateParams(BaseModel):
    """
    Generic smart update parameters.

    Used by update_{entity}_smart actions for natural-language partial updates.
    """
    entity_id: Optional[int] = Field(default=None, description="Entity ID", gt=0)
    entity_name: Optional[str] = Field(default=None, description="Entity name (for lookup)")
    instructions: str = Field(..., description="Natural language update instructions")

    @field_validator('instructions')
    @classmethod
    def validate_instructions(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Instructions cannot be empty")
        return v.strip()

    def model_post_init(self, __context: Any) -> None:
        """Resolve alias fields to generic entity_id/entity_name."""
        if self.entity_id is None:
            for alias in ('guest_id', 'employee_id', 'room_type_id'):
                val = getattr(self, alias, None)
                if val is not None:
                    self.entity_id = val
                    break
        if self.entity_name is None:
            for alias in ('guest_name', 'employee_name', 'room_type_name'):
                val = getattr(self, alias, None)
                if val is not None:
                    self.entity_name = val
                    break

    # Alias fields for backward LLM compatibility
    guest_id: Optional[int] = Field(default=None, exclude=True)
    guest_name: Optional[str] = Field(default=None, exclude=True)
    employee_id: Optional[int] = Field(default=None, exclude=True)
    employee_name: Optional[str] = Field(default=None, exclude=True)
    room_type_id: Optional[int] = Field(default=None, exclude=True)
    room_type_name: Optional[str] = Field(default=None, exclude=True)


# Backward compatibility alias
UpdateGuestSmartParams = SmartUpdateParams


# ============== Query Action Parameters ==============

class FilterClauseParams(BaseModel):
    """Filter clause parameters."""
    field: str = Field(..., description="Field path")
    operator: str = Field(default="eq", description="Operator (eq, ne, gt, gte, lt, lte, in, like, between)")
    value: Any = Field(..., description="Value")

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid_operators = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'like', 'between'}
        if v not in valid_operators:
            raise ValueError(f"Invalid operator: {v}. Supported: {', '.join(valid_operators)}")
        return v


class JoinClauseParams(BaseModel):
    """Join clause parameters."""
    entity: str = Field(..., description="Join entity name")
    on: str = Field(..., description="Join condition (relationship property)")


class OntologyQueryParams(BaseModel):
    """
    Ontology query parameters.

    Used by ontology_query action for dynamic field-level queries.
    """
    entity: str = Field(..., description="Query entity name")
    fields: List[str] = Field(default_factory=list, description="Return fields list")
    filters: Optional[List[FilterClauseParams]] = Field(default=None, description="Filter conditions")
    joins: Optional[List[JoinClauseParams]] = Field(default=None, description="Join conditions")
    order_by: Optional[List[str]] = Field(default=None, description="Order by fields")
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")
    aggregates: Optional[List[dict]] = Field(default=None, description="Aggregate operations")


# ============== Semantic Query Parameters ==============

class SemanticFilterParams(BaseModel):
    """Semantic filter parameters using dot-notation paths."""
    path: str = Field(..., description="Dot-notation path, e.g. stays.status")
    operator: str = Field(default="eq", description="Operator: eq, ne, gt, gte, lt, lte, in, not_in, like, between")
    value: Any = Field(default=None, description="Filter value")

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v: str) -> str:
        valid_operators = {
            'eq', 'ne', 'gt', 'gte', 'lt', 'lte',
            'in', 'not_in', 'like', 'not_like',
            'between', 'is_null', 'is_not_null'
        }
        if v.lower() not in valid_operators:
            raise ValueError(f"Invalid operator: {v}. Supported: {', '.join(sorted(valid_operators))}")
        return v.lower()


class SemanticQueryParams(BaseModel):
    """Semantic query parameters using dot-notation paths."""
    root_object: str = Field(..., description="Root entity name")
    fields: List[str] = Field(default_factory=list, description="Field list with dot-notation paths")
    filters: List[SemanticFilterParams] = Field(default_factory=list, description="Filter conditions")
    order_by: List[str] = Field(default_factory=list, description="Order by fields")
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Offset")
    distinct: bool = Field(default=False, description="Distinct results")


# ============== Result Models ==============

class ActionResult(BaseModel):
    """Action execution result."""
    success: bool
    message: str
    data: Optional[dict] = None
    requires_confirmation: bool = False
    error: Optional[str] = None


# ============== Webhook Action Parameters ==============

class SyncOTAParams(BaseModel):
    """Sync OTA status parameters."""
    channel: str = Field(default="all", description="OTA channel")
    room_type: Optional[str] = Field(default=None, description="Room type name")


class FetchChannelReservationsParams(BaseModel):
    """Fetch channel reservations parameters."""
    channel: str = Field(..., description="Channel name")
    date_from: Optional[date] = Field(default=None, description="Start date")
    date_to: Optional[date] = Field(default=None, description="End date")


# ============== Notification Action Parameters ==============

class NotificationParams(BaseModel):
    """Notification parameters."""
    target: Optional[str] = Field(default=None, description="Notification target")
    message: Optional[str] = Field(default=None, description="Custom message")
    channel: str = Field(default="system", description="Channel: system, sms, wechat")


# ============== Interface Action Parameters ==============

class BookResourceParams(BaseModel):
    """Book resource parameters (generic interface action)."""
    resource_type: str = Field(default="Room", description="Resource type")
    resource_id: Optional[Union[int, str]] = Field(default=None, description="Resource ID")
    guest_name: Optional[str] = Field(default=None, description="Guest name")
    start_date: Optional[date] = Field(default=None, description="Start date")
    end_date: Optional[date] = Field(default=None, description="End date")


__all__ = [
    "SmartUpdateParams",
    "UpdateGuestSmartParams",
    "FilterClauseParams",
    "JoinClauseParams",
    "OntologyQueryParams",
    "SemanticFilterParams",
    "SemanticQueryParams",
    "ActionResult",
    "SyncOTAParams",
    "FetchChannelReservationsParams",
    "NotificationParams",
    "BookResourceParams",
]
