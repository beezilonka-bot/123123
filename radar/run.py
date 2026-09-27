"""Scheduled radar collection entrypoint."""
from app import collect_and_persist


if __name__ == "__main__":
    print(collect_and_persist())
