# LEOScope Codebase Flow Documentation

## Overview

This document explains the LEOScope testbed codebase architecture and the detailed function call stack for key operations. LEOScope is a distributed system with three main components:

1. **Orchestrator** - Central management system that handles scheduling and authentication
2. **Measurement Nodes** - Physical nodes that run experiments
3. **Kernel Service** - Privileged service on nodes that controls kernel parameters

## Architecture Diagram Reference

Refer to `extras/leoscope_arch.jpg` for the visual architecture diagram.

---

## Key Communication Flow: Kernel Service Access Verification

This section describes one of the most critical flows in the system - how kernel services verify user access rights before allowing privileged operations.

### Components Involved

1. **Kernel Service** (`services/kernel/__main__.py`)
   - Runs on measurement nodes
   - Listens on port 9000 for incoming connections
   - Provides privileged kernel configuration services

2. **LeotestClient** (`common/client.py`)
   - gRPC client library
   - Handles communication with the orchestrator
   - Manages authentication credentials

3. **Orchestrator gRPC Service** (`orchestrator/orchestrator.py`)
   - Central authentication and scheduling service
   - Validates user permissions
   - Maintains user role database

4. **gRPC Stub** (`common/leotest_pb2_grpc.py`)
   - Auto-generated gRPC stub code
   - Defines RPC interfaces

---

## Detailed Function Call Stack

### Scenario: User Container Requests Kernel Configuration Change

**Flow:** User container → Kernel Service → LeotestClient → gRPC Stub → Orchestrator → Database → Response

#### Step 1: Kernel Service Receives Connection

**File:** `services/kernel/__main__.py`

```
main()
├─ Line 93-108: Creates TCP socket server on port 9000
├─ Line 112-115: Enters infinite loop waiting for connections
└─ Line 115: Accepts client connection
```

**Function:** `main()`
- **Purpose:** Entry point for the kernel service
- **What it does:** 
  - Initializes LeotestClient with orchestrator connection details
  - Creates TCP socket server on 0.0.0.0:9000
  - Listens for incoming connections from user containers

#### Step 2: IP Address to UserID Mapping

**File:** `services/kernel/__main__.py`

```
main() [Line 119-120]
└─ get_userid_from_ipaddr(ip_addr, network='global-testbed_leotest-net')
   ├─ Line 17-37: Function implementation
   ├─ Line 19: Creates Docker client
   ├─ Line 21-22: Gets Docker network and containers
   ├─ Line 24-36: Iterates through containers to match IP
   └─ Line 34: Extracts userid from container labels
```

**Function:** `get_userid_from_ipaddr(ip_addr, network)`
- **Purpose:** Maps IP address to user ID by inspecting Docker containers
- **What it does:**
  - Connects to Docker daemon
  - Retrieves all containers on the specified network
  - Matches IP address to container
  - Extracts and returns the `userid` from container labels
- **Returns:** `userid` string or `None` if not found

#### Step 3: Kernel Access Verification Request

**File:** `services/kernel/__main__.py`

```
main() [Line 121-124]
└─ leotest_client.kernel_access(userid=userid)
```

**File:** `common/client.py`

```
LeotestClient.kernel_access(userid) [Line 638-642]
├─ Line 639: Logs request
├─ Line 640-641: Creates pb2.message_kernel_access message
└─ Line 642: Calls self.grpc_stub.kernel_access(message, timeout=self.timeout)
```

**Function:** `LeotestClient.kernel_access(userid)`
- **Purpose:** Sends gRPC request to orchestrator to verify kernel access
- **What it does:**
  - Creates a protobuf message with the userid
  - Invokes the gRPC stub's kernel_access method
  - Returns the response from orchestrator
- **Returns:** gRPC response message

#### Step 4: gRPC Communication Layer

**File:** `common/leotest_pb2_grpc.py`

```
LeotestOrchestratorStub.__init__() [Lines visible in snippet]
└─ self.kernel_access = channel.unary_unary(
       '/unary.LeotestOrchestrator/kernel_access',
       request_serializer=common_dot_leotest__pb2.message_kernel_access.SerializeToString,
       response_deserializer=common_dot_leotest__pb2.message_kernel_access_response.FromString
   )
```

