# Repository Patterns

The **AI Dashboard** application accesses backing storage systems directly via specialized data services rather than using a dedicated Repository Pattern layer.

---

## Architectural Decision: Bypassing Intermediate Abstraction Layers

In traditional enterprise applications, repository layers abstract underlying database driver mechanics to support replacing data stores without refactoring client logic. 

However, the dashboard platform handles dynamic, generative SQL constructed contextually by LLMs. As a result, implementing standard object-relational abstraction methods introduces several limitations:

### 1. Dynamic Query Generation
Because LLMs formulate arbitrary SQL schemas based on natural language questions, mapping output metrics to static model entities is impractical. The query execution layer must process arbitrary string combinations dynamically.

### 2. Direct Query-to-DataFrame Handoff
By executing raw reads via **SQLAlchemy** pools and outputting results directly as **Pandas DataFrames**, data serialization remains fast and direct. This avoids the CPU overhead of instantiating large arrays of transient intermediate ORM entities.

---

## Data Access Implementations

Data interaction is organized by storage target:

### Relational Storage Access
Handled by `services/database/db_connection_service.py`, which validates and executes generated read strings directly against connection pool adapters.

### Document Storage Access
Governed by `services/dashboard/session_service.py`, using localized PyMongo driver wrappers to store and query session documents.
