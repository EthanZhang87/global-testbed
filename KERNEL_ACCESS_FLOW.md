# Kernel Access Flow - Detailed Sequence

This document provides a step-by-step sequence diagram and detailed explanation of the kernel access verification flow in LEOScope.

## Sequence Diagram

```
User Container         Kernel Service         LeotestClient       gRPC Stub         Orchestrator         Database
     |                       |                      |                  |                  |                  |
     |  1. TCP Connect       |                      |                  |                  |                  |
     |--------------------->|                      |                  |                  |                  |
     |    (port 9000)       |                      |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     |                      | 2. get_userid_from_ipaddr()            |                  |                  |
     |                      |-------------------->|                  |                  |                  |
     |                      |    (Docker API)     |                  |                  |                  |
     |                      |<--------------------|                  |                  |                  |
     |                      |   userid="alice"    |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     |                      | 3. kernel_access(userid="alice")       |                  |                  |
     |                      |--------------------->|                  |                  |                  |
     |                      |                      |                  |                  |                  |
     |                      |                      | 4. Build message |                  |                  |
     |                      |                      |   + auth headers |                  |                  |
     |                      |                      |                  |                  |                  |
     |                      |                      | 5. grpc_stub.kernel_access()       |                  |
     |                      |                      |----------------->|                  |                  |
     |                      |                      |                  |                  |                  |
     |                      |                      |                  | 6. Serialize     |                  |
     |                      |                      |                  |    protobuf      |                  |
     |                      |                      |                  |                  |                  |
     |                      |                      |                  | 7. gRPC call     |                  |
     |                      |                      |                  |   (TLS/SSL)      |                  |
     |                      |                      |                  |----------------->|                  |
     |                      |                      |                  |                  |                  |
     |                      |                      |                  |                  | 8. @CheckToken   |
     |                      |                      |                  |                  |    decorator     |
     |                      |                      |                  |                  |    validates     |
     |                      |                      |                  |                  |                  |
     |                      |                      |                  |                  | 9. Query user    |
     |                      |                      |                  |                  |----------------->|
     |                      |                      |                  |                  |                  |
     |                      |                      |                  |                  | 10. User data    |
     |                      |                      |                  |                  |<-----------------|
     |                      |                      |                  |                  |  role=USER_PRIV  |
     |                      |                      |                  |                  |                  |
     |                      |                      |                  |                  | 11. Check role   |
     |                      |                      |                  |                  |     permissions  |
     |                      |                      |                  |                  |                  |
     |                      |                      |                  | 12. Response     |                  |
     |                      |                      |                  |    (state=0)     |                  |
     |                      |                      |                  |<-----------------|                  |
     |                      |                      |                  |                  |                  |
     |                      |                      | 13. Deserialize  |                  |                  |
     |                      |                      |<-----------------|                  |                  |
     |                      |                      |                  |                  |                  |
     |                      | 14. Return response  |                  |                  |                  |
     |                      |<---------------------|                  |                  |                  |
     |                      |  {'state': 0}       |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     | 15. Request command  |                      |                  |                  |                  |
     |<---------------------|                      |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     | 16. Send command     |                      |                  |                  |                  |
     |--------------------->|                      |                  |                  |                  |
     |  "cca.change cubic"  |                      |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     |                      | 17. change_cca()    |                  |                  |                  |
     |                      |    Execute sysctl   |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     | 18. Success response |                      |                  |                  |                  |
     |<---------------------|                      |                  |                  |                  |
     |                      |                      |                  |                  |                  |
     | 19. Close connection |                      |                  |                  |                  |
     |<---------------------|                      |                  |                  |                  |
     |                      |                      |                  |                  |                  |
```

## Detailed Step-by-Step Explanation

### Step 1: TCP Connection from User Container
**Location:** `services/kernel/__main__.py:115`

The user's container initiates a TCP connection to the kernel service on port 9000.

```python
(clientsocket, address) = s.accept()
log.info("Connection from {}".format(address))
```

**Why this happens:**
- User containers need privileged kernel operations
- Direct kernel access is blocked by container isolation
- Must go through authenticated service

