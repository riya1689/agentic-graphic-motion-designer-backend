from packages.icon_library.application.service import IconLibraryService
from packages.icon_library.infrastructure.sqlite.repository import SQLiteIconAssetStore, SQLiteIconRepository
from packages.sqlite_storage.connection import connect


def build_sqlite_icon_library_service():
    return IconLibraryService(repository=SQLiteIconRepository(connect), asset_store=SQLiteIconAssetStore(connect))


def check_sqlite_connection():
    from packages.sqlite_storage.connection import check_connection
    return check_connection()

