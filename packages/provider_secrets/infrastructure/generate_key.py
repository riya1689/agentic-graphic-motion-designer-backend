"""Generate a Fernet key for PROVIDER_SECRETS_ENCRYPTION_KEY."""

from cryptography.fernet import Fernet


def main() -> None:
    print(Fernet.generate_key().decode("utf-8"))


if __name__ == "__main__":
    main()
