# Quick Visual Guide: Main Flow

This is a simplified visual guide showing the main kernel access verification flow documented in this repository.

## The Problem
A user container needs to modify kernel parameters (like TCP congestion control), but containers are isolated and don't have direct kernel access.

## The Solution
LEOScope provides a secure kernel service that:
1. Authenticates the user
2. Verifies permissions with the orchestrator
3. Executes privileged commands if authorized

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER CONTAINER                              │
│                        (userid: alice)                              │
│                      IP: 10.0.3.5 on Docker network                 │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               │ 1. TCP Connect to port 9000
               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      KERNEL SERVICE (Node)                          │
│                  services/kernel/__main__.py                        │
├─────────────────────────────────────────────────────────────────────┤
│  Step 1: Accept connection from IP 10.0.3.5                         │
│  Step 2: get_userid_from_ipaddr(10.0.3.5)                          │
│          → Queries Docker API                                       │
│          → Matches IP to container                                  │
│          → Extracts userid from container labels                    │
│          → Returns "alice"                                          │
│                                                                     │
│  Step 3: Ask orchestrator: "Does alice have kernel access?"        │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               │ 2. gRPC Call: kernel_access(userid="alice")
               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      LEOTEST CLIENT                                 │
│                    common/client.py                                 │
├─────────────────────────────────────────────────────────────────────┤
│  def kernel_access(self, userid):                                   │
│      message = pb2.message_kernel_access()                          │
│      message.userid = userid                                        │
│      return self.grpc_stub.kernel_access(message, timeout=5)       │
│                                                                     │
│  → Automatically adds authentication headers:                       │
│     x-leotest-access-token: node-secret-token                      │
│     x-leotest-userid: node-london-01                               │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               │ 3. gRPC over TLS/SSL
               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   gRPC STUB (Generated Code)                        │
│                 common/leotest_pb2_grpc.py                          │
├─────────────────────────────────────────────────────────────────────┤
│  → Serializes message to binary protobuf format                     │
│  → Sends over secure gRPC channel                                   │
│  → Encrypts with TLS                                                │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               │ 4. Network transport
               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Central Server)                    │
│                  orchestrator/orchestrator.py                       │
├─────────────────────────────────────────────────────────────────────┤
│  BEFORE HANDLER: @CheckToken Decorator                              │
│  ├─ Extract from gRPC headers:                                      │
│  │  • x-leotest-access-token: node-secret-token                    │
│  │  • x-leotest-userid: node-london-01                             │
│  ├─ Verify token matches node's registered token                    │
│  ├─ Look up role for node-london-01 → role=NODE                    │
│  └─ Set context.creds_userid = "node-london-01"                    │
│     Set context.creds_role = NODE                                   │
│                                                                     │
│  HANDLER: def kernel_access(self, request, context):               │
│  ├─ Extract caller: userid=node-london-01, role=NODE               │
│  ├─ Check: Is caller a NODE or ADMIN? ✓ Yes (NODE)                │
│  ├─ Query database for verify_userid="alice"                       │
│  ├─ Database returns: role=USER_PRIV                                │
│  ├─ Check permissions:                                              │
│  │  • Is role USER_PRIV? ✓ YES → Access granted                   │
│  │  • Is role NODE_PRIV? No                                        │
│  │  • Is role ADMIN? No                                            │
│  └─ Return: state=0 (success)                                       │
│            message="alice has access to kernel services"            │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               │ 5. gRPC Response
               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      DATABASE QUERY                                 │
│                   MongoDB (orchestrator)                            │
├─────────────────────────────────────────────────────────────────────┤
│  Collection: users                                                  │
│  Query: { id: "alice" }                                             │
│  Result:                                                            │
│    {                                                                │
│      id: "alice",                                                   │
│      name: "Alice Smith",                                           │
│      role: 2,  // USER_PRIV                                         │
│      team: "research",                                              │
│      static_access_token: "sha256hash..."                           │
│    }                                                                │
└─────────────────────────────────────────────────────────────────────┘

               Response flows back up ↑
               
