"""
Shared constant values used across models, routes, templates, and the AI
module. Centralized here so a category or status never drifts out of
sync between the DB layer, the API layer, and the AI prompt.
"""

POST_CATEGORIES = [
    "Corporate Fraud",
    "Workplace Harassment",
    "Government & Public Sector",
    "Environmental",
    "Financial Misconduct",
    "Safety Violation",
    "Corruption & Bribery",
    "Data Privacy & Security",
    "Healthcare & Medical",
    "Academic & Research",
    "Consumer Protection",
    "Human Rights",
    "Conflicts of Interest",
    "Other",
]

REPORT_REASONS = [
    "Information is not true or misleading",
    "Copyright infringement or already published elsewhere",
    "Pornographic or sexually explicit content",
    "Hate speech or abusive content",
    "Personal information or doxxing",
    "Spam or advertising",
    "Threats or illegal content",
    "Other",
]

# Statuses an admin can move a report through -- this is one of the
# things that meaningfully differs from a generic Reddit-style feed:
# whistleblower reports have a lifecycle, not just a vote count.
POST_STATUSES = ["open", "under_review", "resolved"]
POST_STATUS_LABELS = {
    "open": "Open",
    "under_review": "Under Review",
    "resolved": "Resolved",
}

MAX_IMAGES_PER_POST = 3
MAX_COMMENT_LENGTH = 3000
MAX_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 10000
