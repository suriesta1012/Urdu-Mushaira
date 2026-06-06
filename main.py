#!/usr/bin/env python3
"""
Main CLI entry point for Urdu Mushaira.
Provides commands for running, resuming, and querying mushaira sessions.

Usage:
    python main.py run --theme "ishq aur judai"
    python main.py resume --session-id <uuid>
    python main.py list
    python main.py stats
"""

import argparse
import sys
from pathlib import Path

from core.orchestrator import run_mushaira_simple, resume_mushaira
from core.persistence import SessionStore, StorageConfig


def cmd_run(args):
    """Run a new mushaira"""
    theme = args.theme
    storage_dir = args.storage_dir or "./data"
    
    print(f"\n🎭 Starting mushaira with theme: '{theme}'")
    
    try:
        session = run_mushaira_simple(
            theme=theme,
            storage_dir=storage_dir,
            verbose=True,
        )
        print(f"\n✅ Mushaira completed successfully!")
        print(f"   Session ID: {session.session_id}")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


def cmd_resume(args):
    """Resume an interrupted mushaira"""
    session_id = args.session_id
    storage_dir = args.storage_dir or "./data"
    
    print(f"\n📖 Resuming session: {session_id}")
    
    try:
        session = resume_mushaira(
            session_id=session_id,
            storage_dir=storage_dir,
        )
        print(f"\n✅ Session resumed")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


def cmd_list(args):
    """List recent mushaira sessions"""
    storage_dir = args.storage_dir or "./data"
    limit = args.limit or 20
    status_filter = args.status
    
    config = StorageConfig(base_dir=storage_dir)
    store = SessionStore(config)
    
    sessions = store.list_sessions(limit=limit, status_filter=status_filter)
    
    if not sessions:
        print("No sessions found")
        return 0
    
    print("\n📋 Recent Mushaira Sessions")
    print("=" * 100)
    print(f"{'ID':<36} {'Theme':<30} {'Status':<12} {'Poets':<8} {'Created':<20}")
    print("-" * 100)
    
    for session in sessions:
        session_id = session['session_id'][:8] + "..."
        theme = session['theme'][:28]
        status = session['status']
        poet_count = session['poet_count'] or 0
        created = session['created_at'][:10]
        
        print(f"{session_id:<36} {theme:<30} {status:<12} {poet_count:<8} {created:<20}")
    
    print("=" * 100)
    return 0


def cmd_stats(args):
    """Show aggregate statistics"""
    storage_dir = args.storage_dir or "./data"
    
    config = StorageConfig(base_dir=storage_dir)
    store = SessionStore(config)
    
    stats = store.get_session_stats()
    
    print("\n📊 Mushaira Statistics")
    print("=" * 60)
    print(f"Total sessions: {stats['total_sessions']}")
    print(f"Completed sessions: {stats['completed_sessions']}")
    print(f"Completion rate: {stats['completion_rate']:.1%}")
    print(f"Total tokens used: {stats['total_tokens_used']:,}")
    print(f"Total cost: ${stats['total_cost_usd']:.2f}")
    print("=" * 60)
    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Urdu Mushaira: AI-powered 7-poet recitation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a new mushaira
  python main.py run --theme "ishq aur judai"
  
  # Resume interrupted session
  python main.py resume --session-id abc123...
  
  # List recent sessions
  python main.py list --limit 10
  
  # Show statistics
  python main.py stats
        """,
    )
    
    parser.add_argument(
        "--storage-dir",
        default="./data",
        help="Directory for storing sessions and outputs (default: ./data)",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run a new mushaira")
    run_parser.add_argument(
        "--theme",
        required=True,
        help="Theme for the mushaira (e.g., 'ishq aur judai')",
    )
    run_parser.set_defaults(func=cmd_run)
    
    # resume command
    resume_parser = subparsers.add_parser("resume", help="Resume an interrupted mushaira")
    resume_parser.add_argument(
        "--session-id",
        required=True,
        help="Session UUID to resume",
    )
    resume_parser.set_defaults(func=cmd_resume)
    
    # list command
    list_parser = subparsers.add_parser("list", help="List recent sessions")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Number of sessions to show (default: 20)",
    )
    list_parser.add_argument(
        "--status",
        choices=["pending", "running", "completed", "failed", "paused"],
        help="Filter by status",
    )
    list_parser.set_defaults(func=cmd_list)
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show aggregate statistics")
    stats_parser.set_defaults(func=cmd_stats)
    
    # Parse args
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Run command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
