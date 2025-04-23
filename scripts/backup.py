#!/usr/bin/env python3
"""Comprehensive backup and recovery system for Healthcare API."""

import os
import sys
import json
import shutil
import subprocess
import tarfile
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import boto3
from botocore.exceptions import ClientError

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class BackupManager:
    """Comprehensive backup manager for Healthcare API."""
    
    def __init__(self):
        self.backup_dir = Path("/opt/backups/healthcare-api")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup configuration
        self.config = {
            "database": {
                "enabled": True,
                "retention_days": 30,
                "compression": True
            },
            "files": {
                "enabled": True,
                "paths": [
                    "/opt/healthcare-api/static",
                    "/opt/healthcare-api/media",
                    "/opt/healthcare-api/logs"
                ],
                "retention_days": 7
            },
            "config": {
                "enabled": True,
                "paths": [
                    "/etc/healthcare-api",
                    "/etc/nginx/sites-available/healthcare-api",
                    "/etc/systemd/system/healthcare-api.service"
                ],
                "retention_days": 90
            },
            "s3": {
                "enabled": os.getenv("AWS_ACCESS_KEY_ID") is not None,
                "bucket": os.getenv("AWS_S3_BUCKET", "healthcare-api-backups"),
                "region": os.getenv("AWS_REGION", "us-east-1"),
                "retention_days": 90
            }
        }
    
    def create_database_backup(self) -> str:
        """Create database backup."""
        if not self.config["database"]["enabled"]:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"database_backup_{timestamp}.sql"
        
        try:
            # Extract database connection details
            db_url = settings.database_url
            if db_url.startswith("postgresql://"):
                # Parse PostgreSQL URL
                parts = db_url.replace("postgresql://", "").split("@")
                if len(parts) == 2:
                    user_pass, host_db = parts
                    user, password = user_pass.split(":")
                    host, db = host_db.split("/")
                    host, port = host.split(":") if ":" in host else (host, "5432")
                    
                    # Create pg_dump command
                    env = os.environ.copy()
                    env["PGPASSWORD"] = password
                    
                    cmd = [
                        "pg_dump",
                        "-h", host,
                        "-p", port,
                        "-U", user,
                        "-d", db,
                        "--no-password",
                        "--verbose",
                        "--clean",
                        "--if-exists",
                        "--create"
                    ]
                    
                    with open(backup_file, "w") as f:
                        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)
                    
                    if result.returncode != 0:
                        raise Exception(f"pg_dump failed: {result.stderr.decode()}")
                    
                    logger.info(f"Database backup created: {backup_file}")
                    
                    # Compress if enabled
                    if self.config["database"]["compression"]:
                        compressed_file = f"{backup_file}.gz"
                        with open(backup_file, 'rb') as f_in:
                            with gzip.open(compressed_file, 'wb') as f_out:
                                shutil.copyfileobj(f_in, f_out)
                        os.remove(backup_file)
                        backup_file = compressed_file
                        logger.info(f"Database backup compressed: {backup_file}")
                    
                    return str(backup_file)
                else:
                    raise Exception("Invalid database URL format")
            else:
                raise Exception("Only PostgreSQL backups are supported")
        
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            return None
    
    def create_files_backup(self) -> str:
        """Create files backup."""
        if not self.config["files"]["enabled"]:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"files_backup_{timestamp}.tar.gz"
        
        try:
            with tarfile.open(backup_file, "w:gz") as tar:
                for path in self.config["files"]["paths"]:
                    if os.path.exists(path):
                        tar.add(path, arcname=os.path.basename(path))
                        logger.info(f"Added to backup: {path}")
                    else:
                        logger.warning(f"Path not found: {path}")
            
            logger.info(f"Files backup created: {backup_file}")
            return str(backup_file)
        
        except Exception as e:
            logger.error(f"Files backup failed: {e}")
            return None
    
    def create_config_backup(self) -> str:
        """Create configuration backup."""
        if not self.config["config"]["enabled"]:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"config_backup_{timestamp}.tar.gz"
        
        try:
            with tarfile.open(backup_file, "w:gz") as tar:
                for path in self.config["config"]["paths"]:
                    if os.path.exists(path):
                        tar.add(path, arcname=os.path.basename(path))
                        logger.info(f"Added to config backup: {path}")
                    else:
                        logger.warning(f"Config path not found: {path}")
            
            logger.info(f"Configuration backup created: {backup_file}")
            return str(backup_file)
        
        except Exception as e:
            logger.error(f"Configuration backup failed: {e}")
            return None
    
    def upload_to_s3(self, file_path: str, s3_key: str) -> bool:
        """Upload backup file to S3."""
        if not self.config["s3"]["enabled"]:
            return False
        
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name=self.config["s3"]["region"]
            )
            
            s3_client.upload_file(
                file_path,
                self.config["s3"]["bucket"],
                s3_key
            )
            
            logger.info(f"Uploaded to S3: s3://{self.config['s3']['bucket']}/{s3_key}")
            return True
        
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            return False
    
    def cleanup_old_backups(self) -> None:
        """Clean up old backup files."""
        try:
            # Clean up database backups
            if self.config["database"]["enabled"]:
                self._cleanup_backups(
                    pattern="database_backup_*",
                    retention_days=self.config["database"]["retention_days"]
                )
            
            # Clean up files backups
            if self.config["files"]["enabled"]:
                self._cleanup_backups(
                    pattern="files_backup_*",
                    retention_days=self.config["files"]["retention_days"]
                )
            
            # Clean up config backups
            if self.config["config"]["enabled"]:
                self._cleanup_backups(
                    pattern="config_backup_*",
                    retention_days=self.config["config"]["retention_days"]
                )
        
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
    
    def _cleanup_backups(self, pattern: str, retention_days: int) -> None:
        """Clean up backup files matching pattern."""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        for backup_file in self.backup_dir.glob(pattern):
            if backup_file.is_file():
                file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    backup_file.unlink()
                    logger.info(f"Deleted old backup: {backup_file}")
    
    def create_full_backup(self) -> Dict[str, Any]:
        """Create a full system backup."""
        logger.info("Starting full system backup")
        
        backup_info = {
            "timestamp": datetime.now().isoformat(),
            "backups": {},
            "success": True,
            "errors": []
        }
        
        try:
            # Database backup
            db_backup = self.create_database_backup()
            if db_backup:
                backup_info["backups"]["database"] = db_backup
                
                # Upload to S3 if enabled
                if self.config["s3"]["enabled"]:
                    s3_key = f"database/{os.path.basename(db_backup)}"
                    if self.upload_to_s3(db_backup, s3_key):
                        backup_info["backups"]["database_s3"] = s3_key
            
            # Files backup
            files_backup = self.create_files_backup()
            if files_backup:
                backup_info["backups"]["files"] = files_backup
                
                # Upload to S3 if enabled
                if self.config["s3"]["enabled"]:
                    s3_key = f"files/{os.path.basename(files_backup)}"
                    if self.upload_to_s3(files_backup, s3_key):
                        backup_info["backups"]["files_s3"] = s3_key
            
            # Config backup
            config_backup = self.create_config_backup()
            if config_backup:
                backup_info["backups"]["config"] = config_backup
                
                # Upload to S3 if enabled
                if self.config["s3"]["enabled"]:
                    s3_key = f"config/{os.path.basename(config_backup)}"
                    if self.upload_to_s3(config_backup, s3_key):
                        backup_info["backups"]["config_s3"] = s3_key
            
            # Cleanup old backups
            self.cleanup_old_backups()
            
            # Save backup info
            info_file = self.backup_dir / f"backup_info_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(info_file, "w") as f:
                json.dump(backup_info, f, indent=2)
            
            logger.info("Full system backup completed successfully")
            return backup_info
        
        except Exception as e:
            logger.error(f"Full backup failed: {e}")
            backup_info["success"] = False
            backup_info["errors"].append(str(e))
            return backup_info


