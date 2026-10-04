#!/usr/bin/env python3
"""
Re-run the analysis (dimensions, EXIF, perceptual hashes) of photos already in the
database, e.g. after the analysis itself improves (orientation-aware hashes, lens model).

Usage (from backend/):
    python reanalyze.py          # every folder
    python reanalyze.py 3 7      # only folders 3 and 7
"""

import argparse
import logging

from api.similar import clear_pending_groups
from database import SessionLocal, Folder, Photo, init_db
from utils.analysis import analyze_folder

logging.basicConfig(level=logging.WARNING)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder_ids", nargs="*", type=int, help="folders to re-analyze (default: all)")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        query = db.query(Folder)
        if args.folder_ids:
            query = query.filter(Folder.id.in_(args.folder_ids))
        folders = query.all()

        for folder in folders:
            # analyze_folder() processes photos without a hash
            db.query(Photo).filter(
                Photo.folder_id == folder.id,
                Photo.is_deleted == False
            ).update({Photo.phash: None, Photo.dhash: None}, synchronize_session=False)
            db.commit()

            result = analyze_folder(folder.id)
            clear_pending_groups(db, folder.id)
            print(f"[{folder.id}] {folder.path}: {result['analyzed']}/{result['total']} analyzed, {result['errors']} errors")
    finally:
        db.close()

    print("Done. Open 'Find duplicates' again to regroup with the new hashes.")


if __name__ == "__main__":
    main()