**Function:** `LeotestOrchestratorStub.kernel_access()`
- **Purpose:** Auto-generated gRPC stub method
- **What it does:**
  - Serializes the request message to protocol buffer format
  - Sends request over gRPC channel to orchestrator
  - Deserializes response from protocol buffer format
  - Handles network communication and retries

#### Step 5: Orchestrator Receives and Processes Request

**File:** `orchestrator/orchestrator.py`

```
LeotestOrchestratorGrpc.kernel_access(request, context) [Line 1538-1598]
├─ Line 1541-1544: @CheckToken decorator validates authentication
├─ Line 1556-1561: Extracts credentials from context
├─ Line 1566-1567: Checks if caller has NODE or ADMIN role
├─ Line 1571: Queries database for verify_userid
├─ Line 1572-1586: Checks if verify_userid has required privileges
│  ├─ USER_PRIV role → access granted
│  ├─ NODE_PRIV role → access granted
│  ├─ ADMIN role → access granted
│  └─ Other roles → access denied
└─ Line 1594-1598: Returns response with state and message
```

**Function:** `LeotestOrchestratorGrpc.kernel_access(request, context)`
- **Purpose:** Validates if a user has permission to access kernel services
- **What it does:**
  1. **Authentication Check:** The `@CheckToken` decorator verifies the caller's credentials
  2. **Authorization Check:** Verifies caller is NODE or ADMIN
  3. **User Lookup:** Retrieves user information from database
  4. **Permission Check:** Verifies user has USER_PRIV, NODE_PRIV, or ADMIN role
  5. **Response:** Returns state (0=success, 1=failure) and detailed message
- **Returns:** `pb2.message_kernel_access_response`

#### Step 6: Authentication Decorator (CheckToken)

**File:** `orchestrator/orchestrator.py`

```
CheckToken.__call__(f) [Line 47-93]
├─ Line 49: Wrapped function decorator
├─ Line 50-60: Extracts credentials from gRPC metadata
│  ├─ x-leotest-access-token
│  ├─ x-leotest-userid
│  └─ x-leotest-jwt-access-token
├─ Line 65-73: If JWT token present, verify via verify_jwt()
├─ Line 76-88: If userid/access_token present, verify via verify_user()
└─ Line 90-92: If verification fails, return error response
```

**Function:** `CheckToken` (Decorator Class)
- **Purpose:** Validates authentication before allowing RPC execution
- **What it does:**
  - Intercepts all incoming gRPC requests
  - Extracts authentication tokens from gRPC metadata headers
  - Verifies tokens using either JWT or static token method
  - Sets `context.creds_userid` and `context.creds_role` if valid
  - Rejects request with UNAUTHENTICATED status if invalid

#### Step 7: Response Handling in Kernel Service

**File:** `services/kernel/__main__.py`

```
main() [Line 122-132]
├─ Line 122-124: Receives response from kernel_access()
├─ Line 128-132: Checks response state
│  ├─ If state=='FAILED': Send 'access_denied' and close connection
│  └─ If successful: Continue to command execution
├─ Line 136-140: Receives command from client
└─ Line 145-156: Executes appropriate command
```

**Function:** Response handling in `main()`
- **Purpose:** Processes the access verification response
- **What it does:**
  - Parses the response from orchestrator
  - If access denied: Sends error message and closes connection
  - If access granted: Proceeds to receive and execute kernel commands
  - Executes commands like `cca.check`, `cca.change`, `bbr2.param.set`

---

## Command Execution Functions

After access is verified, the kernel service can execute privileged commands:

### Function: `check_cca()` [Line 46-49]
- **Purpose:** Check current TCP congestion control algorithm
- **Command:** `sysctl net.ipv4.tcp_congestion_control`
- **Returns:** Current CCA name as bytes

### Function: `change_cca(cca)` [Line 51-54]
- **Purpose:** Change TCP congestion control algorithm
- **Command:** `sysctl -w net.ipv4.tcp_congestion_control={cca}`
- **Returns:** Command output as bytes

