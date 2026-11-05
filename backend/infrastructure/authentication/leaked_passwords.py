"""Top leaked/common passwords rejected at creation (NIST 800-63B §5.1.1.2).

Curated shortlist of the most abused secrets; 12-char minimum already blocks
most, this catches passphrases built from banned tokens (e.g. 'Password123!').
"""
BANNED_TOKENS = frozenset("""
password passw0rd password123 password1234 password123! qwerty qwerty123 123456 12345678 123456789
letmein welcome admin123 administrator manager123 mamy123 secret123 test123 changeme default123
goms123 the_system system123 company123 riyadh123 jeddah123 saudi123 arabia123
allah mohammed ahmed123 ali123 khaled123 sara123 fatima123 hassan123 omar123 ibrahim123
football soccer dragon monkey sunshine shadow master superman batman trustno1 iloveyou princess
correct horse battery staple passwort motdepasse contrasena senha parola
""".split())


def contains_banned(password: str) -> str | None:
    lowered = password.casefold()
    for token in BANNED_TOKENS:
        if len(token) >= 4 and token in lowered:
            return token
    return None
