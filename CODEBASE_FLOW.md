# LEOScope Codebase Flow Documentation

This document explains how the LEOScope testbed works, following the flow from researchers submitting experiments through to execution on measurement nodes.

## Architecture Overview

LEOScope is a distributed testbed for running experiments on LEO (Low Earth Orbit) satellite networks. The system has four main components:

1. **Researchers/Users** - Submit experiments via Website or CLI
2. **Website/CLI** - User interface for experiment scheduling and monitoring
3. **Cloud Orchestrator** - Central coordinator managing experiments and nodes
4. **Measurement Nodes** - Distributed nodes that execute experiments

```
[Researchers] 
     ↓
[Website/CLI] → gRPC → [Cloud Orchestrator] ← gRPC ← [Measurement Nodes]
                              ↓                              ↓
                        [MongoDB Database]              [Executor]
                              ↓                              ↓
                      [Experiment Metadata]          [Docker Containers]
                                                            ↓
                                                     [Azure Blob Storage]
```

## Flow Diagram Breakdown

### 1. RESEARCHERS → WEBSITE/CLI

**Purpose**: Users submit experiment requests

**Components**:
- Website (not in this repo, separate repository)
- CLI tool (`cli/__main__.py`)

**How it works**:

When a researcher wants to run an experiment on the testbed, they use either:

#### Option A: Website Interface
- Navigate to the LEOScope web portal
- Fill out experiment scheduling form with:
  - Node ID (which node to run on)
  - Job ID (unique identifier for the experiment)
  - Schedule (cron expression or one-time)
  - Time range (start/end dates)
  - Experiment duration
  - Configuration files (YAML)
  - Triggers (optional conditions)

#### Option B: CLI Interface
```bash
python3 -m cli \
  --userid=<user-id> \
  --access-token='<token>' \
  --grpc-host=<orchestrator-ip> \
  job --action=schedule \
  --nodeid=<node-name> \
  --jobid=<experiment-id> \
  --exp-config="experiment-config.yaml" \
  --schedule="*/5 * * * *" \
  --start-date='2024-01-01T00:00:00' \
  --end-date='2024-01-02T00:00:00' \
  --length=300
```

**Code Path**:
1. `cli/__main__.py:main()` - Parses command line arguments
2. Creates a `LeotestClient` instance with orchestrator connection details
3. Reads experiment configuration from YAML file
4. Calls `client.schedule_job()` with all parameters

**Key Files**:
- `cli/__main__.py` - Command line interface entry point (lines 1-422)
- `common/client.py` - gRPC client for communicating with orchestrator

---

### 2. CLI/WEBSITE → CLOUD ORCHESTRATOR

**Purpose**: Send experiment scheduling request to the central coordinator

**Protocol**: gRPC (Google Remote Procedure Call)

**How it works**:

#### Step 2.1: Client prepares the request

**File**: `common/client.py`  
**Function**: `LeotestClient.schedule_job()` (lines 218-285)

```python
def schedule_job(self, jobid, nodeid, type_name, 
                 params_mode, params_deploy, 
                 params_execute, params_finish, schedule, 
                 start_date, end_date, length, overhead, 
                 server=None, trigger=None,
                 experiment_config=""):
```

**What happens**:
1. Validates experiment configuration (YAML format)
2. Creates a gRPC message (`pb2.message_schedule_job`) containing:
   - Job ID and Node ID
   - Job type (CRON for recurring, ATQ for one-time)
   - Experiment parameters (docker image, execution commands)
   - Schedule (crontab string)
   - Time constraints (start date, end date, duration)
   - Optional: server node ID, trigger conditions
   - Experiment configuration as string
3. Sends the request over gRPC to the orchestrator
4. Returns the orchestrator's response

**Authentication**:
- Uses access token for authentication
- Token validated by orchestrator's `@CheckToken` decorator

#### Step 2.2: Orchestrator receives the request

**File**: `orchestrator/orchestrator.py`  
**Function**: `LeotestOrchestratorGrpc.schedule_job()` (lines 478-769)

**Entry Point**: `orchestrator/__main__.py:main()` starts the orchestrator server

The orchestrator server runs continuously, listening for gRPC requests on port 50051.