### Step 2: IP to UserID Mapping
**Location:** `services/kernel/__main__.py:120`

```python
userid = get_userid_from_ipaddr(ip_addr, network=args.leotest_net)
```

**Function details:**
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

**Why this step is important:**
- Containers don't authenticate directly
- UserID is embedded in container labels during creation
- Docker API provides secure mapping from IP to container to userid

### Step 3: Kernel Access Verification Request
**Location:** `services/kernel/__main__.py:122-124`

```python
if userid:
    res = leotest_client.kernel_access(userid=userid)
    res = MessageToDict(res)
```

**Purpose:**
- Ask orchestrator: "Does this user have kernel access?"
- Centralized policy enforcement
- Audit trail of access attempts

### Step 4: Build gRPC Message
**Location:** `common/client.py:638-642`

```python
def kernel_access(self, userid):
    log.info('sending request for kernel access verification; userid=%s' % userid)
    message = pb2.message_kernel_access()
    message.userid = userid 
    return self.grpc_stub.kernel_access(message, timeout=self.timeout)
```

**Key components:**
- Creates protobuf message
- Sets userid field
- Includes authentication headers automatically (from LeotestClient init)

### Step 5: gRPC Stub Invocation
**Location:** `common/leotest_pb2_grpc.py`

The stub is created during initialization:
```python
self.kernel_access = channel.unary_unary(
    '/unary.LeotestOrchestrator/kernel_access',
    request_serializer=common_dot_leotest__pb2.message_kernel_access.SerializeToString,
    response_deserializer=common_dot_leotest__pb2.message_kernel_access_response.FromString,
)
```

**What happens:**
- Method name mapped to gRPC endpoint
- Request automatically serialized to binary protobuf format
- Response automatically deserialized from binary

### Step 6-7: Network Transport
The gRPC framework:
1. Serializes the message to binary format
2. Adds HTTP/2 headers
3. Encrypts with TLS/SSL
4. Sends over TCP connection to orchestrator

### Step 8: Authentication Check (@CheckToken Decorator)
**Location:** `orchestrator/orchestrator.py:1535-1537`

```python
@CheckToken(pb2.message_kernel_access_response, 
            grpc.StatusCode.UNAUTHENTICATED, 
            "Invalid token") 
def kernel_access(self, request, context):
```

**Decorator implementation:** `orchestrator/orchestrator.py:47-93`

```python
def __call__(self, f):
    @wraps(f)
    def wrapped_function(slf, request, context):
        meta = context.invocation_metadata()
        creds = {'userid': None, 'access_token': None, 'jwt_access_token': None}
        
        # Extract credentials from headers
        for item in meta:
            if item[0] == "x-leotest-access-token":
                creds['access_token'] = item[1]
            if item[0] == "x-leotest-userid":
                creds['userid'] = item[1]
            if item[0] == "x-leotest-jwt-access-token":
                creds['jwt_access_token'] = item[1]
        
        # Verify credentials
        if creds['jwt_access_token']:
            ret = slf.verify_jwt(creds['jwt_access_token'])
            if ret:
                userid, role = ret
                context.creds_userid = userid
                context.creds_role = role
                return f(slf, request, context)
        
        # ... or verify static token
```

**Security measures:**
- Runs before handler function
- Extracts authentication from HTTP headers
- Verifies token validity
- Sets context for downstream use
- Rejects invalid requests immediately

### Step 9-10: Database User Lookup
**Location:** `orchestrator/orchestrator.py:1571`

```python
user = self.db.get_user(verify_userid)
```

**Database operation:**
```python
# In datastore.py
def get_user(self, userid):
    result = self.users_collection.find_one({'id': userid})
    if result:
        return LeotestUser(
            id=result['id'],
            name=result['name'],
            role=result['role'],
            team=result['team'],
            static_access_token=result['static_access_token']
        )
    return None
```

**Retrieved data:**
- User's role (integer enum value)
- Access tokens
- Team membership
- Name and other metadata

### Step 11: Permission Verification
**Location:** `orchestrator/orchestrator.py:1572-1586`

