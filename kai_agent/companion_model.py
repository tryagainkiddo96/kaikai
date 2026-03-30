"""
Kai Companion Model
UI interaction patterns and intent system for Kai's interface.
Based on Codex's companion_model.py — preserved for the UI layer.
"""

# Kai's intents — what the user might want
KAI_INTENTS = [
    {
        "name": "Build",
        "description": "Code help, debugging, and shipping ideas.",
        "prompt": "Help me build this step by step.",
        "examples": ["Debug this error", "Plan a feature", "Review some code"],
    },
    {
        "name": "Learn",
        "description": "Explanations, summaries, and tutoring.",
        "prompt": "Teach me this in a simple way.",
        "examples": ["Explain a concept", "Quiz me", "Summarize this"],
    },
    {
        "name": "Focus",
        "description": "Planning, prioritizing, and accountability.",
        "prompt": "Help me focus on the next right step.",
        "examples": ["Break this down", "Prioritize tasks", "Start a sprint"],
    },
    {
        "name": "Relax",
        "description": "Low-pressure conversation and lighter prompts.",
        "prompt": "Keep me company for a bit.",
        "examples": ["Check in with me", "Tell a short story", "Help me decompress"],
    },
    {
        "name": "Operate",
        "description": "Spy toolkit, Ghost Mode, stealth operations.",
        "prompt": "Engage Ghost Mode.",
        "examples": ["Scan environment", "Anonymous browse", "Check threat level"],
    },
    {
        "name": "Remember",
        "description": "Memory, mood, relationship, journal.",
        "prompt": "What do you remember?",
        "examples": ["Show my mood journal", "What's my name", "Remember this"],
    },
]

# Capability groups for a "What Kai Can Do" panel
KAI_CAPABILITY_GROUPS = [
    {
        "title": "Build",
        "items": [
            "Analyze code",
            "Generate function",
            "Generate class",
            "Generate test",
            "Scan project",
        ],
    },
    {
        "title": "Operate",
        "items": [
            "Run shell command",
            "Read file",
            "Browse anonymously",
            "Ghost Mode",
            "Environment scan",
        ],
    },
    {
        "title": "Companion",
        "items": [
            "Check mood",
            "View status",
            "Mood journal",
            "Memory",
            "Relationship info",
        ],
    },
    {
        "title": "Senses",
        "items": [
            "Screen capture",
            "Webcam look",
            "WiFi signal",
            "Bluetooth scan",
            "Audio check",
        ],
    },
    {
        "title": "Relax",
        "items": [
            "Chat with me",
            "Tell me a story",
            "What are you thinking",
            "Inner monologue",
        ],
    },
]

# Prompt map — shortcut phrases to full prompts
KAI_PROMPT_MAP = {
    "Debug code": "Help me debug this step by step.",
    "Teach me": "Teach me this like I am learning it for the first time.",
    "Plan next step": "Help me decide the next right step and keep it focused.",
    "Show me more ideas": "Show me more ways you can help today.",
    "How are you": "/mood",
    "What do you remember": "/memory",
    "Full status": "/status",
    "Mood journal": "/journal",
}