```python
@CheckToken(pb2.message_schedule_job_response, 
            grpc.StatusCode.UNAUTHENTICATED, 
            "Invalid token")
def schedule_job(self, request, context):
```

**What happens**:
1. **Authentication**: `@CheckToken` decorator validates the access token
   - Extracts userid and role from the token
   - Verifies against MongoDB database

2. **Extract request data**:
   ```python
   id = request.id              # Job ID
   nodeid = request.nodeid      # Target node
   _type = request.type         # CRON or ATQ
   schedule = request.schedule  # Crontab string
   start_date = request.start_date
   end_date = request.end_date
   length_secs = request.length_secs
   trigger = request.trigger    # Optional trigger expression
   config = request.config      # YAML configuration
   ```

3. **Conflict Detection**: Check if the new job conflicts with existing jobs
   - Query database for existing jobs on the same node
   - For each existing job, check schedule overlap
   - **CRON jobs**: Use `croniter_range` to generate all execution times
   - **ATQ jobs**: Check direct time range overlap
   - If overlap detected, return error response

4. **Trigger Validation** (if trigger specified):
   ```python
   valid, err_msg = verify_trigger_default(trigger)
   ```
   - Validates trigger expression syntax
   - Triggers are conditions like "satellite_elevation > 40"

5. **Save to Database**:
   - Create job object with all parameters
   - Store in MongoDB using `self.db.insert_job()`
   - Job document includes: jobid, nodeid, userid, schedule, dates, config, etc.

6. **Return Response**:
   ```python
   return pb2.message_schedule_job_response(
       state=pb2.response_state.SUCCESS,
       message="job scheduled successfully"
   )
   ```

**Key Database Operations**:
- `orchestrator/datastore.py` - MongoDB interactions
- Collections: `jobs`, `users`, `nodes`, `runs`

---

### 3. CLOUD ORCHESTRATOR → MEASUREMENT NODES

**Purpose**: Nodes poll orchestrator for their job schedules

**How it works**:

Measurement nodes run continuously and periodically check with the orchestrator for jobs.

#### Step 3.1: Node initialization

**File**: `node/__main__.py:main()`

```python
scheduler_loop(nodeid, 
               grpc_hostname=grpc_hostname, 
               grpc_port=grpc_port, 
               interval=interval,         # Poll every N seconds
               workdir=workdir,
               artifactdir=artifactdir,
               executor_config=executor_config,
               access_token=access_token)
```

**What happens on node startup**:
1. Restart cron and atd services (Linux job schedulers)
2. Call `scheduler_loop()` which runs indefinitely

#### Step 3.2: Scheduler loop initialization

**File**: `node/scheduler.py`  
**Function**: `scheduler_loop()` (lines 305-863)

**What happens**:

1. **Create gRPC client**:
   ```python
   client = LeotestClient(
       grpc_hostname=grpc_hostname, 
       grpc_port=grpc_port,
       userid=nodeid, 
       access_token=access_token)
   ```

2. **Fetch node configuration**:
   ```python
   res = client.get_config()
   config = MessageToDict(res)['config']
   weather_api_key = config['weather']['apikey']
   ```

3. **Fetch node information**:
   ```python
   res = client.get_nodes(nodeid=nodeid)
   coords = MessageToDict(res)['nodes'][0]['coords']
   lat, lon = coords.split(',')
   ```

4. **Initialize monitoring modules**:
   - **Trigger Module**: Manages experiment trigger conditions
   - **Satellite Monitor**: Tracks satellite position and elevation
   - **Weather Monitor**: Tracks weather conditions
   - **gRPC Monitor** (if Starlink terminal present): Monitors terminal metrics
   
   ```python
   trigger_module = LeotestTriggerMode()
   satmon = LeotestSatelliteMonitor(trigger_module, name=nodeid, lat=lat, lon=lon, ele=i_ele)
   satmon.run_async()  # Runs in background
   
   weathermon = LeotestWeatherMonitor(trigger_module, api=i_api, lat=i_lat, lon=i_lon)
   weathermon.run_async()  # Runs in background
   ```

