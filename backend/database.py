import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Get database connection. Returns None if DATABASE_URL not set."""
    if not DATABASE_URL:
        return None
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    if not conn:
        print("DATABASE_URL not set - debate history disabled")
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS debates (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT NOW(),
                    question TEXT NOT NULL,
                    context JSONB,
                    recommendation TEXT,
                    confidence INTEGER,
                    consensus_level FLOAT,
                    executives JSONB,
                    final_decision JSONB
                )
            """)
            conn.commit()
        print("Database initialized")
        return True
    except Exception as e:
        print(f"Database init error: {e}")
        return False
    finally:
        conn.close()

def save_debate(debate_data: dict) -> bool:
    """Save a debate to the database."""
    conn = get_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO debates (id, question, context, recommendation, confidence, consensus_level, executives, final_decision)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    question = EXCLUDED.question,
                    context = EXCLUDED.context,
                    recommendation = EXCLUDED.recommendation,
                    confidence = EXCLUDED.confidence,
                    consensus_level = EXCLUDED.consensus_level,
                    executives = EXCLUDED.executives,
                    final_decision = EXCLUDED.final_decision
            """, (
                debate_data.get('id'),
                debate_data.get('question'),
                json.dumps(debate_data.get('context', {})),
                debate_data.get('recommendation'),
                debate_data.get('confidence'),
                debate_data.get('consensus_level'),
                json.dumps(debate_data.get('executives', {})),
                json.dumps(debate_data.get('final_decision', {}))
            ))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error saving debate: {e}")
        return False
    finally:
        conn.close()

def get_all_debates(limit: int = 50) -> list:
    """Get all debates, most recent first."""
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, created_at, question, recommendation, confidence, consensus_level
                FROM debates
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            # Convert datetime to ISO string
            for row in rows:
                if row['created_at']:
                    row['created_at'] = row['created_at'].isoformat()
            return rows
    except Exception as e:
        print(f"Error fetching debates: {e}")
        return []
    finally:
        conn.close()

def get_debate_by_id(debate_id: str) -> dict:
    """Get a single debate with full details."""
    conn = get_connection()
    if not conn:
        return None

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM debates WHERE id = %s
            """, (debate_id,))
            row = cur.fetchone()
            if row and row['created_at']:
                row['created_at'] = row['created_at'].isoformat()
            return row
    except Exception as e:
        print(f"Error fetching debate: {e}")
        return None
    finally:
        conn.close()

def delete_debate(debate_id: str) -> bool:
    """Delete a debate."""
    conn = get_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM debates WHERE id = %s", (debate_id,))
            conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting debate: {e}")
        return False
    finally:
        conn.close()

# Initialize database on module load
init_db()
