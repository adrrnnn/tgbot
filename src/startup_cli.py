"""
CLI Setup Flow for Telegram Bot Manager
Handles:
  1. Dependency checking
  2. Dependency installation (if missing)
  3. Telegram account check
  4. Telegram credential prompts
  5. Database save
"""

import sys
import subprocess
import re
from typing import Dict, Tuple, Optional
import getpass
from src.database import DatabaseManager
from src.config import ConfigManager


class CliSetup:
    """Handles command-line setup flow"""
    
    DEPENDENCIES = {
        'pyrogram': '2.0.106',
        'PyQt5': '5.15.0',
        'cryptography': None,
        'requests': None,
    }
    
    def __init__(self, db: DatabaseManager, config: ConfigManager):
        self.db = db
        self.config = config
        self.logger = None
    
    def run(self) -> bool:
        """Run complete setup flow"""
        print("\n" + "="*70)
        print("TELEGRAM BOT MANAGER - SETUP")
        print("="*70 + "\n")
        
        # Step 1: Check dependencies
        print("[1/4] Checking dependencies...")
        missing = self._check_dependencies()
        
        if missing:
            print(f"\n❌ Missing dependencies: {list(missing.keys())}")
            if not self._prompt_install_dependencies(missing):
                print("Cannot proceed without dependencies. Exiting.")
                return False
        else:
            print("[OK] All dependencies found\n")
        
        # Step 2: Check if Telegram account exists
        print("[2/4] Checking for saved Telegram account...")
        account_exists = self._check_telegram_account_exists()
        
        if account_exists:
            print("[OK] Telegram account found in database\n")
        else:
            print("No account found. Setting up Telegram credentials...\n")
            if not self._prompt_telegram_login():
                print("Setup cancelled. Exiting.")
                return False
        
        print("\n" + "="*70)
        print("[OK] Setup complete! Launching main application...")
        print("="*70 + "\n")
        return True
    
    def _check_dependencies(self) -> Dict[str, str]:
        """Check if all required dependencies are installed"""
        missing = {}
        
        print()
        for package, version in self.DEPENDENCIES.items():
            try:
                __import__(package.replace('-', '_').lower() if package != 'PyQt5' else 'PyQt5')
                if version:
                    print(f"  [OK] {package} ({version})")
                else:
                    print(f"  [OK] {package}")
            except ImportError:
                missing[package] = version
                print(f"  [ERROR] {package} (MISSING)")
        
        return missing
    
    def _prompt_install_dependencies(self, missing: Dict[str, str]) -> bool:
        """Prompt user to install missing dependencies"""
        print()
        response = input("Would you like to install missing dependencies? (y/n): ").strip().lower()
        
        if response != 'y':
            return False
        
        print("\nInstalling dependencies...")
        print("-" * 70)
        
        pip_packages = []
        for package, version in missing.items():
            if version:
                pip_packages.append(f"{package}=={version}")
            else:
                pip_packages.append(package)
        
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install"] + pip_packages,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("-" * 70)
            print("[OK] Dependencies installed successfully\n")
            return True
        except subprocess.CalledProcessError as e:
            print("-" * 70)
            print(f"❌ Failed to install dependencies: {e}")
            print("Please install manually using:")
            print(f"  pip install {' '.join(pip_packages)}")
            return False
    
    def _check_telegram_account_exists(self) -> bool:
        """Check if Telegram account exists in database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, phone FROM accounts WHERE account_type = 'telegram' LIMIT 1"
                )
                result = cursor.fetchone()
                
                if result:
                    account_id, phone = result
                    print(f"  [OK] Account found: {phone}")
                    return True
            return False
        except Exception as e:
            print(f"  ⚠ Could not check account: {e}")
            return False
    
    def _prompt_telegram_login(self) -> bool:
        """Prompt user for Telegram credentials"""
        print()
        print("TELEGRAM ACCOUNT SETUP")
        print("-" * 70)
        print("You need credentials from https://my.telegram.org/apps\n")
        
        # Phone number
        while True:
            phone = input("Enter your Telegram phone number (e.g., +1234567890): ").strip()
            phone = self._validate_phone(phone)
            if phone:
                break
            print("  ❌ Invalid phone format. Use: +1234567890 or similar\n")
        
        # API ID
        while True:
            api_id = input("Enter API ID (from https://my.telegram.org/apps): ").strip()
            if self._validate_api_id(api_id):
                break
            print("  ❌ API ID must be 6-10 numeric digits\n")
        
        # API Hash
        while True:
            api_hash = input("Enter API Hash (from https://my.telegram.org/apps): ").strip()
            if self._validate_api_hash(api_hash):
                break
            print("  ❌ API Hash must be 32 hexadecimal characters\n")
        
        # 2FA Password (optional)
        print("\nDo you have 2-factor authentication enabled? (y/n): ", end="")
        has_2fa = input().strip().lower() == 'y'
        password = None
        
        if has_2fa:
            password = getpass.getpass("Enter 2FA password (hidden): ")
            if not password or len(password) < 4:
                print("  ❌ Password too short (min 4 characters)")
                return False
        
        # Save to database
        print("\n" + "-" * 70)
        print("Saving credentials to database...\n")
        
        try:
            self._save_telegram_credentials(phone, api_id, api_hash, password)
            print("[OK] Credentials saved successfully")
            
            # Also save to config.json for quick access
            self.config.data['telegram'] = {
                'phone': phone,
                'api_id': api_id,
                'api_hash': api_hash,
            }
            self.config.save()
            print("[OK] Saved to config.json\n")
            return True
        
        except Exception as e:
            print(f"❌ Failed to save credentials: {e}")
            return False
    
    def _validate_phone(self, phone: str) -> Optional[str]:
        """Validate and normalize phone number"""
        # Remove spaces, dashes, parentheses
        cleaned = re.sub(r'[\s\-().]', '', phone)
        
        # Must be numeric with at least 10 digits, max 15
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            return None
        
        # Ensure it starts with +
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        return cleaned
    
    def _validate_api_id(self, api_id: str) -> bool:
        """Validate API ID format"""
        return bool(re.match(r'^\d{6,10}$', api_id.strip()))
    
    def _validate_api_hash(self, api_hash: str) -> bool:
        """Validate API Hash format"""
        api_hash = api_hash.strip()
        return len(api_hash) == 32 and bool(re.match(r'^[a-f0-9]{32}$', api_hash.lower()))
    
    def _save_telegram_credentials(self, phone: str, api_id: str, api_hash: str, password: Optional[str]) -> None:
        """Save credentials to database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if account already exists
                cursor.execute(
                    "SELECT id FROM accounts WHERE account_type = 'telegram' AND phone = ?",
                    (phone,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing
                    cursor.execute(
                        """UPDATE accounts 
                           SET api_id = ?, api_hash = ?, password = ?, is_active = 1, updated_at = datetime('now')
                           WHERE id = ?""",
                        (api_id, api_hash, password, existing[0])
                    )
                else:
                    # Insert new
                    cursor.execute(
                        """INSERT INTO accounts 
                           (account_type, phone, api_id, api_hash, password, is_active, created_at)
                           VALUES (?, ?, ?, ?, ?, 1, datetime('now'))""",
                        ('telegram', phone, api_id, api_hash, password)
                    )
        
        except Exception as e:
            raise Exception(f"Database error: {e}")


def run_cli_setup(db: DatabaseManager, config: ConfigManager) -> bool:
    """
    Main entry point for CLI setup
    
    Args:
        db: DatabaseManager instance
        config: ConfigManager instance
    
    Returns:
        bool: True if setup completed successfully
    """
    setup = CliSetup(db, config)
    return setup.run()