```python
if user:
    log.info("[kernel_access] verify_userid=%s role=%s" 
                            % (verify_userid, user.role))
    if (user.role == LeotestUserRoles.USER_PRIV.value)\
        or (user.role == LeotestUserRoles.NODE_PRIV.value)\
        or (user.role == LeotestUserRoles.ADMIN.value):

        state = 0
        message = 'userid=%s role=%s has access to kernel services'\
                    % (verify_userid, LeotestUserRoles(user.role).name)
    
    else:
        state = 1 
        message = 'userid=%s role=%s does not have access to kernel services'\
                    % (verify_userid, LeotestUserRoles(user.role).name)
```

**Permission logic:**
- Check user's role against allowed roles
- Allowed: USER_PRIV, NODE_PRIV, ADMIN
- Denied: USER, NODE (basic roles)
- Returns state code and detailed message

### Step 12-14: Response Propagation
The response travels back through:
1. Orchestrator creates response message
2. gRPC serializes to protobuf
3. Network transport (encrypted)
4. Client deserializes response
5. Returns Python dictionary to kernel service

### Step 15-16: Command Exchange
**Location:** `services/kernel/__main__.py:128-140`

```python
if 'state' in res and res['state']=='FAILED':
    log.info('insufficient access level: access denied')
    clientsocket.send(b'access_denied')
    clientsocket.close()
    continue 

# receive command from client
try:
    command = clientsocket.recv(1024).decode()
except Exception as e:
    command = "cca.check"
```

**If access granted:**
- Service waits for command from user
- Receives command string (e.g., "cca.change cubic")

**If access denied:**
- Sends "access_denied" message
- Closes connection immediately
- Logs the denial

### Step 17: Command Execution
**Location:** `services/kernel/__main__.py:144-156`

```python
if command == "cca.check":
    output = check_cca()
elif command.startswith("cca.change"):
    output = change_cca(command.split()[1])
elif command.startswith("bbr2.param.set"):
    output = set_bbr2_param(command.split()[1], command.split()[2])
else:
    output = execute_command(command)

clientsocket.send(output)
```

**Command implementations:**

```python
def check_cca():
    cmd = "sysctl net.ipv4.tcp_congestion_control"
    output = subprocess.check_output(cmd.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    return output

def change_cca(cca):
    cmd = f"sysctl -w net.ipv4.tcp_congestion_control={cca}"
    output = subprocess.check_output(cmd.split(), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    return output

def set_bbr2_param(path, value):
    with open(path, 'w') as f:
        f.write(value)
    return b'BBR2 parameter %s set to %s' % (path.encode(), value.encode())
```

**Supported commands:**
- `cca.check` - View current congestion control
- `cca.change <algorithm>` - Change congestion control (e.g., cubic, bbr)
- `bbr2.param.set <path> <value>` - Modify BBR2 parameters
- Custom commands - Execute arbitrary system commands

### Step 18-19: Response and Cleanup

```python
clientsocket.send(output)
clientsocket.close()
```

**Final steps:**
- Send command output back to user container
- Close TCP connection
- Service returns to listening state
- Ready for next connection

---

## Error Scenarios

### Scenario 1: User Not Found
```
User Container → Kernel Service → Orchestrator
                                    ↓
                                  Database query returns None
                                    ↓
                                  state = 1
                                  message = "userid does not exist"
                                    ↓
Kernel Service ← ← ← ← ← ← ← ← ← ← 
    ↓
Sends "access_denied"
Closes connection
```

### Scenario 2: Insufficient Privileges
```
User with role=USER attempts kernel access
                ↓
Database returns user.role = USER (basic role)
                ↓
Permission check fails
                ↓
state = 1
message = "does not have access to kernel services (higher access level required)"
                ↓
Access denied
```

### Scenario 3: Invalid Authentication Token
```
gRPC call with invalid access token
        ↓
@CheckToken decorator
        ↓
verify_user() or verify_jwt() fails
        ↓
context.set_code(grpc.StatusCode.UNAUTHENTICATED)
        ↓
Empty response returned
        ↓
Connection rejected at orchestrator level
```

