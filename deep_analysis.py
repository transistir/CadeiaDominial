#!/usr/bin/env python3
"""
Deep analysis of Django codebase to find truly unused files.
Checks imports, URL references, template usage, and admin registration.
"""
import os
import re
from pathlib import Path
from collections import defaultdict

class DeepAnalyzer:
    def __init__(self):
        self.file_usage = defaultdict(int)
        self.class_usage = defaultdict(int)
        self.function_usage = defaultdict(int)
        self.url_references = set()
        self.admin_registered = set()

    def search_references(self, search_term, file_pattern='*.py'):
        """Search for references to a term across the codebase."""
        references = []
        for root, dirs, files in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', 'migrations']]

            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if search_term in content:
                                # Count occurrences
                                count = content.count(search_term)
                                references.append((filepath, count))
                    except:
                        pass
        return references

    def check_url_file(self):
        """Extract all view function references from URLs."""
        url_views = set()
        try:
            with open('./dominial/urls.py', 'r') as f:
                content = f.read()
                # Extract view function names from path() calls
                matches = re.findall(r'path\(\'[^\']+\',\s*(\w+)', content)
                url_views.update(matches)
                # Also check for views.X format
                matches = re.findall(r'views\.(\w+)', content)
                url_views.update(matches)
        except:
            pass
        return url_views

    def check_admin_file(self):
        """Extract all models registered in admin."""
        registered = set()
        try:
            with open('./dominial/admin.py', 'r') as f:
                content = f.read()
                # Find @admin.register decorators
                matches = re.findall(r'@admin\.register\((\w+)\)', content)
                registered.update(matches)
                # Find admin.site.register calls
                matches = re.findall(r'admin\.site\.register\((\w+)\)', content)
                registered.update(matches)
        except:
            pass
        return registered

    def analyze_file(self, filepath):
        """Analyze a single file and determine if it's used."""
        base_name = os.path.basename(filepath).replace('.py', '')

        # Special cases that are always used
        if filepath.endswith('__init__.py'):
            return 'USED', '__init__ file'
        if filepath in ['./manage.py', './cadeia_dominial/settings.py',
                        './cadeia_dominial/urls.py', './cadeia_dominial/wsgi.py',
                        './cadeia_dominial/asgi.py', './dominial/apps.py']:
            return 'USED', 'Core Django file'

        # Check if it's a model file
        if '/models/' in filepath:
            # Extract model class names
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Find class definitions
                    classes = re.findall(r'class (\w+)\(', content)

                    for cls in classes:
                        refs = self.search_references(cls)
                        if refs:
                            # Filter out the file itself
                            external_refs = [(f, c) for f, c in refs if f != filepath]
                            if external_refs:
                                return 'USED', f'Model {cls} is referenced in {len(external_refs)} places'
                return 'CHECK', f'Model file with unclear usage'
            except:
                return 'ERROR', 'Could not read file'

        # Check if it's a view file
        if '/views/' in filepath:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Find function definitions
                    funcs = re.findall(r'^def (\w+)\(', content, re.MULTILINE)

                    # Check if any function is referenced in URLs
                    url_views = self.check_url_file()
                    for func in funcs:
                        if func in url_views:
                            return 'USED', f'View function {func} in URLs'

                    # Check if file is imported in urls.py
                    try:
                        with open('./dominial/urls.py', 'r') as urlf:
                            url_content = urlf.read()
                            if base_name.replace('_', '') in url_content or base_name in url_content:
                                return 'USED', 'View module imported in URLs'
                    except:
                        pass

                    if funcs:
                        return 'CHECK', f'View file with {len(funcs)} functions, not in URLs'
                    return 'UNUSED', 'No view functions found'
            except:
                return 'ERROR', 'Could not read file'

        # Check if it's a service file
        if '/services/' in filepath:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Find class definitions
                    classes = re.findall(r'class (\w+Service)', content)

                    for cls in classes:
                        # Search for imports of this service
                        search_pattern = f'from.*{cls}'
                        refs = self.search_references(search_pattern)
                        if refs:
                            external_refs = [(f, c) for f, c in refs if f != filepath]
                            if external_refs:
                                return 'USED', f'Service {cls} used in {len(external_refs)} places'

                    if classes:
                        return 'CHECK', f'Service file with {len(classes)} services, not directly referenced'
                    return 'UNUSED', 'No service classes found'
            except:
                return 'ERROR', 'Could not read file'

        # Check if it's a form file
        if '/forms/' in filepath:
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Find class definitions
                    classes = re.findall(r'class (\w+Form)', content)

                    for cls in classes:
                        refs = self.search_references(cls)
                        if refs:
                            external_refs = [(f, c) for f, c in refs if f != filepath]
                            if external_refs:
                                return 'USED', f'Form {cls} used in {len(external_refs)} places'

                    if classes:
                        return 'CHECK', f'Form file with {len(classes)} forms, not directly referenced'
                    return 'UNUSED', 'No form classes found'
            except:
                return 'ERROR', 'Could not read file'

        # Management commands are used manually
        if '/management/commands/' in filepath:
            return 'USED', 'Management command (used manually)'

        # Tests are always kept
        if '/tests/' in filepath or filepath.startswith('./dominial/tests'):
            return 'USED', 'Test file'

        # Utils might be imported dynamically
        if '/utils/' in filepath or filepath.endswith('utils.py'):
            try:
                with open(filepath, 'r') as f:
                    content = f.read()
                    funcs = re.findall(r'^def (\w+)\(', content, re.MULTILINE)

                    for func in funcs[:5]:  # Check first 5 functions
                        refs = self.search_references(func)
                        if refs:
                            external_refs = [(f, c) for f, c in refs if f != filepath]
                            if external_refs:
                                return 'USED', f'Util function {func} used'

                    return 'CHECK', 'Utils file - usage unclear'
            except:
                return 'ERROR', 'Could not read file'

        return 'UNKNOWN', 'Unclear file type'

