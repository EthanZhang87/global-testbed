# Additional System Flows in LEOScope

This document covers other important flows in the LEOScope testbed beyond kernel access verification.

---

## Flow 1: Job Scheduling and Execution

### Overview
Users schedule experiments on measurement nodes through the orchestrator. The flow involves job scheduling, node polling, deployment, execution, and result upload.

### Components
- CLI/Website (user interface)
- Orchestrator (central scheduler)
- Node Service (experiment executor)
- Azure Blob Storage (artifact storage)

### Detailed Flow

```
User → CLI → Orchestrator → Database → Node → Executor → Azure Blob → User
```

#### Step 1: User Schedules Job

**File:** `cli/__main__.py`

```python
# User runs CLI command:
python3 -m cli job --action=schedule \
    --userid=alice \
    --nodeid=node-london \
    --jobid=exp-123 \
    --schedule="*/5 * * * *" \
    --start-date="2024-01-01 00:00:00" \
    --end-date="2024-01-02 00:00:00" \
    --length=300
```

**What happens:**
1. CLI parses arguments
2. Creates LeotestClient instance
3. Calls `schedule_job()` method

#### Step 2: gRPC Call to Orchestrator

**File:** `common/client.py:191-285`

```python
def schedule_job(self, jobid, nodeid, type_name, params_mode, params_deploy, 
                params_execute, params_finish, schedule, start_date, end_date, 
                length, overhead, server=None, trigger=None, experiment_config=""):
    
    for attempt in self._retry():
        with attempt:
            _type = pb2.job_type.Value(type_name.upper())
            message = pb2.message_schedule_job(
                id = jobid,
                nodeid = nodeid,
                type = _type,
                params = {
                    'mode': params_mode,
                    'deploy': params_deploy,
                    'execute': params_execute,
                    'finish': params_finish
                },
                schedule = schedule, 
                start_date = start_date,
                end_date = end_date, 
                length_secs = length,
                overhead = overhead,
                trigger = trigger,
                config = experiment_config)
            
            return self.grpc_stub.schedule_job(message, timeout=self.timeout)
```

**Key parameters:**
- **jobid:** Unique identifier for the experiment
- **nodeid:** Target node for deployment
- **type_name:** "CRON" or "ATQ" (recurring or one-time)
- **schedule:** Crontab string (for CRON jobs)
- **start_date/end_date:** Valid time window
- **length:** Duration of each run in seconds
- **overhead:** Whether job counts toward resource limits
- **trigger:** Optional conditional execution logic

#### Step 3: Orchestrator Processes Schedule Request

**File:** `orchestrator/orchestrator.py:464-627`

```python
@CheckToken(pb2.message_schedule_job_response, 
            grpc.StatusCode.UNAUTHENTICATED, 
            "Invalid token")
def schedule_job(self, request, context):
    userid = context.creds_userid
    role = context.creds_role
    
    # Extract job parameters
    id = request.id
    nodeid = request.nodeid 
    _type = request.type 
    schedule = request.schedule
    start_date = request.start_date 
    end_date = request.end_date 
    length_secs = request.length_secs
    overhead = request.overhead
    server = request.server if request.HasField('server') else None
    
    # Check for schedule conflicts
    if overhead == True:
        exists1, jobs_nodeid = self.db.get_jobs_by_nodeid(nodeid=nodeid)
        if server:
            exists2, jobs_server = self.db.get_jobs_by_nodeid(nodeid=server)
            
        # Check conflicts with existing jobs
        conflicts = check_schedule_conflict_list(curr_job, job_list)
        
        if len(conflicts) > 0:
            state = 1
            msg = "schedule conflict: ..."
            return pb2.message_schedule_job_response(state=state, message=msg)
    
    # Verify trigger syntax (if provided)
    if trigger != None:
        valid, err_msg = verify_trigger_default(trigger)
        if not valid:
            state = 1 
            msg = err_msg
            return pb2.message_schedule_job_response(state=state, message=msg)
    
    # Create job object
    if type_name.lower() == 'cron':
        job = LeotestJobCron(
            jobid=id, 
            nodeid=nodeid, 
            userid=userid,
            job_params=params,
            start_date=start_date, 
            end_date=end_date, 
            length_secs=length_secs,
            overhead=overhead,
            server=server,
            trigger=trigger,
            config=config)
        job.set_schedule_cron(schedule)
    else:
        job = LeotestJobAtq(...)
    
    # Save to database
    state, msg = self.db.add_job(job)
    
    return pb2.message_schedule_job_response(state=state, message=msg)
```