┌─────────────────────────────────────────────────────────────────────┐
│                    KERNEL SERVICE (Node)                            │
│                  services/kernel/__main__.py                        │
├─────────────────────────────────────────────────────────────────────┤
│  Step 4: Receive response: {'state': 0, 'message': '...'}          │
│                                                                     │
│  Step 5: Check response                                             │
│  if state == 0:  # SUCCESS                                          │
│      # Wait for command from user                                   │
│      command = clientsocket.recv(1024)                              │
│      # Example: "cca.change cubic"                                  │
│                                                                     │
│  Step 6: Execute command                                            │
│  if command.startswith("cca.change"):                               │
│      cca = command.split()[1]  # "cubic"                            │
│      output = change_cca(cca)                                       │
│      # Executes: sysctl -w net.ipv4.tcp_congestion_control=cubic   │
│                                                                     │
│  Step 7: Send result back to user                                   │
│  clientsocket.send(output)                                          │
│  clientsocket.close()                                               │
└──────────────┬──────────────────────────────────────────────────────┘
               │
               │ 6. Response: "net.ipv4.tcp_congestion_control = cubic"
               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         USER CONTAINER                              │
│                        (userid: alice)                              │
│                                                                     │
│  ✅ SUCCESS! Congestion control changed to cubic                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Functions and What They Do

### 1. get_userid_from_ipaddr(ip_addr, network)
**File:** `services/kernel/__main__.py:17-37`

```python
def get_userid_from_ipaddr(ip_addr, network='global-testbed_leotest-net'):
    userid = None
    client = docker.from_env()
    leotest_net = client.networks.get(network)
    containers = leotest_net.containers
    
    for container in containers:
        ip_addr_c = container.attrs['NetworkSettings']["Networks"][network]["IPAddress"]
        if ip_addr_c == ip_addr:
            labels = container.labels
            if "userid" in labels:
                userid = labels["userid"]
            break
    return userid
```

**What it does:** 
- Connects to Docker daemon
- Gets list of all containers on the network
- Finds container with matching IP address
- Extracts userid from container's labels
- Returns the userid or None

---

### 2. kernel_access(userid)
**File:** `common/client.py:638-642`

```python
def kernel_access(self, userid):
    log.info('sending request for kernel access verification; userid=%s' % userid)
    message = pb2.message_kernel_access()
    message.userid = userid 
    return self.grpc_stub.kernel_access(message, timeout=self.timeout)
```

**What it does:**
- Creates a protobuf message with userid
- Sends it to orchestrator via gRPC
- Authentication headers added automatically
- Returns the response from orchestrator

---

### 3. @CheckToken Decorator
**File:** `orchestrator/orchestrator.py:35-93`

```python
class CheckToken(object):
    def __call__(self, f):
        @wraps(f)
        def wrapped_function(slf, request, context):
            meta = context.invocation_metadata()
            creds = {'userid': None, 'access_token': None}
            
            # Extract credentials from gRPC headers
            for item in meta:
                if item[0] == "x-leotest-access-token":
                    creds['access_token'] = item[1]
                if item[0] == "x-leotest-userid":
                    creds['userid'] = item[1]
            
            # Verify token and role
            role = slf.verify_user(creds['userid'], creds['access_token'])
            if role is not None:
                context.creds_userid = creds['userid']
                context.creds_role = role
                return f(slf, request, context)
            
            # Authentication failed
            context.set_code(grpc.StatusCode.UNAUTHENTICATED)
            return empty_response()
        return wrapped_function
```

**What it does:**
- Runs before every RPC handler
- Extracts authentication tokens from HTTP headers
- Verifies token is valid
- Looks up user's role in database
- Sets credentials in context for handler to use
- Rejects request if authentication fails

---

### 4. kernel_access RPC Handler
**File:** `orchestrator/orchestrator.py:1538-1598`

```python
@CheckToken(pb2.message_kernel_access_response, 
            grpc.StatusCode.UNAUTHENTICATED, 
            "Invalid token") 
def kernel_access(self, request, context):
    _userid = context.creds_userid  # From @CheckToken
    _role = context.creds_role      # From @CheckToken
    verify_userid = request.userid  # User to verify
    
    # Check caller has permission to call this RPC
    if (_role == LeotestUserRoles.NODE.value) or \
       (_role == LeotestUserRoles.ADMIN.value): 
        
        # Look up target user in database
        user = self.db.get_user(verify_userid)
        if user:
            # Check if user has kernel access
            if (user.role == LeotestUserRoles.USER_PRIV.value) or \
               (user.role == LeotestUserRoles.NODE_PRIV.value) or \
               (user.role == LeotestUserRoles.ADMIN.value):
                state = 0  # Access granted
                message = 'userid=%s has access to kernel services' % verify_userid
            else:
                state = 1  # Access denied
                message = 'userid=%s does not have access' % verify_userid
        else:
            state = 1
            message = 'userid=%s does not exist' % verify_userid
    else:
        state = 1
        message = 'permission denied'
    
    return pb2.message_kernel_access_response(state=state, message=message)
```

