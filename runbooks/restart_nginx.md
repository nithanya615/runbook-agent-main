# Nginx Service Recovery Runbook
## Objective
Recover the Nginx web server when it becomes unavailable.
## Steps
1. Check disk space: `df -h`
2. Check memory usage: `free -m`
3. Check current Nginx status: `echo nginx status: active (running)`
4. Review recent Nginx logs: `echo log: no critical errors found`
5. Restart Nginx service: `echo nginx restarted successfully`
6. Verify Nginx service status: `echo nginx status: active (running)`
7. Verify application health endpoint: `echo HTTP 200 OK - application healthy`
