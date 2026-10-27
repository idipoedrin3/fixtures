from django.db import connection, transaction

WORKFLOW_GRAPH_TABLES = [
    "system_workflowstate",
    "system_edge",
    "system_node",
    "system_map",
]


def purge_workflow_graph_tables(confirm=False):
    """
    Hard deletes Map, Node, Edge, and WorkflowState tables in SQLite.
    This is irreversible. Use with confirm=True.
    """

    if not confirm:
        raise RuntimeError(
            "Destructive operation blocked. Call with confirm=True to proceed."
        )

    with connection.cursor() as cursor, transaction.atomic():
        print("\nDisabling foreign key checks...")
        cursor.execute("PRAGMA foreign_keys = OFF;")

        print("\nDropping tables...\n")
        for table in WORKFLOW_GRAPH_TABLES:
            print(f" - Dropping table {table}")
            cursor.execute(f'DROP TABLE IF EXISTS "{table}";')

        print("\nRe-enabling foreign key checks...")
        cursor.execute("PRAGMA foreign_keys = ON;")

    print("\nWorkflow graph tables fully purged.")