5. **Initialize schedulers**:
   ```python
   cron_scheduler = LeotestJobSchedulerCron(client, nodeid, workdir, artifactdir, executor_config)
   atq_scheduler = LeotestJobSchedulerAtq(client, nodeid, workdir, artifactdir, executor_config)
   task_scheduler = LeotestTaskScheduler(client, nodeid)
   ```

6. **Main polling loop**:
   ```python
   while True:
       p = Process(target=_scheduler_execute, args=args)
       p.start()
       p.join(60)  # Wait 60 seconds
       time.sleep(interval)  # Sleep between polls
   ```

#### Step 3.3: Fetching jobs from orchestrator

**Function**: `_scheduler_execute()` in `node/scheduler.py`

**What happens each poll**:

1. **Fetch all jobs for this node**:
   ```python
   res = client.get_jobs_by_nodeid(nodeid)
   jobs = MessageToDict(res)
   ```
   
   This calls the orchestrator's `get_jobs_by_nodeid()` API.

2. **Process each job**:
   ```python
   for job in jobs['jobs']:
       jobid = job['id']
       job_type = job['type']  # 'CRON' or 'ATQ'
       schedule = job['schedule']
       params = job['params']
       trigger = job.get('trigger')
       config = job.get('config')
   ```

3. **Create job objects**:
   ```python
   if job_type == 'CRON':
       job_obj = LeotestJobCron(
           jobid=jobid,
           job_params=params,
           cron_string=schedule,
           start_date=start_date,
           end_date=end_date,
           trigger=trigger,
           config=config
       )
       cron_scheduler.schedule(job_obj)
   
   elif job_type == 'ATQ':
       job_obj = LeotestJobAtq(
           jobid=jobid,
           job_params=params,
           start_date=start_date,
           end_date=end_date,
           trigger=trigger,
           config=config
       )
       atq_scheduler.schedule(job_obj)
   ```

4. **Schedule with Linux job schedulers**:
   - **CRON jobs**: Added to system crontab
   - **ATQ jobs**: Scheduled with `at` daemon for one-time execution

---

### 4. MEASUREMENT NODES → JOB EXECUTION

**Purpose**: Execute scheduled experiments at the right time

**How it works**:

#### Step 4.1: Job trigger

When the scheduled time arrives:

**CRON jobs**: System crontab executes:
```bash
python3 -m node.executor \
  --nodeid=<node-id> \
  --jobid=<job-id> \
  --taskid=<task-id> \
  --runid=<run-id> \
  --start-date='<start>' \
  --end-date='<end>' \
  --length-secs=<duration> \
  ...
```

**ATQ jobs**: The `at` daemon executes the same command at the scheduled time.

#### Step 4.2: Executor initialization

**File**: `node/executor.py`  
**Function**: `main()` (lines 728-849)

**What happens**:

1. **Parse arguments**:
   ```python
   args = parser.parse_args()
   jobid = args.jobid
   nodeid = args.nodeid
   runid = args.runid
   start_date = args.start_date
   end_date = args.end_date
   length_secs = args.length_secs
   ```

2. **Create working directory**:
   ```python
   workdir = os.path.join(args.workdir, jobid)
   os.makedirs(workdir, exist_ok=True)
   ```

3. **Fetch experiment configuration**:
   
   Two options:
   
   **Option A - From Azure Blob Storage** (backward compatibility):
   ```python
   if azclient.check_blob_exists(experiment_config):
       download_file(connection_string, container, 
                    experiment_config, experiment_config_dst)
   ```
   
   **Option B - From Orchestrator** (current method):
   ```python
   res = client.get_job_by_id(jobid)
   exp_args_from_orch = MessageToDict(res)
   exp_config = exp_args_from_orch['config']
   
   with open(experiment_config_dst, 'w') as f:
       f.write(exp_config)
   ```

4. **Fetch experiment arguments**:
   ```python
   if 'config' in exp_config:
       exp_args_from_orch.pop('config')
   
   with open(experiment_args_dst, 'w') as f:
       json.dump(exp_args_from_orch, f)
   ```

5. **Load configurations**:
   ```python
   with open(experiment_config_dst, "r") as stream:
       experiment_config_dict = yaml.safe_load(stream)
   
   with open(executor_config_dst, "r") as stream:
       executor_config_dict = yaml.safe_load(stream)
   ```

