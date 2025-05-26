# KOS Orchestration System User Guide

## Introduction

The KOS Orchestration System provides a robust platform for managing containerized applications. This guide explains how to use the various components of the orchestration system to deploy and manage your applications effectively.

## Core Concepts

### Pods

Pods are the smallest deployable units in KOS. A pod represents a single instance of a running process in the system and can contain one or more containers.

```yaml
kind: Pod
apiVersion: v1
metadata:
  name: my-pod
  namespace: default
  labels:
    app: myapp
spec:
  containers:
  - name: main-container
    image: myapp:latest
    ports:
    - containerPort: 8080
    resources:
      limits:
        cpu: "0.5"
        memory: "512Mi"
      requests:
        cpu: "0.2"
        memory: "256Mi"
```

### Services

Services provide stable networking for pods, allowing other components to discover and connect to them.

```yaml
kind: Service
apiVersion: v1
metadata:
  name: my-service
  namespace: default
spec:
  selector:
    app: myapp
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

## Controllers

### ReplicaSet

ReplicaSets maintain a stable set of pod replicas running at any given time.

```yaml
kind: ReplicaSet
apiVersion: v1
metadata:
  name: my-replicaset
  namespace: default
spec:
  replicas: 3
  selector:
    app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: main-container
        image: myapp:latest
```

### Deployment

Deployments provide declarative updates for pods and ReplicaSets.

```yaml
kind: Deployment
apiVersion: v1
metadata:
  name: my-deployment
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: main-container
        image: myapp:latest
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

### StatefulSet

StatefulSets manage the deployment and scaling of a set of pods with persistent identities.

```yaml
kind: StatefulSet
apiVersion: v1
metadata:
  name: my-statefulset
  namespace: default
spec:
  serviceName: my-stateful-service
  replicas: 3
  selector:
    matchLabels:
      app: mydb
  template:
    metadata:
      labels:
        app: mydb
    spec:
      containers:
      - name: db-container
        image: mydb:latest
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
```

## Network Policies

Network Policies allow you to control the flow of traffic between pods.

```yaml
kind: NetworkPolicy
apiVersion: v1
metadata:
  name: my-network-policy
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: myapp
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - port: 8080
      protocol: TCP
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - port: 5432
      protocol: TCP
```

## Horizontal Pod Autoscaler

The Horizontal Pod Autoscaler automatically scales the number of pods based on observed CPU utilization or other metrics.

```yaml
kind: HorizontalPodAutoscaler
apiVersion: v1
metadata:
  name: my-hpa
  namespace: default
spec:
  scaleTargetRef:
    kind: Deployment
    name: my-deployment
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        value: 50
```

### Using the Autoscaler

1. **Create an HPA**:
   ```python
   from kos.core.orchestration.autoscaler import HorizontalPodAutoscaler, MetricSpec, HPASpec

   # Create metric specification
   metric = MetricSpec(
       type="Resource",
       resource_name="cpu",
       target_type="Utilization",
       target_value=50
   )

   # Create HPA specification
   spec = HPASpec(
       scale_target_ref={
           "kind": "Deployment",
           "name": "my-deployment"
       },
       min_replicas=2,
       max_replicas=10,
       metrics=[metric]
   )

   # Create and save HPA
   hpa = HorizontalPodAutoscaler(
       name="my-hpa",
       namespace="default",
       spec=spec
   )
   hpa.save()
   ```

2. **Start the Autoscaler Controller**:
   ```python
   from kos.core.orchestration.autoscaler import start_autoscaler_controller

   start_autoscaler_controller()
   ```

## Admission Controller

The Admission Controller validates resources before they are accepted by the system.

### Using the Admission Controller

1. **Enable/Disable the Admission Controller**:
   ```python
   from kos.core.orchestration.admission import get_admission_controller

   # Get the admission controller
   controller = get_admission_controller()

   # Enable the controller
   controller.enable()

   # Or disable it
   controller.disable()
   ```

