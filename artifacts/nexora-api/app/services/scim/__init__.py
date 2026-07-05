"""SCIM 2.0 provisioning subsystem (RFC 7643/7644).

* ``errors``      — SCIM error envelope + ``ScimError`` exception
* ``auth``        — per-organization bearer-token context + admin token mgmt
* ``filters``     — minimal SCIM filter parsing (``attr eq "value"``)
* ``serializers`` — ORM ⇄ SCIM JSON (User / Group / ListResponse)
* ``service``     — Users, Groups, PATCH, Bulk, deactivate/reactivate, role sync
"""
