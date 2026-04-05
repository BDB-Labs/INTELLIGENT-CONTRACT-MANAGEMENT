# Windows Packaging Plan

This directory is reserved for the Windows desktop target.

Planned direction:

- reuse `ese/platform/catalog.py` for shared surface metadata
- reuse `ese.desktop.app` runtime concepts where possible
- package the app as a native Windows desktop bundle or installer
- keep Windows-specific signing, icons, and installer assets here

The intent is to keep platform-specific packaging isolated from the core product logic.
