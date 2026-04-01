from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"


setup(
    name="notion-pm-bridge",
    version="0.1.0",
    description="Repo-first handoff bridge that turns approved plans into reviewed Notion execution workspaces for humans and agents.",
    long_description=README.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    author="OpenAI Codex",
    python_requires=">=3.11",
    license="MIT",
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "pm=notion_pm_bridge.cli:main",
        ]
    },
    project_urls={
        "Homepage": "https://github.com/kyungmin-kang/shared-plan-handoff",
        "Repository": "https://github.com/kyungmin-kang/shared-plan-handoff",
        "Issues": "https://github.com/kyungmin-kang/shared-plan-handoff/issues",
    },
    keywords=["codex", "notion", "handoff", "planning", "workflow-automation", "ai-agents"],
)