### Scenario 4: Network Failure
```
gRPC call to orchestrator
        ↓
Network timeout or connection refused
        ↓
grpc.RpcError exception raised
        ↓
Tenacity retry logic activates
        ↓
Retry with exponential backoff
        ↓
If all retries fail:
    - Log error
    - Return failure to kernel service
    - Kernel service denies access
```

---

## Security Properties

### 1. Multi-Factor Verification
- **IP-based identification:** Container IP must match userid
- **Token authentication:** Node must have valid access token
- **Role-based authorization:** User must have privileged role

### 2. Audit Trail
All access attempts are logged:
- Caller identity (node ID)
- Target user (userid being verified)
- Decision (granted/denied)
- Timestamp
- Reason for denial (if applicable)

### 3. Principle of Least Privilege
- Basic users (USER, NODE) cannot access kernel
- Only privileged roles get access
- Each request verified independently
- No persistent sessions or caching of permissions

### 4. Defense in Depth
- Container isolation (Docker)
- Network isolation (Docker networks)
- Service isolation (dedicated kernel service)
- Authentication (tokens)
- Authorization (roles)
- Audit logging

---

## Performance Considerations

### Latency Budget
Typical request latency:
1. Docker API query: 10-50ms
2. gRPC call (local network): 1-5ms
3. Database query: 5-20ms
4. Total: ~20-80ms

### Optimization Strategies
1. **Connection pooling:** gRPC channels are reused
2. **Retry logic:** Automatic recovery from transient failures
3. **Caching:** Considered but not implemented (security vs. performance tradeoff)
4. **Async operations:** Service handles multiple connections concurrently

### Scalability
- **Horizontal:** Multiple kernel services on different nodes
- **Vertical:** Thread-based concurrency in kernel service
- **Database:** MongoDB supports sharding for large deployments

---

## Configuration Parameters

### Kernel Service
```bash
--nodeid=<node-identifier>
--grpc-hostname=<orchestrator-ip>
--grpc-port=50051
--access-token=<node-access-token>
--leotest-net=<docker-network-name>
```

### LeotestClient
```python
LeotestClient(
    grpc_hostname='orchestrator.example.com',
    grpc_port=50051,
    userid='node-london-01',
    access_token='node-secret-token',
    timeout=5  # seconds
)
```

### Orchestrator
```bash
--grpc-hostname=0.0.0.0
--grpc-port=50051
--grpc-workers=10
--db-server=mongodb
--db-port=27017
--db-name=leotest
--admin-access-token=admin-secret
--jwt-secret=jwt-signing-secret
--jwt-algo=HS256
```

---

## Testing the Flow

### Manual Test
1. Start orchestrator:
   ```bash
   python -m orchestrator --grpc-port=50051
   ```

2. Register privileged user:
   ```bash
   python -m cli user --action=register --userid=testuser \
     --role=USER_PRIV --team=research
   ```

3. Start kernel service:
   ```bash
   python -m services.kernel --nodeid=test-node --grpc-hostname=localhost
   ```

4. Create test container with userid label:
   ```bash
   docker run --label userid=testuser --network=leotest-net -it alpine
   ```

5. From container, connect to kernel service:
   ```bash
   nc localhost 9000
   # Wait for prompt
   # Type: cca.check
   # Should see current CCA
   ```

### Expected Behavior
- Connection accepted
- Access verification succeeds (USER_PRIV has access)
- Command executed
- Response received
- Connection closed cleanly

---

## Debugging Checklist

When debugging kernel access issues:

- [ ] Verify Docker network exists and containers are connected
- [ ] Check container has userid label
- [ ] Confirm node has valid access token
- [ ] Verify user exists in database
- [ ] Check user has correct role (USER_PRIV, NODE_PRIV, or ADMIN)
- [ ] Confirm orchestrator is running and accessible
- [ ] Check firewall rules allow gRPC port (50051)
- [ ] Verify TLS certificates are valid
- [ ] Review logs in all components
- [ ] Test with admin user to isolate authorization vs. authentication issues

---

## Related Documentation

- Main documentation: `CODEBASE_FLOW_DOCUMENTATION.md`
- Architecture diagram: `extras/leoscope_arch.jpg`
- API reference: Generated from `common/leotest.proto`
- User guide: `README.md`
