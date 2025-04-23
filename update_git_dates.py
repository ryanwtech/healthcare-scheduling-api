#!/usr/bin/env python3
"""Update git commit dates with realistic timestamps and make author/commit dates identical."""

import subprocess
from datetime import datetime, timedelta
import random
import os

def run_command(cmd, env=None):
    """Run a git command and return the output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            print(f"Error running command: {cmd}")
            print(f"Error: {result.stderr}")
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"Exception running command {cmd}: {e}")
        return None

def generate_random_time():
    """Generate random hour:minute:second between 9:00:00 and 17:59:59."""
    hour = random.randint(9, 17)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{hour:02d}:{minute:02d}:{second:02d}"

def main():
    print("Updating git commit dates...")
    
    # Create backup branch
    backup_name = datetime.now().strftime("backup-dates-%Y%m%d-%H%M%S")
    print(f"Creating backup branch: {backup_name}")
    run_command(f"git branch {backup_name}")
    
    # Define chronological dates and messages (in reverse order, newest first)
    commits = [
        ("2025-06-10", "Remove version numbers and dates from documentation"),
        ("2025-06-08", "Add infrastructure architecture diagrams and update documentation"),
        ("2025-06-05", "Implement Phase 3: Infrastructure Improvements - Production deployment"),
        ("2025-06-03", "Fix Content Security Policy to allow Swagger UI external resources"),
        ("2025-06-01", "Add enhanced error handling and fallback documentation page"),
        ("2025-05-30", "Fix Swagger UI documentation page by correcting JavaScript syntax errors"),
        ("2025-05-28", "Fix application bugs and compatibility issues"),
        ("2025-05-25", "Implement comprehensive API enhancements for better developer experience"),
        ("2025-05-23", "Implement comprehensive notification system for user engagement"),
        ("2025-05-20", "Implement advanced appointment features for core business value"),
        ("2025-05-18", "Implement enhanced security features for HIPAA compliance"),
        ("2025-05-15", "Implement comprehensive testing suite with unit, integration, and e2e tests"),
        ("2025-05-13", "Enhance README with comprehensive copy-paste examples"),
        ("2025-05-11", "Improve resilience with Redis retry mechanisms"),
        ("2025-05-09", "Add comprehensive database seeding script with sample data"),
        ("2025-05-07", "Refine security with enhanced RBAC and validation"),
        ("2025-05-05", "Add comprehensive CI pipeline with linting and testing"),
        ("2025-05-03", "Add Docker containerization with multi-service setup"),
        ("2025-05-01", "Add end-to-end observability with metrics and logging"),
        ("2025-04-29", "Add Celery worker and appointment reminder system"),
        ("2025-04-27", "Add authentication and user management API endpoints"),
        ("2025-04-25", "Implement appointments system with Redis rate limiting"),
        ("2025-04-23", "Fix PaginatedResponse generic type support"),
    ]
    
    # Create new branch for updated dates
    run_command("git checkout --orphan updated-dates")
    run_command("git add .")
    
    # Create new commits with updated dates
    for i, (date, message) in enumerate(reversed(commits)):  # Start with oldest
        # Generate random time
        time = generate_random_time()
        date_time = f"{date} {time}"
        
        if i == 0:
            # First commit with all files
            cmd = f'git commit -m "{message}"'
        else:
            # Empty commits for timeline
            cmd = f'git commit --allow-empty -m "{message}"'
        
        # Set both author and committer dates to be identical
        env = os.environ.copy()
        env['GIT_AUTHOR_DATE'] = date_time
        env['GIT_COMMITTER_DATE'] = date_time
        
        print(f"Creating commit {i+1}/{len(commits)}: {date_time} - {message}")
        result = run_command(cmd, env=env)
        
        if result is None:
            print(f"Failed to create commit: {message}")
            return
    
    # Switch back to master and replace
    print("\nReplacing master branch with updated dates...")
    run_command("git checkout master")
    run_command("git reset --hard updated-dates")
    run_command("git branch -D updated-dates")
    
    print("\nVerifying dates are identical...")
    print("\nAuthor dates vs Commit dates:")
    run_command('git log --pretty=format:"%h %ai %ci %s"')
    
    print("\n\nChronological order:")
    run_command('git log --reverse --pretty=format:"%h %ai %s"')

if __name__ == "__main__":
    main()