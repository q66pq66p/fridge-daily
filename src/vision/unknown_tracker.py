from pathlib import Path

import cv2
import numpy as np


class UnknownTracker:

    def __init__(
        self,
        match_threshold=0.68
    ):
        self.match_threshold = match_threshold


    @staticmethod
    def _center(bbox):

        x1, y1, x2, y2 = bbox

        return (
            (x1 + x2) / 2,
            (y1 + y2) / 2
        )


    def position_similarity(
        self,
        bbox1,
        bbox2,
        width,
        height
    ):

        c1 = self._center(bbox1)
        c2 = self._center(bbox2)

        dx = (
            (c1[0] - c2[0])
            / width
        )

        dy = (
            (c1[1] - c2[1])
            / height
        )

        distance = np.sqrt(
            dx * dx + dy * dy
        )

        return max(
            0.0,
            1.0 - distance / 0.25
        )


    @staticmethod
    def size_similarity(
        bbox1,
        bbox2
    ):

        area1 = max(
            1,
            (bbox1[2] - bbox1[0])
            *
            (bbox1[3] - bbox1[1])
        )

        area2 = max(
            1,
            (bbox2[2] - bbox2[0])
            *
            (bbox2[3] - bbox2[1])
        )

        return (
            min(area1, area2)
            /
            max(area1, area2)
        )


    @staticmethod
    def image_similarity(
        image1,
        image2
    ):

        if image1 is None or image2 is None:
            return 0.0

        if image1.size == 0 or image2.size == 0:
            return 0.0

        size = (128, 128)

        image1 = cv2.resize(
            image1,
            size
        )

        image2 = cv2.resize(
            image2,
            size
        )

        hsv1 = cv2.cvtColor(
            image1,
            cv2.COLOR_BGR2HSV
        )

        hsv2 = cv2.cvtColor(
            image2,
            cv2.COLOR_BGR2HSV
        )

        hist1 = cv2.calcHist(
            [hsv1],
            [0, 1],
            None,
            [30, 32],
            [0, 180, 0, 256]
        )

        hist2 = cv2.calcHist(
            [hsv2],
            [0, 1],
            None,
            [30, 32],
            [0, 180, 0, 256]
        )

        cv2.normalize(hist1, hist1)
        cv2.normalize(hist2, hist2)

        score = cv2.compareHist(
            hist1,
            hist2,
            cv2.HISTCMP_CORREL
        )

        return max(
            0.0,
            min(
                1.0,
                (score + 1) / 2
            )
        )


    def find_best_match(
        self,
        candidate,
        new_crop,
        tracks,
        width,
        height,
        used_track_ids=None
    ):

        if used_track_ids is None:
            used_track_ids = set()

        best_track = None
        best_score = 0.0
        best_details = None

        new_bbox = candidate["bbox"]

        for track in tracks:

            track_id = track["track_id"]

            if track_id in used_track_ids:
                continue

            old_bbox = [
                track["bbox_x1"],
                track["bbox_y1"],
                track["bbox_x2"],
                track["bbox_y2"]
            ]

            old_crop = None

            if track["crop_path"]:

                path = Path(
                    track["crop_path"]
                )

                if path.exists():

                    old_crop = cv2.imread(
                        str(path)
                    )

            image_score = (
                self.image_similarity(
                    new_crop,
                    old_crop
                )
            )

            position_score = (
                self.position_similarity(
                    new_bbox,
                    old_bbox,
                    width,
                    height
                )
            )

            size_score = (
                self.size_similarity(
                    new_bbox,
                    old_bbox
                )
            )

            # UNKNOWN은 외형을 가장 중요하게 사용
            total = (
                image_score * 0.55
                + position_score * 0.25
                + size_score * 0.20
            )

            if total > best_score:

                best_score = total
                best_track = track

                best_details = {
                    "image": round(
                        image_score, 3
                    ),
                    "position": round(
                        float(position_score), 3
                    ),
                    "size": round(
                        size_score, 3
                    ),
                    "total": round(
                        float(total), 3
                    )
                }

        if (
            best_track is not None
            and best_score >= self.match_threshold
        ):

            return (
                best_track,
                best_score,
                best_details
            )

        return (
            None,
            best_score,
            best_details
        )