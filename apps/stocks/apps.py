from django.apps import AppConfig


class StocksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stocks"
    label = "stocks"

    def ready(self):
        from django.db.backends.signals import connection_created

        def _sqlite_pragmas(sender, connection, **kwargs):
            # WAL lets readers and the background quote writers proceed
            # concurrently instead of tripping over each other's locks.
            if connection.vendor == "sqlite":
                try:
                    with connection.cursor() as c:
                        c.execute("PRAGMA journal_mode=WAL;")
                        c.execute("PRAGMA synchronous=NORMAL;")
                except Exception:
                    pass

        connection_created.connect(_sqlite_pragmas, weak=False)
