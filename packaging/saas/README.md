# SaaS Packaging Plan

This directory is reserved for the hosted control-center target.

Planned direction:

- reuse the shared surface catalog from `ese/platform/catalog.py`
- expose the same control-plane concepts through authenticated web routes
- replace local artifact and process assumptions with service-backed APIs and storage

The goal is not to fork the product, but to deliver the same control surface through a different runtime.
