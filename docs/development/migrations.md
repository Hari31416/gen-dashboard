# Migrations Strategy

The **AI Dashboard** application handles data persistence using flexible, document-based stores. This minimizes the need for standard, schema-migration frameworks (such as Alembic).

---

## Architectural Choice: Schema Flexibility over Migrations

### 1. Document Storage (`sessions`, `users`)
Because dashboard sessions are persisted inside **MongoDB** as JSON documents, adding fields to structures (such as tracking parameters or layout configs) does not require altering existing database tables. 

Application code parses historical payloads safely using **Pydantic** models configured with fallback defaults (`default=None`).

### 2. Relational Target Schema Interaction
The platform interfaces with relational databases to execute read queries. Because it does not define application tables within those target schema environments, it does not manage migration lifecycles for external databases.

---

## Automated System Seeding

When initial host instances launch, startup tasks handle baseline seed checks automatically:
- **Admin User Bootstrapping**: `backend/setup_admin_user.py` checks target collections at launch. If user entries are missing, it initializes authentication profiles automatically.