6. **Create executor**:
   ```python
   params = {
       'server_mode': args.server,
       'jobid': jobid,
       'nodeid': nodeid,
       'runid': runid,
       'start_date': start_date,
       'end_date': end_date,
       'length_secs': length_secs,
       'experiment': experiment_config_dict,
       'executor': executor_config_dict,
       ...
   }
   
   executor = LeotestExecutorDocker(params=params)
   executor.run()
   ```

#### Step 4.3: Experiment lifecycle

**File**: `node/executor.py`  
**Class**: `LeotestExecutorDocker` (inherits from `LeotestExecutor`)

The executor manages the complete lifecycle:

**Phase 1: Deploy (Setup)**
```python
def _deploy_job(self):
    """Prepare job environment before execution"""
```
- Pull Docker images if needed
- Set up network configurations
- Prepare volume mounts

**Phase 2: Execute (Run)**
```python
def _execute_job_loop(self):
    """Launch container and run experiment"""
```

**What happens**:

1. **Update run status**:
   ```python
   client.update_run(
       runid=runid,
       jobid=jobid,
       nodeid=nodeid,
       status='RUNNING',
       start_time=str(time_now())
   )
   ```

2. **Prepare Docker configuration**:
   ```python
   src_path = os.path.join(
       self.params["executor"]["docker"]["execute"]["volume"]["source"],
       self.params['expdir']
   )
   dst_path = self.params["executor"]["docker"]["execute"]["volume"]["dest"]
   
   image = self.params["experiment"]["docker"]["image"]
   
   environment = [
       "LEOTEST_SERVER=0",
       f"LEOTEST_START_TIME={start_date}",
       f"LEOTEST_LENGTH={length_secs}",
       f"LEOTEST_RUNID={runid}",
       f"LEOTEST_JOBID={jobid}",
       ...
   ]
   ```

3. **Launch Docker container**:
   ```python
   self.container = self.client.containers.run(
       image=image,
       name=container_name,
       volumes={src_path: {'bind': dst_path, 'mode': 'rw'}},
       network=network,
       environment=environment,
       labels={
           'leotest': 'true',
           'jobid': jobid,
           'runid': runid,
           'nodeid': nodeid,
           ...
       },
       detach=True
   )
   ```

4. **Monitor execution**:
   ```python
   while True:
       self.container.reload()
       if self.container.status == 'exited':
           break
       time.sleep(5)
   ```

5. **Store session in memcache**:
   ```python
   sessionstore.set(
       key=f"{runid}_executor",
       value=json.dumps({'status': 'running'})
   )
   ```

**Phase 3: Finish (Cleanup)**
```python
def _finish_job(self):
    """Upload artifacts and clean up"""
```

**What happens**:

1. **Collect logs**:
   ```python
   logs = self.container.logs()
   with open(log_file, 'wb') as f:
       f.write(logs)
   ```

2. **Create archive**:
   ```python
   archive_path = make_archive(workdir, jobid, runid)
   ```

3. **Upload to Azure Blob Storage**:
   ```python
   upload_folder(
       connection_string,
       container,
       archive_path,
       remote_blob_path
   )
   ```

4. **Update run status**:
   ```python
   client.update_run(
       runid=runid,
       jobid=jobid,
       nodeid=nodeid,
       status='COMPLETED',
       end_time=str(time_now()),
       blob_url=blob_url
   )
   ```

5. **Clean up**:
   ```python
   self.container.remove()
   shutil.rmtree(workdir)
   sessionstore.delete(key=f"{runid}_executor")
   ```

---

## Key Interactions Summary

### 1. User → Orchestrator (Schedule Job)

**Direction**: User → Orchestrator  
**Protocol**: gRPC  
**Functions**:
- `LeotestClient.schedule_job()` (client side)
- `LeotestOrchestratorGrpc.schedule_job()` (server side)
- `LeotestDatastoreMongo.insert_job()` (database)

**Data Flow**:
```
User Input → gRPC Request → Token Validation → Conflict Check 
→ Database Insert → gRPC Response → User Confirmation
```

### 2. Node → Orchestrator (Fetch Jobs)

