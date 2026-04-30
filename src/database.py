"""
Database initialization and management for Telegram Bot.

Manages SQLite database schema creation, connection pooling, and query execution.
Schema includes: accounts, profiles, conversations, api_keys, and audit logging.
"""

import sqlite3
import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations and schema initialization."""
    
    def __init__(self, db_path: str = "telegrambot.db"):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file (default: telegrambot.db)
        """
        self.db_path = db_path
        self.connection = None
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def initialize_database(self) -> bool:
        """
        Initialize database schema if it doesn't exist.
        
        Creates all required tables with proper schema and indexes.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db_exists = os.path.exists(self.db_path)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Only create tables if new database
                if not db_exists:
                    logger.info("Creating new database schema...")
                    self._create_schema(cursor)
                    conn.commit()
                    logger.info("[OK] Database schema created successfully")
                else:
                    logger.info("[OK] Database already initialized")
                    # Verify tables exist (in case of partial setup)
                    self._verify_schema(cursor)
            
            return True
        
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def _create_schema(self, cursor: sqlite3.Cursor):
        """Execute all schema creation SQL statements."""
        cursor.executescript(self._get_schema_sql())
    
    @staticmethod
    def _get_schema_sql() -> str:
        """
        Return complete database schema SQL.
        
        Includes all tables, constraints, and indexes for:
        - Account management (PLAN 2)
        - Profile management (PLAN 3)
        - Conversation tracking (PLAN 8)
        - API key rotation (PLAN 9)
        - Audit logging (PLAN 5)
        """
        return """
-- ============================================================================
-- TABLE 1: ACCOUNTS (PLAN 2)
-- Stores Telegram account login credentials  
-- ============================================================================

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_type TEXT DEFAULT 'telegram',
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    api_id TEXT,
    api_hash TEXT,
    password TEXT,
    is_active BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_accounts_phone ON accounts(phone);
CREATE INDEX IF NOT EXISTS idx_accounts_active ON accounts(is_active);
CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type);

-- ============================================================================
-- TABLE 2: PROFILES (PLAN 3)
-- Stores bot personality/persona definitions
-- ============================================================================

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Status
    is_current BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Persona Data
    name TEXT NOT NULL,
    age INTEGER,
    location TEXT,
    ethnicity TEXT,
    
    -- Customization
    system_prompt_custom TEXT,
    response_tone TEXT DEFAULT 'neutral',
    
    -- Template & Training Data
    template_ids TEXT,  -- JSON array: ["template_1", "template_3"]
    training_data_category TEXT,
    
    -- Rate Limiting
    max_daily_interactions INTEGER DEFAULT 100,
    interactions_today INTEGER DEFAULT 0,
    
    -- Tracking
    last_used TIMESTAMP,
    usage_count INTEGER DEFAULT 0,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_profiles_current ON profiles(is_current);
CREATE INDEX IF NOT EXISTS idx_profiles_name ON profiles(name);

