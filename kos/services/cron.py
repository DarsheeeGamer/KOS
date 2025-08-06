"""
Cron scheduler for KOS
"""

import time
import threading
import re
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

@dataclass 
class CronJob:
    """Cron job definition"""
    minute: str
    hour: str
    day: str
    month: str
    weekday: str
    command: str
    user: str = "root"
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    
    def matches_time(self, dt: datetime) -> bool:
        """Check if job should run at given time"""
        if not self.enabled:
            return False
        
        # Check each field
        if not self._matches_field(self.minute, dt.minute, 0, 59):
            return False
        if not self._matches_field(self.hour, dt.hour, 0, 23):
            return False
        if not self._matches_field(self.day, dt.day, 1, 31):
            return False
        if not self._matches_field(self.month, dt.month, 1, 12):
            return False
        if not self._matches_field(self.weekday, dt.weekday(), 0, 6):
            return False
        
        return True
    
    def _matches_field(self, pattern: str, value: int, min_val: int, max_val: int) -> bool:
        """Check if field matches pattern"""
        if pattern == '*':
            return True
        
        # Handle ranges (e.g., "1-5")
        if '-' in pattern:
            start, end = pattern.split('-')
            return int(start) <= value <= int(end)
        
        # Handle steps (e.g., "*/5")
        if pattern.startswith('*/'):
            step = int(pattern[2:])
            return value % step == 0
        
        # Handle lists (e.g., "1,3,5")
        if ',' in pattern:
            values = [int(v) for v in pattern.split(',')]
            return value in values
        
        # Single value
        try:
            return int(pattern) == value
        except:
            return False

class CronScheduler:
    """Cron job scheduler"""
    
    def __init__(self, vfs=None, executor=None):
        self.vfs = vfs
        self.executor = executor
        self.jobs: List[CronJob] = []
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.crontab_file = "/etc/crontab"
        self.cron_dir = "/etc/cron.d"
        self.user_cron_dir = "/var/spool/cron"
        
        self._load_crontab()
    
    def _load_crontab(self):
        """Load crontab files"""
        if not self.vfs:
            return
        
        # Load system crontab
        if self.vfs.exists(self.crontab_file):
            try:
                with self.vfs.open(self.crontab_file, 'r') as f:
                    self._parse_crontab(f.read().decode())
            except:
                pass
        else:
            # Create default crontab
            self._create_default_crontab()
        
        # Load cron.d files
        if self.vfs.exists(self.cron_dir):
            try:
                for filename in self.vfs.listdir(self.cron_dir):
                    filepath = f"{self.cron_dir}/{filename}"
                    with self.vfs.open(filepath, 'r') as f:
                        self._parse_crontab(f.read().decode())
            except:
                pass
    
    def _create_default_crontab(self):
        """Create default crontab file"""
        if not self.vfs:
            return
        
        default_content = """# /etc/crontab - system crontab
# m h dom mon dow user  command
0 * * * *   root    /usr/bin/hourly-tasks
0 0 * * *   root    /usr/bin/daily-tasks
0 0 * * 0   root    /usr/bin/weekly-tasks
0 0 1 * *   root    /usr/bin/monthly-tasks
*/5 * * * * root    /usr/bin/check-system
"""
        
        try:
            with self.vfs.open(self.crontab_file, 'w') as f:
                f.write(default_content.encode())
        except:
            pass
    
    def _parse_crontab(self, content: str):
        """Parse crontab content"""
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse cron entry
            parts = line.split(None, 6)
            if len(parts) >= 6:
                # Check if user field is present
                if len(parts) == 7:
                    # System crontab format: m h dom mon dow user command
                    minute, hour, day, month, weekday, user, command = parts
                else:
                    # User crontab format: m h dom mon dow command
                    minute, hour, day, month, weekday, command = parts
                    user = "root"
                
                job = CronJob(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    weekday=weekday,
                    command=command,
                    user=user
                )
                
                self.jobs.append(job)
    
    def add_job(self, job: CronJob) -> bool:
        """Add a cron job"""
        self.jobs.append(job)
        self._save_crontab()
        return True
    
    def remove_job(self, command: str) -> bool:
        """Remove a cron job by command"""
        original_count = len(self.jobs)
        self.jobs = [j for j in self.jobs if j.command != command]
        
        if len(self.jobs) < original_count:
            self._save_crontab()
            return True
        return False
    
    def _save_crontab(self):
        """Save crontab to file"""
        if not self.vfs:
            return
        
        content = "# /etc/crontab - system crontab\n"
        content += "# m h dom mon dow user  command\n"
        
        for job in self.jobs:
            content += f"{job.minute} {job.hour} {job.day} {job.month} {job.weekday} "
            content += f"{job.user} {job.command}\n"
        
        try:
            with self.vfs.open(self.crontab_file, 'w') as f:
                f.write(content.encode())
        except:
            pass
    
    def start(self):
        """Start the cron scheduler"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the cron scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        last_minute = -1
        
        while self.running:
            now = datetime.now()
            
            # Only check once per minute
            if now.minute != last_minute:
                last_minute = now.minute
                self._check_jobs(now)
            
            # Sleep until next minute
            time.sleep(60 - now.second)
    
    def _check_jobs(self, dt: datetime):
        """Check and run jobs that match current time"""
        for job in self.jobs:
            if job.matches_time(dt):
                self._run_job(job)
    
    def _run_job(self, job: CronJob):
        """Run a cron job"""
        job.last_run = time.time()
        
        # Execute command
        if self.executor:
            # Use the executor to run the command
            self.executor.execute(job.command, background=True)
        else:
            # Simulate execution
            print(f"[CRON] Running: {job.command}")
    
    def list_jobs(self) -> List[CronJob]:
        """List all cron jobs"""
        return self.jobs
    
    def get_user_crontab(self, username: str) -> List[CronJob]:
        """Get crontab for specific user"""
        return [j for j in self.jobs if j.user == username]
    
    def set_user_crontab(self, username: str, crontab_content: str) -> bool:
        """Set user's crontab"""
        # Remove existing user jobs
        self.jobs = [j for j in self.jobs if j.user != username]
        
        # Parse and add new jobs
        for line in crontab_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split(None, 5)
            if len(parts) == 6:
                minute, hour, day, month, weekday, command = parts
                job = CronJob(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    weekday=weekday,
                    command=command,
                    user=username
                )
                self.jobs.append(job)
        
        self._save_crontab()
        return True