"""
Simple log viewer utility for analyzing Tata Play logs.
Provides real-time viewing and basic analysis features.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from collections import Counter
import time


class LogViewer:
    """Utility for viewing and analyzing logs."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        if not self.log_dir.exists():
            print(f"❌ Log directory not found: {log_dir}")
            print(f"   Please ensure the application has been run and logs created.")
            sys.exit(1)
    
    def list_logs(self):
        """List all available log files."""
        log_files = list(self.log_dir.glob("*.log"))
        
        if not log_files:
            print("❌ No log files found in logs/ directory")
            return
        
        print("\n📁 Available Log Files:")
        print("=" * 60)
        
        for log_file in sorted(log_files):
            size = log_file.stat().st_size
            size_mb = size / (1024 * 1024)
            modified = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            print(f"  📄 {log_file.name}")
            print(f"     Size: {size_mb:.2f} MB")
            print(f"     Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    
    def tail(self, log_file: str = "tataplay_app.log", lines: int = 20):
        """Show last N lines of a log file."""
        file_path = self.log_dir / log_file
        
        if not file_path.exists():
            print(f"❌ Log file not found: {log_file}")
            return
        
        print(f"\n📋 Last {lines} lines of {log_file}:")
        print("=" * 80)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            for line in all_lines[-lines:]:
                print(line.rstrip())
        
        print("=" * 80)
    
    def follow(self, log_file: str = "tataplay_app.log"):
        """Follow a log file in real-time (like tail -f)."""
        file_path = self.log_dir / log_file
        
        if not file_path.exists():
            print(f"❌ Log file not found: {log_file}")
            return
        
        print(f"\n👀 Following {log_file} (Ctrl+C to stop)...")
        print("=" * 80)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            # Move to end of file
            f.seek(0, 2)
            
            try:
                while True:
                    line = f.readline()
                    if line:
                        print(line.rstrip())
                    else:
                        time.sleep(0.1)
            except KeyboardInterrupt:
                print("\n\n✅ Stopped following log file")
    
    def search(self, pattern: str, log_file: str = "tataplay_app.log", context: int = 0):
        """Search for a pattern in log files."""
        file_path = self.log_dir / log_file
        
        if not file_path.exists():
            print(f"❌ Log file not found: {log_file}")
            return
        
        print(f"\n🔍 Searching for '{pattern}' in {log_file}:")
        print("=" * 80)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            matches = []
            
            for i, line in enumerate(lines):
                if pattern.lower() in line.lower():
                    matches.append((i, line))
        
        if not matches:
            print(f"❌ No matches found for '{pattern}'")
            return
        
        print(f"✅ Found {len(matches)} matches:")
        print()
        
        for line_num, line in matches:
            print(f"Line {line_num + 1}: {line.rstrip()}")
            
            # Show context if requested
            if context > 0:
                print("  Context:")
                start = max(0, line_num - context)
                end = min(len(lines), line_num + context + 1)
                for i in range(start, end):
                    if i != line_num:
                        print(f"    {lines[i].rstrip()}")
                print()
    
    def stats(self, log_file: str = "tataplay_access.log"):
        """Show statistics from access logs."""
        file_path = self.log_dir / log_file
        
        if not file_path.exists():
            print(f"❌ Log file not found: {log_file}")
            return
        
        print(f"\n📊 Statistics for {log_file}:")
        print("=" * 80)
        
        endpoints = []
        status_codes = []
        methods = []
        durations = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Try to parse as JSON
                try:
                    data = json.loads(line)
                    if 'endpoint' in data:
                        endpoints.append(data['endpoint'])
                    if 'status_code' in data:
                        status_codes.append(data['status_code'])
                    if 'method' in data:
                        methods.append(data['method'])
                    if 'duration' in data:
                        durations.append(float(data['duration']))
                except json.JSONDecodeError:
                    # Not JSON, try to parse text format
                    if 'Request completed:' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.startswith('/'):
                                endpoints.append(part)
                            if part.startswith('Status:'):
                                try:
                                    status_codes.append(int(parts[i+1]))
                                except:
                                    pass
                            if 'duration=' in part:
                                try:
                                    duration = float(part.split('=')[1].rstrip('s'))
                                    durations.append(duration)
                                except:
                                    pass
        
        # Display statistics
        if endpoints:
            print("\n🎯 Top Endpoints:")
            for endpoint, count in Counter(endpoints).most_common(10):
                print(f"  {count:4d} requests - {endpoint}")
        
        if status_codes:
            print("\n📈 Status Codes:")
            for code, count in sorted(Counter(status_codes).items()):
                emoji = "✅" if 200 <= code < 300 else "⚠️" if 300 <= code < 400 else "❌"
                print(f"  {emoji} {code}: {count:4d} requests")
        
        if methods:
            print("\n🔧 HTTP Methods:")
            for method, count in Counter(methods).most_common():
                print(f"  {method:6s}: {count:4d} requests")
        
        if durations:
            print("\n⏱️  Response Times:")
            print(f"  Average: {sum(durations)/len(durations):.3f}s")
            print(f"  Min:     {min(durations):.3f}s")
            print(f"  Max:     {max(durations):.3f}s")
            
            # Find slow requests
            slow = [d for d in durations if d > 1.0]
            if slow:
                print(f"  Slow requests (>1s): {len(slow)} ({len(slow)/len(durations)*100:.1f}%)")
        
        print("=" * 80)
    
    def errors(self, log_file: str = "tataplay_error.log", limit: int = 10):
        """Show recent errors."""
        file_path = self.log_dir / log_file
        
        if not file_path.exists():
            print(f"❌ Log file not found: {log_file}")
            return
        
        print(f"\n❌ Recent Errors from {log_file}:")
        print("=" * 80)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            if not lines:
                print("✅ No errors found!")
                return
            
            # Show last N errors
            for line in lines[-limit:]:
                try:
                    data = json.loads(line)
                    print(f"\n⏰ {data.get('timestamp', 'N/A')}")
                    print(f"📝 {data.get('message', 'N/A')}")
                    if 'exception' in data:
                        print(f"🔥 {data['exception'][:200]}...")
                except json.JSONDecodeError:
                    print(line.rstrip())
        
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Tata Play Log Viewer Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_logs.py list                    # List all log files
  python view_logs.py tail                    # Show last 20 lines
  python view_logs.py tail -n 50             # Show last 50 lines
  python view_logs.py follow                  # Follow logs in real-time
  python view_logs.py search "error"          # Search for pattern
  python view_logs.py stats                   # Show access log statistics
  python view_logs.py errors                  # Show recent errors
        """
    )
    
    parser.add_argument('command', choices=['list', 'tail', 'follow', 'search', 'stats', 'errors'],
                       help='Command to execute')
    parser.add_argument('-f', '--file', default='tataplay_app.log',
                       help='Log file to operate on (default: tataplay_app.log)')
    parser.add_argument('-n', '--lines', type=int, default=20,
                       help='Number of lines to show (default: 20)')
    parser.add_argument('-p', '--pattern', 
                       help='Search pattern')
    parser.add_argument('-c', '--context', type=int, default=0,
                       help='Number of context lines to show around matches')
    parser.add_argument('--limit', type=int, default=10,
                       help='Limit for error display (default: 10)')
    
    args = parser.parse_args()
    
    viewer = LogViewer()
    
    if args.command == 'list':
        viewer.list_logs()
    elif args.command == 'tail':
        viewer.tail(args.file, args.lines)
    elif args.command == 'follow':
        viewer.follow(args.file)
    elif args.command == 'search':
        if not args.pattern:
            print("❌ Error: --pattern required for search command")
            sys.exit(1)
        viewer.search(args.pattern, args.file, args.context)
    elif args.command == 'stats':
        viewer.stats(args.file)
    elif args.command == 'errors':
        viewer.errors(args.file, args.limit)


if __name__ == "__main__":
    main()