**Validation steps:**
1. Authenticate user (via @CheckToken)
2. Check for scheduling conflicts
3. Validate trigger syntax
4. Create job object
5. Save to MongoDB
6. Return success/failure response

#### Step 4: Node Polls for Jobs

**File:** `node/executor.py` (simplified, actual code is more complex)

```python
# Node runs continuously polling for jobs
while True:
    # Get jobs scheduled for this node
    response = leotest_client.get_jobs_by_nodeid(nodeid=nodeid)
    jobs = MessageToDict(response)['jobs']
    
    for job in jobs:
        # Check if job should run now
        if should_run_now(job):
            # Execute job
            execute_job(job)
    
    # Sleep before next poll
    time.sleep(polling_interval)
```

**What the node does:**
1. Periodically queries orchestrator for jobs
2. Evaluates job schedules (cron or atq)
3. Checks trigger conditions
4. Spawns executor for ready jobs

#### Step 5: Job Execution

**File:** `node/executor.py:255-727`

The executor goes through three phases:

##### Phase 1: Deploy
```python
def deploy_job(self):
    # Download experiment config from blob storage
    # Pull Docker image
    # Prepare execution environment
```

##### Phase 2: Execute
```python
def execute_job(self):
    # Create Docker container with experiment
    # Mount volumes
    # Set environment variables
    # Run container
    # Stream logs
```

**Example Docker run:**
```python
output = self.client.containers.run(
    image=docker_image,
    name=container_name,
    network=network,
    volumes=volumes,
    environment=environment,
    command=command,
    labels=labels,
    detach=False,  # Wait for completion
    stdout=True,
    stderr=True,
    stream=True
)
```

##### Phase 3: Finish
```python
def finish_job(self):
    # Upload logs to Azure Blob Storage
    # Update run status in orchestrator
    # Clean up local files
    # Remove container
```

#### Step 6: Status Updates

Throughout execution, the node updates status:

```python
def update_run(self, runid, jobid, nodeid, userid, start_time, 
               status, status_message, end_time=None, blob_url=''):
    
    message = pb2.message_update_run(run={
        'runid': runid, 
        'jobid': jobid,
        'nodeid': nodeid, 
        'userid': userid, 
        'start_time': start_time,
        'end_time': end_time,
        'blob_url': blob_url, 
        'status': status,
        'status_message': status_message
    })
    
    return self.grpc_stub.update_run(message, timeout=self.timeout)
```

**Status values:**
- `DEPLOYING` - Pulling image, setting up
- `RUNNING` - Experiment is executing
- `UPLOADING` - Uploading results
- `COMPLETED` - Successfully finished
- `FAILED` - Error occurred

#### Step 7: User Retrieves Results

**File:** `common/client.py:398-462`

```python
def download_runs(self, local_path, runid=None, jobid=None, 
                  nodeid=None, time_range=None, limit=None):
    
    # Query orchestrator for run metadata
    res = self.get_runs(runid=runid, jobid=jobid, nodeid=nodeid, 
                        time_range=time_range, limit=limit)
    
    # Download from Azure Blob Storage
    for run in MessageToDict(res)['runs']:
        nodeid = run['nodeid']
        jobid = run['jobid']
        runid = run['runid']
        start_time = datetimeParse(run['startTime'])
        
        remote_path = os.path.join(
            artifact_path, nodeid, jobid,
            str(start_time.year), str(start_time.month), 
            str(start_time.day), runid
        )
        
        blob_storage.download(remote_path, local_path)
```

---

## Flow 2: Node Registration and Heartbeat

### Overview
Nodes must register with the orchestrator and maintain connectivity through heartbeats.

### Registration Flow

#### Step 1: Admin Registers Node

```bash
python -m cli node --action=register \
    --userid=admin \
    --access-token=admin-token \
    --nodeid=node-london-01 \
    --name="London Node" \
    --location=london \
    --coords="51.5074,-0.1278"
```

#### Step 2: Orchestrator Creates Node Entry

**File:** `orchestrator/orchestrator.py:1158-1211`

