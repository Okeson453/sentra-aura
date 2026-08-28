# SentraAura — Helm Deployment

## Overview

This directory contains all Kubernetes deployment configurations for SentraAura services, using Helm for templating and Kustomize for environment-specific patches.

## Directory Structure

```
helm/
├── charts/
│   ├── sentra-service/       # Generic parameterized service chart
│   └── platform/
│       ├── nats/             # NATS JetStream
│       ├── cert-manager/     # TLS certificate management
│       └── default-deny/     # Network policies
├── environments/
│   ├── dev/                  # Dev values and patches
│   ├── staging/              # Staging values and patches
│   ├── canary/               # Canary values and patches
│   └── production/           # Production values and patches
└── releases/
    └── <service-name>/       # Per-service release configurations
        ├── release.yaml      # HelmRelease (FluxCD)
        ├── kustomization.yaml
        └── namespace.yaml
```

## Generic Service Chart

The `sentra-service` chart is a parameterized Helm chart used for all microservices. It provides:

- Deployment with health checks
- Service with ClusterIP
- HorizontalPodAutoscaler
- PodDisruptionBudget
- NetworkPolicy (default deny with explicit allows)
- ServiceAccount with IRSA annotations
- Ingress (optional)
- ConfigMap for non-sensitive configuration

### Values Override Hierarchy

1. Chart defaults (`charts/sentra-service/values.yaml`)
2. Environment values (`environments/<env>/values.yaml`)
3. Service-specific values (in `releases/<service>/release.yaml`)
4. Kustomize patches (`environments/<env>/patches/`)

## Deploying a Service

```bash
# Deploy to dev
helm upgrade --install <service> charts/sentra-service \
  --namespace sentra \
  --values environments/dev/values.yaml \
  --set serviceName=<service> \
  --set imageTag=<tag>

# Using Kustomize + FluxCD
kustomize build releases/<service> | kubectl apply -f -
```

## Platform Services

### NATS JetStream

Event bus for async communication between services.

```bash
helm upgrade --install nats charts/platform/nats --namespace nats
```

### cert-manager

Automated TLS certificate management.

```bash
helm upgrade --install cert-manager charts/platform/cert-manager --namespace cert-manager
```

### Default Deny

Zero-trust network policies.

```bash
helm upgrade --install default-deny charts/platform/default-deny
```

## Environment Configuration

### Development
- Reduced replica counts (1-2)
- Smaller resource limits
- Debug log levels
- No deletion protection

### Staging
- Production-like sizing
- Full test data
- Integration with staging providers

### Canary
- Production mirror
- Used for progressive rollout validation
- Same sizing as production

### Production
- Maximum redundancy
- Strict resource limits
- Info log levels
- Deletion protection enabled
- PDB with minAvailable=2

## Security

- All services run as non-root (UID 1000)
- Read-only root filesystems
- Dropped capabilities
- Network policies restrict egress to known ports
- Secrets mounted via AWS Secrets Manager CSI driver
