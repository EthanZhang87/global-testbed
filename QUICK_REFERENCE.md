# LEOScope Quick Reference Guide

This is a quick reference guide for understanding the LEOScope codebase. For detailed explanations, see [CODEBASE_FLOW.md](CODEBASE_FLOW.md).

## 🏗️ System Architecture

```
┌─────────────┐
│ Researchers │ (Users/Scientists)
└──────┬──────┘
       │ Submit experiments via:
       ├─ Website (separate repo)
       └─ CLI (this repo)
       │
       ▼
┌─────────────────────┐
│   gRPC Protocol     │ (Port 50051)
└─────────────────────┘
       │
       ▼
┌─────────────────────┐
│ Cloud Orchestrator  │ Central Coordinator
│  - Schedule jobs    │ - orchestrator/orchestrator.py
│  - Conflict check   │ - MongoDB database
│  - Auth/authz       │ - gRPC server
└──────────┬──────────┘
           │ (Nodes poll every ~10 sec)
           ▼
┌─────────────────────┐
│ Measurement Nodes   │ Distributed Clients
│  - Poll for jobs    │ - node/scheduler.py
│  - Schedule locally │ - Uses cron/atq
│  - Monitor triggers │ - Monitor satellites/weather
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Executor         │ Job Runner
│  - Launch Docker    │ - node/executor.py
│  - Collect logs     │ - Docker API
│  - Upload results   │ - Azure Blob Storage
└─────────────────────┘
```

## 📂 Key Files & Their Roles

| File | Purpose | Key Functions |
|------|---------|---------------|
| `cli/__main__.py` | Command-line interface | `main()` - Parse commands and call client |
| `common/client.py` | gRPC client library | `schedule_job()`, `get_jobs_by_nodeid()`, `update_run()` |
| `orchestrator/__main__.py` | Orchestrator entry point | Start gRPC server |
| `orchestrator/orchestrator.py` | Core scheduling logic | `schedule_job()`, `get_jobs_by_nodeid()`, conflict detection |
| `orchestrator/datastore.py` | Database operations | MongoDB CRUD operations |
| `node/__main__.py` | Node entry point | Start scheduler loop |
| `node/scheduler.py` | Job polling & scheduling | `scheduler_loop()`, `_scheduler_execute()` |
| `node/executor.py` | Experiment execution | `main()`, `_deploy_job()`, `_execute_job_loop()`, `_finish_job()` |
| `common/job.py` | Job data structures | `LeotestJobCron`, `LeotestJobAtq` |
| `common/leotest.proto` | gRPC API definitions | All message types and RPC methods |

## 🔄 Main Flow Sequences

### 1️⃣ Scheduling an Experiment

```
User → CLI → LeotestClient → gRPC → Orchestrator → MongoDB
                                              ↓
                                          Response
```

**Steps**:
1. User runs: `python3 -m cli job --action=schedule --jobid=... --nodeid=...`
2. CLI calls: `client.schedule_job(jobid, nodeid, config, ...)`
3. Client creates gRPC message and sends to orchestrator
4. Orchestrator validates token, checks conflicts
5. Orchestrator saves job to MongoDB
6. Response sent back to user

### 2️⃣ Node Picks Up Job

```
Node Scheduler → Poll (every 10s) → Orchestrator → MongoDB
         ↓                               ↓
    Job List ← ────────────────────── Response
         ↓
   Local Scheduling (cron/atq)
```

**Steps**:
1. `scheduler_loop()` runs continuously on node
2. Every 10 seconds: `client.get_jobs_by_nodeid(nodeid)`
3. Orchestrator queries MongoDB for jobs on this node
4. Jobs returned to node
5. Node schedules each job with cron (recurring) or atq (one-time)

### 3️⃣ Experiment Execution

```
Cron/atq triggers → Executor starts → Fetch config → Launch Docker
                                           ↓
                                    Monitor execution
                                           ↓
                          Upload logs → Update status → Cleanup
```

