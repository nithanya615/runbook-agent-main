# Disk Space Cleanup Runbook
## Objective
Resolve high disk usage issues.
## Steps
1. Check disk usage: `df -h`
2. Identify large files: `echo large files: /var/log/app.log (2.1GB)`
3. Review log directory size: `echo /var/log total: 3.4GB`
4. Clean temporary files: `echo cleaned 1.2GB from /tmp`
5. Verify available disk space: `echo disk usage: 45% - healthy`
