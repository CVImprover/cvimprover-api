"""
Django Management Command: cleanup_old_data

DESCRIPTION:
    Clean up old AI responses and orphaned resume files to save storage space.
    This command helps maintain database and file system hygiene by removing
    outdated data that is no longer needed.

FEATURES:
    ✅ Configurable retention period (default: 90 days)
    ✅ Dry-run mode for safe testing
    ✅ Confirmation prompts for safety
    ✅ Force mode to skip confirmations
    ✅ Orphaned file cleanup with size reporting
    ✅ Empty directory cleanup
    ✅ Human-readable file size formatting
    ✅ Transaction safety for database operations
    ✅ Detailed logging and progress reporting

USAGE EXAMPLES:

    1. Test what would be cleaned up (safe dry-run):
       python manage.py cleanup_old_data --days=30 --dry-run --cleanup-files

    2. Clean up AI responses older than 60 days (with confirmation):
       python manage.py cleanup_old_data --days=60

    3. Clean up both AI responses and files older than 90 days (default):
       python manage.py cleanup_old_data --cleanup-files

    4. Force cleanup without confirmation prompts:
       python manage.py cleanup_old_data --days=30 --cleanup-files --force

    5. Only clean up orphaned files (no AI responses):
       python manage.py cleanup_old_data --days=0 --cleanup-files

DOCKER USAGE:
    Run inside Docker container:
    docker-compose exec web python manage.py cleanup_old_data --dry-run --cleanup-files

WHAT GETS CLEANED:
    - AIResponse records older than specified days
    - Resume files that are no longer referenced by any CVQuestionnaire
    - Empty directories in the resumes folder

SAFETY FEATURES:
    - Dry-run mode shows what would be deleted without making changes
    - Confirmation prompts before actual deletion (unless --force used)
    - Database operations wrapped in transactions
    - Detailed error handling and reporting

RECOMMENDED WORKFLOW:
    1. First run with --dry-run to see what would be cleaned
    2. Review the output carefully
    3. Run without --dry-run to perform actual cleanup
    4. Consider adding to cron job for regular maintenance

CRON EXAMPLE (monthly cleanup):
    0 2 1 * * cd /app && python manage.py cleanup_old_data --days=90 --cleanup-files --force
"""

import os
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from cv.models import CVQuestionnaire, AIResponse


