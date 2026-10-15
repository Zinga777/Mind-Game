# Running THUNDER on an always-on cloud server (beginner guide)

A small Linux server (1 vCPU, 1–2 GB RAM, Ubuntu 22.04+) is enough. Prefer a region close to India.

1. **Create the server** with your provider and log in: `ssh ubuntu@YOUR_SERVER_IP`.
2. **Install Docker:** `curl -fsSL https://get.docker.com | sudo sh` then `sudo usermod -aG docker $USER`, log out and in.
3. **Copy THUNDER** to the server (from your laptop): `scp -r thunder-ai ubuntu@YOUR_SERVER_IP:~/`
4. **Start it:** `cd ~/thunder-ai && docker compose up -d --build`
5. **View the dashboard safely** (it listens only on the server's own localhost):
   on your laptop run `ssh -L 8501:127.0.0.1:8501 ubuntu@YOUR_SERVER_IP` and open http://127.0.0.1:8501.
   On a phone, use an SSH app with port forwarding, or a private VPN such as Tailscale. **Never open port 8501 to
   the internet** — the dashboard has live controls and CoinDCX's terms restrict publishing market data.
6. **Secrets on a server** are stored in `data/secrets.json` (owner-only permissions) because servers have no keyring.
   If you go live, bind your CoinDCX API key to the server's IP address.
7. **Logs:** `docker compose logs -f engine`. **Stop:** `docker compose down`. **Update:** copy new files, then
   `docker compose up -d --build` (your `data/` folder and `config.yaml` are kept).
8. **Backups:** a copy of the database is made daily in `data/backups/`. Download it now and then:
   `scp -r ubuntu@YOUR_SERVER_IP:~/thunder-ai/data/backups .`
