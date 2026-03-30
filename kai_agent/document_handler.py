"""
Document Handler for Kai
Handles PDF operations, form filling, document organization.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


class DocumentHandler:
    """Document management for Kai."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.docs_dir = workspace / "documents"
        self.docs_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories for organization
        for subdir in ["medical", "forms", "downloads", "misc"]:
            (self.docs_dir / subdir).mkdir(exist_ok=True)

    def organize_downloads(self) -> str:
        """Organize downloaded files into categories."""
        download_dir = self.workspace / "downloads"
        if not download_dir.exists():
            return json.dumps({"action": "organize_downloads", "ok": False, "error": "No downloads directory"}, indent=2)

        moved = []
        for f in download_dir.iterdir():
            if f.is_file():
                category = self._categorize_file(f)
                dest = self.docs_dir / category / f.name
                # Avoid overwriting
                if dest.exists():
                    dest = self.docs_dir / category / f"{f.stem}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{f.suffix}"
                shutil.move(str(f), str(dest))
                moved.append({"file": f.name, "category": category, "path": str(dest)})

        return json.dumps({"action": "organize_downloads", "ok": True, "moved": moved}, indent=2)

    def list_documents(self, category: str = None) -> str:
        """List documents, optionally filtered by category."""
        docs = []
        search_dir = self.docs_dir / category if category else self.docs_dir

        if not search_dir.exists():
            return json.dumps({"action": "list_documents", "ok": False, "error": f"Category not found: {category}"}, indent=2)

        for f in search_dir.rglob("*"):
            if f.is_file():
                docs.append({
                    "name": f.name,
                    "path": str(f),
                    "category": f.parent.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })

        docs.sort(key=lambda d: d["modified"], reverse=True)
        return json.dumps({"action": "list_documents", "ok": True, "documents": docs[:50]}, indent=2)

    def read_document(self, path: str) -> str:
        """Read a document's content (text files only, PDF requires external tools)."""
        target = Path(path)
        if not target.is_absolute():
            target = self.workspace / path

        if not target.exists():
            return json.dumps({"action": "read_document", "ok": False, "error": f"Not found: {target}"}, indent=2)

        ext = target.suffix.lower()

        if ext in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".log"):
            try:
                content = target.read_text(encoding="utf-8", errors="replace")[:10000]
                return json.dumps({"action": "read_document", "ok": True, "path": str(target), "content": content, "type": "text"}, indent=2)
            except Exception as exc:
                return json.dumps({"action": "read_document", "ok": False, "error": str(exc)}, indent=2)

        elif ext == ".pdf":
            # Try to extract text from PDF
            try:
                import subprocess
                result = subprocess.run(
                    ["python", "-c", f"import sys; from pathlib import Path; p=Path(r'{target}'); print(f'PDF: {{p.stat().st_size}} bytes')"],
                    capture_output=True, text=True, timeout=10,
                )
                return json.dumps({
                    "action": "read_document",
                    "ok": True,
                    "path": str(target),
                    "type": "pdf",
                    "size": target.stat().st_size,
                    "message": "PDF detected. Use /screen after opening in a viewer, or install PyPDF2/pymupdf for text extraction.",
                }, indent=2)
            except Exception as exc:
                return json.dumps({"action": "read_document", "ok": False, "error": str(exc)}, indent=2)

        else:
            return json.dumps({
                "action": "read_document",
                "ok": True,
                "path": str(target),
                "type": ext,
                "size": target.stat().st_size,
                "message": f"File type {ext} - use appropriate viewer",
            }, indent=2)

    def find_document(self, query: str) -> str:
        """Find documents matching a query."""
        query_lower = query.lower()
        matches = []

        for f in self.docs_dir.rglob("*"):
            if f.is_file() and query_lower in f.name.lower():
                matches.append({
                    "name": f.name,
                    "path": str(f),
                    "category": f.parent.name,
                    "size": f.stat().st_size,
                })

        # Also search in downloads
        download_dir = self.workspace / "downloads"
        if download_dir.exists():
            for f in download_dir.iterdir():
                if f.is_file() and query_lower in f.name.lower():
                    matches.append({
                        "name": f.name,
                        "path": str(f),
                        "category": "downloads",
                        "size": f.stat().st_size,
                    })

        return json.dumps({"action": "find_document", "ok": True, "query": query, "matches": matches}, indent=2)

    def _categorize_file(self, path: Path) -> str:
        """Categorize a file based on its name and extension."""
        name_lower = path.name.lower()

        medical_keywords = ["patient", "medical", "health", "hospital", "clinic", "doctor", "prescription", "insurance", "hipaa", "release", "consent"]
        if any(kw in name_lower for kw in medical_keywords):
            return "medical"

        form_keywords = ["form", "application", "registration", "signup", "enrollment", "request"]
        if any(kw in name_lower for kw in form_keywords):
            return "forms"

        return "misc"

    def get_stats(self) -> str:
        """Get document library statistics."""
        stats = {}
        total_files = 0
        total_size = 0

        for category_dir in self.docs_dir.iterdir():
            if category_dir.is_dir():
                files = list(category_dir.rglob("*"))
                file_count = len([f for f in files if f.is_file()])
                dir_size = sum(f.stat().st_size for f in files if f.is_file())
                stats[category_dir.name] = {"files": file_count, "size": dir_size}
                total_files += file_count
                total_size += dir_size

        return json.dumps({
            "action": "document_stats",
            "ok": True,
            "total_files": total_files,
            "total_size": total_size,
            "categories": stats,
        }, indent=2)