class Command(BaseCommand):
    help = "Clean up old AI responses and orphaned resume files to save storage space"

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete AI responses older than this many days (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts'
        )
        parser.add_argument(
            '--cleanup-files',
            action='store_true',
            help='Also clean up orphaned resume files'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        force = options['force']
        cleanup_files = options['cleanup_files']

        if days <= 0:
            raise CommandError('Days must be a positive integer')

        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.WARNING(f"🧹 Starting cleanup process...")
        )
        self.stdout.write(f"   Cutoff date: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE("   Running in DRY-RUN mode - no changes will be made")
            )

        # Clean up old AI responses
        self._cleanup_ai_responses(cutoff_date, dry_run, force)
        
        # Clean up orphaned files if requested
        if cleanup_files:
            self._cleanup_orphaned_files(dry_run, force)
        
        self.stdout.write(
            self.style.SUCCESS("✅ Cleanup process completed successfully!")
        )

    def _cleanup_ai_responses(self, cutoff_date, dry_run, force):
        """Delete AI responses older than cutoff date"""
        self.stdout.write("\n📋 Analyzing AI responses...")
        
        # Find old AI responses
        old_responses = AIResponse.objects.filter(created_at__lt=cutoff_date)
        count = old_responses.count()
        
        if count == 0:
            self.stdout.write("   No old AI responses found.")
            return
        
        self.stdout.write(f"   Found {count} AI response(s) older than cutoff date")
        
        if dry_run:
            self.stdout.write("   [DRY-RUN] Would delete these AI responses:")
            for response in old_responses[:10]:  # Show first 10
                self.stdout.write(f"     - Response {response.id} from {response.created_at}")
            if count > 10:
                self.stdout.write(f"     ... and {count - 10} more")
            return
        
        # Confirm deletion unless force is used
        if not force:
            confirm = input(f"\n⚠️  Delete {count} AI response(s)? [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write("   Skipped AI response cleanup.")
                return
        
        # Delete AI responses
        try:
            with transaction.atomic():
                deleted_count, _ = old_responses.delete()
                self.stdout.write(
                    self.style.SUCCESS(f"   ✅ Deleted {deleted_count} AI response(s)")
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error deleting AI responses: {str(e)}")
            )

    def _cleanup_orphaned_files(self, dry_run, force):
        """Remove orphaned resume files that no longer have associated questionnaires"""
        self.stdout.write("\n📁 Analyzing uploaded files...")
        
        # Get the resumes directory path
        media_root = settings.MEDIA_ROOT
        resumes_dir = os.path.join(media_root, 'resumes')
        
        if not os.path.exists(resumes_dir):
            self.stdout.write("   Resumes directory does not exist.")
            return
        
        # Get all files in resumes directory
        try:
            all_files = []
            for root, dirs, files in os.walk(resumes_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, media_root)
                    all_files.append((file_path, relative_path))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"   ❌ Error reading resumes directory: {str(e)}")
            )
            return
        
        if not all_files:
            self.stdout.write("   No files found in resumes directory.")
            return
        
        self.stdout.write(f"   Found {len(all_files)} file(s) in resumes directory")
        
        # Get all resume file paths from questionnaires
        active_resume_paths = set()
        questionnaires_with_resumes = CVQuestionnaire.objects.exclude(resume='').exclude(resume__isnull=True)
        
        for questionnaire in questionnaires_with_resumes:
            if questionnaire.resume:
                # Convert to relative path for comparison
                resume_path = questionnaire.resume.name
                active_resume_paths.add(resume_path)
        
        self.stdout.write(f"   Found {len(active_resume_paths)} active resume reference(s)")
        
        # Find orphaned files
        orphaned_files = []
        total_size = 0
        
        for file_path, relative_path in all_files:
            if relative_path not in active_resume_paths:
                try:
                    file_size = os.path.getsize(file_path)
                    orphaned_files.append((file_path, relative_path, file_size))
                    total_size += file_size
                except OSError:
                    # File might have been deleted or is inaccessible
                    continue
        
        if not orphaned_files:
            self.stdout.write("   No orphaned files found.")
            return
        
        self.stdout.write(f"   Found {len(orphaned_files)} orphaned file(s)")
        self.stdout.write(f"   Total size: {self._format_file_size(total_size)}")
        
        if dry_run:
            self.stdout.write("   [DRY-RUN] Would delete these orphaned files:")
            for file_path, relative_path, file_size in orphaned_files[:10]:
                self.stdout.write(f"     - {relative_path} ({self._format_file_size(file_size)})")
            if len(orphaned_files) > 10:
                self.stdout.write(f"     ... and {len(orphaned_files) - 10} more")
            return
        
        # Confirm deletion unless force is used
        if not force:
            confirm = input(f"\n⚠️  Delete {len(orphaned_files)} orphaned file(s) ({self._format_file_size(total_size)})? [y/N]: ")
            if confirm.lower() not in ['y', 'yes']:
                self.stdout.write("   Skipped orphaned files cleanup.")
                return
        
        # Delete orphaned files
        deleted_count = 0
        deleted_size = 0
        
        for file_path, relative_path, file_size in orphaned_files:
            try:
                os.remove(file_path)
                deleted_count += 1
                deleted_size += file_size
                self.stdout.write(f"     Deleted: {relative_path}")
            except OSError as e:
                self.stdout.write(
                    self.style.WARNING(f"     Failed to delete {relative_path}: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f"   ✅ Deleted {deleted_count} orphaned file(s) "
                f"({self._format_file_size(deleted_size)} freed)"
            )
        )
        
        # Clean up empty directories
        self._cleanup_empty_directories(resumes_dir)

    def _cleanup_empty_directories(self, directory):
        """Remove empty directories within the resumes directory"""
        try:
            for root, dirs, files in os.walk(directory, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):  # Directory is empty
                            os.rmdir(dir_path)
                            self.stdout.write(f"     Removed empty directory: {dir_path}")
                    except OSError:
                        pass  # Directory not empty or other error
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"   Warning: Could not clean up empty directories: {str(e)}")
            )

    def _format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"