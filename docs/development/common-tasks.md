# Common Development Tasks

Developer guides for extending pipeline capabilities and adjusting platform configurations.

---

## 1. Adding a New Agent Stage to the Pipeline

To introduce intermediate processing logic (such as additional data verification steps) into the main generation path:

### A. Define Node Actions
Create a dedicated handler inside `backend/langchain_agents/dashboard/agents/`:

```python
def quality_check_node(state: DashboardGraphState) -> dict:
    """Evaluates intermediate state structures before handoff."""
    # Process attributes and output state dictionary updates
    return {"status": "verified"}
```

### B. Register Node into Graph State Definitions
Update `backend/langchain_agents/dashboard/graph.py` to map the new execution node:

```python
# Bind node definition
workflow.add_node("quality", quality_check_node)

# Insert conditional flow paths
workflow.add_conditional_edges("viz_spec", check_logic, {"continue": "quality"})
workflow.add_edge("quality", "layout")
```

---

## 2. Extending Supported Database Adapters

To enable connections to additional target database engines:
1. Update dependency configurations (`pyproject.toml`) to include required database connection drivers.
2. Update connection string builders inside `services/database/db_connection_service.py` to format standard database URIs for the new target engine type.

---

## 3. Makefile Command Reference

The root Makefile provides shortcuts for common operational tasks:
- `make setup`: Installs required packages for frontend and backend workspaces.
- `make start`: Boots gateway and client dev servers concurrently.
- `make lint`: Runs formatters across Python and Typescript source files.
- `make clean`: Removes local cache directories and compiled build artifacts.
