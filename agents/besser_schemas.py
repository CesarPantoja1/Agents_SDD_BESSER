"""
Pydantic schemas para diagrama de clases (extraídos/adaptados de Besser).
Usados para structured output del LLM antes de pasar por el layout engine.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MethodParameterSpec(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="Parameter name in camelCase")
    type: str = Field(default="String", description="Parameter type: String, int, boolean, float, Date, or a custom class name")


class AttributeSpec(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="Attribute name in camelCase")
    type: Optional[str] = Field(default=None, description="Data type (e.g. String, int, bool, float, Date, or PascalCase class/enum name). Null for enum literals.")
    visibility: Literal["public", "private", "protected", "package"] = Field(default="public", description="UML visibility")
    isDerived: bool = Field(default=False, description="Whether this is a derived/computed attribute.")
    defaultValue: Optional[str] = Field(default=None, description="Default value for the attribute.")
    isOptional: bool = Field(default=False, description="Whether this attribute is optional/nullable.")


class MethodSpec(BaseModel):
    name: str = Field(min_length=1, max_length=50, description="Method name in camelCase only (e.g. getName, calculateTotal). No parameters or return type here.")
    returnType: str = Field(default="void", description="Return type only (e.g. str, int, void). No colon prefix.")
    visibility: Literal["public", "private", "protected", "package"] = Field(default="public", description="UML visibility")
    parameters: List[MethodParameterSpec] = Field(default_factory=list, description="Method parameters, empty if none")
    isAbstract: bool = Field(default=False, description="Whether this is an abstract method.")
    implementationType: Literal["none", "code", "bal", "state_machine", "quantum_circuit"] = Field(
        default="none",
        description="Implementation type (e.g. none, code, bal, state_machine, quantum_circuit)."
    )
    code: Optional[str] = Field(default=None, description="Python implementation code for the method, including the full def statement.")


class SingleClassSpec(BaseModel):
    """A single UML class with attributes and optional methods."""
    className: str = Field(min_length=1, max_length=30, description="Class name in PascalCase, ONE word only (e.g. User, Order, Payment)")
    attributes: List[AttributeSpec] = Field(default_factory=list, description="Class attributes.")
    methods: List[MethodSpec] = Field(default_factory=list, description="Class methods for core domain behavior.")
    isAbstract: bool = Field(default=False, description="Whether this is an abstract class.")
    isEnumeration: bool = Field(default=False, description="Whether this is an enumeration.")


class RelationshipSpec(BaseModel):
    type: Literal[
        "Association", "Inheritance", "Composition", "Aggregation",
        "Realization", "Dependency",
    ] = Field(default="Association", description="Relationship type (e.g. Association, Inheritance, Composition, Aggregation).")
    source: str = Field(description="Source class name")
    target: str = Field(description="Target class name")
    sourceMultiplicity: str = Field(default="1", description="Source multiplicity: 1, 0..1, 0..*, or 1..*")
    targetMultiplicity: str = Field(default="*", description="Target multiplicity: 1, 0..1, 0..*, or 1..*")
    name: Optional[str] = Field(default=None, description="Optional relationship name")


class SystemClassSpec(BaseModel):
    """A complete class diagram with multiple classes and relationships."""
    systemName: str = Field(default="", description="Descriptive system name")
    classes: List[SingleClassSpec] = Field(min_length=1, description="All classes in the system.")
    relationships: List[RelationshipSpec] = Field(default_factory=list, description="Relationships between classes.")
