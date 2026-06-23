import os
import zipfile
from pathlib import Path


def create_archive(folder_path: str, exclude_folders=None, archive_name=None):
    """
    Creates a zip archive of a folder, excluding specified subfolders.

    Args:
        folder_path (str): Path to the folder to archive
        exclude_folders (list[str]): Folder names (not paths) to exclude
        archive_name (str): Optional name for the output zip file

    Returns:
        str: Path to created archive
    """

    if exclude_folders is None:
        exclude_folders = []

    folder_path = Path(folder_path).resolve()

    if not folder_path.is_dir():
        raise ValueError(f"Invalid folder: {folder_path}")

    parent_dir = folder_path.parent

    if archive_name is None:
        archive_name = f"{folder_path.name}.zip"

    archive_path = parent_dir / archive_name

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):

            # modify dirs in-place to skip excluded folders
            dirs[:] = [d for d in dirs if d not in exclude_folders]

            for file in files:
                file_path = Path(root) / file

                # relative path inside archive
                arcname = file_path.relative_to(folder_path)

                zipf.write(file_path, arcname)

    return str(archive_path)


if __name__ == "__main__":
    zip_path = create_archive(
        folder_path=r"C:\Users\mcro\Documents\aoi-web",
        exclude_folders=[".venv", "__pycache__", "logs", "backend/venv", "test"]
    )

    print("Archive created at:", zip_path)