```python
@CheckToken(pb2.message_register_node_response, 
            grpc.StatusCode.UNAUTHENTICATED, 
            "Invalid token")
def register_node(self, request, context):
    userid = context.creds_userid
    role = context.creds_role
    
    if role == LeotestUserRoles.ADMIN.value:
        nodeid = request.node.nodeid
        name = request.node.name
        team = request.node.description
        
        # Generate access token for node
        hl = hashlib.sha256()
        hl.update(nodeid.encode('utf-8'))
        hl.update(name.encode('utf-8'))
        hl.update(team.encode('utf-8'))
        access_token = hl.hexdigest()
        
        # Create node user account
        node_user = LeotestUser(
            id=nodeid, 
            name=name, 
            role=LeotestUserRoles.NODE.value, 
            team=team,
            static_access_token=access_token
        )
        self.db.add_user(node_user)
        
        # Create node entry
        state, message = self.db.register_node(
            LeotestNode(**MessageToDict(request)['node'])
        )
        
        message += " access_token=%s" % access_token
        
    return pb2.message_register_node_response(state=state, message=message)
```

**What gets created:**
1. User account for the node (role=NODE)
2. Node entry with location, coordinates, provider
3. Access token for authentication

#### Step 3: Node Starts and Sends Heartbeats

**File:** Node service (simplified)

```python
def heartbeat_loop():
    while True:
        try:
            response = leotest_client.send_heartbeat(nodeid=nodeid)
            if response.received:
                log.info("Heartbeat acknowledged")
        except Exception as e:
            log.error("Heartbeat failed: %s" % str(e))
        
        time.sleep(heartbeat_interval)  # e.g., 30 seconds
```

#### Step 4: Orchestrator Updates Node Status

**File:** `orchestrator/orchestrator.py:144-169`

```python
@CheckToken(pb2.message_heartbeat_response, 
            grpc.StatusCode.UNAUTHENTICATED, 
            "Invalid token")
def report_heartbeat(self, request, context):
    nodeid = request.nodeid
    _userid = context.creds_userid
    _role = context.creds_role
    
    if nodeid == _userid:
        log.info("[heartbeat] marked nodeid=%s" % (nodeid))
        self.db.mark_node(nodeid)  # Update last_active timestamp
        result = {'received': True}
    else:
        result = {'received': False}
    
    return pb2.message_heartbeat_response(**result)
```

**Database update:**
```python
def mark_node(self, nodeid):
    self.nodes_collection.update_one(
        {'nodeid': nodeid},
        {'$set': {'last_active': datetime.utcnow()}}
    )
```

### Node Liveness Queries

Users/admins can query active nodes:

```python
# Get nodes active in last 10 minutes
nodes = client.get_nodes(active=True, activeThres=600)
```

**File:** `orchestrator/orchestrator.py:1254-1282`

```python
def get_nodes(self, request, context):
    nodeid = request.nodeid if request.HasField('nodeid') else None
    active = request.active if request.HasField('active') else False
    activeThres = request.activeThres if request.HasField('activeThres') else 600
    
    nodes = self.db.get_nodes(nodeid, location, name, provider, 
                              active, activeThres)
    
    return pb2.message_get_nodes_response(nodes=nodes)
```

**Database query:**
```python
def get_nodes(self, nodeid, location, name, provider, active, activeThres):
    query = {}
    
    if nodeid:
        query['nodeid'] = nodeid
    
    if active:
        threshold_time = datetime.utcnow() - timedelta(seconds=activeThres)
        query['last_active'] = {'$gte': threshold_time}
    
    return list(self.nodes_collection.find(query))
```

---

## Flow 3: Task Scheduling (Server Setup)

### Overview
Some experiments require a server component on a different node. The client node schedules a task on the server node.

### Example Scenario
```
Experiment: Iperf3 bandwidth test
Client: node-london
Server: node-paris
```

### Flow

#### Step 1: Client Node Schedules Task on Server

**File:** Node executor (when processing job with server field)

```python
# Job has server='node-paris'
# Client is 'node-london'

# Schedule server task
taskid = generate_task_id()
leotest_client.schedule_task(
    taskid=taskid,
    runid=runid,
    jobid=jobid,
    nodeid='node-paris',  # Server node
    _type='SERVER_SETUP',
    ttl_secs=300  # Task expires after 5 minutes
)
```

#### Step 2: Server Node Polls for Tasks