**Direction**: Node → Orchestrator  
**Protocol**: gRPC  
**Functions**:
- `LeotestClient.get_jobs_by_nodeid()` (client side)
- `LeotestOrchestratorGrpc.get_jobs_by_nodeid()` (server side)
- `LeotestDatastoreMongo.get_jobs()` (database)

**Data Flow**:
```
Scheduler Poll → gRPC Request → Database Query → Job List 
→ gRPC Response → Local Scheduling (cron/atq)
```

### 3. Node → Orchestrator (Update Run Status)

**Direction**: Node → Orchestrator  
**Protocol**: gRPC  
**Functions**:
- `LeotestClient.update_run()` (client side)
- `LeotestOrchestratorGrpc.update_run()` (server side)
- `LeotestDatastoreMongo.update_run()` (database)

**Data Flow**:
```
Executor Status Change → gRPC Request → Database Update 
→ gRPC Response → Continue Execution
```

### 4. Node → Orchestrator (Fetch Experiment Config)

**Direction**: Node → Orchestrator  
**Protocol**: gRPC  
**Functions**:
- `LeotestClient.get_job_by_id()` (client side)
- `LeotestOrchestratorGrpc.get_job_by_id()` (server side)

**Data Flow**:
```
Executor Startup → gRPC Request → Database Query → Config Retrieval 
→ gRPC Response → Local File Write → Experiment Setup
```

### 5. Node → Azure Blob Storage (Upload Results)

**Direction**: Node → Azure  
**Protocol**: Azure SDK  
**Functions**:
- `upload_folder()` in `common/azure.py`

**Data Flow**:
```
Experiment Complete → Archive Logs → Upload to Blob → Update Run Status 
→ User Can Download
```

---

## Trigger System

LEOScope supports conditional experiment execution based on environmental conditions:

**Trigger Types**:
1. **Satellite Position**: `satellite_elevation > 40`
2. **Weather**: `weather.temperature < 30`
3. **Network**: `network.latency < 100`

**How triggers work**:

1. **Monitors run continuously** on each node:
   ```python
   satmon = LeotestSatelliteMonitor(trigger_module, ...)
   satmon.run_async()
   ```

2. **Monitor updates trigger module**:
   ```python
   trigger_module.set('satellite_elevation', 45.2)
   ```

3. **Executor checks trigger before running**:
   ```python
   if trigger:
       if not trigger_module.evaluate(trigger):
           # Skip execution
           return
   ```

4. **Trigger evaluation**:
   - Parse trigger expression
   - Look up current values from monitors
   - Evaluate boolean expression
   - Return True/False

---

## Job Types

### CRON Jobs (Recurring)
- Use crontab syntax: `*/5 * * * *` (every 5 minutes)
- Added to system crontab
- Execute repeatedly until end_date
- Good for: Periodic measurements, long-term monitoring

### ATQ Jobs (One-time)
- Execute once at start_date
- Scheduled with Linux `at` daemon
- Can be rescheduled if aborted (e.g., scavenger mode)
- Good for: One-off experiments, specific time windows

---

## Scavenger Mode

**Purpose**: Allow priority experiments to preempt running jobs

**How it works**:

1. **Administrator sets scavenger mode**:
   ```bash
   python3 -m cli node --action=scavenger-set --nodeid=<node>
   ```

2. **Scheduler detects scavenger mode**:
   ```python
   res = client.get_scavenger_status(nodeid)
   if res.scavenger_mode_active:
       kill_all_jobs(client, nodeid, ...)
   ```

3. **Kill running jobs**:
   - Find all running Docker containers with `overhead=true` label
   - Stop and remove containers
   - Update run status to `ABORTED`
   - For ATQ jobs: Reschedule automatically

---

## Server-Client Experiments

Some experiments need a server-client architecture:

**Setup**:
1. **Schedule server job** on one node:
   ```bash
   --server=<server-node-id>
   ```

2. **Schedule client job** referencing the server:
   ```bash
   --server=<server-node-id>
   ```

**Execution**:
1. Server starts first (higher priority task)
2. Server's IP address stored in orchestrator
3. Client fetches server IP before starting
4. Client connects to server during experiment

**Code**:
```python
if args.server_node:
    # Fetch server IP from orchestrator
    res = client.get_server_ip(server_nodeid)
    server_ip = res.server_ip
```

