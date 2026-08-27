import cv2
import numpy as np


class UnknownDetector:

    def __init__(
        self,
        min_area_ratio=0.002,
        max_area_ratio=0.15,
        overlap_threshold=0.30
    ):

        self.min_area_ratio = min_area_ratio
        self.max_area_ratio = max_area_ratio
        self.overlap_threshold = overlap_threshold


    # ========================================================
    # 두 bbox 교차 비율
    # ========================================================

    @staticmethod
    def overlap_ratio(box1, box2):

        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (
            (x2 - x1) *
            (y2 - y1)
        )

        area1 = (
            (box1[2] - box1[0]) *
            (box1[3] - box1[1])
        )

        if area1 <= 0:
            return 0.0

        return intersection / area1


    # ========================================================
    # UNKNOWN 후보 추출
    # ========================================================

    def detect(
        self,
        image,
        yolo_detections
    ):

        height, width = image.shape[:2]

        image_area = width * height

        # ----------------------------------------------------
        # grayscale
        # ----------------------------------------------------

        gray = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2GRAY
        )

        # ----------------------------------------------------
        # 노이즈 제거
        # ----------------------------------------------------

        blur = cv2.GaussianBlur(
            gray,
            (7, 7),
            0
        )

        # ----------------------------------------------------
        # Edge
        # ----------------------------------------------------

        edges = cv2.Canny(
            blur,
            40,
            120
        )

        # 끊어진 edge 연결
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            (9, 9)
        )

        edges = cv2.morphologyEx(
            edges,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=2
        )

        # ----------------------------------------------------
        # contour
        # ----------------------------------------------------

        contours, _ = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        candidates = []

        yolo_boxes = [
            d["bbox"]
            for d in yolo_detections
        ]

        for contour in contours:

            x, y, w, h = cv2.boundingRect(
                contour
            )

            area = w * h

            area_ratio = (
                area / image_area
            )

            # 너무 작은 영역
            if area_ratio < self.min_area_ratio:
                continue

            # 너무 큰 영역
            if area_ratio > self.max_area_ratio:
                continue

            # 너무 가늘거나 이상한 영역 제거
            aspect = w / max(h, 1)

            if aspect < 0.15:
                continue

            if aspect > 6.0:
                continue

            bbox = [
                x,
                y,
                x + w,
                y + h
            ]

            # ----------------------------------------------
            # 기존 YOLO 객체와 겹치면 제거
            # ----------------------------------------------

            overlapped = False

            for yolo_box in yolo_boxes:

                overlap = self.overlap_ratio(
                    bbox,
                    yolo_box
                )

                if overlap >= self.overlap_threshold:

                    overlapped = True
                    break

            if overlapped:
                continue

            candidates.append({
                "bbox": bbox,
                "area_ratio": area_ratio
            })

        return candidates