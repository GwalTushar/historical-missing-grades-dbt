import sys
from dbt.cli.main import dbtRunner

if __name__ == "__main__":
    runner = dbtRunner()
    res = runner.invoke(sys.argv[1:])

    if res.exception:
        print(res.exception)
        sys.exit(1)

    sys.exit(0)