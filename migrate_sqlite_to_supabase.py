from pathlib import Path

from sqlalchemy import create_engine, MetaData, select, text, func

from app import create_app
from app.extensions import db


# Tables must be inserted in foreign-key dependency order.
TABLES = [
    "user",
    "category",
    "course",
    "section",
    "lesson",
    "enrollment",
    "lesson_progress",
    "profile_update",
    "report",
    "login_attempt",
]

# Locate the original SQLite database.
BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "instance" / "courses.db"

app = create_app()


def migrate_data():

    if not SQLITE_PATH.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {SQLITE_PATH}"
        )

    source_engine = create_engine(
        f"sqlite:///{SQLITE_PATH.as_posix()}"
    )

    source_metadata = MetaData()
    target_metadata = MetaData()

    source_metadata.reflect(
        bind=source_engine,
        only=TABLES
    )

    target_metadata.reflect(
        bind=db.engine,
        only=TABLES
    )

    print("\nSOURCE DATABASE: SQLite")
    print("DESTINATION DATABASE: Supabase")
    print("-" * 45)

    try:
        # Read all source records.
        source_records = {}

        with source_engine.connect() as source_connection:

            for table_name in TABLES:
                table = source_metadata.tables[table_name]

                rows = source_connection.execute(
                    select(table)
                ).mappings().all()

                source_records[table_name] = [
                    dict(row) for row in rows
                ]

                print(
                    f"{table_name}: "
                    f"{len(source_records[table_name])} source records"
                )

        # Validate and transfer the records in one destination transaction.
        with db.engine.begin() as target_connection:

            for table_name in TABLES:
                table = target_metadata.tables[table_name]

                count = target_connection.execute(
                    select(func.count()).select_from(table)
                ).scalar_one()

                if count != 0:
                    raise RuntimeError(
                        f"Destination table '{table_name}' "
                        f"is not empty. Found {count} records."
                    )

            print("\nDestination verified: all tables are empty.")

            # Transfer records.
            print("\nSTARTING DATA TRANSFER")
            print("-" * 45)

            for table_name in TABLES:
                records = source_records[table_name]
                table = target_metadata.tables[table_name]

                if records:
                    target_connection.execute(table.insert(), records)

                print(
                    f"Transferred {len(records)} "
                    f"records into {table_name}"
                )

            # Reset PostgreSQL ID sequences.
            print("\nRESETTING ID SEQUENCES")
            print("-" * 45)

            for table_name in TABLES:
                table = target_metadata.tables[table_name]

                sequence_name = target_connection.execute(
                    text("""
                        SELECT pg_get_serial_sequence(
                            :table_name, 'id'
                        )
                    """),
                    {"table_name": f"public.{table_name}"}
                ).scalar_one()

                if sequence_name:
                    max_id = target_connection.execute(
                        select(func.max(table.c.id))
                    ).scalar_one()

                    target_connection.execute(
                        text("""
                            SELECT setval(
                                CAST(:sequence_name AS regclass),
                                :last_id,
                                :is_called
                            )
                        """),
                        {
                            "sequence_name": sequence_name,
                            "last_id": max_id if max_id is not None else 1,
                            "is_called": max_id is not None
                        }
                    )

                    print(f"Sequence reset: {table_name}")

            # Verify transferred record counts.
            print("\nVERIFYING TRANSFER")
            print("-" * 45)

            for table_name in TABLES:
                table = target_metadata.tables[table_name]

                destination_count = target_connection.execute(
                    select(func.count()).select_from(table)
                ).scalar_one()
                source_count = len(source_records[table_name])

                if destination_count != source_count:
                    raise RuntimeError(
                        f"Count mismatch in {table_name}: "
                        f"source={source_count}, "
                        f"destination={destination_count}"
                    )

                print(
                    f"{table_name}: "
                    f"{destination_count} records verified"
                )

        print("\nSUCCESS: DATA TRANSFER COMMITTED.")

    finally:
        source_engine.dispose()


if __name__ == "__main__":

    with app.app_context():
        migrate_data()