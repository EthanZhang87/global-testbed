# LEOScope Documentation Index

This directory contains comprehensive documentation explaining the LEOScope testbed codebase architecture, function call stacks, and system flows.

## Documentation Files

### 1. [CODEBASE_FLOW_DOCUMENTATION.md](./CODEBASE_FLOW_DOCUMENTATION.md)
**Main documentation covering:**
- System architecture overview
- Kernel service access verification flow (detailed function call stack)
- Authentication and authorization mechanisms
- Database schema
- Configuration files
- Design patterns used throughout the codebase

**Start here if:** You're new to the codebase and want to understand the overall architecture.

### 2. [KERNEL_ACCESS_FLOW.md](./KERNEL_ACCESS_FLOW.md)
**Detailed sequence diagram and step-by-step walkthrough:**
- Complete sequence diagram showing all components
- Detailed explanation of each step (19 steps total)
- Error scenarios and handling
- Security properties
- Performance considerations
- Debugging checklist

**Start here if:** You want to understand exactly how kernel access verification works, including network communication and database queries.

### 3. [ADDITIONAL_SYSTEM_FLOWS.md](./ADDITIONAL_SYSTEM_FLOWS.md)
**Coverage of other important flows:**
- Job scheduling and execution
- Node registration and heartbeat
- Task scheduling for distributed experiments
- User management (create, modify, delete)
- Global configuration management

**Start here if:** You want to understand how experiments are scheduled, how nodes communicate, or how user management works.

## Quick Reference

### Key Components

| Component | File Location | Purpose |
|-----------|--------------|---------|
| Orchestrator | `orchestrator/orchestrator.py` | Central management, authentication, scheduling |
| Kernel Service | `services/kernel/__main__.py` | Privileged kernel operations on nodes |
| LeotestClient | `common/client.py` | gRPC client library for all components |
| Node Executor | `node/executor.py` | Experiment execution on measurement nodes |
| CLI | `cli/__main__.py` | Command-line interface for users |
| gRPC Stubs | `common/leotest_pb2_grpc.py` | Auto-generated gRPC code |

### Function Call Stacks by Use Case

#### Use Case 1: User wants to change TCP congestion control algorithm
```
User Container
  ↓
services/kernel/__main__.py:main()
  ├─ get_userid_from_ipaddr() [Line 17-37]
  ├─ leotest_client.kernel_access() [Line 122]
  │   └─ common/client.py:kernel_access() [Line 638-642]
  │       └─ grpc_stub.kernel_access()
  │           └─ Network transport
  │               └─ orchestrator/orchestrator.py:kernel_access() [Line 1538-1598]
  │                   ├─ @CheckToken decorator [Line 35-93]
  │                   ├─ self.db.get_user() [Line 1571]
  │                   └─ Permission check [Line 1575-1586]
  └─ change_cca() [Line 51-54]
```

#### Use Case 2: Admin schedules experiment
```
CLI
  ↓
cli/__main__.py
  └─ common/client.py:schedule_job() [Line 191-285]
      └─ grpc_stub.schedule_job()
          └─ orchestrator/orchestrator.py:schedule_job() [Line 464-627]
              ├─ @CheckToken decorator
              ├─ Check schedule conflicts [Line 517-576]
              ├─ Verify trigger syntax [Line 586-591]
              ├─ Create job object [Line 594-619]
              └─ self.db.add_job() [Line 621]
```

#### Use Case 3: Node sends heartbeat
```
Node Service
  ↓
common/client.py:send_heartbeat() [Line 109-116]
  └─ grpc_stub.report_heartbeat()
      └─ orchestrator/orchestrator.py:report_heartbeat() [Line 144-169]
          ├─ @CheckToken decorator
          └─ self.db.mark_node() [Line 163]
```

### User Roles and Permissions

| Role | Value | Kernel Access | Job Scheduling | Node Registration | User Management |
|------|-------|--------------|----------------|-------------------|-----------------|
| ADMIN | 0 | ✅ | ✅ | ✅ | ✅ |
| NODE_PRIV | 1 | ✅ | ✅ | ❌ | ❌ |
| USER_PRIV | 2 | ✅ | ✅ | ❌ | ❌ |
| NODE | 3 | ❌ | ❌ (only polls) | ❌ | ❌ |
| USER | 4 | ❌ | ✅ (basic) | ❌ | ❌ |

### Common Commands

#### Register a node
```bash
python -m cli node --action=register \
  --userid=admin \
  --access-token=admin-token \
  --nodeid=node-london-01 \
  --name="London Node" \
  --location=london \
  --coords="51.5074,-0.1278"
```

#### Register a user
```bash
python -m cli user --action=register \
  --userid=alice \
  --name="Alice Smith" \
  --role=USER_PRIV \
  --team=research
```

#### Schedule an experiment
```bash
python -m cli job --action=schedule \
  --userid=alice \
  --access-token=alice-token \
  --nodeid=node-london-01 \
  --jobid=exp-123 \
  --schedule="*/5 * * * *" \
  --start-date="2024-01-01 00:00:00" \
  --end-date="2024-01-02 00:00:00" \
  --length=300
```

#### Start orchestrator
```bash
python -m orchestrator \
  --grpc-hostname=0.0.0.0 \
  --grpc-port=50051 \
  --db-server=localhost \
  --db-port=27017 \
  --admin-access-token=admin-secret
```

#### Start kernel service
```bash
python -m services.kernel \
  --nodeid=node-london-01 \
  --grpc-hostname=orchestrator.example.com \
  --access-token=node-token
```

### Architecture Diagram

