# Global Middleware

The backend uses custom middleware and localized response parameter tuning to manage cross-origin access and streaming buffering.

---

## 1. Cross-Origin Resource Sharing (CORS)

To enable client interaction from diverse local or edge frontend origins, `backend/app.py` attaches strict CORS headers globally:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adaptable via deployment config files
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 2. Server-Sent Events Header Overrides

Standard proxy infrastructure (such as Nginx) often caches output bytes to optimize connection throughput. This buffering can break real-time streaming updates.

To resolve this, streaming routes explicitly inject non-buffering directives directly into their responses:

```python
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Instructs Nginx to bypass output buffering
    },
)
```