def main():
    analyzer = DeepAnalyzer()

    print("=" * 100)
    print("DEEP ANALYSIS OF DJANGO CODEBASE")
    print("=" * 100)

    results = {
        'USED': [],
        'CHECK': [],
        'UNUSED': [],
        'ERROR': [],
        'UNKNOWN': []
    }

    # Analyze all Python files
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', 'migrations']]

        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                status, reason = analyzer.analyze_file(filepath)
                results[status].append((filepath, reason))

    # Print results by category
    print("\n" + "=" * 100)
    print("✅ USED FILES (clearly in use - DO NOT DELETE)")
    print("=" * 100)
    for filepath, reason in sorted(results['USED']):
        print(f"{filepath}")
        print(f"  → {reason}")

    print("\n" + "=" * 100)
    print("⚠️  CHECK FILES (unclear usage - MANUAL VERIFICATION NEEDED)")
    print("=" * 100)
    for filepath, reason in sorted(results['CHECK']):
        print(f"{filepath}")
        print(f"  → {reason}")

    print("\n" + "=" * 100)
    print("❌ UNUSED FILES (candidates for deletion)")
    print("=" * 100)
    for filepath, reason in sorted(results['UNUSED']):
        print(f"{filepath}")
        print(f"  → {reason}")

    print("\n" + "=" * 100)
    print("📊 SUMMARY")
    print("=" * 100)
    print(f"✅ Used:      {len(results['USED'])} files")
    print(f"⚠️  Check:     {len(results['CHECK'])} files")
    print(f"❌ Unused:    {len(results['UNUSED'])} files")
    print(f"❌ Error:     {len(results['ERROR'])} files")
    print(f"❓ Unknown:   {len(results['UNKNOWN'])} files")
    print("=" * 100)

if __name__ == '__main__':
    main()
