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
]

KAI_CAPABILITY_GROUPS = [
    {
        "title": "Build",
        "items": [
            "Help me code",
            "Debug something",
            "Brainstorm a feature",
            "Explain this error",
        ],
    },
    {
        "title": "Learn",
        "items": [
            "Teach me a topic",
            "Quiz me",
            "Summarize this",
            "Make a study plan",
        ],
    },
    {
        "title": "Focus",
        "items": [
            "Break down a task",
            "Help me prioritize",
            "Plan my next hour",
            "Keep me accountable",
        ],
    },
    {
        "title": "Relax",
        "items": [
            "Chat with me",
            "Tell me a story",
            "Cheer me up",
            "Give me a reset prompt",
        ],
    },
    {
        "title": "Customize",
        "items": [
            "Suggest a Kai outfit",
            "Pick a vibe",
            "Recommend a mode mix",
            "Show me more ideas",
        ],
    },
]

KAI_DISCOVERY_PROMPTS = [
    "Kai can help you explore a feature without forcing you to memorize menus.",
    "Use the intent chips for quick direction, then open What Kai Can Do when you want the full range.",
    "The best way to showcase abilities is through examples, so each capability group opens with ready-to-run prompts.",
    "Kai stays lighter on the surface by grouping abilities into Build, Learn, Focus, Relax, and Customize.",
]

KAI_PROMPT_MAP = {
    "Debug code": "Help me debug this step by step.",
    "Teach me": "Teach me this like I am learning it for the first time.",
    "Plan next step": "Help me decide the next right step and keep it focused.",
    "Show me more ideas": "Show me more ways you can help today.",
}
