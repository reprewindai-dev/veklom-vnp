# Deployment Playbook for VNP Standalone Service (v0.1.5)

This will deploy the VNP microservice exactly as configured in this repository (running on Port 8089 and pointing to your live Coolify Postgres database).

**1. Secure Copy (SCP) the repository to your Hetzner Server**
Run this from your local Windows machine in PowerShell to copy the standalone service to the server:
```powershell
scp -i ~/.ssh/veklom-deploy -r c:\Users\antho\.windsurf\veklom-vnp-standalone root@5.78.135.11:/root/veklom-vnp-standalone
```

**2. SSH into the Server**
```bash
ssh -i ~/.ssh/veklom-deploy root@5.78.135.11
```

**3. Build and Start the Service**
```bash
cd /root/veklom-vnp-standalone
docker-compose up -d --build
```

**4. Verify the Deployment**
Check that the VNP Standalone Node is running and responsive:
```bash
curl http://localhost:8089/health
```

Expected Output:
`{"status": "healthy", "version": "0.1.5", "node_type": "standalone-vnp"}`

**Why this is better than the original ZIP file script:**
- **Real Database Integration:** It natively connects to the exact same PostgreSQL database (`llwfyzhnft87bz6brddiax1z`) as `veklom-byos-backend-2` and `cappo-backend`.
- **Anti-Gaming Activated:** It includes the 3σ outlier detection we just built.
- **True WebSockets & SSE:** It natively feeds the real-time VNP leaderboards based on actual DB telemetry rather than mocked random data.
