#!/usr/bin/env python3
import os
import sqlite3
import json

HARNESS_BASE = os.path.expanduser('~/.config/claude-harness')
CANONICAL_FALLBACKS = [
    os.path.expanduser('~/.config/claude-desktop'),
    os.path.expanduser('~/.config/claude'),
    os.path.expanduser('~/.config/Claude')  # Enforcing absolute casing matching your directory path
]
PROFILES = ['pro', 'free1', 'free2', 'free3']

def extract_token_from_db(db_path):
    """Safely attempts to extract the sessionKey from a target SQLite Cookies vault."""
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM cookies WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey';")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except sqlite3.OperationalError:
        return "LOCKED"  # Explicitly flag an active engine instance lock
    except Exception:
        pass
    return None

print(f"==================================================")
print(f"   STOA CORE: EREBOS MULTI-SESSION TOKEN Census   ")
print(f"==================================================")

for profile in PROFILES:
    cookie_path = os.path.join(HARNESS_BASE, profile, 'session-data', 'Cookies')
    config_path = os.path.join(HARNESS_BASE, profile, 'session-data', 'claude_desktop_config.json')
    
    # Extract token using primary harness target path
    token = extract_token_from_db(cookie_path)
    
    # Branching fallback logic: If PRO failed to pull a token, sweep canonical paths
    if profile == 'pro' and (token is None or token == "LOCKED"):
        for fallback_root in CANONICAL_FALLBACKS:
            fallback_cookie = os.path.join(fallback_root, 'Cookies')
            fallback_token = extract_token_from_db(fallback_cookie)
            
            if fallback_token:
                token = fallback_token
                config_path = os.path.join(fallback_root, 'claude_desktop_config.json')
                break

    # Extract Account ID safely handling your nested configuration schema
    account_id = "Unknown"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = json.load(f)
                accounts = cfg.get('coworkModelAutoFallbackByAccount')
                if not accounts and 'preferences' in cfg:
                    accounts = cfg['preferences'].get('coworkModelAutoFallbackByAccount', {})
                if accounts:
                    account_id = list(accounts.keys())[0]
        except Exception:
            pass

    # Print Final Consolidated Output
    print(f"[+] Profile: {profile.upper()}")
    print(f"    Account ID:  {account_id}")
    
    if token == "LOCKED":
        print(f"    Session Key: Database Locked (Instance Running).")
    elif token:
        print(f"    Session Key: {token}")
    else:
        print(f"    Session Key: Empty or Session Expired.")
        
    print(f"--------------------------------------------------")