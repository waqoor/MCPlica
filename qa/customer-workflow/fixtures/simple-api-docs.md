# QA Bookstore API — Documentation

This document describes the Bookstore API used by internal catalog tools.

## Overview

The Bookstore API lets integrators list, create, and retrieve books in the
catalog. All endpoints require a bearer token issued by the store's auth
service.

## Books

- Books have a title, author, price, and availability status.
- Status is one of: available, out of stock, or discontinued.
- Listing supports filtering by status and a result limit.

## Notes for integrators

Prices are always in USD. Newly created books default to "available"
status unless specified otherwise.

## Support

For questions about this API, contact the catalog team.

(This documentation deliberately does NOT mention deleting or updating
books — those operations don't exist in the source OpenAPI spec. This is
intentional: MCPlica must not invent executable tools for capabilities
that only appear in documentation, not in the executable source.)
