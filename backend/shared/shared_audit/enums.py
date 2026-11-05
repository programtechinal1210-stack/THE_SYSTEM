from enum import Enum

class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    ASSIGN = "ASSIGN"
    COMPLETE = "COMPLETE"
    REJECT = "REJECT"
    APPROVE = "APPROVE"

class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AuditModule(str, Enum):
    CASES = "cases"
    USERS = "users"
    EXECUTION = "execution"
    SETTINGS = "settings"
    NOTIFICATIONS = "notifications"
    ORGANIZATIONS = "organizations"

class FollowupType(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    REMINDER = "reminder"

class FollowupCategory(str, Enum):
    GENERAL = "GENERAL"
    URGENT = "URGENT"
    REVIEW = "REVIEW"
    APPROVAL = "APPROVAL"
    FOLLOWUP = "FOLLOWUP"

class AnomalyResolution(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
    FALSE_POSITIVE = "false_positive"

class ExportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ReportStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED = "generated"
    FAILED = "failed"
    ARCHIVED = "archived"

class CleanupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DRY_RUN = "dry_run"