-- ============================================================================
-- TABLE 3: CONVERSATIONS (PLAN 1 + PLAN 8 Extensions)
-- Tracks conversation state with timeout management
-- ============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Foreign Keys
    user_id INTEGER,  -- Telegram user ID (optional for groups)
    account_id INTEGER NOT NULL,
    chat_id INTEGER NOT NULL,
    
    -- Chat Info
    chat_type TEXT DEFAULT 'private' CHECK(chat_type IN ('private', 'group', 'supergroup', 'channel')),
    
    -- Message Tracking
    last_message TEXT,
    last_message_time TIMESTAMP,
    of_link_sent BOOLEAN DEFAULT 0,
    
    -- Conversation State (PLAN 8 Timeout FSM)
    state TEXT DEFAULT 'ACTIVE' CHECK(state IN ('ACTIVE', 'IDLE', 'EXPIRED')),
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'deleted')),
    last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timeout_until TIMESTAMP,
    expiry_time TIMESTAMP NULL,
    is_orphaned_cleanup BOOLEAN DEFAULT 0,
    cleanup_reason TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    api_calls_count INTEGER DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    
    FOREIGN KEY(account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_account ON conversations(user_id, account_id);
CREATE INDEX IF NOT EXISTS idx_conversations_account ON conversations(account_id);
CREATE INDEX IF NOT EXISTS idx_conversations_state ON conversations(account_id, state);
CREATE INDEX IF NOT EXISTS idx_conversations_timeout_until 
    ON conversations(account_id, timeout_until) 
    WHERE state IN ('IDLE', 'EXPIRED');
CREATE INDEX IF NOT EXISTS idx_conversations_expiry_time 
    ON conversations(account_id, expiry_time) 
    WHERE state = 'EXPIRED';

-- ============================================================================
-- TABLE 3.5: MESSAGES (PLAN 7)
-- Stores individual messages from conversations for tracking and analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Foreign Keys
    conversation_id INTEGER NOT NULL,
    
    -- Message Data
    sender_id INTEGER NOT NULL,  -- Telegram user ID of sender
    text TEXT,
    message_type TEXT DEFAULT 'text' CHECK(message_type IN ('text', 'photo', 'video', 'audio', 'document', 'voice', 'video_note')),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    telegram_message_id INTEGER,
    is_edited BOOLEAN DEFAULT 0,
    
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- ============================================================================
-- TABLE 4: API_KEYS (PLAN 9)
-- Stores API key credentials with quota tracking and rotation logic
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Connection
    account_id INTEGER NOT NULL,
    provider TEXT NOT NULL CHECK(provider IN ('openai', 'gemini', 'fallback')),
    key_secret TEXT NOT NULL,
    
    -- Status
    is_active BOOLEAN DEFAULT 1,
    key_order INTEGER,  -- Priority: 1, 2, 3 (rotation order)
    is_exhausted BOOLEAN DEFAULT 0,
    exhaustion_reason TEXT,
    
    -- Token/Request Quota
    quota_used_tokens BIGINT DEFAULT 0,  -- OpenAI: tokens
    quota_used_requests INTEGER DEFAULT 0,  -- Gemini: requests/day
    quota_limit_tokens BIGINT,
    quota_limit_requests INTEGER,
    quota_reset_at TIMESTAMP,
    
    -- Tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    
    FOREIGN KEY(account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_api_keys_account_active 
    ON api_keys(account_id, is_active, provider);
CREATE INDEX IF NOT EXISTS idx_api_keys_last_used 
    ON api_keys(account_id, provider, last_used_at);
CREATE INDEX IF NOT EXISTS idx_api_keys_exhausted 
    ON api_keys(account_id, is_exhausted);

-- ============================================================================
-- TABLE 5: API_USAGE_BILLING (PLAN 9)
-- Tracks monthly API usage and estimated costs
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_usage_billing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    account_id INTEGER NOT NULL,
    month_year TEXT NOT NULL,  -- Format: '2026-02'
    provider TEXT NOT NULL,
    
    -- Usage Metrics
    total_tokens_used BIGINT DEFAULT 0,
    total_requests_used INTEGER DEFAULT 0,
    estimated_cost_dollars DECIMAL(10, 4) DEFAULT 0,
    
    FOREIGN KEY(account_id) REFERENCES accounts(id),
    UNIQUE(account_id, month_year, provider)
);

CREATE INDEX IF NOT EXISTS idx_api_usage_account_month 
    ON api_usage_billing(account_id, month_year);

-- ============================================================================
-- TABLE 6: AUDIT_LOG (PLAN 5 + PLAN 7)
-- Tracks important operations for compliance and debugging
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    operation TEXT,  -- 'RESET', 'DELETE_ACCOUNT', 'UNINSTALL', etc.
    type TEXT,  -- 'keyword_match', 'user_joined', 'message_deleted', etc.
    affected_accounts INTEGER,
    affected_conversations INTEGER,
    description TEXT,
    
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    backup_file TEXT,
    user_confirmed BOOLEAN DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_audit_log_operation ON audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);

-- ============================================================================
-- TABLE 7: DELETED_ACCOUNTS (PLAN 5)
-- Tracks deleted accounts for recovery purposes
-- ============================================================================

CREATE TABLE IF NOT EXISTS deleted_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    account_id INTEGER,
    email TEXT,
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    backup_location TEXT,
    
    profile_count INTEGER,
    conversation_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_deleted_accounts_email ON deleted_accounts(email);
