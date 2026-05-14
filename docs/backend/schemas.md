# Validation Schemas

To maintain clean data boundaries, the backend maps incoming JSON payloads and outputs from LLM generation stages using **Pydantic** validation classes.

---

## 1. Edge Request Payloads

Incoming REST and streaming payloads are validated via target schemas:

```python
class DashboardGenerateRequest(BaseModel):
    user_prompt: str = Field(..., description="Natural language prompt")
    connection_name: str = Field(..., description="Target database config name")
    max_charts: int = Field(10, ge=1, le=10, description="Max allowed charts")
    theme: Optional[str] = Field("default", description="UI rendering theme")

class DashboardRefineRequest(BaseModel):
    session_id: str = Field(..., description="Active session context ID")
    new_feedback: str = Field(..., description="Conversational modification prompt")
    target_chart_id: Optional[str] = Field(None, description="Target chart ID")

class DashboardFilterRequest(BaseModel):
    session_id: str = Field(..., description="Active session context ID")
    filter_state: Dict[str, Any] = Field(..., description="Active key-value filter parameters")
```

---

## 2. Agent Contract Schemas

LLM stages output structured JSON blocks validated using strict Pydantic models:

```python
class ChartGoal(BaseModel):
    chart_id: str
    question: str
    chart_type: str
    variables: List[str]
    rationale: str

class SingleVizSpec(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    spec: Dict[str, Any]
    data: Optional[Dict[str, Any]] = None

class ComposedDashboardSpec(BaseModel):
    title: str
    description: Optional[str] = None
    vega_lite_spec: Dict[str, Any]
    individual_specs: List[SingleVizSpec]
    layout_config: Optional[LayoutConfig] = None
    layout_type: str = "grid"
    chart_count: int = 0
    sql_queries: List[Dict[str, str]] = []
```

---

## 3. Serialization Sanitization

Because base Python execution libraries can yield objects that are not directly JSON-serializable, API handoff functions run internal translation checks:
- **`Decimal`**: Casts financial metrics to native floating-point numbers.
- **`datetime` / `date`**: Converts internal object references into ISO-formatted string records.
- **`NaN` / `Inf`**: Converts standard arithmetic floating-point errors to explicit `null` boundaries.