class RecoveryManager:
    """Recovery manager for Healthcare API."""
    
    def __init__(self):
        self.backup_dir = Path("/opt/backups/healthcare-api")
    
    def list_available_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        backups = []
        
        for info_file in self.backup_dir.glob("backup_info_*.json"):
            try:
                with open(info_file, "r") as f:
                    backup_info = json.load(f)
                    backups.append(backup_info)
            except Exception as e:
                logger.error(f"Failed to read backup info {info_file}: {e}")
        
        return sorted(backups, key=lambda x: x["timestamp"], reverse=True)
    
    def restore_database(self, backup_file: str) -> bool:
        """Restore database from backup."""
        try:
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Extract database connection details
            db_url = settings.database_url
            if db_url.startswith("postgresql://"):
                parts = db_url.replace("postgresql://", "").split("@")
                if len(parts) == 2:
                    user_pass, host_db = parts
                    user, password = user_pass.split(":")
                    host, db = host_db.split("/")
                    host, port = host.split(":") if ":" in host else (host, "5432")
                    
                    # Create psql command
                    env = os.environ.copy()
                    env["PGPASSWORD"] = password
                    
                    cmd = [
                        "psql",
                        "-h", host,
                        "-p", port,
                        "-U", user,
                        "-d", "postgres"  # Connect to postgres to drop/create database
                    ]
                    
                    # Handle compressed files
                    if backup_file.endswith('.gz'):
                        import gzip
                        with gzip.open(backup_file, 'rt') as f:
                            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, env=env)
                    else:
                        with open(backup_file, "r") as f:
                            result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, env=env)
                    
                    if result.returncode != 0:
                        logger.error(f"Database restore failed: {result.stderr.decode()}")
                        return False
                    
                    logger.info(f"Database restored from: {backup_file}")
                    return True
                else:
                    logger.error("Invalid database URL format")
                    return False
            else:
                logger.error("Only PostgreSQL restores are supported")
                return False
        
        except Exception as e:
            logger.error(f"Database restore failed: {e}")
            return False
    
    def restore_files(self, backup_file: str, target_dir: str = "/opt/healthcare-api") -> bool:
        """Restore files from backup."""
        try:
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(target_dir)
            
            logger.info(f"Files restored from: {backup_file}")
            return True
        
        except Exception as e:
            logger.error(f"Files restore failed: {e}")
            return False
    
    def restore_config(self, backup_file: str) -> bool:
        """Restore configuration from backup."""
        try:
            if not os.path.exists(backup_file):
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall("/")
            
            logger.info(f"Configuration restored from: {backup_file}")
            return True
        
        except Exception as e:
            logger.error(f"Configuration restore failed: {e}")
            return False


