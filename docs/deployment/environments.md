# Deployment Environments

The platform architecture segregates configurations by environment mode to support safe validation before deploying updates.

---

## 1. Environment Topology

```txt
Deployment Topologies
├── Local Development           # Embedded dev servers utilizing non-optimized JS/TS builds
├── Staging Validation          # Pre-production validation environment mimicking cloud infrastructure
└── Production Cluster          # Highly available, scaled production nodes
```

---

## 2. Configuration Isolation

To prevent cross-environment data contamination, deployments use distinct backend connection properties:
- **Database Targets**: Staging workers target scrubbed data sources to validate queries safely. Production clusters connect directly to live production DB instances.
- **Session DB Segregation**: Separate MongoDB connection strings are used per environment to isolate active user dashboard configurations.
