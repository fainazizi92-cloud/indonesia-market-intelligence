from imi.db import check_database_health


def main() -> None:
    result = check_database_health()

    print("Indonesia Market Intelligence - Database Health Check")
    print("-----------------------------------------------------")
    print(f"Status       : {result['status']}")
    print(f"Database     : {result['database']}")
    print(f"User         : {result['user']}")
    print(f"Total tables : {result['total_tables']}")


if __name__ == "__main__":
    main()
    