def main():
    """Main backup script entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Healthcare API Backup Manager")
    parser.add_argument("--action", choices=["backup", "restore", "list"], required=True,
                       help="Action to perform")
    parser.add_argument("--type", choices=["full", "database", "files", "config"],
                       help="Backup type (for backup action)")
    parser.add_argument("--backup-file", help="Backup file path (for restore action)")
    parser.add_argument("--target-dir", default="/opt/healthcare-api",
                       help="Target directory for restore")
    
    args = parser.parse_args()
    
    if args.action == "backup":
        backup_manager = BackupManager()
        
        if args.type == "full":
            result = backup_manager.create_full_backup()
            print(json.dumps(result, indent=2))
        elif args.type == "database":
            backup_file = backup_manager.create_database_backup()
            print(f"Database backup: {backup_file}")
        elif args.type == "files":
            backup_file = backup_manager.create_files_backup()
            print(f"Files backup: {backup_file}")
        elif args.type == "config":
            backup_file = backup_manager.create_config_backup()
            print(f"Config backup: {backup_file}")
    
    elif args.action == "restore":
        if not args.backup_file:
            print("Error: --backup-file is required for restore action")
            sys.exit(1)
        
        recovery_manager = RecoveryManager()
        
        if args.backup_file.endswith("database_backup_"):
            success = recovery_manager.restore_database(args.backup_file)
        elif args.backup_file.endswith("files_backup_"):
            success = recovery_manager.restore_files(args.backup_file, args.target_dir)
        elif args.backup_file.endswith("config_backup_"):
            success = recovery_manager.restore_config(args.backup_file)
        else:
            print("Error: Unknown backup file type")
            sys.exit(1)
        
        print(f"Restore {'successful' if success else 'failed'}")
    
    elif args.action == "list":
        recovery_manager = RecoveryManager()
        backups = recovery_manager.list_available_backups()
        print(json.dumps(backups, indent=2))


if __name__ == "__main__":
    main()
