"""Create the DatabaseCache table (settings.CACHES) as part of `migrate`,
so nobody has to remember to run `createcachetable` by hand."""
from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("stocks", "0001_initial")]
    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
