"""Control-list XLSX export package (WP-CL-003).

The package initializer intentionally has no eager imports.  The projection
service imports ``app.directory.rbac``; keeping this boundary lazy prevents a
cycle while the directory router is being registered.
"""
