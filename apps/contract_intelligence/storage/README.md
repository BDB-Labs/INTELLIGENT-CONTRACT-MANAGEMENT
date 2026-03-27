# Storage Boundary

This directory now contains the first persistence slice for the
contract-intelligence product.

Current records:

- durable case records
- bid-review run records
- committed contract records
- current and by-commit obligation snapshots
- monitoring run records
- current and historical alert snapshots

Planned next records:

- precedents

The storage layer is intentionally lightweight and filesystem-backed for now so
the lifecycle model can settle before a database boundary is introduced.