```python
# On node-paris
while True:
    tasks = leotest_client.get_tasks(nodeid='node-paris')
    
    for task in tasks:
        if task.status == 'TASK_SCHEDULED':
            execute_task(task)
            
            # Update status
            leotest_client.update_task(
                taskid=task.taskid,
                status='TASK_COMPLETE'
            )
```

#### Step 3: Client Node Waits for Task Completion

```python
# On node-london (client)
timeout = 300  # 5 minutes
start_time = time.time()

while time.time() - start_time < timeout:
    tasks = leotest_client.get_tasks(taskid=taskid)
    
    if tasks[0].status == 'TASK_COMPLETE':
        # Server is ready, start client
        start_experiment()
        break
    
    time.sleep(5)  # Poll every 5 seconds
```

#### Step 4: Orchestrator Manages Task State

**File:** `orchestrator/orchestrator.py:1416-1532`

```python
def schedule_task(self, request, context):
    _type = request.task.type
    taskid = request.task.taskid
    runid = request.task.runid 
    jobid = request.task.jobid
    nodeid = request.task.nodeid 
    ttl_secs = request.task.ttl_secs 
    
    task = LeotestTask(
        taskid=taskid, 
        runid=runid, 
        jobid=jobid, 
        nodeid=nodeid, 
        task_type=_type,
        ttl_secs=ttl_secs
    )
    task.set_status(1)  # TASK_SCHEDULED
    
    state, message = self.db.schedule_task(task)
    
    return pb2.message_schedule_task_response(state=state, message=message)

def get_tasks(self, request, context):
    taskid = request.taskid if request.HasField('taskid') else None
    runid = request.runid if request.HasField('runid') else None
    jobid = request.jobid if request.HasField('jobid') else None
    nodeid = request.nodeid if request.HasField('nodeid') else None
    
    tasks = self.db.get_tasks(taskid=taskid, runid=runid, 
                              jobid=jobid, nodeid=nodeid)
    
    return pb2.message_get_tasks_response(tasks=tasks)

def update_task(self, request, context):
    taskid = request.taskid 
    status = request.status 
    
    state, message = self.db.update_task(taskid=taskid, status=status)
    
    return pb2.message_update_task_response(state=state, message=message)
```

---

## Flow 4: User Management

### Overview
Admin users can create, modify, and delete user accounts with different privilege levels.

### User Registration

```bash
python -m cli user --action=register \
    --userid=bob \
    --name="Bob Smith" \
    --role=USER_PRIV \
    --team=research
```

**File:** `orchestrator/orchestrator.py:238-290`

```python
def register_user(self, request, context):
    id = request.id
    name = request.name
    role = request.role
    team = request.team
    
    _userid = context.creds_userid
    _role = context.creds_role
    
    if _role == LeotestUserRoles.ADMIN.value:
        # Generate access token
        hl = hashlib.sha256()
        hl.update(id.encode('utf-8'))
        hl.update(name.encode('utf-8'))
        hl.update(team.encode('utf-8'))
        access_token = hl.hexdigest()
        
        state, msg = self.db.add_user(
            LeotestUser(id, name, role, team, 
                       static_access_token=access_token)
        )
        
        if state == 0:
            msg += " access_token=%s" % access_token
    else:
        state = 1
        msg = "permission denied"
    
    return pb2.message_register_user_response(state=state, message=msg)
```

### User Role Modification

```bash
python -m cli user --action=modify \
    --userid=bob \
    --role=ADMIN
```

**File:** `orchestrator/orchestrator.py:335-373`

```python
def modify_user(self, request, context):
    id = request.id
    name = request.name
    role = request.role
    team = request.team
    
    _userid = context.creds_userid
    _role = context.creds_role
    
    if _role == LeotestUserRoles.ADMIN.value:
        state, msg = self.db.modify_user(
            LeotestUser(id, name, role, team)
        )
    else:
        state = 1
        message = "permission denied"
    
    return pb2.message_modify_user_response(state=state, message=msg)
```

---

## Flow 5: Global Configuration Management

### Overview
The orchestrator maintains global configuration that all nodes can access.

### Update Configuration

```bash
python -m cli config --action=update \
    --path=global_config.json
```

**Example global_config.json:**
```json
{
  "datastore": {
    "blob": {
      "connectionString": "DefaultEndpointsProtocol=https;...",
      "container": "experiments",
      "artifactPath": "jobs"
    }
  },
  "network": {
    "docker_network": "global-testbed_leotest-net"
  }
}
```

