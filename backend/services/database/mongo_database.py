from utilities import create_simple_logger, get_dataframe_summary
from env import MONGO_URI, DEFAULT_USERNAME
from typing import Tuple
from pymongo import MongoClient

import io
import gridfs
import pandas as pd

logger = create_simple_logger(__name__)


def get_mongo_connection(
    mongo_uri: str = MONGO_URI, user_name: str = DEFAULT_USERNAME
) -> Tuple:
    client = MongoClient(mongo_uri, authSource="admin", serverSelectionTimeoutMS=2000)
    db = client[user_name]
    fs = gridfs.GridFS(db)
    try:
        client.admin.command("ping")
        logger.info("Connected to MongoDB server successfully.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB server: {e}")
        raise e

    return client, db, fs


def _push_to_fs(fs: gridfs.GridFS, file_name: str, df: pd.DataFrame) -> str:
    with io.StringIO() as csv_buffer:
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)
        val = csv_buffer.getvalue()
        val_encoded = val.encode("utf-8")
        file_id = fs.put(val_encoded, filename=file_name)
    logger.info(f"File {file_name} uploaded to GridFS.")
    file_id = str(file_id)
    return file_id


def push_to_gridfs(
    fs: gridfs.GridFS, file_name: str, df: pd.DataFrame, overwrite: bool = True
) -> str:
    if not fs.exists({"filename": file_name}):
        return _push_to_fs(fs, file_name, df)
    else:
        logger.info(f"File {file_name} already exists in GridFS.")
        if overwrite:
            ids = list(fs.find({"filename": file_name}).distinct("_id"))
            for file_id in ids:
                fs.delete(file_id)
                logger.info(f"Deleted existing file with id {file_id} from GridFS.")

            return _push_to_fs(fs, file_name, df)
        else:
            logger.info(f"Overwrite is False. Existing file {file_name} retained.")
        file_id = fs.find_one({"filename": file_name})._id
        file_id = str(file_id)
        return file_id


def show_all_files_in_fs(fs: gridfs.GridFS):
    files = fs.find()
    file_list = []
    for file in files:
        file_info = {
            "file_id": str(file._id),
            "filename": file.filename,
            "upload_date": str(file.upload_date),
            "length": file.length,
            # "content_type": file.content_type,
        }
        file_list.append(file_info)
    return file_list


def _push_to_mongodb(db, file_id: str, file_name: str, df: pd.DataFrame) -> str:
    text_representation = get_dataframe_summary(df)
    metadata = {
        "file_id": file_id,
        "file_name": file_name,
        "num_rows": df.shape[0],
        "num_columns": df.shape[1],
        "columns": df.columns.tolist(),
        "text_representation": text_representation,
        "file_path": f"/files/{file_name}",
        "database": db.name,
        "upload_date": pd.Timestamp.now(),
    }

    result = db["file_metadata"].insert_one(metadata)
    logger.info(f"Metadata for {file_name} inserted with id {result.inserted_id}.")
    return str(result.inserted_id)


def push_to_mongodb(
    db, file_id: str, file_name: str, df: pd.DataFrame, overwrite: bool = True
) -> str:
    existings = list(db["file_metadata"].find({"file_name": file_name}))
    existing = existings[0] if existings else None
    if not existing:
        return _push_to_mongodb(db, file_id, file_name, df)
    else:
        logger.info(f"Metadata for {file_name} already exists in MongoDB.")
        if overwrite:
            for exist in existings:
                db["file_metadata"].delete_one({"_id": exist["_id"]})
                logger.info(
                    f"Deleted existing metadata with id {exist['_id']} from MongoDB."
                )
            return _push_to_mongodb(db, file_id, file_name, df)
        else:
            logger.info(
                f"Overwrite is False. Existing metadata for {file_name} retained."
            )
        return str(existing["_id"])


def show_all_metadata(db):
    metadata_list = list(db["file_metadata"].find())
    for metadata in metadata_list:
        metadata["_id"] = str(metadata["_id"])
    return metadata_list


def delete_file_in_mongodb(db, fs: gridfs.GridFS, file_name: str) -> bool:
    files = list(fs.find({"filename": file_name}))
    gridfs_deleted = False
    if not files:
        logger.warning(f"No file named {file_name} found in GridFS.")
    else:
        for file in files:
            fs.delete(file._id)
            logger.info(f"Deleted file {file_name} with id {file._id} from GridFS.")
        gridfs_deleted = True

    result = db["file_metadata"].delete_many({"file_name": file_name})
    metadata_deleted = False
    if result.deleted_count > 0:
        logger.info(
            f"Deleted {result.deleted_count} metadata entries for {file_name} from MongoDB."
        )
        metadata_deleted = True
    else:
        logger.warning(f"No metadata entries for {file_name} found in MongoDB.")

    return gridfs_deleted or metadata_deleted
