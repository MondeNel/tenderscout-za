"""
routers/_query_helpers.py

Reusable SQLAlchemy query helpers for building ILIKE filters.

This module provides small, composable utilities that are shared across
search, tenders, and any other routers that need to filter a database
query against a list of string values using case‑insensitive pattern
matching (ILIKE).

Why separate helpers?
- Avoids repeating the same or_(*[... ilike ...]) pattern in every router.
- Makes filter logic self‑documenting (e.g., `apply_ilike_filter(query,
  Tender.province, user_provinces)` is clearer than the raw SQLAlchemy).
- Centralises the empty‑list guard so callers don't accidentally build
  an `or_()` with zero conditions (which would filter out everything).
"""

from sqlalchemy import or_
from sqlalchemy.orm import Query


def ilike_any(column, values: list[str]) -> "BinaryExpression":
    """
    Build an OR clause that matches `column` ILIKE any value in `values`.

    Each value is wrapped in '%' wildcards to perform a substring search,
    matching how the user-facing filters work (e.g., searching "Western"
    will match "Western Cape").

    Args:
        column: A SQLAlchemy Column (e.g., `Tender.province`).
        values: A list of strings to match against (can be empty).

    Returns:
        A SQLAlchemy BinaryExpression (the OR clause). If `values` is
        empty, this will produce an `or_()` with no arguments, which in
        SQLAlchemy filters out all rows – callers should guard against
        empty lists with `apply_ilike_filter` instead.
    """
    return or_(*[column.ilike(f"%{v}%") for v in values])


def apply_ilike_filter(query: Query, column, values: list[str]) -> Query:
    """
    Apply an ILIKE OR filter to `query` only when `values` is non‑empty.

    This is the safe, recommended wrapper around `ilike_any`. It prevents
    the accidental empty‑list foot‑gun and keeps calling code concise.

    Example:
        query = db.query(Tender)
        query = apply_ilike_filter(query, Tender.province, ["Gauteng", "Western Cape"])
        query = apply_ilike_filter(query, Tender.town, ["Durban"])

    Args:
        query: An existing SQLAlchemy Query object.
        column: The Column to filter on.
        values: A list of strings; if empty or None-like, the query is
                returned unchanged.

    Returns:
        The modified Query with the ILIKE OR condition added, or the
        original Query if `values` is falsy.
    """
    if values:
        query = query.filter(ilike_any(column, values))
    return query