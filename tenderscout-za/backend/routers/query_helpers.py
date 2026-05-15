"""
routers/_query_helpers.py

Small utilities shared across search, tenders, and any future routers
that build SQLAlchemy ilike filters from lists of strings.
"""
from sqlalchemy import or_
from sqlalchemy.orm import Query


def ilike_any(column, values: list[str]) -> "BinaryExpression":
    """
    Return an OR clause matching column ILIKE any value in the list.

    Usage:
        query = query.filter(ilike_any(Tender.province, ["Western Cape", "Gauteng"]))
    """
    return or_(*[column.ilike(f"%{v}%") for v in values])


def apply_ilike_filter(query: Query, column, values: list[str]) -> Query:
    """
    Apply an ilike_any filter only when values is non-empty.
    Returns the query unchanged if values is empty.
    """
    if values:
        query = query.filter(ilike_any(column, values))
    return query