# AWS EC2 & ALB Deployment Guide | Group9-Log-Aggregator

This guide walks through deploying the **Group9 Distributed Log Aggregator & Indexer** in **AWS Mumbai (`ap-south-1`)** backed by an **Application Load Balancer (ALB)**, Ubuntu EC2 instance (`t3.small`), Docker Compose, isolated internal Elasticsearch, S3 cold storage archival, and Amazon CloudWatch monitoring.

---

## 1. Architecture & Security Model

```
                    Internet / Log Agents / End Users
                                │
                    Port 80 (HTTP) / 443 (HTTPS)
                                ▼
         ┌──────────────────────────────────────────────┐
         │     AWS Application Load Balancer (ALB)      │
         │  (group9-alb-sg: Public 80/443 Inbound)      │
         │  • Multi-AZ Listeners (ap-south-1a & 1b)     │
         │  • Health Check Target Probe: /health/live   │
         └──────────────────────┬───────────────────────┘
                                │ Forward Port 80
                                │ (VPC Internal Network)
                                ▼
         ┌──────────────────────────────────────────────┐
         │           Amazon EC2 Instance (Ubuntu)        │
         │  (group9-ec2-sg: Port 80 ONLY from ALB SG,   │
         │                  Port 22 from Admin IP)      │
         │                                              │
         │   ┌──────────────────────────────────────┐   │
         │   │       Nginx Reverse Proxy & UI       │   │
         │   │         (frontend container)         │   │
         │   └──────────────────┬───────────────────┘   │
         │                      │ Internal Docker       │
         │                      │ (group9-network)      │
         │   ┌──────────────────▼───────────────────┐   │
         │   │           FastAPI Backend            │   │
         │   │         (backend container)          │   │
         │   └──────────────────┬───────────────────┘   │
         │                      │ Internal Docker       │
         │                      │ (Port 9200 NOT exposed)
         │   ┌──────────────────▼───────────────────┐   │
         │   │        Elasticsearch Indexer         │   │
         │   │      (group9-es-prod container)      │   │
         │   └──────────────────┬───────────────────┘   │
         │                      │                       │
         │           EBS Volume (es_prod_data)          │
         └──────────────────────┬───────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        │ IAM Role: Group9-LogAggregator-EC2Role        │
        │ (Temporary STS credentials - No hardcoded keys│
        ├───────────────────────┬───────────────────────┤
        ▼                       ▼                       ▼
 Amazon S3 Cold Storage     CloudWatch Agent       CloudWatch Logs
 (group9-log-archives)     (Host & Disk Metrics)   (/aws/ec2/group9/...)
```

### Key Security Principles
1. **ALB-Only Public Ingress**: Public users and agents access the ALB. The EC2 instance security group allows HTTP port 80 **strictly from the ALB's security group ID**.
2. **Elasticsearch is Never Exposed**: Port `9200` is strictly internal to Docker's bridge network. No external agent or browser can reach Elasticsearch directly.
3. **FastAPI is Never Directly Exposed**: Port `8000` is internal to Docker. All requests pass through Nginx on port 80.
4. **No Hardcoded Credentials**: The EC2 instance accesses S3 and CloudWatch via an attached **IAM Instance Profile** using temporary AWS STS credentials.
5. **Restricted Admin Access**: Port `22` (SSH) is restricted to your specific workstation IP.

---

## 2. AWS Prerequisites & Setup (Region: Mumbai `ap-south-1`)

### A. Create S3 Bucket for Cold Storage
In the AWS Console or via AWS CLI in `ap-south-1`:
```bash
aws s3api create-bucket \
  --bucket group9-log-archives \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1
```
Enable bucket default encryption (AES256) and block all public access.

