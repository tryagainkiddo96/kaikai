class Config:
    # API Configuration
    API_BASE_URL = "https://api.emailsec.shop"

    # AI Models
    AI_MODEL_TECHNICAL = "mistralai/mistral-nemotron"
    AI_MODEL_DISPLAY = "Black Worm AI"

    # Accent Colors
    ACCENT_COLOR = "#00f5ff"
    ACCENT_GRADIENT = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f5ff, stop:1 #0099ff)"
    )

    # Text Colors
    TEXT_COLOR = "#ffffff"
    TEXT_SECONDARY = "#b0b0b0"
    TEXT_MUTED = "#666666"

    # Status Colors
    ERROR_COLOR = "#ff4444"
    BUTTON_HOVER = "#00d4e0"
    BUTTON_PRESSED = "#00a8b3"

    # Gradients
    MODERN_GRADIENT_1 = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1a1a2e, stop:1 #16213e)"
    )
    MODERN_GRADIENT_2 = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f0f23, stop:1 #1a1a2e)"
    )
    CARD_GRADIENT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(255,255,255,0.08), stop:1 rgba(255,255,255,0.03))"
    TEAL_GRADIENT = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,245,255,0.15), stop:1 rgba(0,153,255,0.08))"
    NEON_GRADIENT = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00f5ff, stop:0.5 #00ccff, stop:1 #0099ff)"

    # Fonts
    FONT_FAMILY = "Segoe UI"
    FONT_FAMILY_MONO = "Consolas"

    # Font Sizes
    FONT_SIZE_SMALL = 11
    FONT_SIZE_NORMAL = 13
    FONT_SIZE_MEDIUM = 14
    FONT_SIZE_LARGE = 16
    FONT_SIZE_HEADER = 20
    FONT_SIZE_TITLE = 24

    # Timing
    SPLASH_DURATION = 3000