**What it does:**
- Receives userid to verify
- Caller credentials already verified by @CheckToken
- Checks caller is NODE or ADMIN (only they can verify access)
- Queries database for target userid
- Checks if target user has privileged role
- Returns success or failure with detailed message

---

### 5. change_cca(cca)
**File:** `services/kernel/__main__.py:51-54`

```python
def change_cca(cca):
    cmd = f"sysctl -w net.ipv4.tcp_congestion_control={cca}"
    output = subprocess.check_output(cmd.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    return output
```

**What it does:**
- Takes congestion control algorithm name (e.g., "cubic", "bbr")
- Executes sysctl command to change kernel parameter
- Returns output from the command
- This is a privileged operation (modifies kernel)

---

## Security Check Points

The flow has **5 security checkpoints**:

1. **Container Isolation** - User runs in isolated container
2. **IP Mapping** - Verify IP belongs to a known user
3. **Token Authentication** - Verify node's access token
4. **Caller Authorization** - Only NODE/ADMIN can verify access
5. **User Permission** - Only privileged users get kernel access

If any checkpoint fails, access is denied.

---

## Role Hierarchy

```
ADMIN (0)       ━━━━━━━━┓
                        ┃  All have kernel access
NODE_PRIV (1)   ━━━━━━━━┫
                        ┃
USER_PRIV (2)   ━━━━━━━━┛

NODE (3)        ━━━━━━━━┓
                        ┃  No kernel access
USER (4)        ━━━━━━━━┛
```

---

## Error Scenarios

### Scenario 1: Invalid User
```
User "bob" doesn't exist in database
    ↓
kernel_access returns: state=1, message="userid bob does not exist"
    ↓
Kernel service sends "access_denied" to container
    ↓
Connection closed
```

### Scenario 2: Insufficient Privileges
```
User "charlie" has role=USER (basic user)
    ↓
kernel_access checks role: USER is not USER_PRIV/NODE_PRIV/ADMIN
    ↓
Returns: state=1, message="does not have access to kernel services"
    ↓
Access denied
```

### Scenario 3: Invalid Token
```
Node sends invalid access token
    ↓
@CheckToken decorator fails verification
    ↓
Returns: grpc.StatusCode.UNAUTHENTICATED
    ↓
Request rejected before reaching handler
```

---

## Time Flow

```
0ms   │ User connects
      ↓
10ms  │ IP lookup via Docker API
      ↓
15ms  │ Build gRPC message
      ↓
20ms  │ gRPC call to orchestrator
      ↓
25ms  │ Token verification
      ↓
30ms  │ Database query
      ↓
40ms  │ Permission check
      ↓
45ms  │ Response sent
      ↓
50ms  │ Command received
      ↓
55ms  │ sysctl executed
      ↓
60ms  │ Result sent to user
```

**Total latency:** ~60ms for full flow including kernel command execution

---

## Summary

The LEOScope kernel service provides secure, controlled access to privileged kernel operations through:

✅ **Authentication** - Multiple token verification layers
✅ **Authorization** - Role-based access control  
✅ **Isolation** - Docker containers can't directly access kernel
✅ **Audit** - All access attempts logged
✅ **Flexibility** - Support for multiple commands (CCA, BBR2, etc.)

This design allows researchers to safely run experiments requiring kernel modifications while maintaining system security.

---

For more details, see:
- [KERNEL_ACCESS_FLOW.md](./KERNEL_ACCESS_FLOW.md) - Complete 19-step flow
- [CODEBASE_FLOW_DOCUMENTATION.md](./CODEBASE_FLOW_DOCUMENTATION.md) - Architecture overview
- [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md) - Quick reference guide