2. **Enable/Disable Specific Rules**:
   ```python
   # Enable a rule
   controller.enable_rule("pod_resource_limits", "Pod")

   # Disable a rule
   controller.disable_rule("pod_resource_limits", "Pod")
   ```

3. **List Available Rules**:
   ```python
   # List all rules
   rules = controller.list_rules()

   # List rules for a specific resource kind
   pod_rules = controller.list_rules("Pod")
   ```

4. **Validate a Resource**:
   ```python
   from kos.core.orchestration.admission import validate_resource

   # Define a resource
   pod = {
       "kind": "Pod",
       "apiVersion": "v1",
       "metadata": {
           "name": "my-pod",
           "namespace": "default"
       },
       "spec": {
           "containers": [
               {
                   "name": "main-container",
                   "image": "myapp:latest"
               }
           ]
       }
   }

   # Validate the resource
   result = validate_resource(pod)
   if result.allowed:
       print("Resource is valid")
   else:
       print(f"Resource is invalid: {result.reason}")
   ```

## Service Discovery

Service Discovery allows pods to discover each other using DNS-based methods.

### Using Service Discovery

1. **Lookup a Service**:
   ```python
   from kos.core.orchestration.service_discovery import ServiceDiscovery

   # Get the service discovery instance
   discovery = ServiceDiscovery.instance()

   # Lookup a service
   service_info = discovery.lookup_service("my-service", "default")
   ```

2. **Lookup a Pod**:
   ```python
   # Lookup a pod
   pod_info = discovery.lookup_pod("my-pod-0", "default")
   ```

## Metrics Collection

The Metrics Collection system monitors system performance and resource usage.

### Using Metrics Collection

1. **Collect Metrics**:
   ```python
   from kos.core.monitoring.metrics import MetricsCollector

   # Get the metrics collector instance
   collector = MetricsCollector.instance()

   # Collect metrics
   metrics = collector.collect_metrics()
   ```

2. **Get Specific Metrics**:
   ```python
   # Get CPU metrics
   cpu_metrics = collector.get_metrics(name="cpu_percent")

   # Get memory metrics
   memory_metrics = collector.get_metrics(name="memory_percent")

   # Get pod metrics with specific labels
   pod_metrics = collector.get_metrics(
       name="pod_cpu_percent",
       labels={"app": "myapp"}
   )
   ```

## Best Practices

1. **Resource Management**:
   - Always specify resource requests and limits for your containers
   - Use the Horizontal Pod Autoscaler for workloads with variable traffic

2. **Networking**:
   - Use Services to provide stable network endpoints
   - Implement NetworkPolicies to secure communication between pods

3. **State Management**:
   - Use StatefulSets for stateful applications
   - Configure volume claims for persistent storage

4. **High Availability**:
   - Deploy multiple replicas for critical services
   - Implement liveness and readiness probes

5. **Monitoring**:
   - Regularly check metrics for system health
   - Set up alerts for critical metrics

## Troubleshooting

### Common Issues

1. **Pods Not Starting**:
   - Check the pod status for error messages
   - Verify resource requests and limits
   - Check if admission controller is rejecting the pod

2. **Network Connectivity Issues**:
   - Verify NetworkPolicies allow required traffic
   - Check if the Service is correctly targeting the pods
   - Ensure DNS resolution is working properly

3. **Autoscaling Problems**:
   - Verify metrics collection is working
   - Check HPA configuration
   - Ensure the target deployment exists

## API Reference

For detailed API references, see the following documentation:

- [Pod API Reference](./pod_api.md)
- [Service API Reference](./service_api.md)
- [Controller API Reference](./controller_api.md)
- [Network Policy API Reference](./network_policy_api.md)
- [Metrics API Reference](./metrics_api.md)
- [Autoscaler API Reference](./autoscaler_api.md)
- [Admission Controller API Reference](./admission_api.md)