### Function: `set_bbr2_param(path, value)` [Line 56-60]
- **Purpose:** Set BBR2 parameters
- **What it does:** Writes value to specified sysfs path
- **Returns:** Confirmation message as bytes

### Function: `execute_command(command)` [Line 39-44]
- **Purpose:** Generic command execution
- **What it does:** Executes arbitrary shell command
- **Returns:** "Command executed." message

---

## Key Design Patterns

### 1. Defense in Depth
- Multiple authentication layers (CheckToken, role verification, user lookup)
- IP-based user identification plus credential verification
- Principle of least privilege for kernel access

### 2. gRPC Communication
- Type-safe protocol buffers for all messages
- Secure TLS/SSL communication
- Automatic retry logic in client

### 3. Docker Integration
- Uses Docker API to map container IPs to user IDs
- Container labels store user metadata
- Network isolation through Docker networks

### 4. Role-Based Access Control (RBAC)
- Multiple user roles: USER, USER_PRIV, NODE, NODE_PRIV, ADMIN
- Hierarchical permission model
- Kernel access limited to privileged roles

---

## User Role Hierarchy

```
ADMIN           → Full system access (can do everything)
    ↓
NODE_PRIV       → Privileged node operations + kernel access
    ↓
USER_PRIV       → Privileged user operations + kernel access
    ↓
NODE            → Node operations only (no kernel access)
    ↓
USER            → Basic user operations (no kernel access)
```

**Kernel Access Permissions:**
- ✅ ADMIN
- ✅ NODE_PRIV
- ✅ USER_PRIV
- ❌ NODE
- ❌ USER

---

## Network Flow Diagram

```
┌─────────────────┐
│  User Container │ (userid=alice)
│  IP: 10.0.3.5   │
└────────┬────────┘
         │ TCP connection
         │ Port 9000
         ↓
┌─────────────────────────────────────┐
│    Kernel Service (on Node)         │
│  services/kernel/__main__.py        │
├─────────────────────────────────────┤
│  1. Accept connection               │
│  2. Extract IP → userid mapping     │
│  3. Create kernel_access request    │
└────────┬────────────────────────────┘
         │ gRPC call (TLS/SSL)
         │ kernel_access(userid='alice')
         ↓
┌─────────────────────────────────────┐
│    LeotestClient                    │
│  common/client.py                   │
├─────────────────────────────────────┤
│  1. Build protobuf message          │
│  2. Add authentication headers      │
│  3. Send via gRPC stub              │
└────────┬────────────────────────────┘
         │ Network (Protocol Buffers)
         ↓
┌─────────────────────────────────────┐
│  gRPC Stub                          │
│  common/leotest_pb2_grpc.py         │
├─────────────────────────────────────┤
│  1. Serialize request               │
│  2. Transport over network          │
│  3. Deserialize response            │
└────────┬────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────┐
│  Orchestrator gRPC Server           │
│  orchestrator/orchestrator.py       │
├─────────────────────────────────────┤
│  @CheckToken Decorator              │
│    ├─ Extract auth headers          │
│    ├─ Verify JWT or static token   │
│    └─ Set context credentials       │
│                                     │
│  kernel_access() Handler            │
│    ├─ Check caller role (NODE?)    │
│    ├─ Query DB for userid='alice'  │
│    ├─ Check alice's role            │
│    └─ Return GRANTED or DENIED      │
└────────┬────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────┐
│  MongoDB Database                   │
│  orchestrator/datastore.py          │
├─────────────────────────────────────┤
│  Collections:                       │
│    - users (role, access_token)     │
│    - nodes (status, location)       │
│    - jobs (schedules)               │
└─────────────────────────────────────┘

         Response flows back up ↑
```

---

## Initialization and Setup

### Orchestrator Startup

**File:** `orchestrator/__main__.py`

```
main() [Line 12-65]
├─ Line 13-48: Parses command line arguments
│  ├─ grpc-hostname/port
│  ├─ db-server/port/name
│  └─ admin-access-token, jwt-secret
├─ Line 50-60: Creates parameter dictionary
└─ Line 63-64: Creates and starts LeotestOrchestrator
```