---

## Database Schema

### Jobs Collection
```json
{
  "jobid": "exp-001",
  "nodeid": "node-seattle",
  "userid": "researcher-1",
  "type": "CRON",
  "schedule": "*/10 * * * *",
  "start_date": "2024-01-01T00:00:00",
  "end_date": "2024-01-02T00:00:00",
  "length_secs": 300,
  "params": {
    "mode": "docker",
    "execute": "...",
    ...
  },
  "trigger": "satellite_elevation > 40",
  "config": "experiment: {...}",
  "overhead": true,
  "server": "node-london"
}
```

### Runs Collection
```json
{
  "runid": "run-001-001",
  "jobid": "exp-001",
  "nodeid": "node-seattle",
  "userid": "researcher-1",
  "start_time": "2024-01-01T00:10:00",
  "end_time": "2024-01-01T00:15:00",
  "status": "COMPLETED",
  "status_message": "",
  "blob_url": "https://storage.../artifacts/..."
}
```

### Nodes Collection
```json
{
  "nodeid": "node-seattle",
  "name": "Seattle Starlink Node",
  "location": "Seattle, WA",
  "coords": "47.6062,-122.3321",
  "provider": "Starlink",
  "last_active": "2024-01-01T12:00:00",
  "public_ip": "203.0.113.42",
  "scavenger_mode_active": false
}
```

---

## Configuration Files

### Global Config (`global_config.json`)
```json
{
  "datastore": {
    "blob": {
      "connectionString": "DefaultEndpointsProtocol=https;...",
      "container": "artifacts",
      "artifactPath": "/artifacts"
    }
  },
  "weather": {
    "apikey": "weather-api-key-here"
  }
}
```

### Experiment Config (`experiment-config.yaml`)
```yaml
experiment:
  docker:
    image: "projectleopard/experiment:latest"
    execute:
      name: "my-experiment"
      ports:
        "8080/tcp": 8080
    environment:
      - "MY_VAR=value"
```

### Executor Config (`executor-config.yaml`)
```yaml
executor:
  docker:
    execute:
      volume:
        source: "/home/leotest"
        dest: "/workspace"
      network: "host"
```

---

## Error Handling

### Schedule Conflicts
- Orchestrator checks for overlapping jobs
- Returns error with conflict details
- User must choose different time window

### Node Offline
- Orchestrator tracks last_active timestamp
- Jobs remain scheduled
- Execute when node comes back online

### Experiment Failure
- Executor updates run status to FAILED
- Logs uploaded to blob storage
- User can debug from logs

### Trigger Not Met
- Executor evaluates trigger
- If false, skips execution
- Updates run status to SKIPPED

---

## Complete Flow Example

Let's trace a complete example: **Measuring satellite latency every 10 minutes**

### Step 1: User submits experiment
```bash
python3 -m cli \
  --userid=researcher-1 \
  --access-token='secret-token' \
  --grpc-host=orchestrator.example.com \
  job --action=schedule \
  --nodeid=node-seattle \
  --jobid=latency-test-001 \
  --exp-config="latency-config.yaml" \
  --schedule="*/10 * * * *" \
  --start-date='2024-01-01T00:00:00' \
  --end-date='2024-01-01T12:00:00' \
  --length=60 \
  --trigger="satellite_elevation > 30"
```

### Step 2: CLI sends to orchestrator
- `LeotestClient.schedule_job()` called
- gRPC message created with all parameters
- Sent to `orchestrator.example.com:50051`

### Step 3: Orchestrator processes request
- Token validated (researcher-1 authenticated)
- Check conflicts: No overlapping jobs found
- Validate trigger: `satellite_elevation > 30` is valid
- Insert into MongoDB jobs collection
- Return success response

### Step 4: Node polls orchestrator
- Every 10 seconds: `scheduler_loop()` calls `_scheduler_execute()`
- `client.get_jobs_by_nodeid('node-seattle')` returns job list
- New job found: `latency-test-001`

### Step 5: Node schedules locally
- Job type is CRON
- Add to system crontab:
  ```
  */10 * * * * python3 -m node.executor --jobid=latency-test-001 ...
  ```

