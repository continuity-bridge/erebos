import plyvel

db_path = '/home/tallest/.config/claude-harness/free1/session-data/Local Storage/leveldb'

# Define the exact prefix bytes Chromium is using
PREFIX = b'_https://claude.ai\x00\x01'

try:
    # Ensure the free1 instance is fully closed so the lockfile is free
    db = plyvel.DB(db_path, create_if_missing=False)
    
    print("--- Targeted LevelDB Sweep Started ---")
    match_count = 0
    
    for key, value in db:
        if key.startswith(PREFIX):
            # Strip the protocol layout prefix to isolate the actual key name
            clean_key_bytes = key[len(PREFIX):]
            
            # Decode using ignore/replace to handle trailing binary markers safely
            key_name = clean_key_bytes.decode('utf-8', errors='ignore')
            
            # Print any keys that handle state, authentication, or tokens
            if any(x in key_name.lower() for x in ["token", "auth", "session", "user", "key"]):
                match_count += 1
                value_str = value.decode('utf-8', errors='ignore')
                
                print(f"[{match_count}] Clean Key: {repr(key_name)}")
                print(f"    -> Value: {value_str[:120]}...")
                print("-" * 50)
                
    db.close()
    print(f"--- Sweep Complete. Found {match_count} target keys. ---")

except Exception as e:
    print(f"Error reading LevelDB: {e}")