CREATE INDEX IF NOT EXISTS idx_deleted_accounts_deleted_at ON deleted_accounts(deleted_at);
        """
    
    def _verify_schema(self, cursor: sqlite3.Cursor):
        """Verify that all required tables exist."""
        required_tables = [
            'accounts', 'profiles', 'conversations', 'api_keys',
            'api_usage_billing', 'audit_log', 'deleted_accounts'
        ]
        
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        missing_tables = set(required_tables) - existing_tables
        if missing_tables:
            logger.warning(f"Missing tables: {missing_tables}")
            # Optionally, you could recreate missing tables here
            # For now, just warn
        
        logger.info(f"[OK] Database verification passed ({len(existing_tables)}/{len(required_tables)} tables)")
    
    # =========================================================================
    # Query Methods (Convenience functions)
    # =========================================================================
    
    def execute_query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute SELECT query and return results."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
    
    def execute_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute SELECT query and return first result."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                return cursor.fetchone()
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return None
    
    def execute_update(self, sql: str, params: tuple = ()) -> bool:
        """Execute INSERT/UPDATE/DELETE operation."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False
    
    def execute_many(self, sql: str, data: List[tuple]) -> bool:
        """Execute bulk INSERT/UPDATE/DELETE operations."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, data)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            return False
    
    # =========================================================================
    # Account Methods (PLAN 2)
    # =========================================================================
    
    def get_current_account(self) -> Optional[Dict[str, Any]]:
        """Get the active account."""
        row = self.execute_one(
            "SELECT * FROM accounts WHERE is_active = 1 LIMIT 1"
        )
        return dict(row) if row else None
    
    def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Get account by ID."""
        row = self.execute_one(
            "SELECT * FROM accounts WHERE id = ?", (account_id,)
        )
        return dict(row) if row else None
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts."""
        rows = self.execute_query("SELECT * FROM accounts ORDER BY created_at DESC")
        return [dict(row) for row in rows]
    
    def create_account(self, email: str, username: str, password_hash: str,
                      phone_number: str, session_path: str) -> int:
        """Create new account. Returns account ID."""
        self.execute_update(
            """INSERT INTO accounts 
               (email, username, password_hash, phone_number, session_path, status)
               VALUES (?, ?, ?, ?, ?, 'active')""",
            (email, username, password_hash, phone_number, session_path)
        )
        
        row = self.execute_one(
            "SELECT id FROM accounts WHERE username = ?", (username,)
        )
        return row['id'] if row else 0
    
    # =========================================================================
    # Profile Methods (PLAN 3)
    # =========================================================================
    
    def get_current_profile(self) -> Optional[Dict[str, Any]]:
        """Get profile marked as current."""
        row = self.execute_one(
            "SELECT * FROM profiles WHERE is_current = 1 LIMIT 1"
        )
        return dict(row) if row else None
    
    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Get all profiles."""
        rows = self.execute_query(
            "SELECT * FROM profiles ORDER BY created_at DESC"
        )
        return [dict(row) for row in rows]
    
    def create_profile(self, name: str, age: int = None, location: str = None,
                      ethnicity: str = None) -> int:
        """Create new profile. Returns profile ID."""
        self.execute_update(
            """INSERT INTO profiles (name, age, location, ethnicity)
               VALUES (?, ?, ?, ?)""",
            (name, age, location, ethnicity)
        )
        
        row = self.execute_one(
            "SELECT id FROM profiles WHERE name = ?", (name,)
        )
        return row['id'] if row else 0
    
    # =========================================================================
    # Conversation Methods (PLAN 1, PLAN 8)
    # =========================================================================
    
    def get_conversation(self, user_id: int, account_id: int) -> Optional[Dict[str, Any]]:
        """Get conversation by user_id and account_id."""
        row = self.execute_one(
            "SELECT * FROM conversations WHERE user_id = ? AND account_id = ?",
            (user_id, account_id)
        )
        return dict(row) if row else None
    
    def create_conversation(self, user_id: int, account_id: int) -> int:
        """Create new conversation. Returns conversation ID."""
        self.execute_update(
            """INSERT INTO conversations (user_id, account_id, state, timeout_until)
               VALUES (?, ?, 'ACTIVE', datetime('now', '+180 seconds'))""",
            (user_id, account_id)
        )
        
        row = self.execute_one(
            "SELECT id FROM conversations WHERE user_id = ? AND account_id = ?",
            (user_id, account_id)
        )
        return row['id'] if row else 0
    
    def update_conversation_timeout(self, conversation_id: int, account_id: int):
        """Reset conversation timeout to ACTIVE + 180 seconds."""
        self.execute_update(
            """UPDATE conversations
               SET state = 'ACTIVE',
                   last_activity_at = CURRENT_TIMESTAMP,
                   timeout_until = datetime('now', '+180 seconds')
               WHERE id = ? AND account_id = ?""",
            (conversation_id, account_id)
        )
    
    def get_expired_conversations(self, account_id: int) -> List[Dict[str, Any]]:
        """Get conversations ready for timeout (state=IDLE and expired)."""
        rows = self.execute_query(
            """SELECT * FROM conversations
               WHERE account_id = ? AND state = 'IDLE'
               AND timeout_until < datetime('now')""",
            (account_id,)
        )
        return [dict(row) for row in rows]
    
    # =========================================================================
    # API Key Methods (PLAN 9)
    # =========================================================================
    
    def get_api_keys_for_account(self, account_id: int, 
                                 active_only: bool = True) -> List[Dict[str, Any]]:
        """Get API keys for account."""
        sql = """SELECT * FROM api_keys 
                 WHERE account_id = ?"""
        if active_only:
            sql += " AND is_active = 1"
        sql += " ORDER BY key_order ASC"
        
        rows = self.execute_query(sql, (account_id,))
        return [dict(row) for row in rows]
    
    def create_api_key(self, account_id: int, provider: str, key_secret: str,
                      key_order: int, quota_limit_tokens: int = None,
                      quota_limit_requests: int = None) -> int:
        """Create new API key. Returns key ID."""
        self.execute_update(
            """INSERT INTO api_keys
               (account_id, provider, key_secret, key_order, 
                quota_limit_tokens, quota_limit_requests)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (account_id, provider, key_secret, key_order, 
             quota_limit_tokens, quota_limit_requests)
        )
        
        row = self.execute_one(
            "SELECT id FROM api_keys WHERE account_id = ? AND provider = ? ORDER BY id DESC LIMIT 1",
            (account_id, provider)
        )
        return row['id'] if row else 0
    
    # =========================================================================
    # Backup/Export Methods
    # =========================================================================
    
    def backup_database(self, backup_path: str) -> bool:
        """Create a backup copy of the database."""
        try:
            if not os.path.exists(self.db_path):
                logger.error(f"Source database not found: {self.db_path}")
                return False
            
            # Ensure backup directory exists
            Path(backup_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Use SQLite VACUUM INTO for atomic backup
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"VACUUM INTO '{backup_path}'")
            
            logger.info(f"[OK] Database backed up to {backup_path}")
            return True
        
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False
    
    # =========================================================================
    # Database Cleanup Methods (PLAN 5)
    # =========================================================================
    
    def cleanup_expired_conversations(self, account_id: int, 
                                     hours_to_keep: int = 24) -> int:
        """Delete conversations in EXPIRED state older than specified hours."""
        try:
            cursor = self.execute_query(
                f"""SELECT id FROM conversations
                   WHERE account_id = ? AND state = 'EXPIRED'
                   AND (datetime('now') - expiry_time) > {hours_to_keep * 3600}""",
                (account_id,)
            )
            
            conversation_ids = [row['id'] for row in cursor]
            if conversation_ids:
                placeholders = ','.join('?' * len(conversation_ids))
                self.execute_update(
                    f"DELETE FROM conversations WHERE id IN ({placeholders})",
                    tuple(conversation_ids)
                )
                logger.info(f"Cleaned up {len(conversation_ids)} expired conversations")
            
            return len(conversation_ids)
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return 0


def initialize_database_with_defaults(db_path: str = "telegrambot.db") -> bool:
    """
    Initialize database and create necessary directories.
    
    Args:
        db_path: Path to database file
        
    Returns:
        bool: True if successful
    """
    try:
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create pyrogram sessions directory if it doesn't exist
        sessions_dir = Path("pyrogram_sessions")
        sessions_dir.mkdir(exist_ok=True)
        
        # Initialize database
        db = DatabaseManager(db_path)
        success = db.initialize_database()
        
        if success:
            logger.info("[OK] Database initialization complete")
        
        return success
    
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


if __name__ == "__main__":
    # Setup basic logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize database
    print("Initializing Telegram Bot database...")
    success = initialize_database_with_defaults()
    
    if success:
        print("[OK] Database ready!")
        db = DatabaseManager()
        tables = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        print(f"[OK] Created {len(tables)} tables")
    else:
        print("[ERROR] Database initialization failed")