**File:** `orchestrator/orchestrator.py:171-208`

```python
def update_global_config(self, request, context):
    _userid = context.creds_userid
    _role = context.creds_role
    
    if _role == LeotestUserRoles.ADMIN.value:
        config = MessageToDict(request.config) 
        state, msg = self.db.update_config(config)
    else:
        state = 1
        msg = "permission denied"
    
    return pb2.message_update_global_config_response(state=state, message=msg)
```

### Get Configuration

Nodes retrieve configuration on startup:

```python
response = leotest_client.get_config()
config = MessageToDict(response)['config']

# Extract Azure connection string
connection_string = config['datastore']['blob']['connectionString']
```

---

## Summary of System Flows

### 1. Job Scheduling
User → CLI → Orchestrator → Database → Node → Executor → Storage

### 2. Node Management
Admin → Register → Orchestrator → Node starts → Heartbeats

### 3. Task Coordination
Client Node → Schedule Task → Server Node → Executes → Client Proceeds

### 4. User Administration
Admin → User CRUD → Orchestrator → Database → Tokens Generated

### 5. Configuration
Admin → Update Config → Orchestrator → Nodes Pull → Use in Experiments

### 6. Kernel Access (detailed in KERNEL_ACCESS_FLOW.md)
Container → Kernel Service → Client → Orchestrator → Permission Check

---

## Common Patterns Across Flows

### 1. Authentication via @CheckToken
All orchestrator RPC methods use this decorator

### 2. Role-Based Authorization
Different operations require different roles:
- ADMIN: All operations
- NODE: Heartbeats, job queries, task management
- USER_PRIV: Job scheduling, kernel access
- USER: Basic job scheduling only

### 3. gRPC Communication
All inter-component communication uses gRPC with:
- TLS encryption
- Protocol buffers
- Automatic retries

### 4. Database as Source of Truth
MongoDB stores:
- Users and roles
- Nodes and their status
- Jobs and schedules
- Tasks
- Run history
- Global configuration

### 5. Azure Blob Storage for Artifacts
All experiment outputs stored in blob storage:
- Logs
- Packet captures
- Measurement results

---

## Debugging Tips for Each Flow

### Job Scheduling Issues
- Check user has correct permissions
- Verify no scheduling conflicts
- Validate cron syntax
- Ensure node is active (heartbeating)

### Node Connection Issues
- Verify access token
- Check network connectivity to orchestrator
- Review TLS certificate validity
- Confirm MongoDB is accessible

### Task Coordination Problems
- Check both nodes are active
- Verify task TTL hasn't expired
- Ensure server task completes before timeout
- Review task status in database

### User Management Errors
- Confirm caller has ADMIN role
- Check for duplicate userids
- Verify all required fields provided

### Configuration Issues
- Ensure caller has ADMIN role
- Validate JSON syntax
- Check required fields present
- Verify Azure connection string valid

---

## Performance Characteristics

### Job Scheduling
- **Latency:** 50-200ms (includes conflict checking)
- **Throughput:** ~100 jobs/second
- **Scalability:** Limited by database write speed

### Node Heartbeats
- **Frequency:** Every 30-60 seconds
- **Latency:** 10-50ms
- **Overhead:** Minimal (single DB update)

### Task Coordination
- **Overhead:** Polling-based, 5-second intervals
- **Latency:** Up to 5 seconds to detect completion
- **Optimization:** Could use pub/sub for real-time updates

### User Operations
- **Frequency:** Low (admin operations)
- **Latency:** 20-100ms
- **Caching:** Token verification could be cached (not implemented)

---

## Security Considerations for Each Flow

### Job Scheduling
- User can only schedule on accessible nodes
- Scheduling conflicts prevent resource exhaustion
- Triggers validated to prevent code injection

### Node Management
- Only ADMIN can register/delete nodes
- Nodes get unique access tokens
- Heartbeat requires authentication

### Task Coordination
- Tasks have TTL to prevent stale entries
- Only authorized nodes can create tasks
- Task status updates authenticated

### User Administration
- Only ADMIN can create/modify users
- Access tokens are hashed (SHA256)
- Roles strictly enforced

### Configuration Management
- Only ADMIN can modify
- All nodes can read
- Sensitive data (connection strings) encrypted in transit