See `extras/leoscope_arch.jpg` for the visual architecture diagram showing all components and their interactions.

## Understanding the Code

### Step 1: Read the Main Documentation
Start with [CODEBASE_FLOW_DOCUMENTATION.md](./CODEBASE_FLOW_DOCUMENTATION.md) to understand:
- Overall architecture
- Key design patterns
- Component responsibilities

### Step 2: Dive into Specific Flows
Choose a flow that interests you:
- **Security-focused:** Read [KERNEL_ACCESS_FLOW.md](./KERNEL_ACCESS_FLOW.md)
- **Scheduling-focused:** Read [ADDITIONAL_SYSTEM_FLOWS.md](./ADDITIONAL_SYSTEM_FLOWS.md) - Flow 1
- **Node management:** Read [ADDITIONAL_SYSTEM_FLOWS.md](./ADDITIONAL_SYSTEM_FLOWS.md) - Flow 2

### Step 3: Explore the Code
With the documentation as your guide:
1. Open the relevant files
2. Follow the function call stacks
3. Set breakpoints to trace execution
4. Examine database queries and API calls

### Step 4: Run Examples
Try the examples in each documentation file:
- Register a test node
- Create a test user
- Schedule a simple experiment
- Monitor execution with logs

## Common Patterns to Look For

### 1. Decorator Pattern for Authentication
```python
@CheckToken(pb2.response_type, grpc.StatusCode.UNAUTHENTICATED, "Invalid token")
def some_rpc_method(self, request, context):
    # Method automatically has authentication check
    userid = context.creds_userid
    role = context.creds_role
```

### 2. Retry Logic for Network Calls
```python
for attempt in self._retry():
    with attempt:
        # This code will retry on grpc.RpcError
        return self.grpc_stub.some_method(message, timeout=self.timeout)
```

### 3. Role-Based Authorization
```python
if _role == LeotestUserRoles.ADMIN.value:
    # Admin-only operation
elif _role == LeotestUserRoles.NODE.value:
    # Node-only operation
else:
    # Permission denied
```

### 4. gRPC Message Construction
```python
message = pb2.message_type()
message.field1 = value1
message.field2 = value2
return self.grpc_stub.method_name(message, timeout=self.timeout)
```

## Debugging Guide

### Enable Debug Logging
```python
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format="%(asctime)s %(filename)s:%(lineno)s %(thread)d %(levelname)s %(message)s"
)
```

### Common Issues and Solutions

#### Issue: "Invalid token" errors
**Solution:** 
1. Check access token matches what was returned during registration
2. Verify token is being sent in correct header: `x-leotest-access-token`
3. Confirm user exists in database

#### Issue: "Permission denied" errors
**Solution:**
1. Check user role in database
2. Verify operation requires that role
3. For kernel access, ensure role is USER_PRIV, NODE_PRIV, or ADMIN

#### Issue: gRPC connection failures
**Solution:**
1. Verify orchestrator is running and accessible
2. Check firewall rules for port 50051
3. Confirm TLS certificates are valid
4. Test with `telnet orchestrator-host 50051`

#### Issue: Job not executing
**Solution:**
1. Verify node is sending heartbeats (check orchestrator logs)
2. Check job schedule is correct (cron syntax)
3. Ensure no schedule conflicts
4. Review node executor logs

### Tracing a Request

To trace a request through the system:

1. **Start with the entry point:**
   ```python
   # services/kernel/__main__.py
   log.info("Connection from {}".format(address))  # Add this log
   ```

2. **Follow the gRPC call:**
   ```python
   # common/client.py
   log.info('sending request for kernel access verification; userid=%s' % userid)
   ```

3. **Check orchestrator reception:**
   ```python
   # orchestrator/orchestrator.py
   log.info("[kernel_access] userid=%s role=%s verify_userid=%s" 
                                          % (_userid, _role_name, verify_userid))
   ```

4. **Verify database query:**
   ```python
   # orchestrator/datastore.py
   log.info("Querying user: %s" % userid)
   ```

5. **Trace response:**
   Look for return statements and response construction at each level

## API Reference

For detailed API documentation, see:
- Protocol Buffer definitions: `common/leotest.proto`
- Generated documentation: `doc/_build/html/`

## Contributing

When adding new features:
1. Follow existing patterns (authentication, retry logic, etc.)
2. Update relevant documentation
3. Add logging at key points
4. Consider security implications
5. Test error cases

## Additional Resources

- **README.md:** Setup and deployment instructions
- **Architecture Diagram:** `extras/leoscope_arch.jpg`
- **Example Configs:** `extras/experiment-config.yaml`, `global_config.json`
- **Docker Files:** `docker/` directory
- **Generated Docs:** `doc/_build/html/`

## Summary

The LEOScope testbed is a sophisticated distributed system with:
- **Security:** Multi-layer authentication and authorization
- **Scalability:** gRPC-based microservices architecture
- **Flexibility:** Support for various experiment types and scheduling
- **Robustness:** Automatic retries, heartbeats, and error handling
- **Auditability:** Comprehensive logging and database tracking

These documentation files provide a complete understanding of how the system works, from high-level architecture to detailed function calls. Use them to:
- Understand the codebase
- Debug issues
- Add new features
- Deploy the system
- Train new developers

## Questions?

If you have questions about the code:
1. Check these documentation files first
2. Search for relevant functions in the code
3. Review logs from a running system
4. Contact the maintainers (see MAINTAINERS.md)

---

**Last Updated:** 2024
**Documentation Version:** 1.0
**Code Version:** Compatible with main branch