### B. Create IAM Role & Instance Profile
1. Create an IAM Role named `Group9-LogAggregator-EC2Role` with trust policy for `ec2.amazonaws.com`.
2. Attach the least-privilege policy defined in [aws/iam-policy.json](file:///d:/Projects/ACC_Group9_Log_Aggregator_and_Indexer/aws/iam-policy.json).
3. Create an Instance Profile with the same name and attach it to the role.

### C. Security Group Configuration

#### 1. ALB Security Group (`group9-alb-sg`)
| Type | Port Range | Protocol | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **HTTP** | `80` | TCP | `0.0.0.0/0` | Public dashboard access & log ingestion |
| **HTTPS**| `443`| TCP | `0.0.0.0/0` | Secure public access (when ACM certificate added) |

#### 2. EC2 Instance Security Group (`group9-ec2-sg`)
| Type | Port Range | Protocol | Source | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **HTTP** | `80` | TCP | `sg-xxxx (group9-alb-sg)` | Allow traffic **strictly** from the ALB |
| **SSH**  | `22` | TCP | `YOUR_IP/32` | Administrative shell access |
| **Custom** | `8000` | TCP | **NONE** | **Never expose FastAPI directly** |
| **Custom** | `9200` | TCP | **NONE** | **Never expose Elasticsearch directly** |

---

## 3. Ubuntu EC2 Host Setup

Launch an EC2 instance:
- **AMI**: Ubuntu Server 24.04 LTS (HVM) or 22.04 LTS
- **Instance Type**: `t3.small` (2 vCPU, 2 GiB RAM) or `t3.medium` (2 vCPU, 4 GiB RAM)
- **Storage**: 20–30 GiB gp3 EBS volume
- **IAM Instance Profile**: `Group9-LogAggregator-EC2Role`
- **Security Group**: `group9-ec2-sg`

SSH into the instance:
```bash
ssh -i /path/to/your-key.pem ubuntu@<EC2_PUBLIC_IP>
```

### Step 1: Update System Packages
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git jq unzip ca-certificates
```

### Step 2: Configure System for Elasticsearch
Elasticsearch requires `vm.max_map_count` to be at least `262144`:
```bash
# Apply immediately
sudo sysctl -w vm.max_map_count=262144

# Persist across reboots
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.d/99-elasticsearch.conf
```

### Step 3: Configure 2GB Swap (Essential for `t3.small`)
To prevent the Linux OOM (Out Of Memory) killer from killing Elasticsearch on a 2GB RAM instance:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Step 4: Install Docker Engine & Docker Compose
```bash
# Add Docker's official GPG key & repository
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow ubuntu user to run Docker commands without sudo
sudo usermod -aG docker ubuntu
newgrp docker
```

---

## 4. Deploying the Application via Docker Compose

### Step 1: Clone Repository
```bash
cd /opt
sudo git clone https://github.com/DikshaP-2506/ACC_Group9_Log_Aggregator_and_Indexer.git
sudo chown -R ubuntu:ubuntu /opt/ACC_Group9_Log_Aggregator_and_Indexer
cd /opt/ACC_Group9_Log_Aggregator_and_Indexer
```

### Step 2: Verify Production Configuration
Ensure `docker-compose.prod.yml` and environment variables are in place:
```bash
# Verify backend production environment configuration
cp backend/.env.example backend/.env
```

### Step 3: Build & Launch Production Containers
```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 4: Verify Container Health
```bash
docker compose -f docker-compose.prod.yml ps
```
Output should indicate:
- `group9-es-prod` is **healthy** (running Elasticsearch 8.11.3)
- `group9-backend-prod` is **healthy** (running FastAPI on port 8000 internally)
- `group9-frontend-prod` is **running** (serving React via Nginx on port 80)

Verify local HTTP response:
```bash
curl http://localhost/health/live
```
Must return `{"status":"live"}`.

---

## 5. Application Load Balancer (ALB) Setup

Now that the application container is actively serving traffic on port 80, create and link the ALB.

### Step 1: Create Target Group (`group9-alb-tg`)
In the AWS Console (EC2 -> Target Groups) or AWS CLI:
1. **Target type**: Instances
2. **Target group name**: `group9-alb-tg`
3. **Protocol**: `HTTP`, **Port**: `80`
4. **VPC**: Default VPC
5. **Health check settings**:
   - **Protocol**: HTTP
   - **Path**: `/health/live`
   - **Healthy threshold**: 2
   - **Unhealthy threshold**: 2
   - **Timeout**: 5 seconds
   - **Interval**: 15 seconds
   - **Success codes**: 200

### Step 2: Create Public Application Load Balancer (`group9-alb`)
In EC2 -> Load Balancers -> Create Application Load Balancer:
1. **Name**: `group9-alb`
2. **Scheme**: Internet-facing
3. **IP address type**: IPv4
4. **Network mapping**: Select your default VPC and at least two Availability Zones (e.g. `ap-south-1a` and `ap-south-1b`).
5. **Security groups**: Select `group9-alb-sg` (allows inbound 80/443).
6. **Listeners and routing**:
   - **Protocol**: HTTP, **Port**: 80
   - **Default action**: Forward to `group9-alb-tg`
7. *(Optional HTTPS)*: If you possess a domain name, request an AWS Certificate Manager (ACM) SSL certificate in `ap-south-1`, add an HTTPS:443 listener forwarding to `group9-alb-tg`, and set HTTP:80 to redirect to HTTPS:443.

### Step 3: Register EC2 Target
1. In Target Groups -> `group9-alb-tg` -> **Register targets**.
2. Select your launched EC2 instance (`Port: 80`).
3. Click **Include as pending below** and **Register pending targets**.
4. Monitor target status until it transitions from `initial` -> `healthy`.

---

## 6. End-to-End Verification via ALB

Once the ALB target group reports the EC2 instance as **healthy**:

### Test 1: Access Web Dashboard via ALB DNS
Copy the DNS name of your ALB from the AWS Console (e.g., `http://group9-alb-xxxx.ap-south-1.elb.amazonaws.com/`).
Open it in your web browser:
- The React single-page dashboard loads securely.
- Real-time KPI stats and cluster status are online.
- Network requests route: Browser -> ALB:80 -> EC2 Nginx:80 -> FastAPI:8000 -> Elasticsearch:9200.

### Test 1: Service Health Endpoints
```bash
# Test liveness probe
curl http://localhost/health/live

# Test readiness probe
curl http://localhost/health/ready

# Test full cluster health
curl http://localhost/health
```

### Test 2: Ingest a Test Log via Reverse Proxy
```bash
curl -X POST http://localhost/logs \
  -H "Content-Type: application/json" \
  -d '{
    "level": "INFO",
    "source": "aws-ec2-test",
    "message": "AWS Production deployment verification log entry."
  }'
```
Expected response: HTTP `201 Created` with unique log ID and assigned deterministic routing partition.

### Test 3: Search Ingested Logs
```bash
curl "http://localhost/logs/search?query=verification"
```

### Test 4: Web Dashboard
Open your web browser and navigate to:
```
http://<EC2_PUBLIC_IP>/
```
You will see the dark-mode dashboard displaying live statistics, cluster health, and the newly indexed log entry.

---

## 7. S3 Historical Log Archival Setup

The archival script compresses eligible logs using `gzip` and uploads them to S3 with `AES256` encryption.

### Step 1: Install Python Dependencies on EC2 Host
```bash
sudo apt-get install -y python3-pip python3-venv
python3 -m venv /opt/archiver-venv
/opt/archiver-venv/bin/pip install boto3 elasticsearch
```

### Step 2: Test Archival in Dry-Run Mode
```bash
/opt/archiver-venv/bin/python3 /opt/ACC_Group9_Log_Aggregator_and_Indexer/scripts/s3_log_archiver.py \
  --bucket group9-log-archives \
  --retention-days 7 \
  --from-es \
  --es-url http://localhost:9200 \
  --dry-run
```

### Step 3: Schedule Daily Archival via Cron
```bash
sudo mkdir -p /var/log/group9
sudo chown -R ubuntu:ubuntu /var/log/group9

# Open crontab
crontab -e
```
Add the following entry to execute every day at 02:00 AM UTC:
```cron
0 2 * * * /opt/archiver-venv/bin/python3 /opt/ACC_Group9_Log_Aggregator_and_Indexer/scripts/s3_log_archiver.py --bucket group9-log-archives --retention-days 7 >> /var/log/group9/archival.log 2>&1
```

---

## 8. Amazon CloudWatch Agent Setup

Stream CPU, Memory, Disk, and log files to CloudWatch.

### Step 1: Download and Install Agent
```bash
wget https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb
```

### Step 2: Copy Configuration File
```bash
sudo cp /opt/ACC_Group9_Log_Aggregator_and_Indexer/aws/cloudwatch/amazon-cloudwatch-agent.json \
  /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

### Step 3: Start CloudWatch Agent
```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

Verify agent status:
```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a status
```

---

## 9. Maintenance & Troubleshooting

### Viewing Container Logs
```bash
# View backend logs in real-time
docker compose -f docker-compose.prod.yml logs -f backend

# View Elasticsearch logs
docker compose -f docker-compose.prod.yml logs -f elasticsearch

# View Nginx access & error logs
docker compose -f docker-compose.prod.yml logs -f frontend
```

### Restarting the Stack
```bash
docker compose -f docker-compose.prod.yml restart
```

### Graceful Shutdown
```bash
docker compose -f docker-compose.prod.yml down
```
*(Indexed data in `es_prod_data` volume is completely preserved).*

### If Elasticsearch Fails to Start
1. Check `vm.max_map_count`:
   ```bash
   sysctl vm.max_map_count
   ```
   Must be `>= 262144`.
2. Check memory usage:
   ```bash
   free -m
   ```
   Ensure swap is active if RAM is under 2GB.