**File:** `orchestrator/orchestrator.py`

```
LeotestOrchestrator.__init__() [Line 1676-1720]
├─ Line 1713-1716: Creates LeotestOrchestratorGrpc instance
│  └─ Connects to MongoDB database
└─ Line 1722-1746: Starts gRPC server
   ├─ Line 1729-1730: Adds service to server
   ├─ Line 1737-1742: Loads SSL certificates
   └─ Line 1743-1746: Starts server and waits
```

### Kernel Service Startup

**File:** `services/kernel/__main__.py`

```
main() [Line 62-163]
├─ Line 64-78: Parses command line arguments
│  ├─ nodeid (identity of this node)
│  ├─ grpc-hostname/port (orchestrator address)
│  └─ access-token (node's authentication token)
├─ Line 85-88: Creates LeotestClient instance
├─ Line 93-103: Creates TCP socket server
└─ Line 112-159: Main server loop
```

---

## Error Handling and Security

### Authentication Failures
- **Invalid Token:** Returns `grpc.StatusCode.UNAUTHENTICATED`
- **Missing Credentials:** Connection rejected immediately
- **Token Expired:** Re-initialization of gRPC channel (line 61 in client.py)

### Access Denial Scenarios
1. **User Not Found:** `state=1, message='userid does not exist'`
2. **Insufficient Privileges:** `state=1, message='does not have access to kernel services'`
3. **Permission Denied:** `state=1, message='permission denied: userid=X and role=Y'`

### Network Resilience
- **Retry Logic:** Client uses tenacity library for automatic retries
- **Timeout Handling:** All gRPC calls have configurable timeout (default 5 seconds)
- **Connection Refresh:** Failed connections trigger channel re-initialization

---

## Database Schema (MongoDB)

### Users Collection
```javascript
{
  _id: ObjectId,
  id: "alice",           // userid
  name: "Alice Smith",
  role: 3,              // LeotestUserRoles enum value
  team: "research",
  static_access_token: "sha256hash...",
  access_token: "dynamic_token..."
}
```

### Nodes Collection
```javascript
{
  _id: ObjectId,
  nodeid: "node-london-01",
  name: "London Node 1",
  description: "Test node in London",
  coords: "51.5074,-0.1278",
  location: "london",
  provider: "starlink",
  last_active: ISODate("2024-01-01T00:00:00Z"),
  scavenger_mode_active: false
}
```

---

## Configuration Files

### Global Configuration
**File:** `global_config.json`
- Database connection settings
- Blob storage credentials
- Network configuration

### Executor Configuration  
**File:** `executor-config.yaml`
- Node-specific settings
- Docker configuration
- Resource limits

### Docker Compose Files
- `docker-compose-orchestrator.yaml` - Orchestrator deployment
- `docker-compose-node.yaml` - Node deployment

---

## Summary

The LEOScope codebase implements a secure, distributed testbed for LEO satellite network experiments. The kernel service access verification flow demonstrates:

1. **Multi-layer security** with authentication and authorization
2. **Role-based access control** for privileged operations
3. **gRPC-based microservices** architecture
4. **Docker integration** for user isolation
5. **Centralized orchestration** with distributed execution

This architecture allows researchers to safely run experiments with kernel-level access while maintaining security through strict access control and audit trails.

---

## Related Files to Explore

- `common/leotest.proto` - Protocol buffer definitions
- `common/user.py` - User and role management classes
- `common/job.py` - Job scheduling and management
- `node/executor.py` - Experiment execution on nodes
- `orchestrator/datastore.py` - Database abstraction layer

---

## Developer Notes

### To trace a specific flow:
1. Start from the entry point (`__main__.py` files)
2. Follow the function calls in order
3. Check decorator implementations (especially `@CheckToken`)
4. Trace gRPC calls through the stub files
5. Examine database operations in datastore.py

### Common debugging points:
- Token validation: `orchestrator/orchestrator.py:CheckToken`
- gRPC communication: `common/client.py:LeotestClient`
- Command execution: `services/kernel/__main__.py:main()`
- Database queries: `orchestrator/datastore.py`
