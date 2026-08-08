-- JARVIS v4 SQLite Database Schema

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    thought TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    key_name TEXT NOT NULL UNIQUE,
    value_data TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS self_learning_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_phrase TEXT NOT NULL,
    wrong_behavior TEXT NOT NULL,
    corrected_behavior TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_shortcuts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL UNIQUE,
    executable_path TEXT NOT NULL,
    launch_args TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_name TEXT NOT NULL UNIQUE,
    phone_number TEXT,
    email_address TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    module TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Initial default facts & shortcuts
INSERT OR IGNORE INTO user_facts (category, key_name, value_data) VALUES 
('user', 'user_name', 'Sir'),
('preferences', 'theme', 'dark_neon'),
('preferences', 'wake_word', 'jarvis');

INSERT OR IGNORE INTO app_shortcuts (app_name, executable_path) VALUES 
('chrome', 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'),
('edge', 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'),
('vscode', 'code'),
('notepad', 'notepad.exe'),
('calculator', 'calc.exe'),
('paint', 'mspaint.exe'),
('cmd', 'cmd.exe'),
('powershell', 'powershell.exe'),
('explorer', 'explorer.exe');
