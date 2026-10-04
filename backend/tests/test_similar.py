"""
Similar-photo grouping and review.
"""

import random

import numpy as np
import pytest

from api.similar import _average_distance, _find_groups
from conftest import make_thumb, wait_for_task
from database import Photo, SimilarGroup


def group(client, folder_id):
    return client.post(f"/api/similar/group/{folder_id}").json()


def test_groups_near_duplicates_only(client, scanned):
    _, folder_id, ids = scanned

    result = group(client, folder_id)

    assert result["groups_found"] == 1
    members = {p["id"] for p in client.get(f"/api/similar/group/{result['groups'][0]['id']}").json()["photos"]}
    assert members == {ids["a.jpg"], ids["b.jpg"], ids["d.png"]}


def test_regrouping_replaces_pending_groups(client, db, scanned):
    _, folder_id, _ = scanned

    first = group(client, folder_id)
    group(client, folder_id)

    count = db.query(SimilarGroup).filter(SimilarGroup.folder_id == folder_id).count()
    assert count == first["groups_found"]


def test_select_best_rejects_photo_outside_group(client, scanned):
    _, folder_id, ids = scanned
    group_id = group(client, folder_id)["groups"][0]["id"]

    response = client.post(f"/api/similar/group/{group_id}/select/{ids['c.jpg']}")

    assert response.status_code == 400


def test_select_best_delete_others_moves_all_variants(client, db, scanned):
    folder, folder_id, ids = scanned
    make_thumb(folder, "b.jpg")
    group_id = group(client, folder_id)["groups"][0]["id"]

    response = client.post(
        f"/api/similar/group/{group_id}/select/{ids['a.jpg']}", params={"delete_others": True}
    ).json()

    assert response["deleted_count"] == 2
    assert (folder / "a.jpg").exists()
    for name in ("b.jpg", "d.png"):
        assert not (folder / name).exists()
        assert (folder / "cancellate" / name).exists()
        assert db.get(Photo, ids[name]).is_deleted
    assert (folder / "cancellate" / "thumbs" / "b.jpg").exists()


def test_reviewed_photos_are_not_regrouped(client, scanned):
    _, folder_id, ids = scanned
    group_id = group(client, folder_id)["groups"][0]["id"]
    client.post(f"/api/similar/group/{group_id}/skip")

    result = group(client, folder_id)

    assert result.get("groups_found", 0) == 0
    pending = client.get(f"/api/similar/groups/{folder_id}", params={"only_unreviewed": True}).json()
    assert pending["total_groups"] == 0


def test_analyze_computes_missing_hashes_in_background(client, db, scanned):
    _, folder_id, ids = scanned
    db.get(Photo, ids["c.jpg"]).phash = None
    db.commit()

    response = client.post(f"/api/similar/analyze/{folder_id}").json()

    assert response["status"] == "started"
    assert wait_for_task(client, response["task_id"])["result"]["analyzed"] == 1
    db.expire_all()
    assert db.get(Photo, ids["c.jpg"]).phash is not None


def test_analyze_with_nothing_pending_returns_no_task(client, scanned):
    _, folder_id, _ = scanned

    assert client.post(f"/api/similar/analyze/{folder_id}").json()["task_id"] is None


def _naive_groups(hashes, threshold):
    """The original pair-by-pair greedy grouping, kept as the reference behaviour."""
    processed, groups = set(), []
    for i, h1 in enumerate(hashes):
        if i in processed:
            continue
        members = [i]
        for j in range(i + 1, len(hashes)):
            if j not in processed and bin(h1 ^ hashes[j]).count("1") <= threshold:
                members.append(j)
                processed.add(j)
        if len(members) > 1:
            groups.append(members)
            processed.add(i)
    return groups


@pytest.mark.parametrize("seed", range(5))
def test_vectorized_grouping_matches_pairwise_reference(seed):
    rng = random.Random(seed)
    # Clusters of near-identical hashes plus random noise
    centers = [rng.getrandbits(64) for _ in range(20)]
    hashes = [c ^ (1 << rng.randrange(64)) ^ (1 << rng.randrange(64)) for c in centers for _ in range(rng.randrange(1, 5))]
    hashes += [rng.getrandbits(64) for _ in range(200)]
    rng.shuffle(hashes)

    assert _find_groups(np.array(hashes, dtype=np.uint64), 5) == _naive_groups(hashes, 5)


def test_average_distance():
    hashes = np.array([0b0000, 0b0011, 0b1111], dtype=np.uint64)
    assert _average_distance(hashes) == pytest.approx((2 + 4 + 2) / 3)