### Step 6: First execution (00:10:00)
- Crontab triggers at 00:10:00
- `node.executor.main()` called
- Fetch config from orchestrator
- Check trigger: satellite_elevation = 42° > 30° ✓
- Create workdir: `/home/leotest/latency-test-001/run-001`
- Update run status: RUNNING

### Step 7: Docker container launch
- Pull image: `projectleopard/latency-test:latest`
- Mount volume: `/home/leotest/latency-test-001/run-001:/workspace`
- Set environment variables (LEOTEST_START_TIME, etc.)
- Run container for 60 seconds
- Container executes ping measurements

### Step 8: Container completes
- Exit status: 0 (success)
- Collect logs from container
- Create archive: `latency-test-001-run-001.tar.gz`
- Upload to Azure: `artifacts/node-seattle/latency-test-001/run-001.tar.gz`

### Step 9: Cleanup
- Update run status: COMPLETED
- Set blob_url in database
- Remove container
- Clean workdir
- Delete memcache session

### Step 10: Next execution (00:20:00)
- Crontab triggers again
- Repeat steps 6-9 with run-002
- Continue until end_date (12:00:00)

### Step 11: User downloads results
```bash
python3 -m cli \
  run --action=download \
  --jobid=latency-test-001 \
  --local-path=./results
```
- CLI queries orchestrator for run list
- Downloads all archives from Azure
- Extracts to `./results/`

---

## Component Responsibilities

### CLI (`cli/`)
- Parse user commands
- Validate input
- Format gRPC requests
- Display responses

### Client (`common/client.py`)
- gRPC client implementation
- Connection management
- Retry logic
- Request/response handling

### Orchestrator (`orchestrator/`)
- Central coordination
- Job scheduling logic
- Conflict detection
- Database management
- Authentication/authorization

### Node Scheduler (`node/scheduler.py`)
- Poll orchestrator
- Manage local job schedulers (cron/atq)
- Monitor environmental conditions
- Handle scavenger mode

### Executor (`node/executor.py`)
- Experiment lifecycle management
- Docker container orchestration
- Status updates
- Artifact collection and upload

### Common (`common/`)
- Shared data structures
- gRPC protocol definitions
- Utility functions
- Azure blob storage client

---

## Key Patterns

### Polling Pattern
Nodes poll orchestrator rather than orchestrator pushing to nodes:
- **Advantage**: Works with NAT/firewalls
- **Advantage**: Nodes control their own workload
- **Disadvantage**: Slight delay in job propagation

### Dual Configuration Source
Experiment configs can come from orchestrator OR blob storage:
- **Modern**: Config stored in MongoDB, fetched via gRPC
- **Legacy**: Config uploaded to blob storage, downloaded by node
- Executor checks both for backward compatibility

### Session Store (Memcache)
Used for inter-process communication:
- Scheduler stores job information
- Executor reads job information
- Prevents race conditions during scavenger mode

### Status Tracking
Run status tracked through lifecycle:
```
SCHEDULED → RUNNING → COMPLETED
                   → FAILED
                   → ABORTED
                   → SKIPPED
```

---

## Debugging Tips

### Check job scheduled
```bash
python3 -m cli job --action=get --jobid=<jobid>
```

### Check node status
```bash
python3 -m cli node --action=get --nodeid=<nodeid>
```

### Check run status
```bash
python3 -m cli run --action=get --jobid=<jobid>
```

### View orchestrator logs
```bash
docker logs orchestrator
```

### View node scheduler logs
```bash
docker logs node-scheduler
```

### Check system crontab
```bash
crontab -l
```

### Check at queue
```bash
atq
```

---

## Summary

The LEOScope testbed follows a distributed architecture where:

1. **Users** submit experiments via CLI or website
2. **Orchestrator** stores jobs in database and handles scheduling logic
3. **Nodes** poll orchestrator, schedule jobs locally with cron/atq
4. **Executors** manage Docker containers for each run
5. **Results** uploaded to Azure blob storage for download

The design prioritizes:
- **Flexibility**: Support various experiment types and triggers
- **Scalability**: Distributed nodes, centralized coordination
- **Reliability**: Status tracking, error handling, automatic retries
- **Security**: Token authentication, role-based access control

Each component has a clear responsibility and communicates via well-defined gRPC APIs.