**Steps**:
1. Scheduled time arrives, cron/atq launches: `python3 -m node.executor ...`
2. Executor fetches config: `client.get_job_by_id(jobid)`
3. Executor creates Docker container with experiment
4. Container runs for specified duration
5. Logs collected and uploaded to Azure Blob Storage
6. Status updated: `client.update_run(status='COMPLETED', blob_url=...)`
7. Container removed, files cleaned up

## 🔑 Key Concepts

### Job Types

| Type | Description | Scheduler | Use Case |
|------|-------------|-----------|----------|
| **CRON** | Recurring jobs | System crontab | Periodic measurements (every 10 min) |
| **ATQ** | One-time jobs | Linux `at` daemon | Specific time windows |

### Job Statuses

```
SCHEDULED → RUNNING → COMPLETED ✓
                   → FAILED ✗
                   → ABORTED (scavenger mode) ⊗
                   → SKIPPED (trigger not met) ⊘
```

### Triggers

Conditional execution based on environment:

```yaml
Examples:
  - "satellite_elevation > 40"       # Run when satellite is high
  - "weather.temperature < 30"       # Run when cool
  - "network.latency < 100"          # Run when fast connection
```

## 🔧 Common Commands

### Schedule a job
```bash
python3 -m cli \
  --userid=user1 \
  --access-token='token' \
  --grpc-host=orchestrator.example.com \
  job --action=schedule \
  --nodeid=node-seattle \
  --jobid=exp-001 \
  --exp-config="config.yaml" \
  --schedule="*/10 * * * *" \
  --start-date='2024-01-01T00:00:00' \
  --end-date='2024-01-02T00:00:00' \
  --length=300 \
  --trigger="satellite_elevation > 30"
```

### Get job info
```bash
python3 -m cli job --action=get --jobid=exp-001
```

### Get node info
```bash
python3 -m cli node --action=get --nodeid=node-seattle
```

### Check run status
```bash
python3 -m cli run --action=get --jobid=exp-001 --limit=10
```

### Download results
```bash
python3 -m cli run --action=download \
  --jobid=exp-001 \
  --local-path=./results
```

### Register a new node
```bash
python3 -m cli node --action=register \
  --nodeid=node-london \
  --name="London Node" \
  --location=london \
  --coords="51.5074,-0.1278"
```

## 🐳 Docker Components

### Orchestrator Container
```yaml
Services:
  - gRPC server (port 50051)
  - MongoDB connection
  - API endpoints
```

### Node Container
```yaml
Services:
  - Scheduler (polls orchestrator)
  - Cron daemon
  - ATD daemon
  - Satellite/weather monitors
  - Memcache
```

### Experiment Containers
```yaml
Purpose: Run actual experiments
Lifecycle: Created → Run → Stopped → Removed
Labels: jobid, runid, nodeid, type
Environment: LEOTEST_* variables
```

## 📊 Database Collections

### jobs
```javascript
{
  jobid: "exp-001",
  nodeid: "node-seattle",
  userid: "user1",
  type: "CRON",
  schedule: "*/10 * * * *",
  start_date: ISODate("2024-01-01"),
  end_date: ISODate("2024-01-02"),
  length_secs: 300,
  config: "...",
  trigger: "satellite_elevation > 30"
}
```

### runs
```javascript
{
  runid: "run-001-001",
  jobid: "exp-001",
  nodeid: "node-seattle",
  status: "COMPLETED",
  start_time: ISODate("2024-01-01T00:10:00"),
  end_time: ISODate("2024-01-01T00:15:00"),
  blob_url: "https://storage.../artifacts/..."
}
```

### nodes
```javascript
{
  nodeid: "node-seattle",
  name: "Seattle Starlink Node",
  coords: "47.6062,-122.3321",
  last_active: ISODate("2024-01-01T12:00:00"),
  public_ip: "203.0.113.42",
  scavenger_mode_active: false
}
```

## 🔍 Debugging Checklist

- [ ] **Job not scheduling?**
  - Check orchestrator logs: `docker logs orchestrator`
  - Verify token: `python3 -m cli user --action=get --id=<userid>`
  - Check conflicts: Query MongoDB for overlapping jobs
  
- [ ] **Node not picking up jobs?**
  - Check node logs: `docker logs node-scheduler`
  - Verify node registered: `python3 -m cli node --action=get --nodeid=<nodeid>`
  - Check last_active timestamp in database
  
