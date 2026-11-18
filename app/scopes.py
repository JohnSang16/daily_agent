"""The only OAuth scopes the app may ever request. A test fails the build on any other."""

ALLOWED_SCOPES = frozenset(
    {
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
    }
)
