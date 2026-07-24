# Deployment Playbook for VNP Standalone Service (VNP Methodology v1.0)

This deploys the standalone VNP service exactly as configured in this repository: FastAPI on port 8089, Vite assets served by the same container, and production data coming from the deployment-managed Coolify PostgreSQL connection.

**1. Secure Copy (SCP) the repository to your Hetzner server**
Run this from your local Windows machine in PowerShell to copy the standalone service to the server:
```powershell
scp -i ~/.ssh/veklom-deploy -r C:\Users\antho\.windsurf\veklom-vnp root@5.78.135.11:/root/veklom-vnp
```

**2. SSH into the Server**
```bash
ssh -i ~/.ssh/veklom-deploy root@5.78.135.11
```

**3. Build and Start the Service**
```bash
cd /root/veklom-vnp
docker compose up -d --build
```

**4. Verify the Deployment**
Check that the VNP Standalone Node is running and responsive:
```bash
curl http://localhost:8089/health
```

Expected Output:
`{"status":"healthy","service":"veklom-vnp","environment":"production","demo_mode":false}`

**Production checks:**
- **Database-backed only:** production startup refuses missing `DATABASE_URL`.
- **No demo runtime:** production refuses `VNP_ALLOW_DEMO_DATA=true`.
- **Live BYOS evidence:** `/v1/status/capabilities` derives VNP capability states from `https://api.veklom.com/api/v1/vnp/methodology` and `https://api.veklom.com/api/v1/beacon/topology`.
- **Truthful status labels:** unimplemented surfaces remain `Not Yet Wired`, `Partially Implemented`, or `Insufficient Evidence` until their backend evidence exists.