- [ ] **Experiment not running?**
  - Check crontab: `crontab -l`
  - Check atq: `atq`
  - Check executor logs: Look in node container
  - Verify trigger conditions: Check satellite/weather monitors
  
- [ ] **Results not uploading?**
  - Check Azure connection string in global_config.json
  - Check network connectivity from node
  - Check container exit code: `docker ps -a`

## 📡 gRPC API Methods

### User Management
- `register_user(id, name, role, team)`
- `get_user(id)`
- `modify_user(id, name, role, team)`
- `delete_user(id)`

### Job Management
- `schedule_job(jobid, nodeid, type, schedule, dates, config, trigger)`
- `get_job_by_id(jobid)`
- `get_jobs_by_nodeid(nodeid)`
- `get_jobs_by_userid(userid)`
- `reschedule_job_nearest(jobid, starttime, endtime)`
- `delete_job_by_id(jobid)`

### Run Management
- `update_run(runid, jobid, nodeid, status, times, blob_url)`
- `get_runs(runid, jobid, nodeid, time_range, limit)`
- `get_scheduled_runs(nodeid, start, end)`

### Node Management
- `register_node(nodeid, name, coords, location, provider)`
- `get_nodes(nodeid, location, name, active)`
- `update_node(nodeid, name, coords, last_active, public_ip)`
- `delete_node(nodeid, deleteJobs)`
- `set_scavenger_status(nodeid, active)`
- `get_scavenger_status(nodeid)`

### Configuration
- `get_config()` - Get global configuration
- `update_config(config_json)` - Update global configuration

## ⚙️ Configuration Files

### global_config.json
```json
{
  "datastore": {
    "blob": {
      "connectionString": "...",
      "container": "artifacts",
      "artifactPath": "/artifacts"
    }
  },
  "weather": {
    "apikey": "..."
  }
}
```

### experiment-config.yaml
```yaml
experiment:
  docker:
    image: "projectleopard/myexp:latest"
    execute:
      name: "myexp"
      ports:
        "8080/tcp": 8080
```

### executor-config.yaml
```yaml
executor:
  docker:
    execute:
      volume:
        source: "/home/leotest"
        dest: "/workspace"
      network: "host"
```

## 🎯 Design Patterns

### Polling vs. Push
- **Pattern**: Nodes poll orchestrator
- **Why**: Works through NAT/firewalls
- **Trade-off**: Slight delay (10 sec) in job propagation

### State Machine
```
Job: SCHEDULED → (time arrives) → Execute
Run: RUNNING → (container done) → COMPLETED
```

### Idempotency
- Job IDs are unique
- Run IDs are unique (jobid + timestamp)
- Safe to retry failed operations

### Separation of Concerns
- **Orchestrator**: Scheduling logic, no execution
- **Node**: Execution, no scheduling logic
- **Executor**: Container management only

## 🚀 Getting Started

1. **Start Orchestrator**:
   ```bash
   docker-compose -f docker-compose-orchestrator.yaml up -d
   ```

2. **Register Node**:
   ```bash
   python3 -m cli node --action=register --nodeid=mynode \
     --name="My Node" --coords="0,0"
   ```

3. **Start Node**:
   ```bash
   docker-compose -f docker-compose-node.yaml up -d
   ```

4. **Schedule Experiment**:
   ```bash
   python3 -m cli job --action=schedule --nodeid=mynode \
     --jobid=test1 --schedule="*/5 * * * *" ...
   ```

5. **Monitor Results**:
   ```bash
   python3 -m cli run --action=get --jobid=test1
   ```

## 📚 Additional Resources

- **Full Documentation**: [CODEBASE_FLOW.md](CODEBASE_FLOW.md)
- **README**: [README.md](README.md)
- **Architecture Diagram**: `extras/leoscope_arch.jpg`
- **gRPC Protocol**: `common/leotest.proto`

---

**Quick Tip**: For detailed explanations of any component, function calls, or interactions, refer to [CODEBASE_FLOW.md](CODEBASE_FLOW.md).
