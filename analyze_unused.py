#!/usr/bin/env python3
"""
Analyze Python files to find unused code in Django project.
Tracks imports, references, and usage patterns.
"""
import os
import re
import ast
from pathlib import Path
from collections import defaultdict

class FileAnalyzer:
    def __init__(self):
        self.imports = defaultdict(set)  # file -> set of imported modules
        self.references = defaultdict(set)  # file -> set of referenced files
        self.service_methods = defaultdict(set)  # service -> set of methods
        self.view_functions = defaultdict(set)  # view -> set of functions
        self.url_patterns = defaultdict(set)  # view -> set of URL names

    def extract_imports(self, filepath):
        """Extract all import statements from a Python file."""
        imports = set()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content, filename=filepath)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        imports.add(module)

        except Exception as e:
            print(f"Error parsing {filepath}: {e}")

        return imports

    def extract_function_names(self, filepath):
        """Extract function and class names from a Python file."""
        functions = set()
        classes = set()
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content, filename=filepath)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.add(node.name)

        except Exception as e:
            print(f"Error parsing {filepath}: {e}")

        return functions, classes

    def find_file_for_module(self, module_name):
        """Find the file path for a given module name."""
        # Convert module import to file path
        if module_name == 'dominial':
            return './dominial'
        elif module_name.startswith('dominial.'):
            parts = module_name.split('.')
            if len(parts) >= 2:
                subpath = '/'.join(parts[1:])
                # Try different combinations
                for path in [
                    f"./dominial/{subpath}.py",
                    f"./dominial/{subpath}/__init__.py",
                ]:
                    if os.path.exists(path):
                        return path
        return None

    def analyze_project(self):
        """Analyze the entire project structure."""
        all_files = []

        # Collect all Python files
        for root, dirs, files in os.walk('.'):
            # Exclude .venv, __pycache__, and migrations
            dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', 'migrations']]

            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    all_files.append(full_path)

        # Analyze each file
        file_info = {}
        for filepath in all_files:
            imports = self.extract_imports(filepath)
            functions, classes = self.extract_function_names(filepath)

            file_info[filepath] = {
                'imports': imports,
                'functions': functions,
                'classes': classes,
            }

        return file_info, all_files

def main():
    analyzer = FileAnalyzer()
    file_info, all_files = analyzer.analyze_project()

    # Build reference map
    referenced_files = set()

    # Check which files are imported
    for filepath, info in file_info.items():
        for imp in info['imports']:
            target_file = analyzer.find_file_for_module(imp)
            if target_file and os.path.exists(target_file):
                referenced_files.add(target_file)

    # Find all files that aren't directly referenced
    potentially_unused = []
    for filepath in all_files:
        # Skip __init__ files and main entry points
        if filepath.endswith('__init__.py'):
            continue
        if filepath in ['./manage.py', './cadeia_dominial/wsgi.py', './cadeia_dominial/asgi.py']:
            continue

        # Check if file is in models/, views/, services/, forms/
        if any(x in filepath for x in ['/models/', '/views/', '/services/', '/forms/']):
            # These need special checking
            module_path = filepath.replace('./', '').replace('.py', '').replace('/', '.')
            if module_path.startswith('dominial.'):
                if filepath not in referenced_files:
                    potentially_unused.append(filepath)
        else:
            # Management commands, tests, utils are less likely to be imported
            pass

    print("=" * 80)
    print("POTENTIALLY UNUSED FILES (need manual verification):")
    print("=" * 80)
    for f in sorted(potentially_unused):
        print(f"\n{f}")
        # Show what it exports
        if f in file_info:
            info = file_info[f]
            if info['functions']:
                print(f"  Functions: {', '.join(list(info['functions'])[:5])}")
            if info['classes']:
                print(f"  Classes: {', '.join(list(info['classes'])[:5])}")

    print("\n" + "=" * 80)
    print(f"Total files analyzed: {len(all_files)}")
    print(f"Potentially unused files: {len(potentially_unused)}")
    print("=" * 80)

if __name__ == '__main__':
    main()
