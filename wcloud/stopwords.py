# stopwords.py — Stop words and Discord noise filters

import re

# Regex patterns for Discord noise removal (applied before tokenization)
DISCORD_NOISE_PATTERNS = [
    re.compile(r"https?://\S+"),          # URLs
    re.compile(r"<@!?\d+>"),              # User mentions
    re.compile(r"<@&\d+>"),               # Role mentions
    re.compile(r"<#\d+>"),                # Channel mentions
    re.compile(r"<a?:\w+:\d+>"),          # Custom emoji
    re.compile(r"```[\s\S]*?```"),         # Code blocks
    re.compile(r"`[^`]+`"),               # Inline code
    re.compile(r"\|\|[\s\S]*?\|\|"),       # Spoiler text
]

# Common bot command prefixes — skip entire message if it starts with one
BOT_PREFIXES = ("!", "?", ".", "-", "$", "%", "&", ">", "/", "[p]")

# Standard English stop words
ENGLISH_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an",
    "and", "any", "are", "aren't", "as", "at", "be", "because", "been",
    "before", "being", "below", "between", "both", "but", "by", "can",
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "get", "got", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how",
    "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "just", "let's", "like", "me",
    "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of",
    "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd",
    "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
    "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've",
    "were", "weren't", "what", "what's", "when", "when's", "where",
    "where's", "which", "while", "who", "who's", "whom", "why", "why's",
    "will", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves",
}

# Discord/internet shorthand noise
DISCORD_STOP_WORDS = {
    "http", "https", "www", "com", "org", "net", "gg", "io",
    "lol", "lmao", "lmfao", "rofl", "xd", "omg", "omfg", "brb",
    "gonna", "gotta", "wanna", "kinda", "sorta",
    "dont", "doesnt", "didnt", "cant", "wont", "wouldnt", "shouldnt",
    "im", "ive", "youre", "youve", "theyre", "theyve", "weve",
    "hes", "shes", "thats", "whats", "heres", "theres",
    "yeah", "yea", "yep", "nah", "nope",
    "ok", "okay", "ya", "ye",
}

# Combined stop words set
ALL_STOP_WORDS = ENGLISH_STOP_WORDS | DISCORD_STOP_WORDS

# Minimum word length to include
MIN_WORD_LENGTH = 2


def clean_message(content: str) -> str:
    """Remove Discord noise from a message string."""
    for pattern in DISCORD_NOISE_PATTERNS:
        content = pattern.sub("", content)
    return content


def is_bot_command(content: str) -> bool:
    """Check if a message looks like a bot command."""
    stripped = content.strip()
    return any(stripped.startswith(p) for p in BOT_PREFIXES)


def extract_words(content: str) -> list:
    """Extract filtered words from a cleaned message.

    Returns a list of lowercase words with stop words and short words removed.
    """
    content = clean_message(content)
    # Lowercase and split on whitespace
    tokens = content.lower().split()
    # Strip punctuation from edges, filter
    words = []
    for token in tokens:
        word = token.strip(".,!?;:\"'()[]{}~*_<>\\/#@+=-")
        if len(word) >= MIN_WORD_LENGTH and word not in ALL_STOP_WORDS:
            # Skip tokens that are just numbers or single repeated chars
            if not word.isdigit():
                words.append(word)
    return words
